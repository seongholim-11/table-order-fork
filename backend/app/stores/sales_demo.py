"""여러 메뉴로 하루 상승·주간 하락을 함께 설명하는 발표용 주문을 준비한다."""

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone

from app.services.grades import KST
from app.services.stats import order_time
from app.stores.db import Database


LEGACY_LABEL = "[시연] 매출 상승률 v1"
DEMO_LABEL = "[시연] 매출 증감률 v2"


def sales_demo_orders(db: Database) -> list[dict]:
    """기존·새 시연 주문만 찾아 주문금액과 전체 메뉴 줄 합계를 대조한다."""
    return db.all(
        "SELECT o.id, o.total, SUM(i.unit_price*i.qty) AS items_total FROM orders o "
        "JOIN order_items i ON i.order_id=o.id WHERE EXISTS "
        "(SELECT 1 FROM order_items d WHERE d.order_id=o.id AND d.option_label IN (?, ?)) "
        "GROUP BY o.id, o.total ORDER BY o.id", (LEGACY_LABEL, DEMO_LABEL))


def sales_demo_menus(db: Database) -> list[dict]:
    """전체 메뉴의 기존 가중치와 시연 판매 분포를 확인한다. 메뉴 설정은 수정하지 않는다."""
    return db.all(
        "SELECT m.id, m.name, m.category_id, m.price, m.weight, m.is_soldout, "
        "COALESCE(SUM(CASE WHEN i.option_label IN (?, ?) THEN i.qty ELSE 0 END), 0) AS demo_qty "
        "FROM menus m LEFT JOIN order_items i ON i.menu_id=m.id "
        "GROUP BY m.id, m.name, m.category_id, m.price, m.weight, m.is_soldout ORDER BY m.id",
        (LEGACY_LABEL, DEMO_LABEL))


def _stamp(value) -> datetime:
    """PostgreSQL datetime과 SQLite 문자열을 같은 한국 시각으로 읽는다."""
    return order_time(value.isoformat() if isinstance(value, datetime) else value)


def _summary(totals: Counter, last: date) -> dict:
    """실제 통계 API와 대조할 비교 금액을 함께 반환한다."""
    previous_day = totals[last - timedelta(days=7)]
    week = sum(totals[last - timedelta(days=i)] for i in range(7))
    previous_week = sum(totals[last - timedelta(days=i)] for i in range(7, 14))
    return {
        "last_order_date": last.isoformat(),
        "last_day_revenue": totals[last], "previous_day_revenue": previous_day,
        "last_day_change": (totals[last] - previous_day) / previous_day if previous_day else None,
        "week_revenue": week, "previous_week_revenue": previous_week,
        "week_change": (week - previous_week) / previous_week if previous_week else None,
    }


def _demo_records(db: Database) -> tuple[list[dict], dict]:
    """다른 주문·쿠폰 등이 섞이지 않은 시연 주문만 교체 대상으로 인정한다."""
    orders = [dict(row) for row in db._execute(
        "SELECT o.* FROM orders o WHERE EXISTS (SELECT 1 FROM order_items i "
        "WHERE i.order_id=o.id AND i.option_label IN (?, ?)) ORDER BY o.id",
        (LEGACY_LABEL, DEMO_LABEL)).fetchall()]
    lines = defaultdict(list)
    for order in orders:
        rows = [dict(row) for row in db._execute(
            "SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order["id"],)).fetchall()]
        if (order["member_id"] is not None or order["ai_combo"] or order["roulette_discount_percent"]
                or order["recommendation_event_id"] is not None or not rows
                or sum(row["unit_price"] * row["qty"] for row in rows) != order["total"]
                or any(row["option_label"] not in (LEGACY_LABEL, DEMO_LABEL) or row["kind"] != "menu"
                       or not 1 <= row["qty"] <= 3 or row["menu_id"] is None for row in rows)):
            raise ValueError("시연 주문에 다른 내역이 연결되어 교체를 중단합니다.")
        if db._execute("SELECT COUNT(*) AS n FROM coupons WHERE used_order_id=?", (order["id"],)).fetchone()["n"]:
            raise ValueError("쿠폰과 연결된 시연 주문은 자동 교체하지 않습니다.")
        if db._execute("SELECT COUNT(*) AS n FROM order_item_components c JOIN order_items i ON i.id=c.order_item_id "
                       "WHERE i.order_id=?", (order["id"],)).fetchone()["n"]:
            raise ValueError("조합 내역이 추가된 시연 주문은 자동 교체하지 않습니다.")
        lines[order["id"]] = rows
    return orders, lines


def _menu_cycle(menus: list[dict]) -> list[dict]:
    """안주·주류 등 분류를 번갈아 돌며 모든 판매 가능 메뉴에 수량을 분산한다."""
    groups = defaultdict(list)
    for menu in menus:
        groups[menu["category_id"]].append(menu)
    return [group[index] for index in range(max(map(len, groups.values())))
            for group in groups.values() if index < len(group)]


def _pick_units(menus: list[dict], budget: int, offset: int) -> list[dict]:
    """실제 단가로 예산에 가깝게 담는다. 같은 순환에서 한 메뉴를 반복 선택하지 않는다."""
    chosen, remaining = [], budget
    cycle = menus[offset % len(menus):] + menus[:offset % len(menus)]
    while remaining >= min(menu["price"] for menu in menus):
        used = False
        for menu in cycle:
            if menu["price"] <= remaining:
                chosen.append(menu)
                remaining -= menu["price"]
                used = True
        if not used:
            break
    cheapest = min(menus, key=lambda menu: (menu["price"], menu["id"]))
    if remaining > cheapest["price"] / 2:
        chosen.append(cheapest)
    return chosen


def _signature(orders: list[dict], lines: dict) -> list:
    """동일한 계획을 다시 실행하면 삭제·재추가도 하지 않도록 내용으로 비교한다."""
    return sorted((order["table_no"], _stamp(order["created_at"]).date().isoformat(), order["total"],
                   tuple(sorted((row["menu_id"], row["name"], row["unit_price"], row["qty"], row["option_label"])
                                for row in lines[order["id"]]))) for order in orders)


def _spread_day_orders(orders: list[dict], lines: dict, day: date, tables: int) -> tuple[list[dict], dict]:
    """메뉴 수량·단가·시간대별 매출을 유지한 채 15개 테이블의 주문 30건으로 나눈다."""
    current = [order for order in orders if _stamp(order["created_at"]).date() == day]
    by_hour = defaultdict(list)
    for order in current:
        hour = _stamp(order["created_at"]).hour
        for line in lines[order["id"]]:
            by_hour[hour].extend([{**line, "qty": 1}] * line["qty"])
    # 작은 테스트 자료나 메뉴 수량이 부족한 DB에 빈 주문·임의 금액을 만들지 않는다.
    if tables < 15 or sum(map(len, by_hour.values())) < 30:
        return orders, lines
    quotas = {hour: (len(units) + 2) // 3 for hour, units in by_hour.items()}
    if sum(quotas.values()) > 30:
        return orders, lines
    while sum(quotas.values()) < 30:
        hour = max((hour for hour in quotas if quotas[hour] < len(by_hour[hour])),
                   key=lambda hour: (len(by_hour[hour]) / quotas[hour], -hour))
        quotas[hour] += 1
    # 번호순이 아닌 주문 건수순으로 순위가 정해지도록 서로 다른 주문 빈도를 준다.
    counts = {7: 6, 12: 5, 3: 4, 9: 3, 14: 2}
    counts.update({table: 1 for table in range(1, 16) if table not in counts})
    schedule = [table for turn in range(6) for table, count in counts.items() if turn < count]
    grouped = []
    for hour in sorted(by_hour):
        units = sorted(by_hour[hour], key=lambda line: (-line["unit_price"], line["menu_id"], line["name"]))
        baskets = [[] for _ in range(quotas[hour])]
        for index, unit in enumerate(units):
            baskets[index % len(baskets)].append(unit)
        for index, basket in enumerate(baskets):
            # 같은 시간대 안에서만 다시 묶어 매출 그래프의 기존 금액도 그대로 유지한다.
            stamp = datetime.combine(day, time(hour, index * 55 // max(len(baskets) - 1, 1)), tzinfo=KST)
            now = datetime.now(KST)
            if day == now.date() and hour == now.hour:
                stamp = min(stamp, now.replace(second=0, microsecond=0))
            merged = {}
            for unit in basket:
                key = (unit["menu_id"], unit["name"], unit["unit_price"], unit["option_label"])
                if key not in merged:
                    merged[key] = {**unit, "qty": 0}
                merged[key]["qty"] += 1
            rows = list(merged.values())
            order = {"table_no": schedule[len(grouped)], "created_at": stamp.isoformat(),
                     "total": sum(row["unit_price"] * row["qty"] for row in rows)}
            grouped.append((order, rows))
    # 다른 날짜의 주문은 테이블·시각·금액·내역을 그대로 넘긴다.
    grouped.extend((order, lines[order["id"]]) for order in orders if _stamp(order["created_at"]).date() != day)
    return ([{**order, "id": index} for index, (order, _) in enumerate(grouped)],
            {index: rows for index, (_, rows) in enumerate(grouped)})


def rebalance_sales_demo_tables(db: Database, *, apply: bool = False) -> dict:
    """마지막 영업일의 시연 주문만 재분배한다. 매출·다른 날짜·일반 주문은 유지한다."""
    with db._lock:
        with db._conn.transaction() if db.pg else db._conn:
            if db.pg and apply:
                db._execute("SELECT pg_advisory_xact_lock(73102517)")
            owned, lines = _demo_records(db)
            if not owned:
                raise ValueError("재분배할 시연 주문이 없습니다.")
            latest = max(_stamp(row["created_at"]).date() for row in db._execute(
                "SELECT created_at FROM orders").fetchall())
            current = [order for order in owned if _stamp(order["created_at"]).date() == latest]
            store = db._execute("SELECT tables FROM store_info WHERE id=1").fetchone()
            planned, planned_lines = _spread_day_orders(current, lines, latest, store["tables"] if store else 0)
            if len(planned) != 30 or len({order["table_no"] for order in planned}) != 15:
                raise ValueError("15개 테이블에 30건을 나눌 수 있는 시연 메뉴 수량이 필요합니다.")
            if sum(order["total"] for order in current) != sum(order["total"] for order in planned):
                raise ValueError("재분배 전후 매출이 일치하지 않습니다.")
            unchanged = _signature(current, lines) == _signature(planned, planned_lines)
            created_ids, replaced_ids = [], []
            if apply and not unchanged:
                for order in current:
                    db._execute("DELETE FROM order_items WHERE order_id=?", (order["id"],))
                    db._execute("DELETE FROM orders WHERE id=?", (order["id"],))
                    replaced_ids.append(order["id"])
                for order in planned:
                    order_id = db._execute("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?) RETURNING id",
                                           (order["table_no"], order["total"],
                                            _stamp(order["created_at"]).astimezone(timezone.utc).isoformat())).fetchone()["id"]
                    for line in planned_lines[order["id"]]:
                        db._execute("INSERT INTO order_items (order_id, menu_id, name, option_label, unit_price, qty, kind) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (order_id, line["menu_id"], line["name"], line["option_label"],
                                     line["unit_price"], line["qty"], "menu"))
                    created_ids.append(order_id)
            counts = Counter(order["table_no"] for order in planned)
            return {"applied": apply, "unchanged": unchanged, "last_order_date": latest.isoformat(),
                    "last_day_demo_revenue": sum(order["total"] for order in planned),
                    "before_orders": len(current), "after_orders": len(planned),
                    "table_counts": dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))),
                    "order_amounts": [order["total"] for order in planned],
                    "created_order_ids": created_ids, "replaced_order_ids": replaced_ids}


def consolidate_sales_demo_orders(db: Database, *, apply: bool = False) -> dict:
    """마지막 주문일의 시연 추가 주문만 테이블별로 묶고 메뉴·수량·매출은 유지한다."""
    with db._lock:
        # 메뉴 줄 이동과 중복 주문 삭제를 함께 처리해 실패하면 원래 주문으로 돌아간다.
        with db._conn.transaction() if db.pg else db._conn:
            if db.pg and apply:
                db._execute("SELECT pg_advisory_xact_lock(73102517)")
            owned, lines = _demo_records(db)
            if not owned:
                raise ValueError("묶을 시연 주문이 없습니다.")
            latest = max(_stamp(row["created_at"]).date() for row in db._execute(
                "SELECT created_at FROM orders").fetchall())
            current = [order for order in owned if _stamp(order["created_at"]).date() == latest]
            if not current:
                raise ValueError("마지막 주문일에 묶을 시연 주문이 없습니다.")
            prices = {row["id"]: row["price"] for row in db._execute("SELECT id, price FROM menus").fetchall()}
            if any(prices.get(line["menu_id"]) != line["unit_price"]
                   for order in current for line in lines[order["id"]]):
                raise ValueError("시연 주문의 단가가 현재 등록 메뉴 가격과 달라 적용하지 않습니다.")
            grouped = defaultdict(list)
            for order in sorted(current, key=lambda order: (_stamp(order["created_at"]), order["id"])):
                grouped[order["table_no"]].append(order)
            amounts = [sum(order["total"] for order in grouped[table]) for table in sorted(grouped)]
            removed_ids = []
            if apply:
                for group in grouped.values():
                    kept = group[0]
                    for extra in group[1:]:
                        # 같은 테이블의 첫 주문에 기존 메뉴 줄을 옮겨 단가·수량·줄 ID를 보존한다.
                        db._execute("UPDATE order_items SET order_id=? WHERE order_id=?", (kept["id"], extra["id"]))
                        db._execute("DELETE FROM orders WHERE id=?", (extra["id"],))
                        removed_ids.append(extra["id"])
                    if len(group) > 1:
                        db._execute("UPDATE orders SET total=? WHERE id=?",
                                    (sum(order["total"] for order in group), kept["id"]))
            total = sum(amounts)
            return {"applied": apply, "unchanged": len(current) == len(grouped),
                    "last_order_date": latest.isoformat(), "before_orders": len(current),
                    "after_orders": len(grouped), "total": total, "average": total // len(grouped),
                    "table_amounts": dict(zip(sorted(grouped), amounts)), "removed_order_ids": removed_ids}


def seed_sales_demo(db: Database, today: date, *, apply: bool = False) -> dict:
    """하루는 약 +10%, 일주일은 약 -6%로 구성한다. 기본 실행은 미리보기다."""
    with db._lock:
        # 기존 시연 삭제와 새 주문 저장을 묶어, 실패하면 이전 상태 전체를 복원한다.
        with db._conn.transaction() if db.pg else db._conn:
            if db.pg and apply:
                db._execute("SELECT pg_advisory_xact_lock(73102517)")
            old_orders, old_lines = _demo_records(db)
            old_ids = {order["id"] for order in old_orders}
            totals, actual = Counter(), Counter()
            for row in db._execute("SELECT id, total, created_at FROM orders").fetchall():
                day = _stamp(row["created_at"]).date()
                actual[day] += row["total"]
                if row["id"] not in old_ids:
                    totals[day] += row["total"]
            if totals and max(totals) > today:
                raise ValueError("미래 주문이 있어 발표 기준 날짜를 확인해야 합니다.")
            base = _summary(totals, today)
            if not base["previous_day_revenue"] or not base["previous_week_revenue"]:
                raise ValueError("전주 같은 요일과 이전 7일의 기존 매출이 있어야 시연을 준비할 수 있습니다.")
            menus = [dict(row) for row in db._execute(
                "SELECT id, name, price, category_id FROM menus WHERE price>0 AND is_soldout=? ORDER BY category_id, id",
                (False,)).fetchall()]
            store = db._execute("SELECT tables FROM store_info WHERE id=1").fetchone()
            if len(menus) < 3 or not store or store["tables"] < 1:
                raise ValueError("판매 가능한 메뉴 3개 이상과 매장 테이블 설정이 필요합니다.")
            menus = _menu_cycle(menus)
            plans, plan_lines, distribution = [], {}, Counter()

            def add_units(units: list[dict], days: list[date]):
                # 한 주문에 서로 다른 메뉴를 최대 3개 담고, 여러 테이블·영업 시간에 나눈다.
                for start in range(0, len(units), 3):
                    basket = units[start:start + 3]
                    index = len(plans)
                    day = days[(start // 3) % len(days)]
                    stamp = datetime.combine(day, time(17), tzinfo=KST) + timedelta(minutes=(index * 19) % 240)
                    if day == today:
                        stamp = min(stamp, datetime.now(KST).replace(second=0, microsecond=0))
                    counts = Counter(menu["id"] for menu in basket)
                    rows = []
                    for menu in basket:
                        if menu["id"] in counts:
                            rows.append({"menu_id": menu["id"], "name": menu["name"], "unit_price": menu["price"],
                                         "qty": counts.pop(menu["id"]), "option_label": DEMO_LABEL})
                    total = sum(row["unit_price"] * row["qty"] for row in rows)
                    plans.append({"id": index, "table_no": index % store["tables"] + 1,
                                  "created_at": stamp.isoformat(), "total": total})
                    plan_lines[index] = rows
                    totals[day] += total
                    distribution.update(menu["id"] for menu in basket)

            target_day = round(base["previous_day_revenue"] * 1.10)
            add_units(_pick_units(menus, max(target_day - totals[today], 0), 0), [today])
            current = _summary(totals, today)
            target_week = round(current["previous_week_revenue"] * .94)
            if current["week_revenue"] < target_week:
                budget = target_week - current["week_revenue"]
                days = [today - timedelta(days=i) for i in range(1, 7)]
            else:
                # 전주 같은 요일은 건드리지 않아 하루 비교 기준을 일정하게 유지한다.
                budget = round(current["week_revenue"] / .94) - current["previous_week_revenue"]
                days = [today - timedelta(days=i) for i in range(8, 14)]
            add_units(_pick_units(menus, max(budget, 0), sum(distribution.values())), days)
            after = _summary(totals, today)
            if not (.03 <= after["last_day_change"] <= .18 and -.15 <= after["week_change"] <= -.01):
                raise ValueError("기존 매출을 유지하면서 완만한 상승·하락을 만들 수 없어 적용하지 않습니다.")

            # 시연을 다시 준비해도 한 테이블에 1건씩만 생기는 예전 구성으로 돌아가지 않는다.
            plans, plan_lines = _spread_day_orders(plans, plan_lines, today, store["tables"])
            unchanged = _signature(old_orders, old_lines) == _signature(plans, plan_lines)
            created_ids, replaced_ids = [], []
            if apply and not unchanged:
                for order in old_orders:
                    db._execute("DELETE FROM order_items WHERE order_id=?", (order["id"],))
                    db._execute("DELETE FROM orders WHERE id=?", (order["id"],))
                    replaced_ids.append(order["id"])
                for order in plans:
                    order_id = db._execute("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?) RETURNING id",
                                           (order["table_no"], order["total"],
                                            _stamp(order["created_at"]).astimezone(timezone.utc).isoformat())).fetchone()["id"]
                    for line in plan_lines[order["id"]]:
                        db._execute("INSERT INTO order_items (order_id, menu_id, name, option_label, unit_price, qty, kind) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (order_id, line["menu_id"], line["name"], DEMO_LABEL, line["unit_price"], line["qty"], "menu"))
                    created_ids.append(order_id)
            return {"applied": apply, "before": _summary(actual, today), "base": base, "after": after,
                    "unchanged": unchanged, "planned_orders": len(plans), "created_order_ids": created_ids,
                    "replaced_order_ids": replaced_ids, "replaceable_orders": len(old_orders),
                    "added_amount": sum(order["total"] for order in plans) if not unchanged else 0,
                    "menu_quantities": dict(distribution), "label": DEMO_LABEL}
