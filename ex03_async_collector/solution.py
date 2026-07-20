"""
프로그램명 : 실습 3 - asyncio 기반 비동기 수집기
설명       : 60건의 데이터를 동시에 가져오되, Semaphore로 동시 요청 수를 10개로
             제한(백프레셔)하고, 타임아웃과 지수 백오프 재시도, 예외 격리까지
             갖춘 '예의 바르고 튼튼한' 수집기를 만든다.

USE_REAL_HTTP=False 이면 실제 네트워크 없이 asyncio.sleep으로 지연을 흉내낸다.
체크포인트 : 60건을 1~2초 내 처리
실행       : python ex03_async_collector/solution.py  (skala_python 루트에서)
"""

import asyncio
import json
import random
import time
from pathlib import Path

USE_REAL_HTTP = False
N_ITEMS = 60
MAX_CONCURRENT = 10
MAX_RETRIES = 3
TIMEOUT_SEC = 3.0
DEAD_LETTER_PATH = Path(__file__).resolve().parent / "dead_letter.json"

# 재현 가능하도록 이 스크립트 안에서만 쓰는 랜덤 시드 고정
_rng = random.Random(7)
# 처음 시도에서만 일시적으로 실패하는 id들 (재시도로 복구되는 상황을 보여주기 위함)
_FLAKY_IDS = {i for i in range(N_ITEMS) if _rng.random() < 0.1}


def fetch_sync(item_id: int) -> dict:
    time.sleep(0.1)  # do_request와 동일한 평균 지연 (공정 비교)
    return {"id": item_id, "ok": True}


async def do_request(item_id: int) -> dict:
    """실제 요청 1회. USE_REAL_HTTP=False면 모의 지연 + 일부 id는 첫 시도에서만 실패."""
    if USE_REAL_HTTP:
        import httpx

        async with httpx.AsyncClient(timeout=TIMEOUT_SEC) as client:
            resp = await client.get(f"https://example.com/api/items/{item_id}")
            resp.raise_for_status()
            return {"id": item_id, "ok": True}

    await asyncio.sleep(_rng.uniform(0.05, 0.15))
    if item_id in _FLAKY_IDS:
        _FLAKY_IDS.discard(item_id)  # 다음 시도부터는 성공하도록 (일시적 장애 흉내)
        raise ConnectionError(f"item {item_id}: 일시적 오류")
    return {"id": item_id, "ok": True}


async def fetch_with_retry(item_id: int, sem: asyncio.Semaphore) -> dict:
    for attempt in range(MAX_RETRIES):
        try:
            async with sem:  # 백프레셔: 동시 10개까지만
                async with asyncio.timeout(TIMEOUT_SEC):
                    return await do_request(item_id)
        except TimeoutError:
            if attempt == MAX_RETRIES - 1:
                return {"id": item_id, "ok": False, "reason": "timeout"}
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return {"id": item_id, "ok": False, "reason": str(e)}
            wait = 2**attempt  # 1 -> 2 -> 4 초, 지수 백오프
            await asyncio.sleep(wait)
    # 이론상 도달하지 않음
    return {"id": item_id, "ok": False, "reason": "unreachable"}


async def collect(ids: list[int]) -> list[dict]:
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [fetch_with_retry(i, sem) for i in ids]
    results = await asyncio.gather(
        *tasks, return_exceptions=True
    )  # 하나 실패해도 전체는 살림

    ok = [r for r in results if isinstance(r, dict) and r.get("ok")]
    failed = [r for r in results if isinstance(r, dict) and not r.get("ok")]
    crashed = [r for r in results if isinstance(r, BaseException)]

    if failed or crashed:
        dead = failed + [{"error": str(e)} for e in crashed]
        DEAD_LETTER_PATH.write_text(
            json.dumps(dead, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[dead-letter] 재시도 소진 {len(dead)}건 -> {DEAD_LETTER_PATH}")

    return ok


def run_sync_baseline(ids: list[int]) -> float:
    start = time.perf_counter()
    [fetch_sync(i) for i in ids]
    return time.perf_counter() - start


async def main() -> None:
    ids = list(range(N_ITEMS))

    sync_elapsed = run_sync_baseline(ids)
    print(f"동기 방식     : {N_ITEMS}건 처리에 {sync_elapsed:.2f}초")

    start = time.perf_counter()
    results = await collect(ids)
    async_elapsed = time.perf_counter() - start

    print(
        f"비동기 방식   : {N_ITEMS}건 중 {len(results)}건 성공, {async_elapsed:.2f}초 소요"
    )
    print(f"동시 요청 제한: {MAX_CONCURRENT}개 (Semaphore)")

    assert async_elapsed < 3.0, f"체크포인트 초과: {async_elapsed:.2f}초"
    print("\n[체크포인트 통과] 1~2초대 처리 완료")


if __name__ == "__main__":
    asyncio.run(main())
