import unittest
from unittest.mock import MagicMock
from Lab_16_2.fraud_service import FraudQueryService

class TestFraudQueryService(unittest.TestCase):
    def test_merged_polyglot_results(self):
        mock_mongo = MagicMock()
        mock_mongo.__getitem__.return_value.transactions.find_one.return_value = {
            "txn_id": "TXN-MOCK-1",
            "user_id": "USR-MOCK",
            "amount": 5000.0,
            "risk_score": 0.91,
        }

        mock_cass = MagicMock()
        row = MagicMock(user_id="USR-MOCK", event_time="2026-11-19 00:00:00", txn_id="TXN-MOCK-1", amount=5000.0, channel="WIRE")
        mock_cass.execute.return_value = [row]

        mock_neo = MagicMock()
        mock_session = MagicMock()
        mock_session.run.return_value = [{"ring_path": ["USR-MOCK", "USR-MULE-1", "USR-MULE-2"], "hops": 2}]
        mock_neo.session.return_value.__enter__.return_value = mock_session

        svc = FraudQueryService(mongo_client=mock_mongo, cassandra_session=mock_cass, neo4j_driver=mock_neo, db_name="lab_16")
        merged = svc.analyze_fraud_case("TXN-MOCK-1", "USR-MOCK", max_hops=3)

        self.assertEqual(merged["transaction"]["txn_id"], "TXN-MOCK-1")
        self.assertEqual(len(merged["recent_events"]), 1)
        self.assertEqual(merged["fraud_rings"][0]["hops"], 2)

    def test_circuit_breaker_opens_after_three_failures(self):
        mock_mongo = MagicMock()
        mock_mongo.__getitem__.return_value.transactions.find_one.side_effect = RuntimeError("MongoDB timeout")

        svc = FraudQueryService(mongo_client=mock_mongo, db_name="lab_16")
        for _ in range(3):
            res = svc.get_transaction("TXN-FAIL")
            self.assertEqual(res["status"], "error")

        # 4th call must short-circuit without hitting MongoDB
        self.assertEqual(svc.cb_mongo.state, "OPEN (SKIPPED)")
        skipped = svc.get_transaction("TXN-FAIL")
        self.assertEqual(skipped["status"], "circuit_open")
        self.assertEqual(mock_mongo.__getitem__.return_value.transactions.find_one.call_count, 3)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestFraudQueryService)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)