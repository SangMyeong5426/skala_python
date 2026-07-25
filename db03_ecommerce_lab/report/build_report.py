import re
import markdown
from pathlib import Path

BASE = Path("/Users/psm/workspace/skala_python/db03_ecommerce_lab/report")
SCREENSHOT_DIR = BASE / "screenshot"

report_md = (BASE / "report.md").read_text(encoding="utf-8")
opt_md = (BASE / "optimizer_report.md").read_text(encoding="utf-8")

# --- split report.md into: Q-sections body, and the final summary section ---
marker = "## 전체 튜닝 패턴 요약"
idx = report_md.index(marker)
q_body = report_md[:idx].strip()
summary_body = report_md[idx:].strip()

# drop the very first H1 + intro lines of report.md (title/description), keep from first "---" onward
# report.md starts with "# 종합실습4...\n\n- 스키마...\n- 각 문항은...\n\n---\n\n## Q1)..."
q_body = q_body.split("---", 1)[1].strip()  # everything after first ---

# --- optimizer_report.md: drop its own H1 title + intro paragraph, keep from first "---" onward ---
opt_body = opt_md.strip()
opt_body = opt_body.split("---", 1)[1].strip()

# --- assemble full markdown ---
full_md = f"""# 1. 10개 문항별 튜닝 전·후 쿼리와 결과 화면

{q_body}

---

{opt_body}

---

# 부록: 전체 튜닝 패턴 요약

{summary_body.split(marker,1)[1].strip()}
"""

# --- markdown -> HTML ---
html_body = markdown.markdown(
    full_md,
    extensions=["tables", "fenced_code", "sane_lists", "toc"],
)

# --- fix image paths: screenshot/xxx.png -> file:///abs/path ---
def fix_img(m):
    alt, src = m.group(1), m.group(2)
    if src.startswith("screenshot/"):
        abs_path = (SCREENSHOT_DIR / src.split("screenshot/", 1)[1]).resolve()
        return f'<img alt="{alt}" src="file://{abs_path}">'
    return m.group(0)

html_body = re.sub(r'<img alt="([^"]*)" src="([^"]+)"\s*/?>', fix_img, html_body)

# --- full HTML document ---
CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body {
  font-family: -apple-system, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
  font-size: 10.5pt;
  line-height: 1.55;
  color: #1c1c1e;
}
.cover {
  height: 253mm;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  page-break-after: always;
}
.cover .kicker { color: #2563eb; font-weight: 700; letter-spacing: 0.08em; font-size: 11pt; margin-bottom: 12px; }
.cover h1 { font-size: 30pt; margin: 0 0 10px 0; line-height: 1.25; }
.cover p.desc { font-size: 12pt; color: #444; max-width: 80%; }
.cover .meta { margin-top: 40px; display: flex; gap: 48px; }
.cover .meta div { font-size: 10.5pt; }
.cover .meta .label { color: #888; font-size: 9pt; margin-bottom: 3px; }
.toc { page-break-after: always; }
.toc h1 { font-size: 22pt; }
.toc ol { font-size: 12pt; line-height: 2.2; }
h1 {
  font-size: 18pt;
  border-bottom: 3px solid #2563eb;
  padding-bottom: 6px;
  margin-top: 36px;
  page-break-before: always;
}
h1:first-of-type { page-break-before: avoid; }
h2 { font-size: 14pt; color: #1d4ed8; margin-top: 26px; border-left: 4px solid #93c5fd; padding-left: 8px; }
h3 { font-size: 11.5pt; color: #333; margin-top: 18px; }
p { margin: 8px 0; }
strong { color: #111; }
code {
  background: #f1f3f5;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 9.2pt;
}
pre {
  background: #1e1e2e;
  color: #e6e6e6;
  padding: 12px 14px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 8.8pt;
  line-height: 1.5;
  page-break-inside: avoid;
}
pre code { background: none; color: inherit; padding: 0; }
table {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
  font-size: 9pt;
  page-break-inside: avoid;
}
th, td {
  border: 1px solid #d0d7de;
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}
th { background: #eef2ff; }
img {
  max-width: 100%;
  border: 1px solid #ddd;
  border-radius: 4px;
  margin: 6px 0;
  display: block;
  page-break-inside: avoid;
}
hr { border: none; border-top: 1px solid #e5e7eb; margin: 28px 0; }
em { color: #555; }
li { margin: 3px 0; }
"""

COVER = """
<div class="cover">
  <div class="kicker">E-COMMERCE · ANALYTICS · QUERY TUNING</div>
  <h1>종합 실습 4<br>ecommerce 매출 분석 및 정리</h1>
  <p class="desc">전자상거래 주문·상품·고객·재고·리뷰 데이터를 대상으로 매출, RFM, 재구매율, 재고 위험, 쿠폰 효과를 분석하고
  실행 계획과 인덱스를 이용해 성능을 비교했다.</p>
  <div class="meta">
    <div><div class="label">소속</div>광주 3반</div>
    <div><div class="label">이름</div>박상명</div>
    <div><div class="label">DBMS</div>PostgreSQL</div>
  </div>
</div>
"""

TOC = """
<div class="toc">
  <h1>목차</h1>
  <ol>
    <li>10개의 문항별 튜닝 전 쿼리와 결과 화면, 튜닝 후 쿼리와 결과 화면 정리</li>
    <li>3가지 조인에 대한 차이점 정리 (Hash Join / Nested Loop / Bitmap Heap Scan)</li>
    <li>Materialized View 생성 스크립트와 실행 후 결과 화면</li>
    <li>DBMS 엔진별 옵티마이저 조사</li>
  </ol>
</div>
"""

full_html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>종합실습4 보고서</title>
<style>{CSS}</style>
</head>
<body>
{COVER}
{TOC}
{html_body}
</body>
</html>
"""

out_html = BASE / "종합실습4_보고서.html"
out_html.write_text(full_html, encoding="utf-8")
print("wrote", out_html)
