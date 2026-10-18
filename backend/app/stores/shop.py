"""메뉴·주문·직원 호출·추천 기록 저장소.

테이블별 코드는 shop_menus / shop_orders / shop_calls / shop_recommendations 파일에 나뉘어 있고,
여기서는 하나의 ShopStore 로 합쳐 `app.state.shop` 으로 쓴다 (라우터는 shop.xxx() 를 부른다).
[뼈대] 지금은 각 메서드가 NotImplementedError 이고 라우터는 dummy/ 응답을 돌려준다.
"""

from app.stores import shop_calls, shop_menus, shop_orders, shop_recommendations
from app.stores.db import Database
from app.stores.shop_calls import CallMixin
from app.stores.shop_menus import MenuMixin
from app.stores.shop_orders import OrderMixin
from app.stores.shop_recommendations import RecommendationMixin

SCHEMAS = (shop_menus.SCHEMA, shop_orders.SCHEMA, shop_calls.SCHEMA, shop_recommendations.SCHEMA)


class ShopStore(MenuMixin, OrderMixin, CallMixin, RecommendationMixin):
    def __init__(self, db: Database):
        self.db = db
        for schema in SCHEMAS:
            db.script(schema)

        self.seed_menus()
