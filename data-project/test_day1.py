"""
프로그램명 : Day1 종합실습 - 스키마 검증 pytest
작성자     : 박상명
작성일     : 2026-07-20
설명       : 네트워크 호출 없이(고정된 가짜 데이터로) WeatherRecord 스키마와
             parse_weather 파싱 함수가 올바르게 동작하는지 검증한다.
"""

import pytest
from pydantic import ValidationError

from 광주_3반_박상명_day1 import CountryInfo, WeatherRecord, parse_weather


def test_정상_날씨_레코드는_통과한다():
    """상식적인 범위의 기온·강수확률은 검증을 통과해야 한다."""
    record = WeatherRecord(time='2026-07-20T00:00', temperature=23.5, precip_prob=45)
    assert record.temperature == 23.5
    assert record.precip_prob == 45


def test_기온이_범위를_벗어나면_거부한다():
    """기온이 상식 범위(-50~60)를 벗어나면 ValidationError가 발생해야 한다."""
    with pytest.raises(ValidationError):
        WeatherRecord(time='2026-07-20T00:00', temperature=200, precip_prob=50)


def test_강수확률이_100_초과면_거부한다():
    """강수확률은 0~100 사이여야 한다."""
    with pytest.raises(ValidationError):
        WeatherRecord(time='2026-07-20T00:00', temperature=20, precip_prob=150)


def test_parse_weather는_hourly_배열을_행으로_변환한다():
    """가짜 Open-Meteo 응답 구조를 넣었을 때 행 개수와 값이 올바른지 확인."""
    fake_raw = {
        'hourly': {
            'time': ['2026-07-20T00:00', '2026-07-20T01:00'],
            'temperature_2m': [20.0, 21.0],
            'precipitation_probability': [10, 20],
        }
    }
    rows = parse_weather(fake_raw)
    assert len(rows) == 2
    assert rows[0] == {'time': '2026-07-20T00:00', 'temperature': 20.0, 'precip_prob': 10}


def test_국가정보_인구는_양수여야_한다():
    """population <= 0 이면 검증에 실패해야 한다."""
    with pytest.raises(ValidationError):
        CountryInfo(name='Korea', capital='Seoul', region='Asia',
                    population=-1, area=100_000)
