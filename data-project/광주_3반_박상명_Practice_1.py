"""
프로그램명 : 실습 1 - 자료구조 집계·컴프리헨션·제너레이터
작성자     : 박상명
작성일     : 2026-07-20
설명       : 판매(sales) JSON 데이터 100건을 로드하여 Python 핵심 자료구조와
             문법(컴프리헨션, Counter, defaultdict, 제너레이터)으로 집계를 수행한다.

[실습 목표]
  1) 리스트/딕셔너리 컴프리헨션
     - amount >= 1000 인 거래만 필터링하고, 지역별 총매출 dict를
       컴프리헨션 문법으로 계산한다.
  2) Counter + defaultdict
     - Counter로 지역별 거래 건수를 세고,
       defaultdict로 카테고리별 amount 리스트를 그룹핑한다.
  3) 제너레이터 - 메모리 비교
     - amount > 1000 인 행만 yield하는 제너레이터를 작성하고,
       리스트 방식과 메모리 크기(sys.getsizeof)를 비교한다.
  4) 종합 - 월별 카테고리 매출 집계
     - (month, category) 기준으로 총매출을 집계하고 상위 3개를
       내림차순으로 출력한다.

[입력 데이터] Python_Practice1_Data.json
             - region/category/amount/month 키를 가진 dict 100건의 리스트
             - 1번 파일은 JSON 형식 오류가 있어 교수님 안내에 따라 2번 사용

변경내역   : 2026-07-20 최초 작성
"""

import json
import sys
from collections import Counter, defaultdict

def load_sales(path):
    """JSON 파일을 읽어 리스트로 반환한다. 실패하면 None을 반환한다."""
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f'[오류] 파일이 없습니다: {path}')
        return None
    except json.JSONDecodeError as e:
        print(f'[오류] JSON 형식이 잘못되었습니다: {e}')
        return None
    finally:
        print('데이터 로딩 시도 종료')


# 데이터 로드 (교수님 안내에 따라 2번 파일 사용)
sales = load_sales('Python_Practice1_Data.json')
if sales is None:
    sys.exit(1)    # 데이터가 없으면 이후 코드가 의미 없으므로 종료

print(f'로딩 완료: {len(sales)}건')

# ═════════════════════════════════════
# 1) 리스트/딕셔너리 컴프리헨션
# ─────────────────────────────────────
# [목표] for 루프 대신 컴프리헨션 문법으로 필터링과 집계를 한 줄에 표현한다.
#   ① amount >= 1000 인 거래만 필터링   → 리스트 컴프리헨션
#   ② 지역별 총매출 dict 계산           → 집합 + 딕셔너리 컴프리헨션
# [검증] 지역별 총매출이 모두 양수인지 assert로 확인
# ═════════════════════════════════════

# ① amount가 1000 이상인 거래만 필터링 (리스트 컴프리헨션)
#    [담을것 for 반복변수 in 원본 if 조건] 구조
high_rows = [row for row in sales if row['amount'] >= 1000]
print(f'\n=== 1) amount 1000 이상 거래: {len(high_rows)}건 ===')

# ② 지역별 총매출 (딕셔너리 컴프리헨션)
regions = {row['region'] for row in sales}   # 집합 컴프리헨션: 지역명을 중복 없이 추출
# 각 지역 r에 대해 "r: (r 지역 거래들의 amount 합계)" 쌍을 만든다
region_total = {r: sum(row['amount'] for row in sales if row['region'] == r) for r in regions}
print('지역별 총매출:', region_total)
assert all(v > 0 for v in region_total.values())   # 검증: 총매출은 모두 양수

# ═════════════════════════════════════
# 2) Counter + defaultdict
# ─────────────────────────────────────
# [목표] collections 모듈의 집계 전용 자료구조를 활용한다.
#   ① 지역별 거래 건수 세기            → Counter (직접 루프 카운팅 대체)
#   ② 카테고리별 amount 리스트 그룹핑   → defaultdict(list)
#      (키 존재 여부를 if로 확인하는 패턴을 defaultdict로 대체)
# [검증] most_common(3)으로 건수 상위 3개 지역을 내림차순 출력
# ═════════════════════════════════════

# ① 지역별 거래 건수 (Counter)
region_count = Counter(row['region'] for row in sales)
print('\n=== 2) 지역별 거래 건수 상위 3 ===')
print(region_count.most_common(3))

# ② 카테고리별 amount 리스트 (defaultdict)
category_amounts = defaultdict(list)
for row in sales:
    category_amounts[row['category']].append(row['amount'])
print('카테고리별 건수:', {k: len(v) for k, v in category_amounts.items()})


# ═════════════════════════════════════
# 3) 제너레이터 — 메모리 비교
# ─────────────────────────────────────
# [목표] 같은 필터링을 리스트와 제너레이터 두 방식으로 만들고,
#        제너레이터가 데이터를 미리 만들지 않아 메모리를 거의 쓰지 않음을
#        sys.getsizeof 수치로 직접 확인한다.
# [주의] 제너레이터를 list()로 변환하면 비교 의미가 사라지므로
#        제너레이터 객체 자체의 크기를 측정한다.
# [검증] getsizeof(제너레이터) < getsizeof(리스트) assert 확인
# ═════════════════════════════════════

def high_sales(rows):
    """amount가 1000을 초과하는 행만 하나씩 yield하는 제너레이터.
    yield는 값을 하나 내보내고 멈췄다가, 다음 요청 시 이어서 실행된다."""
    for row in rows:
        if row['amount'] > 1000:
            yield row


gen = high_sales(sales)                                   # 제너레이터 객체
lst = [row for row in sales if row['amount'] > 1000]      # 같은 내용의 리스트

print('\n=== 3) 메모리 비교 ===')
print(f'리스트 크기    : {sys.getsizeof(lst)} bytes')
print(f'제너레이터 크기: {sys.getsizeof(gen)} bytes')
assert sys.getsizeof(gen) < sys.getsizeof(lst)   # 체크포인트: 제너레이터가 더 작아야 함

# ═════════════════════════════════════
# 4) 종합 — 월별 카테고리 매출 집계
# ─────────────────────────────────────
# [목표] 앞에서 배운 기법을 조합해 (month, category) 2개 기준으로
#        총매출을 집계하고, 매출 상위 3개를 내림차순으로 출력한다.
#        - defaultdict(float): 없는 키는 0부터 시작하므로 바로 += 누적 가능
#        - 튜플 (month, category)를 dict의 키로 사용
#        - sorted(key=..., reverse=True)로 금액 기준 내림차순 정렬
# [검증] top3가 내림차순인지 assert 확인
# ═════════════════════════════════════

month_cat = defaultdict(float)
for row in sales:
    month_cat[(row['month'], row['category'])] += row['amount']   # (월, 카테고리) 키로 누적

# 총매출 상위 3개를 내림차순으로
top3 = sorted(month_cat.items(), key=lambda x: x[1], reverse=True)[:3]

print('\n=== 4) 월·카테고리별 매출 top3 ===')
for (month, cat), total in top3:
    print(f'{month} / {cat}: {total:,.0f}')
assert top3[0][1] >= top3[1][1] >= top3[2][1]   # 체크포인트: 내림차순 확인
