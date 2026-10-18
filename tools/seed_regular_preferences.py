"""요청받은 예시 단골 3명과 주문 33건을 현재 DB에 한 번만 추가한다.

저장소 루트에서 backend/.venv/Scripts/python.exe tools/seed_regular_preferences.py 로 실행한다.
예시 주문도 DB 통계에 포함되며 실제 손님·기존 주문·문자 동의는 변경하지 않는다.
--remove-examples를 붙이면 예시 3명과 연결된 예시 주문만 제거하고 다시 추가하지 않는다.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.core.settings import Settings
from app.services.grades import KST
from app.stores.db import Database
from app.stores.regular_examples import remove_regular_examples, seed_regular_examples


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="단골 선호도 예시만 추가하거나 복원 후 재추가합니다.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--reset-examples", action="store_true", help="이번 기능이 만든 예시만 복원한 뒤 다시 추가")
    mode.add_argument("--remove-examples", action="store_true", help="예시 회원과 예시 주문만 제거하고 다시 추가하지 않음")
    args = parser.parse_args()
    try:
        config = Settings(_env_file=ROOT / "backend" / ".env")
        db = Database(config.database_url)
        try:
            result = (remove_regular_examples(db) if args.remove_examples else
                      seed_regular_examples(db, datetime.now(KST).date(), reset_examples=args.reset_examples))
        finally:
            db._conn.close()
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        # 연결 실패 시에도 주소·비밀번호가 포함될 수 있는 예외 원문은 출력하지 않는다.
        print(f"예시 생성 실패: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1)
