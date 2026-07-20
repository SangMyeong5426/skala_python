"""
프로그램명 : 실습 1 - 대용량 로그 스트리밍 집계
설명       : web_logs.csv(20만 행)를 메모리에 전부 올리지 않고 제너레이터로
             한 줄씩 흘려보내며, 단 한 번의 순회(one-pass)로 경로별·상태코드별·
             시간대별·IP별 지표를 동시에 집계한다.

체크포인트 : 총 200,000건, 5xx 비율 ≈ 8.0%
실행       : python ex01_streaming_agg/solution.py  (skala_python 루트에서)
"""

import csv
import tracemalloc
from collections import Counter
from functools import reduce
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "python_data" / "web_logs.csv"


def read_logs(path: Path):
    """한 줄씩 읽어 dict로 흘려보내는 제너레이터. 파일을 통째로 메모리에 올리지 않는다."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def aggregate(path: Path) -> dict:
    """단 한 번의 순회로 여러 지표를 동시에 채운다 (1-pass)."""
    total = 0
    by_status = Counter()
    by_path = Counter()
    by_ip = Counter()
    by_hour = Counter()

    for row in read_logs(path):
        total += 1
        by_status[row["status"]] += 1
        by_path[row["path"]] += 1
        by_ip[row["ip"]] += 1
        hour = row["timestamp"][11:13]  # 'YYYY-MM-DDTHH:MM:SS' -> HH
        by_hour[hour] += 1

    return {
        "total": total,
        "by_status": by_status,
        "by_path": by_path,
        "by_ip": by_ip,
        "by_hour": by_hour,
    }


def fold(acc: dict, row: dict) -> dict:
    """functools.reduce와 함께 쓰는 누적기. for-loop 집계와 동일한 일을 함수형으로 표현."""
    acc["total"] += 1
    acc["status"][row["status"]] += 1
    return acc


def aggregate_with_reduce(path: Path) -> dict:
    init = {"total": 0, "status": Counter()}
    return reduce(fold, read_logs(path), init)


def print_report(stats: dict) -> None:
    total = stats["total"]
    by_status = stats["by_status"]
    by_path = stats["by_path"]
    by_ip = stats["by_ip"]
    by_hour = stats["by_hour"]

    err_5xx = sum(c for s, c in by_status.items() if str(s).startswith("5"))
    ratio = err_5xx / total * 100

    print("=" * 40)
    print(f"총 요청 수 : {total:,}")
    print(f"5xx 오류율 : {ratio:.1f}% ({err_5xx:,}건)")

    print("-- 상태코드별 분포 --")
    for status, cnt in by_status.most_common():
        print(f"  {status:<6} {cnt:>7,}")

    print("-- 인기 경로 TOP 5 --")
    for path, cnt in by_path.most_common(5):
        print(f"  {path:<20} {cnt:>7,}")

    print("-- 시간대별 요청 수 (TOP 5) --")
    for hour, cnt in sorted(by_hour.items(), key=lambda kv: -kv[1])[:5]:
        print(f"  {hour}시    {cnt:>7,}")

    print("-- 접속 상위 IP TOP 5 --")
    for ip, cnt in by_ip.most_common(5):
        print(f"  {ip:<20} {cnt:>7,}")


def compare_memory(path: Path) -> None:
    """확장 과제: readlines() 방식 vs 제너레이터 방식의 최대 메모리 비교."""

    tracemalloc.start()
    with path.open(encoding="utf-8") as f:
        lines = f.readlines()  # 뷔페 방식 - 전부 메모리에
    _ = len(lines)
    _, peak_list = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del lines   

    tracemalloc.start()
    total = 0
    for _ in read_logs(path):  # 컨베이어벨트 방식
        total += 1
    _, peak_gen = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print("\n-- 확장 과제: 메모리 비교 (tracemalloc) --")
    print(f"  readlines() 방식 최대 메모리 : {peak_list / 1024 / 1024:.2f} MB")
    print(f"  제너레이터 방식 최대 메모리   : {peak_gen / 1024 / 1024:.2f} MB")


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(
            f"[오류] 데이터가 없습니다: {DATA_PATH}\n"
            "python_data/generate_data.py 를 먼저 실행하세요."
        )

    stats = aggregate(DATA_PATH)
    print_report(stats)

    # functools.reduce 버전도 같은 total 을 내는지 확인
    reduced = aggregate_with_reduce(DATA_PATH)
    assert reduced["total"] == stats["total"], "reduce 버전과 결과가 다릅니다"
    print(f"\n[fold/reduce 버전 확인] total = {reduced['total']:,} (일치)")

    compare_memory(DATA_PATH)


if __name__ == "__main__":
    main()
