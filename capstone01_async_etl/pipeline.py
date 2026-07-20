"""
종합실습 1 - 비동기 ETL 파이프라인
Extract(실습3의 세마포어+재시도 비동기 수집) -> Transform(실습2의 Pydantic 검증) ->
Load(CSV/Parquet 저장) -> run()이 셋을 순서대로 조율한다.

각 단계는 독립적으로 테스트 가능하도록 순수 함수/작은 비동기 함수로 분리했다.
실행: python capstone01_async_etl/pipeline.py  (skala_python 루트에서)
"""

import asyncio
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from models import Product

MAX_CONCURRENT = 10
MAX_RETRIES = 3
TIMEOUT_SEC = 3.0

# 모의 원격 데이터 소스. id 5/17/42는 음수 가격(오염), 나머지는 대소문자/공백이
# 섞인 category를 포함해 정규화 검증기가 실제로 동작하는지 보여준다.
_RAW_CATEGORIES = [" Food ", "ELECTRONICS", "clothing", "Books", " toys"]
_MOCK_DB: dict[int, dict] = {
    i: {
        "id": i,
        "name": f"product_{i:03d}",
        "category": _RAW_CATEGORIES[i % len(_RAW_CATEGORIES)],
        "price": -1.0 if i in (5, 17, 42) else round(10.0 + i * 0.5, 2),
    }
    for i in range(60)
}


async def _fetch_one(item_id: int, sem: asyncio.Semaphore) -> dict:
    """모의 원격 조회 1건. 세마포어로 동시 요청 수를 제한하고, 실패 시 지수 백오프로 재시도한다."""
    for attempt in range(MAX_RETRIES):
        try:
            async with sem:
                async with asyncio.timeout(TIMEOUT_SEC):
                    await asyncio.sleep(0.01)  # 네트워크 대기 흉내
                    if item_id not in _MOCK_DB:
                        raise KeyError(f"id={item_id} 를 찾을 수 없습니다")
                    return _MOCK_DB[item_id]
        except Exception:
            if attempt == MAX_RETRIES - 1:
                raise
            await asyncio.sleep(2**attempt)
    raise RuntimeError("unreachable")


async def extract(ids: list[int], max_concurrent: int = MAX_CONCURRENT) -> list[dict]:
    """비동기로 원본 레코드를 모아온다. 하나가 실패해도 나머지는 살아남는다(예외 격리)."""
    sem = asyncio.Semaphore(max_concurrent)
    results = await asyncio.gather(
        *(_fetch_one(i, sem) for i in ids), return_exceptions=True
    )
    return [r for r in results if not isinstance(r, BaseException)]


def transform(raw: list[dict]) -> tuple[list[Product], list[dict]]:
    """입력만 받아 결과만 돌려주는 순수 함수. 네트워크/파일을 전혀 건드리지 않는다."""
    valid: list[Product] = []
    invalid: list[dict] = []
    for row in raw:
        try:
            valid.append(Product(**row))
        except ValidationError as e:
            invalid.append({"data": row, "errors": e.errors()})
    return valid, invalid


def load(valid: list[Product], out_dir: str = "output") -> pd.DataFrame:
    out_path = Path(__file__).resolve().parent / out_dir
    out_path.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([v.model_dump() for v in valid])
    df.to_csv(out_path / "products.csv", index=False)
    df.to_parquet(out_path / "products.parquet", index=False)
    return df


async def run(ids: list[int]) -> dict:
    raw = await extract(ids)  # E
    valid, invalid = transform(raw)  # T
    df = load(valid)  # L
    return {
        "total": len(raw),
        "valid": len(valid),
        "invalid": len(invalid),
        "rows_saved": len(df),
    }


if __name__ == "__main__":
    summary = asyncio.run(run(list(range(60))))
    print(summary)
    assert summary["total"] == summary["valid"] + summary["invalid"]
    print("[체크포인트 통과] E-T-L 파이프라인 정상 동작")
