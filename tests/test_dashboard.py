"""Tests for dashboard statistics and the recipe-centered graph view."""
import unittest
from unittest.mock import patch

import graph_view
import recipe_graph


class DashboardQueryTests(unittest.TestCase):
    @patch("recipe_graph.read_query")
    def test_dashboard_combines_counts_and_usage_rates(self, read_query):
        read_query.side_effect = [
            [{
                "node_count": 100, "relationship_count": 250,
                "recipe_count": 40, "ingredient_count": 20,
                "dish_type_count": 8, "group_count": 2,
            }],
            [{"name": "찌개", "recipe_count": 30}, {"name": "튀김", "recipe_count": 10}],
            [{"name": "소금", "recipe_count": 20}, {"name": "대파", "recipe_count": 10}],
        ]

        result = recipe_graph.load_dashboard(object(), "test")

        self.assertEqual(result["summary"]["node_count"], 100)
        self.assertEqual(result["groups"][0], {"name": "찌개", "recipe_count": 30})
        self.assertEqual(result["ingredients"][0]["usage_rate"], 50.0)
        self.assertEqual(result["ingredients"][1]["usage_rate"], 25.0)

    @patch("recipe_graph.read_query")
    def test_recipe_graph_returns_real_labels_and_relationships(self, read_query):
        read_query.return_value = [{
            "group": "찌개", "dish_type": "김치찌개",
            "recipe_uid": "r1", "title": "두부 김치찌개",
            "ingredients": ["김치", "두부"],
        }]

        result = recipe_graph.load_recipe_graph(object(), "test", "r1")

        self.assertEqual([node["label"] for node in result["nodes"]],
                         ["찌개", "김치찌개", "두부 김치찌개", "김치", "두부"])
        self.assertEqual([edge["label"] for edge in result["edges"]],
                         ["HAS_TYPE", "HAS_DISH", "INGREDIENT", "INGREDIENT"])


class GraphViewTests(unittest.TestCase):
    def test_graph_spec_contains_edges_nodes_labels_and_pastel_colors(self):
        graph = {
            "nodes": [
                {"id": "group:찌개", "label": "찌개", "kind": "DishGroup"},
                {"id": "dish:r1", "label": "두부 김치찌개", "kind": "Dish"},
                {"id": "ingredient:두부", "label": "두부", "kind": "Ingredient"},
            ],
            "edges": [
                {"source": "group:찌개", "target": "dish:r1", "label": "HAS_DISH"},
                {"source": "dish:r1", "target": "ingredient:두부", "label": "INGREDIENT"},
            ],
        }

        spec = graph_view.build_graph_spec(graph)

        self.assertEqual(len(spec["layer"]), 3)
        self.assertEqual(len(spec["layer"][0]["data"]["values"]), 2)
        self.assertEqual(len(spec["layer"][1]["data"]["values"]), 3)
        self.assertIn("#B7E4C7", str(spec))

    def test_graph_spec_handles_an_empty_graph(self):
        self.assertIsNone(graph_view.build_graph_spec({"nodes": [], "edges": []}))


if __name__ == "__main__":
    unittest.main()
