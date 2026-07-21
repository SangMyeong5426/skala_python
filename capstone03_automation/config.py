"""종합실습 3의 불변 설정. frozen=True 로 실행 도중 몰래 바뀌는 버그를 원천 차단한다."""

from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    data_path: Path = _ROOT / "python_data" / "sales_raw.csv"
    output_dir: Path = Path(__file__).resolve().parent / "output"
    template_dir: Path = Path(__file__).resolve().parent / "templates"
    template_name: str = "report.html"
    title: str = "일일 매출 리포트"
    top_n: int = 5


CONFIG = Config()

if __name__ == "__main__":
    # 시도해보기: CONFIG.title = "바꿔보기" -> FrozenInstanceError 가 나야 정상 동작
    try:
        CONFIG.title = "바꿔보기"  # type: ignore[misc]
    except Exception as e:
        print(
            f"[의도된 동작] frozen dataclass 는 수정이 막힌다: {type(e).__name__}: {e}"
        )
