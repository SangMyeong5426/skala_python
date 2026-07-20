"""
프로그램명 : 실습 2 - 파일 I/O, 예외 처리, Pydantic 검증 파이프라인
작성자     : 박상명
작성일     : 2026-07-20
설명       : JSON 판매 데이터를 안전하게 로드한 뒤 Pydantic v2 스키마로
             한 건씩 검증하여 정상(valid)/오류(errors) 데이터를 분리하고,
             결과를 CSV/JSON 파일로 저장한 후 재로딩하여 건수를 확인한다.

[실습 목표]
  1) 예외 처리 + 파일 읽기 : safe_load_csv()
     - 파일 없음/형식 오류 시 None 반환 + logger.error
     - 성공 시 dict 리스트 반환 + logger.info
     - finally에서 '로딩 종료' 출력 (성공/실패 무관하게 항상 실행)
  2) Pydantic v2 스키마 정의 : SalesRecord
     - month·region: 빈 값 금지 / amount: 0 초과 / category: 없어도 됨
     - 정상 데이터(검증 성공)와 불량 데이터(검증 실패) 샘플 시연
  3) 검증 파이프라인 (valid / errors 분리)
     - raw_data를 순회하며 SalesRecord 변환 시도
     - 성공 → valid 리스트 / 실패 → errors 리스트({row, error})
  4) 결과 파일 저장 + 재로딩 확인
     - valid → CSV(model_dump 사용) / errors → JSON(ensure_ascii=False)
     - 두 파일 모두 다시 읽어 건수를 assert로 검증

[체크포인트 대응]
  - safe_load_csv 동작 + assert None 통과        → main() 앞부분
  - ValidationError 발생 시 오류 내용 출력       → demo_schema() + validate_records()
  - valid 4건 / errors 3건 assert 통과           → main()의 검증 결과 확인
  - 재로딩 후 len(reloaded) == 4 통과            → reload_and_check()

[입력 데이터] Python_Practice2_Data.json : 총 104건 (정상 100건 + 오류 4건)
             이 중 체크포인트 기준(valid 4 / errors 3)에 맞춰
             정상 4건(파일 앞부분) + 오류 3건(파일 뒷부분)만 골라 검증한다.
               ① region 빈 문자열        → string_too_short (빈 값 위반)
               ② amount 음수             → greater_than (범위 위반)
               ③ amount가 숫자 아닌 문자 → float_parsing (타입 오류)

[코드 구조] 작업 단위를 함수로 분리하고 main()이 순서대로 호출한다.
            if __name__ == '__main__' 패턴으로, 이 파일을 import해도
            파이프라인이 자동 실행되지 않아 함수 재사용·테스트가 가능하다.

변경내역   : 2026-07-20 최초 작성
             2026-07-20 오류 데이터 4유형 확장, 성공/실패 샘플 시연 추가
             2026-07-20 함수 + main() 구조로 재편, 검증 대상을
                        체크포인트 기준(valid 4 / errors 3)으로 구성
"""

import csv
import json
import logging
import sys
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

# ─────────────────────────────────────
# 전역 설정: 파일 경로 상수와 logging
# ─────────────────────────────────────
SOURCE_JSON = 'Python_Practice2_Data.json'
VALID_CSV = 'valid_records.csv'
ERRORS_JSON = 'errors.json'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s|%(levelname)s|%(message)s',
)
logger = logging.getLogger('practice2')


# ═════════════════════════════════════
# 1) 예외 처리 + 파일 읽기 : safe_load_csv()
# ─────────────────────────────────────
# [목표] 파일이 없거나 형식이 깨져도 프로그램이 죽지 않는 로딩 함수
#   - 실패: logger.error 기록 후 None 반환
#   - 성공: logger.info 기록 후 dict 리스트 반환
#   - finally: 성공/실패와 무관하게 '로딩 종료' 출력
# ═════════════════════════════════════
def safe_load_csv(path: str) -> Optional[list]:
    """JSON 데이터 파일을 안전하게 읽어 dict 리스트로 반환한다.
    파일이 없거나 JSON 형식이 잘못된 경우 None을 반환한다."""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f'로딩 성공: {path} ({len(data)}건)')
        return data
    except FileNotFoundError:
        logger.error(f'파일 없음: {path}')
        return None
    except json.JSONDecodeError as e:
        logger.error(f'JSON 형식 오류: {path} - {e}')
        return None
    finally:
        print('로딩 종료')


# ═════════════════════════════════════
# 2) Pydantic v2 스키마 정의 : SalesRecord
# ─────────────────────────────────────
# [목표] 타입 힌트 기반으로 데이터 규칙(스키마)을 선언한다.
#   - month, region : 문자열, 최소 1글자(빈 문자열 금지)
#   - amount        : 숫자, 0 초과(gt=0)
#   - category      : 문자열 또는 None (없어도 됨)
# ═════════════════════════════════════
class SalesRecord(BaseModel):
    """판매 데이터 1건의 스키마(검증 규칙) 정의"""
    month: str = Field(min_length=1, description='판매 월(빈 값 금지)')
    region: str = Field(min_length=1, description='지역명(빈 값 금지)')
    amount: float = Field(gt=0, description='판매 금액(0 초과)')
    category: Optional[str] = None  # 없어도 되는 필드


def demo_schema(file_data: list) -> None:
    """스키마가 정상 데이터는 통과시키고(성공 샘플),
    불량 데이터는 잡아내는지(실패 샘플) 시연한다."""
    print('\n=== 2) SalesRecord 스키마 정의 및 동작 확인 ===')
    print('스키마 필드:', list(SalesRecord.model_fields.keys()))

    # ① 검증 성공 샘플: 정상 1건 (amount 1500 → 1500.0 자동 타입 변환 확인)
    sample = SalesRecord(**file_data[0])
    print('검증 성공 예시:', sample.model_dump())

    # ② 검증 실패 샘플: 규칙 위반 데이터로 ValidationError 확인
    #    (month 빈 문자열 + amount 음수 → 한 건에서 오류 2개 동시 발생)
    bad_sample = {'month': '', 'region': '서울', 'amount': -1}
    print('검증 실패 예시 입력값:', bad_sample)
    try:
        SalesRecord(**bad_sample)
    except ValidationError as e:
        print(f'→ 검증 실패 (오류 {e.error_count()}건):')
        for err in e.errors():  # 실패한 필드(loc)와 사유(msg)를 하나씩 출력
            print(f'  - {err["loc"][0]}: {err["msg"]}')


# ═════════════════════════════════════
# 3) 검증 파이프라인 (valid / errors 분리)
# ─────────────────────────────────────
def build_raw_data(file_data: list) -> list:
    """체크포인트 기준(valid 4 / errors 3)에 맞춰 검증 대상을 구성한다.
    파일 앞부분의 정상 4건 + 뒷부분의 오류 3건(빈 값/음수/문자)을 선택."""
    return file_data[:4] + file_data[100:103]


def validate_records(raw_data: list) -> tuple:
    """raw_data를 한 건씩 SalesRecord로 검증하여
    성공은 valid 리스트, 실패는 errors 리스트({row, error})로 분리한다.
    예외는 Exception이 아닌 ValidationError로 정밀하게 잡는다."""
    valid, errors = [], []
    for i, row in enumerate(raw_data):  # enumerate: 번호와 데이터를 함께 꺼냄
        try:
            valid.append(SalesRecord(**row))  # **row: dict를 키워드 인자로 전달
        except ValidationError as e:
            errors.append({'row': i, 'error': str(e)})
            first = e.errors()[0]  # 첫 오류의 필드명(loc)과 사유(msg)를 로그로
            logger.warning(f'{i}번째 행 검증 실패: {first["loc"][0]} - {first["msg"]}')
    return valid, errors


# ═════════════════════════════════════
# 4) 결과 파일 저장 + 재로딩 확인
# ─────────────────────────────────────
def save_results(valid: list, errors: list) -> bool:
    """valid는 CSV로, errors는 JSON으로 저장한다. 실패 시 False 반환."""
    try:
        # valid 저장: Pydantic 객체 → dict 변환은 반드시 model_dump() 사용
        with open(VALID_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(SalesRecord.model_fields))
            writer.writeheader()  # 첫 줄에 컬럼명 기록
            for record in valid:
                writer.writerow(record.model_dump())

        # errors 저장: ensure_ascii=False가 없으면 한글이 \uXXXX로 깨짐
        with open(ERRORS_JSON, 'w', encoding='utf-8') as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)

        logger.info(f'저장 완료: {VALID_CSV}({len(valid)}건), {ERRORS_JSON}({len(errors)}건)')
        return True
    except OSError as e:
        logger.error(f'파일 저장 실패: {e}')
        return False


def reload_and_check() -> None:
    """저장한 두 결과 파일을 다시 읽어 건수가 맞는지 assert로 검증한다."""
    print('\n=== 4) 저장 및 재로딩 확인 ===')

    # ① CSV 재로딩: 헤더를 키로 하는 dict 리스트로 읽음
    try:
        with open(VALID_CSV, encoding='utf-8') as f:
            reloaded = list(csv.DictReader(f))
    except OSError as e:
        logger.error(f'재로딩 실패: {VALID_CSV} - {e}')
        sys.exit(1)

    print(f'CSV 재로딩: {len(reloaded)}건 / 첫 레코드: {reloaded[0]}')
    assert len(reloaded) == 4, f'재로딩 건수는 4건이어야 함 (현재 {len(reloaded)}건)'

    # ② errors.json 재로딩 (safe_load_csv 재사용)
    reloaded_errors = safe_load_csv(ERRORS_JSON)
    assert reloaded_errors is not None and len(reloaded_errors) == 3, \
        'errors.json 재로딩 건수는 3건이어야 함'
    print(f'errors.json 재로딩: {len(reloaded_errors)}건')


# ═════════════════════════════════════
# main: 전체 파이프라인을 순서대로 실행
# ═════════════════════════════════════
def main() -> None:
    """읽기 → 스키마 시연 → 검증 → 저장 → 재로딩 순으로 실행한다."""
    # 1) 파일 로딩 + 없는 파일 처리 확인
    file_data = safe_load_csv(SOURCE_JSON)
    if file_data is None:
        sys.exit(1)  # 데이터가 없으면 이후 진행이 의미 없으므로 종료

    missing_result = safe_load_csv('no_such_file.json')  # 반환값을 받아 확인
    assert missing_result is None  # 체크포인트: 없는 파일은 None 반환

    print(f'\n=== 1) 파일 로딩: {len(file_data)}건 로딩 성공 ===')
    print(f'없는 파일(no_such_file.json) 로딩 반환값: {missing_result}')

    # 2) 스키마 정의 동작 시연 (성공/실패 샘플)
    demo_schema(file_data)

    # 3) 검증 파이프라인: 정상 4건 + 오류 3건 구성 후 검증
    raw_data = build_raw_data(file_data)
    print(f'\n=== 3) 검증 파이프라인 실행: 대상 {len(raw_data)}건 ===')
    valid, errors = validate_records(raw_data)
    print(f'검증 결과: 유효 {len(valid)}건 / 오류 {len(errors)}건')

    # 체크포인트: valid 4건 / errors 3건
    assert len(valid) == 4, f'valid는 4건이어야 함 (현재 {len(valid)}건)'
    assert len(errors) == 3, f'errors는 3건이어야 함 (현재 {len(errors)}건)'
    # 무결성 검증: 모든 데이터는 valid 또는 errors 중 한 곳에만 속해야 한다
    assert len(valid) + len(errors) == len(raw_data), '분류 누락/중복 발생'

    # 4) 저장 + 재로딩 확인
    if not save_results(valid, errors):
        sys.exit(1)
    reload_and_check()

    logger.info('실습 2 파이프라인 정상 종료')


if __name__ == '__main__':  # 직접 실행할 때만 main()이 동작 (import 시에는 실행 안 됨)
    main()
