from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.features.errors import InsufficientPointsError
from app.features.points import service as points_service


class EnsurePointsTests(unittest.TestCase):
    @patch("app.features.points.db.user_has_points", new_callable=AsyncMock)
    def test_sufficient_points_passes(self, mock_has):
        mock_has.return_value = True
        asyncio.run(points_service.ensure_points({"id": "user_1"}, 100))
        mock_has.assert_called_once_with("user_1", 100)

    @patch("app.features.points.db.user_has_points", new_callable=AsyncMock)
    def test_insufficient_points_raises(self, mock_has):
        mock_has.return_value = False
        with self.assertRaises(InsufficientPointsError):
            asyncio.run(points_service.ensure_points({"id": "user_1"}, 100))

    @patch("app.features.points.db.user_has_points", new_callable=AsyncMock)
    def test_zero_cost_skips_check(self, mock_has):
        asyncio.run(points_service.ensure_points({"id": "user_1"}, 0))
        mock_has.assert_not_called()

    @patch("app.features.points.db.user_has_points", new_callable=AsyncMock)
    def test_negative_cost_skips_check(self, mock_has):
        asyncio.run(points_service.ensure_points({"id": "user_1"}, -10))
        mock_has.assert_not_called()


class CostForShotsTests(unittest.TestCase):
    def test_basic_calculation(self):
        shots = [{"duration": 3}, {"duration": 5}]
        self.assertEqual(points_service.cost_for_shots(shots, 10), 80)

    def test_missing_duration_defaults_to_1(self):
        shots = [{"duration": None}, {}]
        self.assertEqual(points_service.cost_for_shots(shots, 10), 20)

    def test_zero_duration_defaults_to_1(self):
        shots = [{"duration": 0}]
        self.assertEqual(points_service.cost_for_shots(shots, 10), 10)

    def test_empty_shots(self):
        self.assertEqual(points_service.cost_for_shots([], 10), 0)


if __name__ == "__main__":
    unittest.main()
