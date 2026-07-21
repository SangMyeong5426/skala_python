"""
프로그램명 : 종합실습 2 - EDA + 통계 + ML 파이프라인
설명       : telco_churn.csv(7천 행, 이탈 예측용)를 대상으로
             EDA(Polars) -> 시각화(Seaborn+Plotly) -> 통계 검정(t-test/카이제곱) ->
             ML(scikit-learn Pipeline) 순서로 실습4/5(정제·집계)와 실습1~3에서 배운
             원칙(순서를 지킨다·검증 없는 결론을 내지 않는다)을 하나로 잇는다.

             "요금이 높아서 이탈한다"처럼 인과로 단정하지 않고, 통계 검정으로 확인된
             "연관"까지만 말한다. Pipeline으로 전처리(SimpleImputer 등)를 감싸
             훈련 데이터 안에서만 학습되도록 해 데이터 누수를 구조적으로 막는다.

체크포인트 : t-검정/카이제곱 p값 유의(< 0.05) 출력 + ROC-AUC 출력 + HTML 리포트/모델 저장
실행       : python capstone02_eda_ml/analysis.py  (skala_python 루트에서)
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 화면 없는 환경에서도 저장만 하도록
import joblib
import matplotlib.pyplot as plt
import plotly.express as px
import polars as pl
import seaborn as sns
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

plt.rcParams["font.family"] = "AppleGothic"  # macOS 한글 라벨 깨짐 방지
plt.rcParams["axes.unicode_minus"] = False

DATA_PATH = Path(__file__).resolve().parent.parent / "python_data" / "telco_churn.csv"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

NUM_COLS = ["tenure_months", "monthly_charges", "total_charges", "num_services"]
CAT_COLS = ["gender", "senior", "contract", "payment_method"]


def eda(df: pl.DataFrame) -> None:
    """STEP 0~1 - Polars EDA. 타깃 비율부터 확인하는 것이 첫 순서."""
    print("=" * 50)
    print("[STEP 0] Polars EDA")
    print(f"shape: {df.shape}")
    print(df.columns)
    print(df.describe())

    print("\n-- 타깃(churn) 비율 --")
    print(df.group_by("churn").len().sort("churn"))

    print("\n-- 결측치 개수 --")
    print(df.null_count())

    print("\n[STEP 1] 이탈 여부별 그룹 비교")
    print(
        df.group_by("churn").agg(
            [
                pl.col("monthly_charges").mean().round(2).alias("평균요금"),
                pl.col("tenure_months").mean().round(1).alias("평균근속개월"),
                pl.len().alias("인원"),
            ]
        )
    )


def visualize(pdf) -> None:
    """STEP 2 - Seaborn(정적) + Plotly(인터랙티브) 시각화. 눈으로 먼저 확인한다."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    sns.boxplot(data=pdf, x="churn", y="monthly_charges", ax=axes[0])
    axes[0].set_title("이탈 여부별 월 요금 분포")
    axes[0].set_xlabel("이탈 여부(0=잔류, 1=이탈)")

    ct = pdf.groupby(["contract", "churn"]).size().rename("cnt").reset_index()
    sns.barplot(data=ct, x="contract", y="cnt", hue="churn", ax=axes[1])
    axes[1].set_title("계약 유형별 이탈 건수")
    plt.tight_layout()
    png_path = OUTPUT_DIR / "churn_eda.png"
    fig.savefig(png_path, dpi=120)
    plt.close(fig)
    print(f"\n[STEP 2] Seaborn 정적 차트 저장 -> {png_path}")

    fig_px = px.box(
        pdf,
        x="churn",
        y="monthly_charges",
        color="churn",
        title="이탈 여부별 월 요금 분포 (인터랙티브)",
    )
    html_path = OUTPUT_DIR / "churn_charges.html"
    fig_px.write_html(html_path)
    print(f"[STEP 2] Plotly 인터랙티브 차트 저장 -> {html_path}")


def statistical_tests(pdf) -> tuple[float, float]:
    """STEP 3 - t-검정(요금 차이) + 카이제곱(계약유형과 이탈의 연관성)."""
    print("\n" + "=" * 50)
    print("[STEP 3] 통계 검정")

    churn_yes = pdf[pdf["churn"] == 1]["monthly_charges"]
    churn_no = pdf[pdf["churn"] == 0]["monthly_charges"]
    t, p_t = stats.ttest_ind(churn_yes, churn_no, equal_var=False)
    print(f"t-검정 (이탈 vs 잔류 월요금)   : t={t:.3f}, p={p_t:.3e}")

    crosstab = pdf.pivot_table(
        index="contract",
        columns="churn",
        values="customer_id",
        aggfunc="count",
        fill_value=0,
    )
    chi2, p_chi2, dof, _ = stats.chi2_contingency(crosstab)
    print(
        f"카이제곱 (계약유형 x 이탈)     : chi2={chi2:.3f}, dof={dof}, p={p_chi2:.3e}"
    )

    print(
        "\n해석: 요금·계약 유형이 이탈과 '통계적으로 유의한 연관'을 보인다"
        "(p < 0.05). 다만 이는 연관(association)이지 인과(causation)가 아니다 -"
        " 요금이 높은 고객이 원래 단기 계약을 쓰는 경향(제3의 변수) 때문일 수도 있다."
    )
    return p_t, p_chi2


def build_pipeline() -> Pipeline:
    """STEP 4~5 - ColumnTransformer + Pipeline. 결측 대치는 반드시 Pipeline 안에서
    (= train 데이터로만 fit) 이루어지도록 해 데이터 누수를 구조적으로 막는다."""
    preprocessor = ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                NUM_COLS,
            ),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_COLS),
        ]
    )
    return Pipeline(
        [
            ("prep", preprocessor),
            ("model", RandomForestClassifier(n_estimators=200, random_state=42)),
        ]
    )


def train_and_evaluate(pdf) -> float:
    """STEP 6~7 - train/test 분리(stratify) -> 학습 -> ROC-AUC 평가 -> 모델 저장."""
    print("\n" + "=" * 50)
    print("[STEP 4~7] ML Pipeline (전처리 + RandomForest)")

    X = pdf[NUM_COLS + CAT_COLS]
    y = pdf["churn"]

    # 불균형(이탈 24% vs 잔류 76%) 데이터이므로 정확도가 아니라 ROC-AUC 로 평가한다.
    print(f"타깃 비율 : {y.value_counts(normalize=True).round(3).to_dict()}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipe = build_pipeline()
    pipe.fit(X_train, y_train)

    proba = pipe.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, proba)
    print(f"\nROC-AUC = {auc:.3f}")
    print(classification_report(y_test, pipe.predict(X_test)))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = OUTPUT_DIR / "churn_model.joblib"
    joblib.dump(pipe, model_path)  # 전처리까지 통째로 저장 -> 재현 가능
    print(f"모델(전처리 포함) 저장 -> {model_path}")

    return auc


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(
            f"[오류] 데이터가 없습니다: {DATA_PATH}\n"
            "python_data/generate_data.py 를 먼저 실행하세요."
        )

    df_pl = pl.read_csv(DATA_PATH)
    eda(df_pl)

    pdf = df_pl.to_pandas()
    visualize(pdf)
    p_t, p_chi2 = statistical_tests(pdf)
    auc = train_and_evaluate(pdf)

    assert p_t < 0.05, "t-검정이 유의하지 않습니다"
    assert p_chi2 < 0.05, "카이제곱 검정이 유의하지 않습니다"
    assert auc > 0.5, "ROC-AUC 가 동전 던지기보다 낫지 않습니다"
    print(
        "\n[체크포인트 통과] "
        f"t-검정 p={p_t:.2e}(유의) · 카이제곱 p={p_chi2:.2e}(유의) · ROC-AUC={auc:.3f}"
    )


if __name__ == "__main__":
    main()
