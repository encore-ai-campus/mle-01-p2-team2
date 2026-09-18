"""Offline UI tests; the external Neo4j boundary is replaced with fixtures."""
import os
from pathlib import Path
import tomllib
import unittest
from unittest.mock import patch

from neo4j.exceptions import ServiceUnavailable
from streamlit.testing.v1 import AppTest

import recipe_graph


ROOT = Path(__file__).resolve().parents[1]
RECIPE = {
    "recipe_uid": "test:1", "title": "두부 김치찌개", "dish_type": "김치찌개",
    "dish_group": "찌개", "views": 120, "servings": "2인분",
    "cooking_time": "20분", "difficulty": "초급",
    "source_url": "https://www.10000recipe.com/recipe/1",
    "cooking_method": "1. 재료를 썬다.\n2. 끓인다.",
}
DASHBOARD = {
    "summary": {"node_count": 100, "relationship_count": 250, "recipe_count": 40,
                "ingredient_count": 20, "dish_type_count": 8, "group_count": 2},
    "groups": [{"name": "찌개", "recipe_count": 30}, {"name": "튀김", "recipe_count": 10}],
    "ingredients": [{"name": "소금", "recipe_count": 20, "usage_rate": 50.0}],
}
RECIPE_GRAPH = {
    "nodes": [
        {"id": "group:찌개", "label": "찌개", "kind": "DishGroup"},
        {"id": "type:김치찌개", "label": "김치찌개", "kind": "DishType"},
        {"id": "dish:test:1", "label": "두부 김치찌개", "kind": "Dish"},
        {"id": "ingredient:두부", "label": "두부", "kind": "Ingredient"},
    ],
    "edges": [
        {"source": "group:찌개", "target": "type:김치찌개", "label": "HAS_TYPE"},
        {"source": "type:김치찌개", "target": "dish:test:1", "label": "HAS_DISH"},
        {"source": "dish:test:1", "target": "ingredient:두부", "label": "INGREDIENT"},
    ],
}


class InputTests(unittest.TestCase):
    def test_ingredient_terms_are_deduplicated_and_trimmed(self):
        self.assertEqual(recipe_graph.parse_ingredients(" 두부, 김치 ,두부,,"), ["두부", "김치"])

    def test_unsafe_source_link_is_not_renderable(self):
        self.assertEqual(recipe_graph.safe_source_url("javascript:alert(1)"), "")
        self.assertEqual(recipe_graph.safe_source_url("https://example.com/r/1"), "https://example.com/r/1")

    def test_missing_credentials_report_keys_without_values(self):
        with self.assertRaisesRegex(ValueError, "NEO4J_PASSWORD"):
            recipe_graph.ConnectionSettings.from_mapping({"NEO4J_URI": "neo4j+s://example.com", "NEO4J_USER": "test"})


class AppTests(unittest.TestCase):
    def setUp(self):
        # Clear Streamlit's process-wide caches between independent UI scenarios.
        import streamlit as st
        st.cache_data.clear()
        st.cache_resource.clear()

    def app(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
        app.secrets.update({
            "NEO4J_URI": "neo4j+s://test.invalid", "NEO4J_USER": "tester",
            "NEO4J_PASSWORD": "test-only-secret", "NEO4J_DATABASE": "test",
        })
        return app

    def test_missing_secret_does_not_fall_back_to_environment_credentials(self):
        with patch.dict(os.environ, {"NEO4J_PASSWORD": "environment-only-password"}), \
             patch("recipe_graph.open_driver", side_effect=AssertionError("Credentials must come from Secrets")):
            app = self.app()
            del app.secrets["NEO4J_PASSWORD"]
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(app.warning)
            self.assertIn("NEO4J_PASSWORD", app.warning[0].value)

    def test_search_and_recipe_detail_survive_widget_rerun(self):
        with patch("recipe_graph.open_driver"), \
             patch("recipe_graph.load_catalog", return_value={"recipe_count": 2, "ingredient_count": 3, "groups": ["찌개"]}), \
             patch("recipe_graph.search_recipes", return_value=[RECIPE]), \
             patch("recipe_graph.load_recipe", return_value={"recipe": RECIPE, "ingredients": [{"name": "두부", "quantity": "1/2", "unit": "모", "raw": "두부 1/2모", "source_group": "재료", "preparation": []}]}):
            app = self.app().run()
            self.assertFalse(app.exception)
            app.text_input(key="keyword").set_value("김치찌개")
            app.button(key="search").click().run()
            self.assertFalse(app.exception)
            self.assertIn("두부 김치찌개", [x.value for x in app.subheader])
            self.assertTrue(any("끓인다" in x.value for x in app.text))
            app.selectbox(key="selected_recipe").set_value("test:1").run()
            self.assertFalse(app.exception)
            self.assertTrue(any("1/2" in str(x.value) for x in app.dataframe))

    def test_brand_navigation_graph_and_statistics_views(self):
        with patch("recipe_graph.open_driver"), \
             patch("recipe_graph.load_catalog", return_value={"recipe_count": 40, "ingredient_count": 20, "groups": ["찌개", "튀김"]}), \
             patch("recipe_graph.search_recipes", return_value=[RECIPE]), \
             patch("recipe_graph.load_dashboard", return_value=DASHBOARD), \
             patch("recipe_graph.load_recipe_graph", return_value=RECIPE_GRAPH):
            app = self.app().run()
            self.assertEqual(app.title[0].value, "요리조리 요리조리~")
            app.segmented_control(key="main_view").set_value("그래프 탐색").run()
            self.assertFalse(app.exception)
            self.assertTrue(app.get("vega_lite_chart"))
            app.segmented_control(key="main_view").set_value("요리 통계").run()
            self.assertFalse(app.exception)
            self.assertEqual([metric.value for metric in app.metric[:4]], ["100개", "250개", "40개", "20개"])

    def test_empty_search_has_no_stale_recipe_details(self):
        with patch("recipe_graph.open_driver"), \
             patch("recipe_graph.load_catalog", return_value={"recipe_count": 2, "ingredient_count": 3, "groups": []}), \
             patch("recipe_graph.search_recipes", side_effect=[[RECIPE], []]), \
             patch("recipe_graph.load_recipe", return_value={"recipe": RECIPE, "ingredients": []}):
            app = self.app().run()
            app.button(key="search").click().run()
            app.text_input(key="keyword").set_value("없는음식")
            app.button(key="search").click().run()
            self.assertFalse(app.exception)
            self.assertFalse(any(x.key == "selected_recipe" for x in app.selectbox))
            self.assertTrue(app.info)

    def test_connection_error_does_not_leak_credentials(self):
        with patch("recipe_graph.open_driver", side_effect=ServiceUnavailable("test-only-secret")):
            app = self.app().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            self.assertNotIn("test-only-secret", str([x.value for x in app.error]))


@unittest.skipUnless(os.getenv("TEST_AURA") == "1", "Set TEST_AURA=1 for read-only live DB checks")
class AuraTests(unittest.TestCase):
    def test_live_search_filters_and_detail(self):
        with (ROOT / ".streamlit" / "secrets.toml").open("rb") as file:
            settings = recipe_graph.ConnectionSettings.from_mapping(tomllib.load(file))
        with recipe_graph.open_driver(settings) as driver:
            catalog = recipe_graph.load_catalog(driver, settings.database)
            self.assertGreater(catalog["recipe_count"], 0)
            rows = recipe_graph.search_recipes(driver, settings.database, "", "", ["두부"], ["소고기"], 5)
            self.assertTrue(rows)
            self.assertLessEqual(len(rows), 5)
            for row in rows:
                detail = recipe_graph.load_recipe(driver, settings.database, row["recipe_uid"])
                names = [item["name"] for item in detail["ingredients"]]
                self.assertIn("두부", names)
                self.assertNotIn("소고기", names)
            group_rows = recipe_graph.search_recipes(driver, settings.database, "김치", "찌개", [], [], 5)
            self.assertTrue(group_rows)
            self.assertTrue(all(r["dish_group"] == "찌개" for r in group_rows))
            dashboard = recipe_graph.load_dashboard(driver, settings.database)
            self.assertGreater(dashboard["summary"]["node_count"], dashboard["summary"]["recipe_count"])
            self.assertTrue(dashboard["groups"])
            self.assertTrue(dashboard["ingredients"])
            recipe_graph_data = recipe_graph.load_recipe_graph(
                driver, settings.database, group_rows[0]["recipe_uid"]
            )
            self.assertTrue(recipe_graph_data["nodes"])
            self.assertTrue(recipe_graph_data["edges"])
            self.assertEqual(recipe_graph.search_recipes(driver, settings.database, "' MATCH (n) DETACH DELETE n //", "", [], [], 5), [])


if __name__ == "__main__":
    unittest.main()
