"""pytest -v 로 실행. 6개 테스트: Transform 3개 + Load(Parquet) 1개 + Extract 1개 + run() 종단 1개."""

import asyncio

import pandas as pd

from pipeline import extract, run, transform


def test_카테고리_소문자화():
    valid, _ = transform([{"id": 1, "name": "A", "category": " FOOD ", "price": 10}])
    assert valid[0].category == "food"


def test_음수_가격_거부():
    valid, invalid = transform(
        [{"id": 1, "name": "A", "category": "food", "price": -5}]
    )
    assert len(valid) == 0
    assert len(invalid) == 1


def test_유효_무효_건수_일치():
    rows = [
        {"id": 1, "name": "A", "category": "food", "price": 10},
        {"id": 2, "name": "B", "category": "toys", "price": 20},
        {"id": 3, "name": "C", "category": "food", "price": -1},  # 오염
    ]
    valid, invalid = transform(rows)
    assert len(valid) + len(invalid) == len(rows)  # 하나도 안 새는지
    assert len(valid) == 2
    assert len(invalid) == 1


def test_parquet_라운드트립(tmp_path):
    df = pd.DataFrame({"id": [1, 2], "price": [10.5, 20.0]})
    p = tmp_path / "test.parquet"
    df.to_parquet(p, index=False)
    back = pd.read_parquet(p)
    pd.testing.assert_frame_equal(df, back)


def test_extract_전체_id_반환():
    results = asyncio.run(extract([0, 1, 2, 3, 4]))
    assert len(results) == 5
    assert {r["id"] for r in results} == {0, 1, 2, 3, 4}


def test_run_요약_필드_일치():
    summary = asyncio.run(run(list(range(60))))
    assert summary["total"] == summary["valid"] + summary["invalid"]
    assert summary["rows_saved"] == summary["valid"]
    assert summary["invalid"] == 3  # id 5/17/42 음수 가격
