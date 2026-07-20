"""
프로그램명 : 실습 2 - Pydantic v2 중첩 스키마 검증
설명       : api_response.json(40건, 중첩 구조 + 오염 4건)을 Pydantic v2 모델로
             검증하여 유효/오염 데이터를 분리하고, 오염 건은 실패 사유와 함께 남긴다.

체크포인트 : 40건 -> 유효 36건 / 오염 4건
실행       : python ex02_pydantic_validation/solution.py  (skala_python 루트에서)
"""

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator

DATA_PATH = Path(__file__).resolve().parent.parent / "python_data" / "api_response.json"


class Profile(BaseModel):
    country: str
    tier: str
    score: float = Field(ge=0, le=100)  # 0~100 범위 초과 오염 차단


class User(BaseModel):
    id: int
    username: str
    email: str  # 필드 자체가 필수 -> 누락된 경우 여기서 걸림
    age: int = Field(ge=0)  # 음수 나이 차단
    is_active: bool
    signup_date: date
    profile: Profile
    tags: list[str] = []

    @field_validator("email")
    @classmethod
    def check_email_format(cls, v: str) -> str:
        # email-validator 의존성 없이 최소한의 형식 검증만 수행
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("올바른 이메일 형식이 아닙니다")
        return v


def load_records(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["results"]  # 최상위는 {status, count, results} dict


def inspect(records: list[dict]) -> None:
    print("전체 건수:", len(records))
    print(json.dumps(records[0], indent=2, ensure_ascii=False))
    print("-- 앞 10건 키/타입 훑어보기 --")
    for i, row in enumerate(records[:10]):
        print(i, {k: type(v).__name__ for k, v in row.items()})


def validate(records: list[dict]) -> tuple[list[User], list[dict]]:
    valid: list[User] = []
    invalid: list[dict] = []
    for i, row in enumerate(records):
        try:
            valid.append(User(**row))
        except ValidationError as e:
            invalid.append({"index": i, "data": row, "errors": e.errors()})
    return valid, invalid


def print_invalid_table(invalid: list[dict]) -> None:
    print(f"\n{'행':<4}{'필드':<20}{'사유'}")
    for item in invalid:
        for err in item["errors"]:
            field = ".".join(str(x) for x in err["loc"])
            print(f"{item['index']:<4}{field:<20}{err['msg']}")


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(
            f"[오류] 데이터가 없습니다: {DATA_PATH}\n"
            "python_data/generate_data.py 를 먼저 실행하세요."
        )

    records = load_records(DATA_PATH)
    inspect(records)

    valid, invalid = validate(records)
    print(f"\n전체 {len(records)}건 -> 유효 {len(valid)} / 오염 {len(invalid)}")
    print_invalid_table(invalid)

    assert len(valid) == 36, f"유효 36건이어야 하는데 {len(valid)}건"
    assert len(invalid) == 4, f"오염 4건이어야 하는데 {len(invalid)}건"
    print("\n[체크포인트 통과] 유효 36 / 오염 4")


if __name__ == "__main__":
    main()
