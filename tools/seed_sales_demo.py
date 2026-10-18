"""하루 상승·주간 하락을 함께 보여주는 시연 주문 미리보기. --apply일 때만 저장한다.

실행: backend/.venv/Scripts/python.exe tools/seed_sales_demo.py [--apply]
기존 시연 주문만 교체하고 여러 메뉴에 분산하며, 일반 주문과 메뉴 가중치는 유지한다.
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
from app.stores.sales_demo import consolidate_sales_demo_orders, rebalance_sales_demo_tables, seed_sales_demo


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="메뉴를 분산해 하루 상승·주간 하락을 함께 보여주는 시연 주문 준비")
    parser.add_argument("--apply", action="store_true", help="미리보기 대신 DB에 시연 주문 저장")
    parser.add_argument("--rebalance-tables", action="store_true", help="매출을 유지하고 마지막 영업일의 시연 주문만 15개 테이블에 재분배")
    parser.add_argument("--consolidate-orders", action="store_true", help="매출·메뉴 수량을 유지하고 마지막 주문일의 시연 주문을 테이블별 한 건으로 묶기")
    args = parser.parse_args()
    if args.rebalance_tables and args.consolidate_orders:
        parser.error("테이블 재분배와 주문 묶기는 동시에 실행할 수 없습니다.")
    try:
        config = Settings(_env_file=ROOT / "backend" / ".env")
        database_url = config.database_url
        if database_url.startswith("sqlite:///") and database_url != "sqlite:///:memory:":
            # 서버를 backend 폴더에서 실행할 때와 같은 SQLite 파일을 사용한다.
            path = Path(database_url.removeprefix("sqlite:///"))
            database_url = "sqlite:///" + str(path if path.is_absolute() else ROOT / "backend" / path)
        db = Database(database_url)
        try:
            result = (consolidate_sales_demo_orders(db, apply=args.apply) if args.consolidate_orders else
                      rebalance_sales_demo_tables(db, apply=args.apply) if args.rebalance_tables else
                      seed_sales_demo(db, datetime.now(KST).date(), apply=args.apply))
        finally:
            db._conn.close()
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        # DB 연결 예외에는 비밀번호가 포함될 수 있어 예외 종류만 출력한다.
        print(f"매출 시연 준비 실패: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1)
