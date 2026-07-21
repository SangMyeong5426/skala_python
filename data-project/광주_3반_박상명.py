"""
프로그램명 : 실습 4 - 시각화 4종 · 통계 검정(t-test/카이제곱) · sklearn Pipeline
작성자     : 박상명
작성일     : 2026-07-21
설명       : 실습 3(광주_3반_박상명_Practice_3.py)에서 IQR 이상치를 제거한
            sales_100k.csv 데이터를 그대로 이어받아,
              1) 2x2 서브플롯으로 EDA 시각화 4종(분포·박스플롯·월별추이·상관히트맵)
              2) 서울 vs 부산 t-test로 region x category 카이제곱 검정으로 확인
              3) ColumnTransformer + Pipeline을 완성하고 훈련·평가·저장·재로딩 수행
              4) 지역·카테고리별 총매출 Plotly 인터랙티브 막대 차트 저장
            을 순서대로 수행한다.

[실습 3 연계]
  - importlib로 광주_3반_박상명_Practice_3 모듈을 동적 임포트해
    load_and_clean() / DATA_PATH / pandas_agg() 를 재사용한다.
  - IQR 이상치 제거된 df_clean 을 4번 실습 전체의 입력 데이터로 사용한다.
  - region·category groupby(pandas_agg) 결과를 Plotly 차트 데이터로 재사용한다.

[실습 목표 대응]
  1) EDA 시각화 4종 (2x2 서브플롯)        → plot_eda_grid()
  2) 통계 검정 - t-test + 카이제곱        → run_statistical_tests()
  3) sklearn Pipeline 구성 + 저장         → build_and_save_pipeline()
  4) Plotly 인터랙티브 차트 저장          → save_plotly_chart()

변경내역   : 2026-07-21 최초 작성
"""

import importlib
import logging
import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns
from scipy.stats import chi2_contingency, ttest_ind
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# ─────────────────────────────────────
# 전역 설정: 실습 3 모듈 동적 임포트 + 경로/컬럼 상수
# ─────────────────────────────────────
practice3 = importlib.import_module("광주_3반_박상명_Practice_3")

# 차트 한글 글자 깨짐 방지 (macOS 기본 탑재 폰트)
plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False

EDA_IMG_PATH = Path("eda_4panel.png")
PIPELINE_PATH = Path("sales_ridge_pipeline.joblib")
PLOTLY_HTML_PATH = Path("regional_category_sales.html")

NUM_FEATURES = ["quantity", "customer_age"]
CAT_FEATURES = ["region", "category", "payment_method", "customer_gender"]
TARGET = "amount"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s|%(levelname)s|%(message)s",
)
logger = logging.getLogger("practice4")


# ═════════════════════════════════════
# 1) EDA 시각화 4종 (2x2 서브플롯)
# ─────────────────────────────────────
def plot_eda_grid(df_clean: pd.DataFrame) -> None:
    """히스토그램+KDE·박스플롯·월별 매출 라인·상관 히트맵을 한 figure에 그린다."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # [0,0] amount 분포 (히스토그램 + KDE)
    sns.histplot(data=df_clean, x="amount", kde=True, ax=axes[0, 0])
    axes[0, 0].set_title("매출(amount) 분포")

    # [0,1] 지역별 매출 박스플롯
    sns.boxplot(data=df_clean, x="region", y="amount", ax=axes[0, 1])
    axes[0, 1].set_title("지역별 매출 분포")
    axes[0, 1].tick_params(axis="x", rotation=45)

    # [1,0] 월별 매출 추이 라인차트
    try:
        order_date = pd.to_datetime(df_clean["order_date"], errors="coerce")
        monthly = (
            df_clean.assign(month=order_date.dt.to_period("M").astype(str))
            .dropna(subset=["month"])
            .groupby("month")["amount"]
            .sum()
            .sort_index()
        )
        axes[1, 0].plot(monthly.index, monthly.values, marker="o", color="steelblue")
        axes[1, 0].set_title("월별 총매출 추이")
        axes[1, 0].tick_params(axis="x", rotation=45)
    except Exception as e:
        logger.warning(f"월별 라인차트 생성 실패: {e}")
        axes[1, 0].set_title("월별 총매출 추이 (데이터 오류)")

    # [1,1] 수치형 컬럼 상관 히트맵
    num_cols = ["amount", "quantity", "unit_price", "customer_age"]
    corr = df_clean[num_cols].corr()
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", ax=axes[1, 1])
    axes[1, 1].set_title("수치형 컬럼 상관관계")

    # 4개 서브플롯 간격 조정 및 저장
    plt.tight_layout()
    fig.savefig(EDA_IMG_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"EDA 시각화 4종 저장 완료: {EDA_IMG_PATH}")


# ═════════════════════════════════════
# 2) 통계 검정 — t-test + 카이제곱
# ─────────────────────────────────────
def run_statistical_tests(df_clean: pd.DataFrame) -> None:
    """서울 vs 부산 평균 매출 t-test와 region x category 카이제곱 독립성 검정을 수행한다."""
    print("\n=== 2) 통계 검정 ===")

    # t-test: 서울 vs 부산 평균 매출 차이
    seoul = df_clean.loc[df_clean["region"] == "서울", "amount"].dropna()
    busan = df_clean.loc[df_clean["region"] == "부산", "amount"].dropna()

    # 서울, 부산 표본이 없을 경우 검정을 건너뜀
    if len(seoul) == 0 or len(busan) == 0:
        logger.warning("서울/부산 표본이 부족해 t-test를 건너뜁니다.")
    else:
        t_stat, p_value = ttest_ind(seoul, busan, equal_var=False)
        verdict = "유의미한 차이 있음" if p_value < 0.05 else "유의미한 차이 없음"
        print(
            f"[t-test] 서울(n={len(seoul)}) vs 부산(n={len(busan)}): "
            f"t={t_stat:.3f}, p={p_value:.4f} → {verdict} (α=0.05 기준)"
        )

    # 카이제곱: region x category 독립성 검정
    ct = pd.crosstab(df_clean["region"], df_clean["category"])
    chi2, p_value_chi, dof, _ = chi2_contingency(ct)
    verdict_chi = "독립이 아님(연관 있음)" if p_value_chi < 0.05 else "독립(연관 없음)"
    print(
        f"[카이제곱] region x category: chi2={chi2:.3f}, dof={dof}, "
        f"p={p_value_chi:.4f} → {verdict_chi} (α=0.05 기준)"
    )


# ═════════════════════════════════════
# 3) sklearn Pipeline 구성 + 저장 + 재로딩
# ─────────────────────────────────────
def build_and_save_pipeline(df_clean: pd.DataFrame) -> None:
    """ColumnTransformer + Ridge 회귀를 Pipeline으로 묶어 학습·평가하고,
    joblib로 저장한 뒤 다시 불러와 재검증한다.
    unit_price는 quantity와 곱하면 amount가 그대로 재현되는 결정적 관계라
    트리비얼한 회귀를 막기 위해 피처에서 제외한다."""
    use_cols = NUM_FEATURES + CAT_FEATURES + [TARGET]
    model_df = df_clean[use_cols].dropna()
    if model_df.empty:
        logger.error("Pipeline 학습에 사용할 유효한 행이 없습니다.")
        return

    X = model_df[NUM_FEATURES + CAT_FEATURES]
    y = model_df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    preprocessor = ColumnTransformer(
        [
            ("num", StandardScaler(), NUM_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
        ]
    )
    pipeline = Pipeline([("prep", preprocessor), ("reg", Ridge(alpha=1.0))])

    print("\n=== 3) sklearn Pipeline ===")
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    train_r2 = pipeline.score(X_train, y_train)
    test_r2 = r2_score(y_test, y_pred)
    print(f"학습 R2={train_r2:.4f}, 테스트 R2={test_r2:.4f}")
    print(f"예측값 샘플: {y_pred[:3].round(0)}")

    joblib.dump(pipeline, PIPELINE_PATH)
    logger.info(f"Pipeline 저장 완료: {PIPELINE_PATH}")

    reloaded = joblib.load(PIPELINE_PATH)
    reload_r2 = r2_score(y_test, reloaded.predict(X_test))
    print(f"재로딩 후 테스트 R2={reload_r2:.4f} (원본과 일치 여부: {abs(reload_r2 - test_r2) < 1e-9})")


# ═════════════════════════════════════
# 4) Plotly 인터랙티브 차트 저장
# ─────────────────────────────────────
def save_plotly_chart(df_clean: pd.DataFrame) -> None:
    """실습 3의 pandas_agg() 결과(region·category별 총매출)를 재사용해
    인터랙티브 막대 차트를 HTML로 저장한다."""
    agg_df = practice3.pandas_agg(df_clean)
    fig = px.bar(
        agg_df,
        x="region",
        y="total",
        color="category",
        barmode="group",
        title="지역·카테고리별 총매출",
        labels={"total": "총매출", "region": "지역", "category": "카테고리"},
    )
    fig.write_html(PLOTLY_HTML_PATH)
    logger.info(f"Plotly 차트 저장 완료: {PLOTLY_HTML_PATH}")


# ═════════════════════════════════════
# main: 실습 3 데이터 로딩 → 4개 단계 순차 실행
# ═════════════════════════════════════
def main() -> None:
    """실습 3의 load_and_clean()으로 이상치 제거된 데이터를 가져온 뒤
    시각화 → 통계 검정 → Pipeline → Plotly 순으로 실행한다."""
    try:
        df_clean, _lo, _hi = practice3.load_and_clean(practice3.DATA_PATH)

        plot_eda_grid(df_clean)
        run_statistical_tests(df_clean)
        build_and_save_pipeline(df_clean)
        save_plotly_chart(df_clean)

        logger.info("실습 4 파이프라인 정상 종료")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"데이터 오류로 중단: {e}")
        sys.exit(1)
    except Exception as e:  # 예상치 못한 오류도 로그를 남기고 안전하게 종료
        logger.error(f"파이프라인 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()