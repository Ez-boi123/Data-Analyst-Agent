import unittest
import pandas as pd
from agent.schema import profile_tables
from backend_app import schema_evidence_view


class SchemaConfidenceTest(unittest.TestCase):
    def test_clean_single_table_and_api_explanation(self):
        view = schema_evidence_view(profile_tables({"users": pd.DataFrame({"user_id": [1, 2]})}))
        self.assertEqual(view["assessment"]["score"], 1.0)
        self.assertTrue(view["assessment"]["method"])
        self.assertEqual(view["tables"][0]["confidence"], 1.0)

    def test_empty_data_is_unassessed(self):
        view = schema_evidence_view(profile_tables({"empty": pd.DataFrame({"id": []})}))
        self.assertIsNone(view["assessment"]["score"])

    def test_nulls_reduce_score(self):
        clean = profile_tables({"a": pd.DataFrame({"value": [1, 2]})})
        missing = profile_tables({"a": pd.DataFrame({"value": [1, None]})})
        self.assertLess(missing.assessment["score"], clean.assessment["score"])

    def test_orphans_and_many_to_many_reduce_relation_score(self):
        def score(left, right):
            schema = profile_tables({"a": pd.DataFrame({"user_id": left}), "b": pd.DataFrame({"user_id": right})})
            return schema.relations[0].assessment
        clean = score([1, 2, 1], [1, 2])
        orphan = score([1, 2, 3], [1, 2])
        duplicate = score([1, 1, 2, 2], [1, 1, 2, 2])
        self.assertEqual(clean["score"], 1.0)
        self.assertLess(orphan["score"], clean["score"])
        self.assertLess(duplicate["score"], clean["score"])
        self.assertTrue(duplicate["warnings"])

    def test_unrelated_tables_have_explicit_penalty(self):
        schema = profile_tables({"a": pd.DataFrame({"x": [1]}), "b": pd.DataFrame({"y": [2]})})
        self.assertLess(schema.assessment["score"], 1)
        self.assertTrue(schema.assessment["warnings"])

    def test_numeric_key_types_and_table_order_do_not_change_scores(self):
        tables = {"a": pd.DataFrame({"user_id": [1, 2]}), "b": pd.DataFrame({"user_id": [1.0, 2.0]}), "c": pd.DataFrame({"x": [1]})}
        schema = profile_tables(tables)
        self.assertEqual(schema.relations[0].assessment["score"], 1)
        self.assertEqual(schema.assessment["score"], profile_tables(dict(reversed(list(tables.items())))).assessment["score"])
