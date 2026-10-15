import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from menu_data import MENU_BY_ID
from recommendations import combo_cart_line, ordered_counts, recommend_combos


class RecommendationTests(unittest.TestCase):
    def test_preferences_and_budget_constraints(self):
        for people in range(1, 7):
            for budget in (20000, 30000, 40000, 60000, 100000):
                for spicy in ("상관없어요", "맵지 않게", "매콤하게"):
                    for drink in ("맥주", "소주", "음료", "없이"):
                        combos = recommend_combos(people, budget, spicy, drink)
                        self.assertLessEqual(len(combos), 3)
                        self.assertEqual(len({c["id"] for c in combos}), len(combos))
                        for combo in combos:
                            self.assertLessEqual(combo["price"], budget)
                            self.assertEqual(combo["original"], sum(c["unit"] * c["qty"] for c in combo["components"]))
                            self.assertEqual(combo["price"], combo["original"] * 9 // 10)
                            self.assertTrue(combo["reason"])
                            if spicy == "맵지 않게":
                                self.assertTrue(all("매운맛" not in MENU_BY_ID[c["id"]]["tags"] for c in combo["components"]))
                            if drink in ("음료", "없이"):
                                self.assertTrue(all(MENU_BY_ID[c["id"]]["cat"] not in ("beer", "soju") for c in combo["components"]))

    def test_spicy_preference_changes_menu_selection(self):
        mild = recommend_combos(spicy="맵지 않게")
        spicy = recommend_combos(spicy="매콤하게")
        self.assertNotEqual(mild[0]["components"], spicy[0]["components"])
        self.assertTrue(any("매운맛" in MENU_BY_ID[c["id"]]["tags"] for c in spicy[0]["components"]))
        for combo in spicy:
            for component in combo["components"]:
                self.assertEqual(component["name"], MENU_BY_ID[component["id"]]["name"])
                self.assertEqual(component["unit"], MENU_BY_ID[component["id"]]["price"])
                self.assertEqual(component["opt"], "")

    def test_soldout_excludes_entire_bundle(self):
        with patch.dict(MENU_BY_ID["b1"], soldout=True):
            self.assertEqual(recommend_combos(drink="맥주"), [])
            self.assertTrue(recommend_combos(drink="없이"))

    def test_previous_bundles_influence_next_ranking(self):
        first = recommend_combos()[0]
        _, line = combo_cart_line(first)
        second = recommend_combos(lines=[line])[0]
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(ordered_counts([line])["b1"], 2)
        self.assertTrue(ordered_counts([line])[first["components"][0]["id"]])

    def test_discount_is_member_only(self):
        member = recommend_combos(member=True)[0]
        guest = recommend_combos(member=False)
        self.assertGreater(member["discount"], 0)
        self.assertTrue(all(c["discount"] == 0 and c["price"] == c["original"] for c in guest))
        self.assertTrue(all(c["price"] <= 40000 for c in guest))  # 예산은 정가 기준

    def test_guest_sees_full_price_and_login_hint(self):
        app = AppTest.from_file("app.py").run()
        app.button(key="start_btn").click().run()
        app.button(key="cat_ai").click().run()
        html = " ".join(h.value for h in app.get("html"))
        self.assertIn("회원 로그인 시", html)
        app.button(key="add_combo_1").click().run()
        line = next(iter(app.session_state["cart"].values()))
        self.assertEqual(line["unit"], line["original_unit"])

    def test_empty_results_for_impossible_budget(self):
        self.assertEqual(recommend_combos(people=6, budget=1), [])

    def test_cart_and_order_preserve_discount(self):
        app = AppTest.from_file("app.py")
        app.session_state["member"] = {"id": 1, "nickname": "회원"}  # 조합 할인은 회원 전용
        app.run()
        app.button(key="start_btn").click().run()
        self.assertLess([b.key for b in app.button].index("cat_ai"), [b.key for b in app.button].index("cat_best"))
        app.button(key="cat_ai").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len([b for b in app.button if str(b.key).startswith("add_combo_")]), 3)
        app.button(key="add_combo_1").click().run()
        key, line = next(iter(app.session_state["cart"].items()))
        self.assertLess(line["unit"], line["original_unit"])
        app.button(key=f"q_inc_{key}").click().run()
        self.assertEqual(app.session_state["cart"][key]["qty"], 2)
        app.button(key="order_btn").click().run()
        # AppTest reruns the full script for dialog actions, unlike browser fragment reruns.
        app.session_state["confirm_order"] = True
        next(b for b in app.button if b.label == "주문하기").click().run()
        order = app.session_state["orders"][0]
        self.assertEqual(order["total"], line["unit"] * 2)
        self.assertEqual(order["lines"][0]["original_unit"], line["original_unit"])
        self.assertEqual(app.session_state["cart"], {})
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
