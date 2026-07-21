"""
프로그램명 : 실습 5 - Polars · DuckDB 성능 비교
설명       : events_large.csv(100만 행)에 대해 똑같은 질의
             ("amount > 0 인 거래(구매/환불)만 골라 event_type 별로 묶고,
               건수와 평균 amount 를 구한 뒤 건수 내림차순 정렬")를
             Pandas(baseline) · Polars(Lazy API) · DuckDB(SQL) 세 엔진으로 각각 돌려
             실행 시간을 비교하고, 세 결과가 완전히 동일한지 먼저 검증한다.

핵심 원칙 : "결과가 같음을 증명한 뒤에 성능을 말한다" - 검증 없는 최적화는 버그다.
체크포인트 : 3엔진 결과 일치(assert_frame_equal) + 실행 시간 비교표 출력
실행       : python ex05_polars_duckdb/solution.py  (skala_python 루트에서)
"""

import time
from pathlib import Path

import duckdb
import pandas as pd
import polars as pl

DATA_PATH = Path(__file__).resolve().parent.parent / "python_data" / "events_large.csv"
N_RUNS = 3  # 첫 실행엔 캐시/초기화 비용이 섞이므로 여러 번 돌려 최솟값을 쓴다


def run_pandas(path: Path) -> tuple[pd.DataFrame, float]:
    start = time.perf_counter()
    df = pd.read_csv(path)
    result = (
        df[df["amount"] > 0]
        .groupby("event_type")
        .agg(cnt=("amount", "count"), avg=("amount", "mean"))
        .sort_values("cnt", ascending=False)
        .reset_index()
    )
    return result, time.perf_counter() - start


def run_polars_lazy(path: Path) -> tuple[pd.DataFrame, float]:
    start = time.perf_counter()
    result = (
        pl.scan_csv(path)  # scan = 읽겠다고 계획만 세우기 (지연 실행)
        .filter(pl.col("amount") > 0)
        .group_by("event_type")
        .agg(
            [
                pl.len().alias("cnt"),
                pl.col("amount").mean().alias("avg"),
            ]
        )
        .sort("cnt", descending=True)
        .collect()  # 여기서 실제로 실행됨
    )
    elapsed = time.perf_counter() - start
    return result.to_pandas(), elapsed


def run_duckdb(path: Path) -> tuple[pd.DataFrame, float]:
    start = time.perf_counter()
    result = duckdb.sql(f"""
        SELECT event_type,
               COUNT(amount) AS cnt,
               AVG(amount)   AS avg
        FROM '{path.as_posix()}'
        WHERE amount > 0
        GROUP BY event_type
        ORDER BY cnt DESC
    """).df()
    return result, time.perf_counter() - start


def show_polars_plan(path: Path) -> None:
    """확장: Lazy 실행 계획을 훔쳐본다 - 필터가 스캔 단계로 내려갔는지(pushdown) 확인."""
    plan = (
        pl.scan_csv(path)
        .filter(pl.col("amount") > 0)
        .group_by("event_type")
        .agg(pl.len().alias("cnt"))
        .explain()
    )
    print("\n-- Polars 실행 계획 (predicate/projection pushdown 확인) --")
    print(plan)


def verify_results_match(a: pd.DataFrame, b: pd.DataFrame, c: pd.DataFrame) -> None:
    """이 실습에서 가장 중요한 단계: 성능을 비교하기 전에 결과가 완전히 같은지 확인한다."""

    def normalize(df: pd.DataFrame) -> pd.DataFrame:
        return (
            df.sort_values("event_type")
            .reset_index(drop=True)
            .astype({"cnt": "int64", "avg": "float64"})
        )

    a, b, c = normalize(a), normalize(b), normalize(c)
    pd.testing.assert_frame_equal(a, b, check_dtype=False, atol=1e-6)
    pd.testing.assert_frame_equal(a, c, check_dtype=False, atol=1e-6)
    print(
        "[검증 통과] Pandas · Polars · DuckDB 세 엔진의 집계 결과가 완전히 일치합니다."
    )


def benchmark(path: Path) -> None:
    engines = {
        "Pandas": run_pandas,
        "Polars(Lazy)": run_polars_lazy,
        "DuckDB": run_duckdb,
    }
    best_time: dict[str, float] = {}
    last_result: dict[str, pd.DataFrame] = {}

    for name, fn in engines.items():
        times = []
        for _ in range(N_RUNS):
            result, elapsed = fn(path)
            times.append(elapsed)
            last_result[name] = result
        best_time[name] = min(times)  # 안정된 값(최솟값) 채택

    verify_results_match(
        last_result["Pandas"], last_result["Polars(Lazy)"], last_result["DuckDB"]
    )

    print("\n" + last_result["Pandas"].to_string(index=False))

    total_rows = duckdb.sql(f"SELECT COUNT(*) FROM '{path.as_posix()}'").fetchone()[0]
    print(f"\n-- 벤치마크 (총 {total_rows:,}행, {N_RUNS}회 중 최솟값) --")
    baseline = best_time["Pandas"]
    print(f"{'엔진':<14}{'시간(ms)':>10}{'배속':>10}")
    for name, t in sorted(best_time.items(), key=lambda kv: kv[1]):
        print(f"{name:<14}{t * 1000:>10.1f}{baseline / t:>9.1f}x")

    show_polars_plan(path)


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(
            f"[오류] 데이터가 없습니다: {DATA_PATH}\n"
            "python_data/generate_data.py 를 먼저 실행하세요."
        )

    print(
        "질의: amount > 0 인 거래만 골라 event_type 별 건수·평균 amount, 건수 내림차순 정렬\n"
    )
    benchmark(DATA_PATH)


if __name__ == "__main__":
    main()
