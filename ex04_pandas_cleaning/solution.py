"""
프로그램명 : 실습 4 - Pandas 2.x 데이터 정제
설명       : sales_raw.csv(5천 행, 결측·이상치·타입 불일치가 섞인 '현실 데이터')를
             진단 -> 타입 정규화 -> 결측 처리 -> 이상치 처리 -> 집계 순서로 정제하고,
             groupby.agg / pivot_table / merge 로 의미 있는 요약을 만든다.
             마지막으로 Pandas 2.x(3.x) 의 Copy-on-Write 동작을 직접 확인한다.

체크포인트 : 정제 전후 비교(결측 0건, 이상치 clip 확인) + 집계 결과 출력
실행       : python ex04_pandas_cleaning/solution.py  (skala_python 루트에서)
"""

from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "python_data" / "sales_raw.csv"

# region 이 결측일 때 채워 넣을 값. 지리 정보는 다른 컬럼으로 추정할 근거가 없으므로
# 중앙값/최빈값 대치 대신 '알 수 없음'을 명시적으로 남긴다 (조용히 지어내지 않는다).
UNKNOWN_REGION = "Unknown"


def diagnose(df: pd.DataFrame) -> None:
    # STEP 0 - 치료 전 진단. 정제 방향을 정하기 전에 눈으로 먼저 확인한다.
    print("=" * 50)
    print("[STEP 0] 진단")
    print(f"shape: {df.shape}")
    print("\n-- dtypes --")
    print(df.dtypes)
    print("\n-- 결측치 개수 --")
    print(df.isna().sum())
    print("\n-- 수치형 요약 (이상치 냄새 확인) --")
    print(df[["quantity", "unit_price", "discount"]].describe())


def normalize_types(df: pd.DataFrame) -> pd.DataFrame:
    """STEP 1 - 숫자는 숫자로, 날짜는 날짜로. 결측 처리보다 반드시 먼저 수행한다."""
    df = df.copy()
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["discount"] = pd.to_numeric(df["discount"], errors="coerce")
    df["category"] = df["category"].astype("category")
    return df


def fill_missing(df: pd.DataFrame) -> pd.DataFrame:
    """STEP 2 - 결측 처리. 0 대치는 절대 하지 않는다.

    - unit_price: 같은 category 안의 중앙값으로 대치(중앙값은 이상치에 덜 끌려간다).
    - region: 다른 컬럼으로 추정할 근거가 없으므로 'Unknown'으로 명시.
    """
    df = df.copy()
    df["unit_price"] = df.groupby("category", observed=True)["unit_price"].transform(
        lambda s: s.fillna(s.median())
    )
    df["region"] = df["region"].fillna(UNKNOWN_REGION)
    return df


def winsorize(s: pd.Series, k: float = 1.5) -> pd.Series:
    """IQR 기반 윈저라이징. 삭제 대신 경계선으로 끌어당겨 행을 살린다."""
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    low, high = q1 - k * iqr, q3 + k * iqr
    return s.clip(lower=low, upper=high)


def handle_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """STEP 3 - 이상치 처리. quantity(비정상 대량 주문), unit_price(음수 포함)를 윈저라이징.

    unit_price 는 통계적 IQR 경계만으로는 하한이 여전히 음수로 계산될 만큼
    분포가 넓게 퍼져 있다(가격이 5천~30만 원 사이 균등에 가깝게 분포).
    통계만 맹신하지 않고 '가격은 0 미만일 수 없다'는 도메인 규칙을 IQR 경계 위에
    한 번 더 적용해, 통계적 이상치 처리와 업무 규칙을 함께 반영한다.
    """
    df = df.copy()
    df["quantity"] = winsorize(df["quantity"])
    df["unit_price"] = winsorize(df["unit_price"]).clip(lower=0)
    return df


def add_amount(df: pd.DataFrame) -> pd.DataFrame:
    """정제된 quantity/unit_price/discount 로 최종 매출액을 계산한다."""
    df = df.copy()
    df["amount"] = (df["quantity"] * df["unit_price"] * (1 - df["discount"])).round(0)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_types(df) # 타입 정규화
    df = fill_missing(df) # 결측 처리
    df = handle_outliers(df) # 이상치 처리
    df = add_amount(df) # 파생 컬럼 추가
    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """STEP 4 - groupby.agg: 카테고리별 요약(건수·평균가·중앙값·총매출)."""
    return (
        df.groupby("category", observed=True)
        .agg(
            건수=("amount", "count"),
            평균매출=("amount", "mean"),
            중앙값매출=("amount", "median"),
            총매출=("amount", "sum"),
        )
        .round(1)
        .sort_values("총매출", ascending=False)
    )


def cross_tab(df: pd.DataFrame) -> pd.DataFrame:
    """STEP 5 - pivot_table: region x category 교차표(엑셀 피벗과 동일한 개념)."""
    return df.pivot_table(
        index="region",
        columns="category",
        values="amount",
        aggfunc="sum",
        fill_value=0,
        observed=True,
    )


def merge_with_manager(df: pd.DataFrame) -> pd.DataFrame:
    """STEP 6 - merge: 지역별 담당자 테이블과 결합. merge 전후 행 수를 반드시 비교한다."""
    managers = pd.DataFrame(
        {
            "region": ["Seoul", "Busan", "Incheon", "Daegu", "Gwangju"],
            "manager": ["김서울", "이부산", "박인천", "최대구", "정광주"],
        }
    )
    before = len(df)
    merged = df.merge(managers, on="region", how="left")
    after = len(merged)
    print(
        f"\n[STEP 6] merge 전후 행 수 : {before:,} -> {after:,} (일치: {before == after})"
    )
    print("담당자 미배정(Unknown 지역 등) 건수:", merged["manager"].isna().sum())
    return merged


def demo_copy_on_write(df: pd.DataFrame) -> None:
    """STEP 7 - Copy-on-Write 확인. 슬라이스를 건드려도 원본이 조용히 깨지지 않아야 한다."""
    print("\n" + "=" * 50)
    print("[STEP 7] Copy-on-Write 동작 확인")

    original_first_amount = df.loc[df["region"] == "Seoul", "amount"].iloc[0]

    # 체인 인덱싱으로 슬라이스를 수정 -> CoW 덕분에 복사본만 바뀌고 원본은 안전
    seoul = df[df["region"] == "Seoul"]
    seoul["amount"] = seoul["amount"] * 1.1
    print(
        f"  슬라이스 수정 후 원본 첫 값 : {df.loc[df['region'] == 'Seoul', 'amount'].iloc[0]:,.0f} "
        f"(수정 전과 동일: {df.loc[df['region'] == 'Seoul', 'amount'].iloc[0] == original_first_amount})"
    )

    # 원본을 실제로 바꾸고 싶다면 .loc 으로 명시적으로 지정해야 한다
    df.loc[df["amount"] > 1_000_000, "flag"] = "high_value"
    high_value_cnt = (df["flag"] == "high_value").sum()
    print(f"  .loc 으로 원본에 flag 부여 : high_value {high_value_cnt:,}건")


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(
            f"[오류] 데이터가 없습니다: {DATA_PATH}\n"
            "python_data/generate_data.py 를 먼저 실행하세요."
        )

    raw = pd.read_csv(DATA_PATH)
    diagnose(raw)

    na_before = (
        raw["region"].isna().sum()
        + pd.to_numeric(raw["unit_price"], errors="coerce").isna().sum()
    )
    price_max_before = pd.to_numeric(raw["unit_price"], errors="coerce").max()
    qty_max_before = pd.to_numeric(raw["quantity"], errors="coerce").max()

    df = clean(raw)

    na_after = df["region"].isna().sum() + df["unit_price"].isna().sum()

    print("\n" + "=" * 50)
    print("[정제 전후 비교]")
    print(f"  결측 개수(region+unit_price) : {na_before:,}건 -> {na_after:,}건")
    print(
        f"  unit_price max              : {price_max_before:,.0f} -> {df['unit_price'].max():,.0f}"
    )
    print(
        f"  quantity max                : {qty_max_before:,.0f} -> {df['quantity'].max():,.0f}"
    )
    print(
        f"  dtypes 확인                 : order_date={df['order_date'].dtype}, "
        f"category={df['category'].dtype}"
    )

    print("\n" + "=" * 50)
    print("[STEP 4] 카테고리별 집계 (groupby.agg)")
    print(summarize(df))

    print("\n" + "=" * 50)
    print("[STEP 5] 지역 x 카테고리 교차표 (pivot_table)")
    print(cross_tab(df))

    merged = merge_with_manager(df)

    demo_copy_on_write(df)

    assert na_after == 0, "결측이 남아있으면 안 됩니다"
    assert df["unit_price"].min() >= 0, "윈저라이징 후에도 음수 가격이 남아있습니다"
    assert len(merged) == len(df), "merge 로 행 수가 달라졌습니다(how='left' 확인 필요)"
    print(
        "\n[체크포인트 통과] 결측 0건 · 이상치 윈저라이징 완료 · merge 전후 행 수 일치"
    )


if __name__ == "__main__":
    main()
