"""추가과제 불변 설정. frozen=True 로 실행 도중 몰래 바뀌는 버그를 원천 차단한다."""

from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Config:
    data_path: Path = _ROOT / "data" / "NetflixViewingHistory.csv"
    output_dir: Path = _ROOT / "output"
    template_dir: Path = _ROOT / "templates"
    template_name: str = "report.html"
    title: str = "넷플릭스 시청 기록 연말결산"
    top_n: int = 10
    binge_gap_hours: int = (
        6  # 같은 날 안에서만 시청 기록이 남으므로, 같은 날 연속 시청을 binge로 간주
    )


CONFIG = Config()
