"""
프로그램명 : 실습 3 - Pandas EDA · Polars Lazy · DuckDB SQL 비교
작성자     : 박상명
작성일     : 2026-07-21
설명       : sales_100k.csv를 Pandas로 로드해 기본 EDA를 수행한 뒤 IQR 방법으로 이상치 제거를 진행한다.
            동일한 region·category 집계를 Pandas(named aggregation) · Polars(Lazy
            API) · DuckDB(SQL) 세 가지 방식으로 각각 구현한 뒤 timeit으로 실행
            시간을 비교한다.

[실습 목표]
  1) Pandas EDA 기초 탐색 + 이상치 처리
     - df.info(), isnull().sum() 출력
     - IQR(lo=Q1-1.5*IQR, hi=Q3+1.5*IQR) 범위를 벗어나는 행을 이상치로 제거
     - 제거 전/후 행 수 출력
  2) Pandas groupby named aggregation
     - region·category별 total(총매출)·mean(평균)·cnt(건수)를 named aggregation으로 계산
     - total 내림차순 정렬
  3) Polars Lazy API로 동일 집계 작성
     - scan_csv → filter(1번과 동일한 lo/hi) → group_by → agg → sort → collect
  4) DuckDB SQL + 세 도구 성능 비교
     - 동일 집계를 SQL GROUP BY로 작성, .df()로 DataFrame 변환
     - timeit으로 Pandas·Polars·DuckDB를 동일 반복 횟수(NUMBER_REPEAT)로 측정

[체크포인트 대응]
  - df.info()/isnull().sum() 출력 + IQR 전후 행 수 출력   → load_and_clean()
  - total·mean·cnt named aggregation + total 내림차순     → pandas_agg()
  - scan_csv→filter→group_by→agg→sort→collect 체인        → polars_agg()
  - 동일 집계 SQL GROUP BY + DataFrame 변환                → duckdb_agg()
  - 동일 반복 횟수 timeit 비교                             → compare_performance()

[감점 방지 포인트]
  - named aggregation 사용 (agg({'amount': 'sum'}) 방식 금지)
  - Polars는 scan_csv(Lazy)만 사용, 반드시 collect()로 마무리 (read_csv 금지)
  - IQR 공식: lo = Q1 - 1.5*IQR, hi = Q3 + 1.5*IQR (부호 반대로 쓰지 않도록 주의)
  - timeit 반복 횟수(NUMBER_REPEAT)를 세 도구 모두 동일하게 사용

[입력 데이터] sales_100k.csv (region, category, amount 컬럼 필수)

변경내역   : 2026-07-21 최초 작성
"""

import logging
import sys
import timeit
from pathlib import Path

import duckdb
import pandas as pd
import polars as pl

# ─────────────────────────────────────
# 전역 설정: 파일 경로 상수와 logging
# ─────────────────────────────────────
DATA_PATH = Path("sales_100k.csv")
REQUIRED_COLS = {"region", "category", "amount"}
GROUP_COLS = ["region", "category"]
NUMBER_REPEAT = 5  # 세 도구 timeit 비교 시 동일하게 적용할 반복 횟수

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s|%(levelname)s|%(message)s",
)
logger = logging.getLogger("practice3")


# ═════════════════════════════════════
# 1) Pandas EDA 기초 탐색 + 이상치 처리
# ─────────────────────────────────────
# [목표] 파일을 안전하게 읽고 기본 정보를 확인한 뒤, IQR 기준으로 이상치를
#        제거한다. 여기서 구한 lo/hi는 2)~4)에서 동일한 조건으로 재사용해
#        세 도구의 집계 결과가 같은 데이터를 대상으로 비교되도록 한다.
# ═════════════════════════════════════
def load_and_clean(path: Path) -> tuple[pd.DataFrame, float, float]:
    """CSV를 로드해 기초 EDA(정보·결측치)를 출력하고, IQR 기준 이상치를
    제거한 DataFrame과 필터 경계값(lo, hi)을 반환한다."""
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        logger.error(f"파일 없음: {path} (sales_100k.csv를 프로젝트 폴더에 준비하세요)")
        raise

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    print(f"\n=== 1) 기초 EDA: {path} ===")
    df.info()

    print("\n결측치 현황:")
    print(df.isnull().sum())
    
    q1 = df["amount"].quantile(0.25)
    q3 = df["amount"].quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr

    before = len(df)
    df_clean = df[df["amount"].between(lo, hi)]
    after = len(df_clean)
    print(
        f"\nIQR 이상치 제거 범위: [{lo:.0f}, {hi:.0f}] "
        f"→ {before}행 → {after}행 ({before - after}건 제거)"
    )
    return df_clean, lo, hi


# ═════════════════════════════════════
# 2) Pandas groupby named aggregation
# ─────────────────────────────────────
def pandas_agg(df_clean: pd.DataFrame) -> pd.DataFrame:
    """region·category별 총매출(total)·평균(mean)·건수(cnt)를
    named aggregation으로 계산해 총매출 내림차순으로 정렬한다."""
    return (
        df_clean.groupby(GROUP_COLS)
        .agg(total=("amount", "sum"), mean=("amount", "mean"), cnt=("amount", "count"))
        .reset_index()
        .sort_values("total", ascending=False)
    )


# ═════════════════════════════════════
# 3) Polars Lazy API로 동일 집계 작성
# ─────────────────────────────────────
def polars_agg(path: Path, lo: float, hi: float) -> pl.DataFrame:
    """scan_csv(Lazy) → filter → group_by → agg → sort → collect 체인으로
    Pandas와 동일한 집계를 재현한다."""
    return (
        pl.scan_csv(path)
        .filter(pl.col("amount").is_between(lo, hi))
        .group_by(GROUP_COLS)
        .agg(
            pl.col("amount").sum().alias("total"),
            pl.col("amount").mean().alias("mean"),
            pl.col("amount").count().alias("cnt"),
        )
        .sort("total", descending=True)
        .collect()
    )


# ═════════════════════════════════════
# 4) DuckDB SQL + 세 도구 성능 비교
# ─────────────────────────────────────
def duckdb_agg(path: Path, lo: float, hi: float) -> pd.DataFrame:
    """동일 집계를 SQL GROUP BY로 작성하고 결과를 Pandas DataFrame으로 변환한다."""
    query = f"""
        SELECT region, category,
               SUM(amount) AS total,
               AVG(amount) AS mean,
               COUNT(*)    AS cnt
        FROM '{path}'
        WHERE amount BETWEEN {lo} AND {hi}
        GROUP BY region, category
        ORDER BY total DESC
    """
    return duckdb.sql(query).df()


def compare_performance(df_clean: pd.DataFrame, path: Path, lo: float, hi: float) -> None:
    """Pandas·Polars·DuckDB 집계 함수를 동일 반복 횟수(NUMBER_REPEAT=5)로
    timeit 측정해 실행 시간을 비교 출력한다."""
    times = {
        "pandas": timeit.timeit(lambda: pandas_agg(df_clean), number=NUMBER_REPEAT),
        "polars": timeit.timeit(lambda: polars_agg(path, lo, hi), number=NUMBER_REPEAT),
        "duckdb": timeit.timeit(lambda: duckdb_agg(path, lo, hi), number=NUMBER_REPEAT),
    }
    fastest = min(times.values())
    print(f"\n=== 4) 성능 비교 (반복 {NUMBER_REPEAT}회 합산 시간, 동일 조건) ===")
    for name, sec in times.items():
        print(f"  {name:8s}: {sec:.4f}초  ({sec / fastest:.2f}x)")


# ═════════════════════════════════════
# main: 전체 파이프라인을 순서대로 실행
# ═════════════════════════════════════
def main() -> None:
    """로딩·EDA·이상치 제거 → 3개 도구 집계 → 성능 비교 순으로 실행한다."""
    try:
        df_clean, lo, hi = load_and_clean(DATA_PATH)

        print("\n=== 2) Pandas groupby named aggregation (상위 5행) ===")
        print(pandas_agg(df_clean).head())

        print("\n=== 3) Polars Lazy API (상위 5행) ===")
        print(polars_agg(DATA_PATH, lo, hi).head(5))

        print("\n=== 4) DuckDB SQL (상위 5행) ===")
        print(duckdb_agg(DATA_PATH, lo, hi).head())

        compare_performance(df_clean, DATA_PATH, lo, hi)

        logger.info("실습 3 파이프라인 정상 종료")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"데이터 오류로 중단: {e}")
        sys.exit(1)
    except Exception as e:  # 예상치 못한 오류도 로그를 남기고 안전하게 종료
        logger.error(f"파이프라인 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":  # 직접 실행할 때만 main()이 동작 (import 시에는 실행 안 됨)
    main()
