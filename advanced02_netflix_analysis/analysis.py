"""
프로그램명 : Day2 추가과제 - 넷플릭스 시청 기록 분석
설명       : 실제 내 넷플릭스 시청 기록(NetflixViewingHistory.csv, 2,205건, 2020-11~2026-07)을
             pandas로 정제 -> EDA -> 몰아보기(binge) 탐지 -> 시각화(Seaborn+Plotly) ->
             통계 검정(t-test/카이제곱) 순서로 분석한다.

             Netflix 원본 CSV에는 "영화/시리즈" 구분이 없다. 제목만으로 완벽히 구분하는
             규칙은 없지만("숙련도"처럼 지표화하기 어려운 문제와 비슷하다), 실습4에서 쓴
             "결측치를 규칙으로 채운다"는 원칙을 응용해 두 단계 휴리스틱으로 근사한다:
             1) 같은 show_key(제목의 첫 ':' 앞부분)가 2번 이상 나오면 -> 반복 시청 자체가
                시리즈라는 강한 신호이므로 "시리즈"
             2) 1번 조건에 걸리지 않아도 "3화"/"시즌 2"/"파트 1" 같은 회차 마커가 있으면 "시리즈"
             3) 둘 다 아니면 "영화/단편"

체크포인트 : 몰아보기(binge) 탐지 결과 출력 + t-검정/카이제곱 p값 출력 + HTML 리포트 저장
             + pandas·Polars 집계 결과 교차검증 통과
실행       : python advanced02_netflix_analysis/analysis.py  (skala_python 루트에서)
"""

import re
import time

import matplotlib

matplotlib.use("Agg")  # 화면 없는 환경에서도 저장만 하도록
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import polars as pl
import seaborn as sns
from scipy import stats

from config import CONFIG

plt.rcParams["font.family"] = "AppleGothic"  # macOS 한글 라벨 깨짐 방지
plt.rcParams["axes.unicode_minus"] = False

_EPISODE_MARKER = re.compile(
    r"\d+화$|\d+회$|시즌\s*\d+|파트\s*\d+|\d+기[:：]|Season\s*\d+|Episode|Class\s*\d+|"
    r"\d{4}-\d{2}-\d{2}"
)

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


def load_data() -> pd.DataFrame:
    """STEP 0 - CSV 로드 + 날짜 파싱. Netflix 원본 날짜 포맷은 M/D/YY."""
    df = pd.read_csv(CONFIG.data_path)
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%y")
    df["Title"] = df["Title"].fillna("")
    print("=" * 50)
    print("[STEP 0] 데이터 로드")
    print(f"shape: {df.shape}")
    print(f"기간: {df['Date'].min().date()} ~ {df['Date'].max().date()}")
    return df


def _show_key(title: str) -> str:
    if ": " in title:
        return title.split(": ")[0].strip()
    return title.strip()


def classify_titles(df: pd.DataFrame) -> pd.DataFrame:
    """STEP 1 - show_key 추출 + 시리즈/영화 분류 (규칙은 모듈 docstring 참고)."""
    df = df.copy()
    df["show_key"] = df["Title"].map(_show_key)

    show_counts = df["show_key"].value_counts()

    def _category(row: pd.Series) -> str:
        key = row["show_key"]
        if key == "":
            return "제목정보없음"
        if show_counts[key] >= 2:
            return "시리즈"
        if _EPISODE_MARKER.search(row["Title"]):
            return "시리즈"
        return "영화/단편"

    df["category"] = df.apply(_category, axis=1)

    print("\n" + "=" * 50)
    print("[STEP 1] 시리즈/영화 분류")
    print(df["category"].value_counts())
    unknown = (df["category"] == "제목정보없음").sum()
    if unknown:
        print(
            f"[한계] show_key가 빈 문자열인 레코드 {unknown}건은 Netflix 측 메타데이터 "
            "누락으로 보이며(예: ' : 24화'), '제목정보없음'으로 별도 분류했다."
        )
    return df


def eda(df: pd.DataFrame) -> dict:
    """STEP 2 - 기초 EDA: 총 시청량, 연도별 추이, Top N 콘텐츠."""
    print("\n" + "=" * 50)
    print("[STEP 2] EDA")

    df = df.copy()
    df["year"] = df["Date"].dt.year
    df["month"] = df["Date"].dt.month
    df["weekday"] = df["Date"].dt.weekday  # 0=월

    yearly = df.groupby("year").size()
    print("\n-- 연도별 시청 레코드 수 --")
    print(yearly)

    top_shows = (
        df[df["category"] != "제목정보없음"]
        .groupby(["show_key", "category"])
        .size()
        .rename("시청횟수")
        .reset_index()
        .sort_values("시청횟수", ascending=False)
        .head(CONFIG.top_n)
    )
    print(f"\n-- Top {CONFIG.top_n} 콘텐츠 (시청 레코드 수 기준) --")
    print(top_shows.to_string(index=False))

    return {"yearly": yearly, "top_shows": top_shows}


def verify_with_polars(df: pd.DataFrame, top_shows: pd.DataFrame) -> None:
    """STEP 2.5 - ex05에서 배운 "같은 집계를 두 엔진으로 각각 구해 결과가 일치하는지
    검증한다"는 원칙을 그대로 적용한다. pandas와 별개로 Polars가 원본 CSV를 직접 읽어
    show_key를 뽑고 집계한 뒤, pandas가 낸 Top N과 같은 결론에 도달하는지 확인하고
    두 엔진의 순수 집계 속도를 비교한다."""
    print("\n" + "=" * 50)
    print("[STEP 2.5] pandas <-> Polars 교차검증")

    pl_df = pl.read_csv(CONFIG.data_path).with_columns(
        pl.when(pl.col("Title").str.contains(": ", literal=True))
        .then(pl.col("Title").str.split(": ").list.first())
        .otherwise(pl.col("Title"))
        .str.strip_chars()
        .alias("show_key")
    )
    polars_top = (
        pl_df.filter(pl.col("show_key") != "")
        .group_by("show_key")
        .len()
        .sort("len", descending=True)
        .head(CONFIG.top_n)
    )

    pandas_top_keys = set(top_shows["show_key"])
    polars_top_keys = set(polars_top["show_key"])
    assert pandas_top_keys == polars_top_keys, (
        f"pandas와 Polars의 Top {CONFIG.top_n} show_key 집합이 다르다: "
        f"{pandas_top_keys.symmetric_difference(polars_top_keys)}"
    )
    print(f"[검증 통과] pandas·Polars 모두 동일한 Top {CONFIG.top_n} show_key 도출")

    n_runs = 5
    pd_series = df["show_key"]
    pandas_times = []
    polars_times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        pd_series.value_counts()
        pandas_times.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        pl_df.group_by("show_key").len()
        polars_times.append(time.perf_counter() - t0)

    print(
        f"순수 집계 속도(최소값, {n_runs}회 중) : "
        f"pandas={min(pandas_times) * 1000:.2f}ms · Polars={min(polars_times) * 1000:.2f}ms"
    )
    print(
        "[한계] 2,205행짜리 소규모 데이터라 두 엔진의 속도 차이가 ex05(대용량 데이터)만큼 "
        "크게 벌어지지 않을 수 있다. 이 비교의 핵심은 속도 자체보다 '같은 결론에 "
        "도달하는가'를 코드로 검증했다는 데 있다."
    )


def detect_binge(df: pd.DataFrame) -> pd.DataFrame:
    """STEP 3 - 몰아보기 탐지. 같은 show_key를 같은 날 3화 이상 보면 'binge day'로 정의.
    (Netflix 원본에는 시각 정보가 없어 날짜 단위가 가장 세밀한 해상도다.)"""
    print("\n" + "=" * 50)
    print("[STEP 3] 몰아보기(binge) 탐지")

    series_df = df[df["category"] == "시리즈"]
    daily_counts = (
        series_df.groupby(["show_key", "Date"]).size().rename("episodes").reset_index()
    )
    binge_days = daily_counts[daily_counts["episodes"] >= 3].sort_values(
        "episodes", ascending=False
    )

    print(f"몰아본 날(하루 3화 이상) 총 {len(binge_days)}일")
    print("\n-- 가장 많이 몰아본 Top 5 --")
    print(binge_days.head(5).to_string(index=False))

    if len(binge_days):
        record = binge_days.iloc[0]
        print(
            f"\n최고 기록: {record['Date'].date()}에 '{record['show_key']}' "
            f"{record['episodes']}화 연속 시청"
        )

    return binge_days


def visualize(df: pd.DataFrame, top_shows: pd.DataFrame) -> None:
    """STEP 4 - Seaborn(요일 x 월 히트맵) + Plotly(Top 콘텐츠 막대) 시각화."""
    CONFIG.output_dir.mkdir(parents=True, exist_ok=True)

    df = df.copy()
    df["month"] = df["Date"].dt.month
    df["weekday"] = df["Date"].dt.weekday

    pivot = (
        df.groupby(["weekday", "month"]).size().unstack(fill_value=0).reindex(range(7))
    )
    pivot.index = WEEKDAY_KR

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.heatmap(pivot, cmap="YlGnBu", annot=True, fmt="d", ax=ax)
    ax.set_title("요일 x 월 시청 패턴 히트맵")
    ax.set_xlabel("월")
    ax.set_ylabel("요일")
    plt.tight_layout()
    png_path = CONFIG.output_dir / "weekday_month_heatmap.png"
    fig.savefig(png_path, dpi=120)
    plt.close(fig)
    print(f"\n[STEP 4] Seaborn 히트맵 저장 -> {png_path}")

    fig_px = px.bar(
        top_shows,
        x="시청횟수",
        y="show_key",
        color="category",
        orientation="h",
        title=f"Top {CONFIG.top_n} 콘텐츠 (시청 레코드 수 기준)",
    )
    fig_px.update_layout(yaxis={"categoryorder": "total ascending"})
    html_path = CONFIG.output_dir / "top_shows.html"
    fig_px.write_html(html_path)
    print(f"[STEP 4] Plotly 인터랙티브 차트 저장 -> {html_path}")


def statistical_tests(df: pd.DataFrame) -> tuple[float, float]:
    """STEP 5 - t-검정(평일 vs 주말 일일 시청량) + 카이제곱 적합도(요일 균등분포 여부)."""
    print("\n" + "=" * 50)
    print("[STEP 5] 통계 검정")

    df = df.copy()
    df["weekday"] = df["Date"].dt.weekday

    daily = df.groupby("Date").size()
    daily_weekday = df.assign(date=df["Date"]).groupby("Date")["weekday"].first()
    is_weekend = daily_weekday.isin([5, 6])

    weekend_counts = daily[is_weekend]
    weekday_counts = daily[~is_weekend]
    t, p_t = stats.ttest_ind(weekend_counts, weekday_counts, equal_var=False)
    print(
        f"t-검정 (주말 vs 평일 일일 시청 레코드 수) : t={t:.3f}, p={p_t:.3e}\n"
        f"  주말 평균={weekend_counts.mean():.2f} / 평일 평균={weekday_counts.mean():.2f}"
    )

    observed = df["weekday"].value_counts().sort_index()
    observed = observed.reindex(range(7), fill_value=0)
    expected = [observed.sum() / 7] * 7
    chi2, p_chi2 = stats.chisquare(observed, f_exp=expected)
    print(
        f"\n카이제곱 적합도 (요일별 시청량이 균등한가) : chi2={chi2:.3f}, p={p_chi2:.3e}"
    )
    print("  요일별 레코드 수:", dict(zip(WEEKDAY_KR, observed.tolist())))

    print(
        "\n해석: p < 0.05 면 '요일에 따라 시청 패턴이 유의하게 다르다'는 뜻이다. "
        "다만 이는 이 계정 한 명의 6년치 기록에 대한 연관 관계이지, 일반적인 시청자 "
        "행동을 일반화하는 근거는 아니다."
    )
    return p_t, p_chi2


def main() -> None:
    if not CONFIG.data_path.exists():
        raise SystemExit(f"[오류] 데이터가 없습니다: {CONFIG.data_path}")

    df = load_data()
    df = classify_titles(df)
    eda_result = eda(df)
    verify_with_polars(df, eda_result["top_shows"])
    binge_days = detect_binge(df)
    visualize(df, eda_result["top_shows"])
    p_t, p_chi2 = statistical_tests(df)

    print("\n" + "=" * 50)
    print(
        "[체크포인트 통과] "
        f"몰아본 날={len(binge_days)}일 · t-검정 p={p_t:.2e} · 카이제곱 p={p_chi2:.2e}"
    )


if __name__ == "__main__":
    main()
