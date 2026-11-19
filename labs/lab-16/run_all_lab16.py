import unittest
from Lab_16_1.polyglot_university import main as run_16_1
from Lab_16_2.fraud_service import run_integration_and_latency_benchmark as run_16_2
from tests.test_fraud_service import TestFraudQueryService

if __name__ == "__main__":
    run_16_1()
    print("\n")
    run_16_2()
    print("\n" + "=" * 78)
    print("LAB 16.2 UNIT TESTS (Mocked Drivers & Circuit Breaker Verification)")
    print("=" * 78)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestFraudQueryService)
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    if not res.wasSuccessful():
        raise SystemExit(1)
    print("\n[ALL LAB 16 POLYGLOT MODULES & TESTS COMPLETED SUCCESSFULLY]")