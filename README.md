# skala_python

SKALA 교육 과정에서 진행한 Python 데이터 처리·분석 실습과 PostgreSQL SQL 실습을 모은 저장소다.
ex·capstone 실습은 `python_data/`의 합성 데이터를 공통 입력으로 쓰고, SQL 실습은 폴더마다 스키마·데이터·쿼리 스크립트와 보고서를 함께 둔다.
각 실습의 설명, 실행 결과 화면, 자체 평가는 폴더별 README나 보고서에 있다.

## 구성

| 폴더 | 내용 | 문서 |
|---|---|---|
| `ex01_streaming_agg` | 실습 1. 제너레이터로 `web_logs.csv`(20만 행)를 한 번만 순회하며 상태코드·경로·시간대·IP별 집계 | [README](ex01_streaming_agg/README.md) |
| `ex02_pydantic_validation` | 실습 2. Pydantic v2 중첩 스키마로 `api_response.json`을 검증해 유효/오염 데이터 분리 | [README](ex02_pydantic_validation/README.md) |
| `ex03_async_collector` | 실습 3. asyncio + Semaphore 비동기 수집기(타임아웃, 지수 백오프 재시도, dead-letter 격리) | [README](ex03_async_collector/README.md) |
| `ex04_pandas_cleaning` | 실습 4. pandas로 `sales_raw.csv` 정제(타입 정규화, 결측·이상치 처리) 후 집계, Copy-on-Write 확인 | [README](ex04_pandas_cleaning/README.md) |
| `ex05_polars_duckdb` | 실습 5. 같은 질의를 pandas·Polars·DuckDB로 실행해 결과 일치를 검증한 뒤 실행 시간 비교 | [README](ex05_polars_duckdb/README.md) |
| `capstone01_async_etl` | 종합실습 1. 비동기 수집과 Pydantic 검증을 E-T-L 파이프라인으로 묶고 pytest로 검증 | [README](capstone01_async_etl/README.md) |
| `capstone02_eda_ml` | 종합실습 2. `telco_churn.csv` 이탈 예측: EDA → 시각화 → 통계 검정 → scikit-learn Pipeline | [README](capstone02_eda_ml/README.md) |
| `capstone03_automation` | 종합실습 3. 정제·집계 결과로 Jinja2 HTML 리포트 생성, 1회·루프·schedule 실행 모드 | [README](capstone03_automation/README.md) |
| `advanced01_text_rpg` | 표준 라이브러리만 쓰는 텍스트 RPG. 밸런스 값은 `data/*.json`으로 조절 | [README](advanced01_text_rpg/README.md) |
| `advanced02_netflix_analysis` | 추가과제. 본인 넷플릭스 시청 기록 분석(pandas·Polars 교차검증, 시각화, 통계 검정, 리포트) | [README](advanced02_netflix_analysis/README.md) |
| `db01_academic_management` | 학사관리시스템 DB 설계(5개 테이블, ERD)와 DDL·DML·조회 쿼리 | [보고서](db01_academic_management/report/academic_report.md) |
| `db02_campushub_join_lab` | JOIN, 서브쿼리, 윈도우 함수, `WITH RECURSIVE` 등 25개 문항 | [보고서](db02_campushub_join_lab/report/campushub_report.md) |
| `db03_ecommerce_lab` | E-Commerce 스키마에서 분석 쿼리 10개의 튜닝 전후 `EXPLAIN ANALYZE` 비교, Materialized View, 옵티마이저 조사 | [보고서](db03_ecommerce_lab/report/report.md), [2~4장](db03_ecommerce_lab/report/optimizer_report.md) |
| `data-project` | 수업 실습 1~4와 Day1 종합실습 스크립트, 입력 데이터와 산출물 | 아래 표 참고 |
| `python_data` | ex·capstone 실습용 합성 데이터와 생성 스크립트 `generate_data.py` | - |

`data-project/` 파일 구성은 다음과 같다. 스크립트 상단 docstring에 실습 목표가 정리되어 있다.

| 파일 | 내용 |
|---|---|
| `광주_3반_박상명_Practice_1.py` | 실습 1. JSON 판매 데이터를 컴프리헨션, `Counter`, `defaultdict`, 제너레이터로 집계 |
| `광주_3반_박상명_Practice_2.py` | 실습 2. 예외 처리와 Pydantic 검증으로 정상/오류 데이터 분리, `valid_records.csv`·`errors.json` 저장 |
| `광주_3반_박상명_Practice_3.py` | 실습 3. `sales_100k.csv` EDA와 IQR 이상치 제거, pandas·Polars·DuckDB 집계 시간 비교 |
| `광주_3반_박상명.py` | 실습 4. 실습 3 결과를 이어받아 EDA 시각화 4종, t-검정·카이제곱, Ridge Pipeline 저장, Plotly 차트 |
| `광주_3반_박상명_Comprehensive_Practice_1.py` | Day1 종합실습. 공개 API 3개를 asyncio + httpx로 수집, Pydantic 검증, CSV·Parquet 저장 및 속도 비교 |
| `Python_Practice1_Data.json`, `Python_Practice2_Data.json` | 실습 1·2 입력 데이터 |
| `valid_records.csv`, `errors.json`, `weather.csv`, `weather.parquet`, `eda_4panel.png`, `regional_category_sales.html`, `sales_ridge_pipeline.joblib` | 스크립트 실행 산출물 |
| `requirements.txt` | 버전을 고정한 패키지 목록(`pip freeze` 형식) |

## 실행 환경

저장소 루트에 가상환경 `.venv`를 만들고 그 안의 Python으로 실행하는 것을 전제로 한다(하위 README의 실행 명령이 모두 `.venv/bin/python` 기준이다).
의존성 목록은 `data-project/requirements.txt` 하나뿐이다. 여기에 없는 `jinja2`(capstone03, advanced02), `schedule`(capstone03 schedule 모드), `markdown`(db03 보고서 빌드)은 따로 설치해야 한다.

```bash
cd skala_python
python3 -m venv .venv
.venv/bin/pip install -r data-project/requirements.txt
.venv/bin/pip install jinja2 schedule markdown
```

capstone02와 advanced02는 그래프 한글 폰트를 `AppleGothic`으로 고정해 두어 macOS가 아닌 환경에서는 한글이 깨질 수 있다.

## 실행 방법

Python 실습은 저장소 루트에서 실행한다. 폴더별 세부 옵션과 기대 결과는 각 README에 있다.

```bash
.venv/bin/python ex01_streaming_agg/solution.py          # ex02~ex05도 같은 형식
.venv/bin/python capstone01_async_etl/pipeline.py
(cd capstone01_async_etl && ../.venv/bin/python -m pytest -v)
.venv/bin/python capstone02_eda_ml/analysis.py
.venv/bin/python capstone03_automation/run_scheduler.py --mode once   # loop, schedule 모드도 있음
(cd advanced01_text_rpg && python3 text_rpg.py)
```

`python_data/`의 CSV·JSON은 저장소에 들어 있다. 다시 만들려면 `.venv/bin/python python_data/generate_data.py`를 실행한다. seed가 42로 고정되어 있고, 결과 파일은 스크립트와 같은 폴더에 덮어쓴다.

`data-project/` 스크립트는 입력·출력 파일을 상대 경로로 다루므로 폴더 안에서 실행한다.

```bash
cd data-project
../.venv/bin/python 광주_3반_박상명_Practice_2.py
```

- `Practice_3`와 `광주_3반_박상명.py`는 저장소에 없는 `sales_100k.csv`가 필요하다(아래 참고).
- `Comprehensive_Practice_1`은 Open-Meteo, Countries.dev, ip-api를 호출하므로 인터넷 연결이 필요하다.

SQL 실습은 PostgreSQL 기준이며, 파일 번호 순서대로 실행한다. 실행 위치와 주의사항은 각 SQL 파일 상단 주석에 있다.

- `db01`: `academic_ddl.sql` 상단 주석대로 DB와 `app` 스키마를 만든 뒤 `academic_ddl.sql` → `academic_dml.sql` → `academic_query.sql`
- `db02`: `01_role_db_setup.sql`(postgres DB에서 관리자 계정으로, 비밀번호 자리를 직접 바꿔서) → `02_schema_tables_data.sql`(`skala_db`에서) → `03_queries.sql`
- `db03`: `01_schema.sql` → `02_seed.sql` → `03_queries.sql`. `citext`, `btree_gist` 확장을 사용한다.
- `db03_ecommerce_lab/report/build_report.py`는 `report.md`와 `optimizer_report.md`를 합쳐 HTML 보고서를 만든다. 스크립트 안의 경로가 로컬 절대 경로로 고정되어 있어 다른 환경에서는 `BASE` 값을 바꿔야 한다. 보고서 HTML과 PDF 파일(`종합실습4_보고서.*`)은 저장소에 포함되어 있다.

## 저장소에서 제외한 파일

`.gitignore` 기준으로 다음은 커밋하지 않는다.

- 가상환경과 캐시: `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.DS_Store`
- 실행 산출물: `output/`(capstone, advanced02 결과), `dead_letter.json`(ex03), `advanced01_text_rpg/savegame.json`
- `data-project/sales_100k.csv`: GitHub 권장 용량(50MB)을 넘는 대용량 실습 데이터. 실행 전에 따로 준비해 `data-project/`에 두어야 한다.
- `NetflixViewingHistory.csv`: 개인 시청 기록. 넷플릭스 계정의 프로필 > 시청 활동 > 다운로드에서 받아 `advanced02_netflix_analysis/data/`에 저장한다([advanced02 README](advanced02_netflix_analysis/README.md) 참고).

루트의 `.claude/`, `.vscode/`는 편집기·도구 설정 파일이다.
