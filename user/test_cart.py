import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().with_name("app.py"))


class DirectCartTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(APP).run()
        self.app.button(key="start_btn").click().run()

    def test_direct_add_repeated_add_and_separate_variants(self):
        app = self.app
        app.button(key="cat_chicken").click().run()
        app.button(key="add_c1").click().run()
        self.assertEqual(app.session_state["cart"]["c1|"]["qty"], 1)
        self.assertFalse(app.radio)
        self.assertFalse(app.number_input)
        app.button(key="add_c1").click().run()
        app.button(key="add_c1-half-seasoned").click().run()
        cart = app.session_state["cart"]
        self.assertEqual(cart["c1|"]["qty"], 2)
        self.assertEqual(cart["c1|"]["unit"], 18000)
        self.assertEqual(cart["c1-half-seasoned|"]["unit"], 11000)
        self.assertEqual(len(cart), 2)
        app.button(key="q_inc_c1-half-seasoned|").click().run()
        self.assertEqual(app.session_state["cart"]["c1-half-seasoned|"]["qty"], 2)
        self.assertFalse(app.exception)

    def test_drink_variants_have_independent_prices_and_quantities(self):
        app = self.app
        app.button(key="cat_soju").click().run()
        for item_id in ("j5", "j5-grapefruit", "j5-ginger", "j6", "j6-grape", "j6-peach"):
            app.button(key=f"add_{item_id}").click().run()
        cart = app.session_state["cart"]
        self.assertEqual(len(cart), 6)
        self.assertEqual(sum(line["unit"] * line["qty"] for line in cart.values()), 40000)
        self.assertTrue(all(line["qty"] == 1 and line["opt"] == "" for line in cart.values()))
        self.assertFalse(app.exception)

    def test_soldout_menu_cannot_be_added(self):
        self.app.button(key="cat_anju").click().run()
        self.assertTrue(self.app.button(key="add_a11").disabled)
        self.assertEqual(self.app.session_state["cart"], {})


if __name__ == "__main__":
    unittest.main()


class SpicyBadgeTests(unittest.TestCase):
    def test_spicy_badge_shows_chili_count_of_selected_level(self):
        app = AppTest.from_file(APP).run()
        app.button(key="start_btn").click().run()
        app.button(key="cat_anju").click().run()
        html = lambda: " ".join(e.proto.body for e in app.get("html"))
        app.session_state["spicy_a2"] = "아주 매운맛"
        app.run()
        self.assertIn("🌶🌶🌶 매운맛", html())
        app.session_state["spicy_a2"] = "보통맛"
        app.run()
        self.assertIn("🌶🌶 매운맛", html())
        self.assertFalse(app.exception)


class SpicyGroupTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(APP).run()
        self.app.button(key="start_btn").click().run()
        self.app.button(key="cat_anju").click().run()

    def test_variants_are_merged_into_one_card_with_selector(self):
        keys = [b.key for b in self.app.button if b.key and b.key.startswith("add_")]
        self.assertIn("add_a2", keys)
        self.assertNotIn("add_a2-medium", keys)
        self.assertNotIn("add_a2-hot", keys)
        self.assertNotIn("add_a3-hot", keys)
        self.assertIn("add_a4", keys)  # 단계가 없는 메뉴는 그대로
        self.assertEqual(len(self.app.get("button_group")), 2)  # 골뱅이·닭발 두 그룹

    def test_selected_level_goes_to_cart(self):
        app = self.app
        app.session_state["spicy_a2"] = "아주 매운맛"
        app.run()
        app.button(key="add_a2-hot").click().run()
        line = app.session_state["cart"]["a2-hot|"]
        self.assertEqual(line["name"], "골뱅이 소면 무침 (아주 매운맛)")
        self.assertEqual(line["unit"], 17000)
        self.assertNotIn("a2|", app.session_state["cart"])

    def test_selector_widget_switches_level(self):
        app = self.app
        app.get("button_group")[0].set_value("보통맛").run()
        app.button(key="add_a2-medium").click().run()
        self.assertEqual(list(app.session_state["cart"]), ["a2-medium|"])
        self.assertFalse(app.exception)

    def test_card_content_follows_selected_level(self):
        app = self.app
        app.session_state["spicy_a3"] = "보통맛"
        app.run()
        self.assertTrue(any("직화 무뼈닭발" in e.proto.body and "불향 가득 매콤한" in e.proto.body for e in app.get("html")))
        self.assertFalse(app.exception)
