"""종합실습 1에서 쓰는 Pydantic 모델. 실습 2 패턴(선언적 검증 + 정규화)을 재사용한다."""

from pydantic import BaseModel, Field, field_validator


class Product(BaseModel):
    id: int
    name: str
    category: str
    price: float = Field(gt=0)  # 음수/0 가격 거부

    @field_validator("category")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("category 는 비어 있을 수 없습니다")
        return v
