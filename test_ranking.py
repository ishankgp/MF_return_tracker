import unittest
from unittest.mock import patch
import asyncio

# Mocking the functions to avoid actual API calls
# We need to test the logic snippet we inserted, which is inside fetch_fund_data_async.
# Since it's hard to unit test a script without refactoring, I will simulate the logic directly in the test.

def calculate_score(r1y, r2y, r3y):
    r1y = r1y or 0
    r2y = r2y or 0
    r3y = r3y or 0
    return (r1y * 0.2) + (r2y * 0.3) + (r3y * 0.5)

class TestRankingLogic(unittest.TestCase):
    def test_all_returns_present(self):
        # Case 1: All returns positive
        # 1Y=10, 2Y=20, 3Y=30
        # Score = 2 + 6 + 15 = 23
        score = calculate_score(10, 20, 30)
        self.assertAlmostEqual(score, 23.0)

    def test_missing_1y(self):
        # Case 2: Missing 1Y (e.g. None or 0)
        # 1Y=0, 2Y=20, 3Y=30
        # Score = 0 + 6 + 15 = 21
        score = calculate_score(None, 20, 30)
        self.assertAlmostEqual(score, 21.0)

    def test_negative_returns(self):
        # Case 3: Negative returns
        # 1Y=-10, 2Y=-5, 3Y=10
        # Score = -2 - 1.5 + 5 = 1.5
        score = calculate_score(-10, -5, 10)
        self.assertAlmostEqual(score, 1.5)

    def test_all_zeros(self):
        # Case 4: All zeros
        score = calculate_score(0, 0, 0)
        self.assertEqual(score, 0)

if __name__ == '__main__':
    unittest.main()
