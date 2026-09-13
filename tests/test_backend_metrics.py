import unittest

from backend_app import StoredTask, audit_view, schema_evidence_view, upsert_step
from agent.langchain_agent import LangChainStreamEvent
from agent.schema import SchemaProfile, TableProfile


class BackendMetricsTest(unittest.TestCase):
    def test_repairs_are_counted_before_final_result_and_preserved_after_failure(self):
        task = StoredTask(id="test", title="test", question="test", businessDomain="test", dataSourceUrl=None)
        schema = SchemaProfile(tables=[], relations=[])
        upsert_step(task, LangChainStreamEvent("step", "SQL 自修复", "running"), schema)
        self.assertEqual(audit_view(task)["repairCount"], 1)
        upsert_step(task, LangChainStreamEvent("step", "SQL 自修复", "completed"), schema)
        self.assertEqual(audit_view(task)["repairCount"], 1)
        upsert_step(task, LangChainStreamEvent("step", "SQL 自修复", "running"), schema)
        task.status = "failed_recoverable"
        self.assertEqual(audit_view(task)["repairCount"], 2)

    def test_schema_does_not_claim_an_unmeasured_confidence(self):
        schema = SchemaProfile(tables=[TableProfile(name="orders", row_count=0, columns=[])], relations=[])
        self.assertIsNone(schema_evidence_view(schema)["tables"][0]["confidence"])


if __name__ == "__main__":
    unittest.main()
