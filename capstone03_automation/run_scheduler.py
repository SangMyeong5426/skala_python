"""
종합실습 3 - 실행 조율 (run_scheduler.py)
루프 · schedule 라이브러리 · OS cron, 세 가지 실행 방식 모두 report.run_once() 하나만
호출한다. 어디서 돌려도 결과가 같아야 한다는 "일관성"이 이 파일의 유일한 책임이다.

실행 방식 셋 (택1):
    1) 1회 실행           : python run_scheduler.py
    2) 경량 루프(의존성 0) : python run_scheduler.py --mode loop --interval 60
                            (Ctrl+C 로 중지)
    3) schedule 라이브러리 : python run_scheduler.py --mode schedule --at 09:00
                            (매일 09:00 실행, Ctrl+C 로 중지)

    4) OS cron(운영 환경, 터미널을 닫아도 동작) 은 이 스크립트를 직접 실행하지 않고
       crontab 에 등록한다. 예시는 README 를 참고.
"""

import argparse
import time

from report import run_once


def run_loop(interval: int) -> None:
    """가장 단순한 방식. 외부 패키지 없이 while + sleep 만으로 주기 실행이 된다."""
    print(f"[루프 모드] {interval}초 간격으로 반복 실행합니다. Ctrl+C 로 중지하세요.")
    while True:
        run_once()
        time.sleep(interval)


def run_with_schedule(at: str) -> None:
    """schedule 라이브러리로 '매일 09:00' 같은 규칙을 코드에 선언적으로 표현한다."""
    import schedule

    schedule.every().day.at(at).do(run_once)
    print(
        f"[schedule 모드] 매일 {at} 에 실행되도록 등록했습니다. Ctrl+C 로 중지하세요."
    )
    while True:
        schedule.run_pending()
        time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="종합실습 3 리포트 실행 조율기")
    parser.add_argument(
        "--mode",
        choices=["once", "loop", "schedule"],
        default="once",
        help="once: 1회 실행(기본) / loop: 경량 반복 / schedule: schedule 라이브러리 사용",
    )
    parser.add_argument(
        "--interval", type=int, default=60, help="loop 모드의 반복 간격(초)"
    )
    parser.add_argument(
        "--at", type=str, default="09:00", help="schedule 모드의 실행 시각(HH:MM)"
    )
    args = parser.parse_args()

    if args.mode == "once":
        run_once()
    elif args.mode == "loop":
        run_loop(args.interval)
    else:
        run_with_schedule(args.at)


if __name__ == "__main__":
    main()
