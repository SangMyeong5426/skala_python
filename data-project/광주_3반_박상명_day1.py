"""
프로그램명 : Day1 종합실습 - 데이터 수집 미니 파이프라인
작성자     : 박상명
작성일     : 2026-07-20
설명       : 공개 API 3개(Open-Meteo·Countries.dev·ip-api)를 asyncio + httpx로
             동시 수집하고, Pydantic v2 스키마로 검증한 뒤, 검증된 데이터를
             CSV·Parquet 두 형식으로 저장하며 읽기/쓰기 성능을 비교한다.

[실습 목표]
  1) 비동기 수집 : asyncio.gather()로 3개 API를 동시에 호출한다.
     - Open-Meteo : 서울 3일 시간대별 기온·강수확률 (72건)
     - Countries.dev : 한국 국가 정보 (1건)
     - ip-api : IP(8.8.8.8) 기반 지역 정보 (1건)
     - 한 API가 실패해도 나머지 수집은 계속되어야 한다(return_exceptions).
  2) 스키마 검증 : Pydantic v2 모델로 타입·범위를 검증한다.
     - WeatherRecord : temperature(-50~60), precip_prob(0~100)
     - CountryInfo   : population > 0, area > 0
     - IpInfo        : status == 'success' 등 실 데이터 구조에 맞춘 검증
  3) 저장 및 성능 비교 : 검증 통과 데이터를 CSV·Parquet으로 각각 저장하고
     쓰기/읽기 소요 시간을 timeit 방식(perf_counter)으로 측정해 비교한다.
  4) 테스트·커밋 : test_day1.py로 스키마 검증을 pytest로 확인하고,
     ruff로 코드 스타일을 점검한 뒤 Git에 커밋한다.

[코드 구조] 실습 2에서 정착한 함수 + main() 패턴을 그대로 따른다.
            각 단계(수집/검증/저장)를 독립 함수로 분리해 재사용·테스트가
            가능하도록 구성했다.

변경내역   : 2026-07-20 최초 작성
"""

import asyncio
import json
import logging
import time
from typing import Optional

import httpx
import pandas as pd
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s|%(levelname)s|%(message)s',
)
logger = logging.getLogger('day1')

WEATHER_URL = (
    'https://api.open-meteo.com/v1/forecast'
    '?latitude=37.5665&longitude=126.9780'
    '&hourly=temperature_2m,precipitation_probability'
    '&forecast_days=3&timezone=Asia/Seoul'
)
COUNTRY_URL = 'https://countries.dev/alpha/KOR'
IP_URL = 'http://ip-api.com/json/8.8.8.8'

WEATHER_CSV = 'weather.csv'
WEATHER_PARQUET = 'weather.parquet'


# ═════════════════════════════════════
# 1) 비동기 수집 : fetch_all()
# ─────────────────────────────────────
# [목표] httpx.AsyncClient 하나로 3개 URL을 asyncio.gather()로 동시 호출한다.
# [주의] return_exceptions=True로 한 API 실패가 나머지를 막지 않게 한다.
# ═════════════════════════════════════
async def fetch_one(client: httpx.AsyncClient, name: str, url: str) -> dict:
    """API 하나를 호출해 JSON을 반환한다. 실패 시 {'error': ...} 반환."""
    try:
        r = await client.get(url, timeout=10)
        r.raise_for_status()
        logger.info(f'수집 성공: {name} ({r.status_code})')
        return r.json()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.error(f'수집 실패: {name} - {e}')
        return {'error': str(e)}


async def fetch_all() -> dict:
    """3개 API를 동시에 수집해 이름별 dict로 반환한다."""
    targets = {'weather': WEATHER_URL, 'country': COUNTRY_URL, 'ip': IP_URL}
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[fetch_one(client, name, url) for name, url in targets.items()],
            return_exceptions=True,
        )
    return dict(zip(targets.keys(), results))


# ═════════════════════════════════════
# 2) Pydantic v2 스키마 정의
# ─────────────────────────────────────
# [목표] 각 API 응답을 검증할 스키마 3종을 선언한다.
# ═════════════════════════════════════
class WeatherRecord(BaseModel):
    """시간대별 기온·강수확률 1건의 검증 규칙"""
    time: str = Field(min_length=1)
    temperature: float = Field(ge=-50, le=60, description='기온(섭씨, 상식 범위)')
    precip_prob: float = Field(ge=0, le=100, description='강수확률(%)')


class CountryInfo(BaseModel):
    """국가 정보 검증 규칙"""
    name: str = Field(min_length=1)
    capital: str = Field(min_length=1)
    region: str = Field(min_length=1)
    population: int = Field(gt=0)
    area: float = Field(gt=0)


class IpInfo(BaseModel):
    """IP 기반 지역 정보 검증 규칙"""
    status: str
    country: str = Field(min_length=1)
    city: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    query: str = Field(min_length=1)


# ═════════════════════════════════════
# 파싱 : Open-Meteo의 컬럼형 배열을 행 단위 레코드로 변환
# ─────────────────────────────────────
# [목표] {"hourly": {"time": [...], "temperature_2m": [...], ...}} 구조를
#        [{"time":.., "temperature":.., "precip_prob":..}, ...] 로 뒤집는다.
# ═════════════════════════════════════
def parse_weather(raw: dict) -> list[dict]:
    """Open-Meteo 응답의 hourly 배열 3개를 zip으로 묶어 행 리스트로 변환."""
    hourly = raw['hourly']
    return [
        {'time': t, 'temperature': temp, 'precip_prob': prob}
        for t, temp, prob in zip(
            hourly['time'], hourly['temperature_2m'], hourly['precipitation_probability']
        )
    ]


# ═════════════════════════════════════
# 3) 검증 파이프라인 (valid / errors 분리)
# ─────────────────────────────────────
def validate_weather(rows: list[dict]) -> tuple[list, list]:
    """시간대별 날씨 레코드를 한 건씩 WeatherRecord로 검증한다."""
    valid, errors = [], []
    for i, row in enumerate(rows):
        try:
            valid.append(WeatherRecord(**row))
        except ValidationError as e:
            errors.append({'row': i, 'error': str(e)})
            logger.warning(f'날씨 {i}번째 검증 실패: {e.errors()[0]["msg"]}')
    return valid, errors


def validate_single(model_cls, raw: dict, label: str) -> Optional[BaseModel]:
    """국가정보·IP정보처럼 단건 응답을 검증한다. 실패 시 None 반환."""
    try:
        record = model_cls(**raw)
        logger.info(f'{label} 검증 성공')
        return record
    except ValidationError as e:
        logger.error(f'{label} 검증 실패: {e.errors()[0]["msg"]}')
        return None


# ═════════════════════════════════════
# 4) 저장 및 성능 비교 (CSV vs Parquet)
# ─────────────────────────────────────
# [목표] 검증된 날씨 데이터를 CSV·Parquet 두 형식으로 저장하고,
#        쓰기/읽기 시간을 측정해 비교표로 출력한다.
# ═════════════════════════════════════
def save_and_compare(valid_weather: list) -> None:
    """valid WeatherRecord 리스트를 CSV·Parquet으로 저장하고 성능을 비교한다."""
    df = pd.DataFrame([r.model_dump() for r in valid_weather])

    t0 = time.perf_counter()
    df.to_csv(WEATHER_CSV, index=False)
    csv_write = time.perf_counter() - t0

    t0 = time.perf_counter()
    df.to_parquet(WEATHER_PARQUET, index=False)
    parquet_write = time.perf_counter() - t0

    t0 = time.perf_counter()
    pd.read_csv(WEATHER_CSV)
    csv_read = time.perf_counter() - t0

    t0 = time.perf_counter()
    pd.read_parquet(WEATHER_PARQUET)
    parquet_read = time.perf_counter() - t0

    print(f'\n=== 3) 저장 및 성능 비교 ({len(df)}행) ===')
    print(f"{'형식':<10}{'쓰기(ms)':>12}{'읽기(ms)':>12}")
    print(f"{'CSV':<10}{csv_write * 1000:>12.2f}{csv_read * 1000:>12.2f}")
    print(f"{'Parquet':<10}{parquet_write * 1000:>12.2f}{parquet_read * 1000:>12.2f}")


# ═════════════════════════════════════
# main : 수집 → 검증 → 저장 순서로 실행
# ═════════════════════════════════════
async def run() -> dict:
    """전체 파이프라인을 실행하고 요약 결과를 반환한다."""
    raw = await fetch_all()

    print('\n=== 1) 비동기 수집 결과 ===')
    for name, data in raw.items():
        ok = isinstance(data, dict) and 'error' not in data
        print(f'  {name}: {"성공" if ok else "실패"}')

    weather_rows = parse_weather(raw['weather']) if 'error' not in raw['weather'] else []
    valid_w, errors_w = validate_weather(weather_rows)

    print('\n=== 2) 스키마 검증 결과 ===')
    print(f'날씨: 유효 {len(valid_w)}건 / 오류 {len(errors_w)}건 (전체 {len(weather_rows)}건)')

    country = validate_single(CountryInfo, raw['country'], '국가정보') \
        if 'error' not in raw['country'] else None
    ip = validate_single(IpInfo, raw['ip'], 'IP정보') \
        if 'error' not in raw['ip'] else None

    assert len(valid_w) > 0, '날씨 유효 데이터가 없습니다'
    assert len(valid_w) + len(errors_w) == len(weather_rows), '날씨 분류 누락/중복 발생'

    if valid_w:
        save_and_compare(valid_w)

    return {
        'weather_valid': len(valid_w),
        'weather_errors': len(errors_w),
        'country_ok': country is not None,
        'ip_ok': ip is not None,
    }


def main() -> None:
    summary = asyncio.run(run())
    print(f'\n=== 요약 ===\n{json.dumps(summary, ensure_ascii=False, indent=2)}')
    logger.info('Day1 종합실습 파이프라인 정상 종료')


if __name__ == '__main__':
    main()