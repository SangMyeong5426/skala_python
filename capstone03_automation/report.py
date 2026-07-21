"""
종합실습 3 - 분석 자동화 · 리포트 생성 (핵심 로직)
관심사의 분리: 설정(config.py) · 집계+렌더링(이 파일) · 실행 조율(run_scheduler.py).
집계 함수(aggregate)는 순수 함수로 두고, 파일 쓰기는 render()에서만 일어나게 해
종합실습 1(E-T-L 파이프라인)에서 배운 "계산과 부수효과 분리" 원칙을 그대로 재사용한다.

실행 : python capstone03_automation/report.py  (skala_python 루트에서, 1회 실행)
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from config import CONFIG, Config


def _winsorize(s: pd.Series, k: float = 1.5) -> pd.Series:
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    return s.clip(lower=q1 - k * iqr, upper=q3 + k * iqr)


def load_and_clean(path: Path) -> pd.DataFrame:
    """sales_raw.csv 를 읽어 실습4(ex04_pandas_cleaning)와 동일한 원칙으로 정제한다:
    타입 정규화 -> 결측 처리(그룹별 중앙값/명시적 Unknown) -> 이상치 윈저라이징 -> amount 계산."""
    df = pd.read_csv(path)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["discount"] = pd.to_numeric(df["discount"], errors="coerce")

    df["unit_price"] = df.groupby("category", observed=True)["unit_price"].transform(
        lambda s: s.fillna(s.median())
    )
    df["region"] = df["region"].fillna("Unknown")

    df["quantity"] = _winsorize(df["quantity"])
    df["unit_price"] = _winsorize(df["unit_price"]).clip(lower=0)

    df["amount"] = (df["quantity"] * df["unit_price"] * (1 - df["discount"])).round(0)
    return df


def aggregate(df: pd.DataFrame, top_n: int = 5) -> dict:
    """데이터 -> 리포트에 넣을 값들. 파일/네트워크를 전혀 건드리지 않는 순수 함수."""
    return {
        "kpi": {
            "총매출": int(df["amount"].sum()),
            "주문수": len(df),
            "평균주문액": round(df["amount"].mean(), 1),
        },
        "by_category": (
            df.groupby("category", observed=True)["amount"]
            .sum()
            .sort_values(ascending=False)
            .head(top_n)
            .reset_index()
            .to_dict("records")
        ),
        "by_region": (
            df.groupby("region", observed=True)["amount"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
            .to_dict("records")
        ),
    }


def render(data: dict, cfg: Config = CONFIG) -> Path:
    """집계 결과를 Jinja2 템플릿에 부어 타임스탬프가 붙은 HTML 파일로 저장한다."""
    env = Environment(loader=FileSystemLoader(cfg.template_dir))
    tpl = env.get_template(cfg.template_name)

    html = tpl.render(
        title=cfg.title,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **data,
    )

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = cfg.output_dir / f"report_{stamp}.html"
    out.write_text(html, encoding="utf-8")
    return out


def run_once(cfg: Config = CONFIG) -> Path:
    """루프 · schedule · cron 세 실행 방식이 모두 이 함수 하나만 호출한다(일관성)."""
    df = load_and_clean(cfg.data_path)
    data = aggregate(df, cfg.top_n)
    path = render(data, cfg)
    print(f"[{datetime.now():%H:%M:%S}] 리포트 생성 완료 -> {path}")
    return path


if __name__ == "__main__":
    if not CONFIG.data_path.exists():
        raise SystemExit(
            f"[오류] 데이터가 없습니다: {CONFIG.data_path}\n"
            "python_data/generate_data.py 를 먼저 실행하세요."
        )

    report_path = run_once()
    assert report_path.exists(), "리포트 파일이 생성되지 않았습니다"
    assert report_path.stat().st_size > 0, "리포트 파일이 비어 있습니다"
    print("[체크포인트 통과] 타임스탬프 HTML 리포트 생성 확인")
