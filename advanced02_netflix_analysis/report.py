"""
Day2 추가과제 - 넷플릭스 시청 기록 "연말결산" 스타일 리포트 생성
관심사의 분리: 설정(config.py) · 분석 로직(analysis.py) · 집계+렌더링(이 파일).
analysis.py의 함수들을 그대로 재사용해 print 대신 dict로 모으고, Jinja2로 HTML을 만든다.

실행 : python extra_netflix_analysis/report.py  (skala_python 루트에서)
"""

import base64
from datetime import datetime
from pathlib import Path

import plotly.express as px
from jinja2 import Environment, FileSystemLoader

import analysis
from config import CONFIG, Config


def aggregate() -> dict:
    """analysis.py의 각 STEP 함수를 호출해 리포트에 필요한 값들을 모은다.
    파일 렌더링은 render()에서만 일어나게 해 계산과 부수효과를 분리한다."""
    df = analysis.load_data()
    df = analysis.classify_titles(df)
    eda_result = analysis.eda(df)
    analysis.verify_with_polars(df, eda_result["top_shows"])
    binge_days = analysis.detect_binge(df)
    p_t, p_chi2 = analysis.statistical_tests(df)

    df_m = df.copy()
    df_m["weekday"] = df_m["Date"].dt.weekday
    weekday_counts = (
        df_m["weekday"].value_counts().sort_index().reindex(range(7), fill_value=0)
    )

    category_counts = df["category"].value_counts()

    heatmap_png = CONFIG.output_dir / "weekday_month_heatmap.png"
    analysis.visualize(df, eda_result["top_shows"])  # 히트맵 PNG + Plotly HTML 저장
    heatmap_b64 = base64.b64encode(heatmap_png.read_bytes()).decode("ascii")

    top_fig = px.bar(
        eda_result["top_shows"],
        x="시청횟수",
        y="show_key",
        color="category",
        orientation="h",
        title=f"Top {CONFIG.top_n} 콘텐츠 (시청 레코드 수 기준)",
    )
    top_fig.update_layout(yaxis={"categoryorder": "total ascending"})
    top_shows_html = top_fig.to_html(full_html=False, include_plotlyjs="cdn")

    return {
        "kpi": {
            "총 시청 레코드": len(df),
            "분석 기간(일)": (df["Date"].max() - df["Date"].min()).days,
            "몰아본 날(하루 3화+)": len(binge_days),
            "고유 콘텐츠 수": df.loc[
                df["category"] != "제목정보없음", "show_key"
            ].nunique(),
        },
        "top_shows": eda_result["top_shows"].to_dict("records"),
        "category_counts": category_counts.to_dict(),
        "binge_top5": binge_days.head(5)
        .assign(Date=lambda d: d["Date"].dt.strftime("%Y-%m-%d"))
        .to_dict("records"),
        "weekday_counts": list(zip(analysis.WEEKDAY_KR, weekday_counts.tolist())),
        "stats": {
            "t_test_p": p_t,
            "chi2_p": p_chi2,
        },
        "heatmap_b64": heatmap_b64,
        "top_shows_html": top_shows_html,
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
    data = aggregate()
    path = render(data, cfg)
    print(f"\n[{datetime.now():%H:%M:%S}] 리포트 생성 완료 -> {path}")
    return path


if __name__ == "__main__":
    if not CONFIG.data_path.exists():
        raise SystemExit(f"[오류] 데이터가 없습니다: {CONFIG.data_path}")

    report_path = run_once()
    assert report_path.exists(), "리포트 파일이 생성되지 않았습니다"
    assert report_path.stat().st_size > 0, "리포트 파일이 비어 있습니다"
    print("[체크포인트 통과] 타임스탬프 HTML 리포트 생성 확인")
