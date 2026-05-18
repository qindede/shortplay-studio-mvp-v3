from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.features.errors import ForbiddenError, InsufficientPointsError, NotFoundError
from app.features.ai_job import service as ai_job_service


class StartPaidAiJobTests(unittest.TestCase):
    @patch("app.features.ai_job.db.start_paid_ai_job", new_callable=AsyncMock)
    def test_success(self, mock_start):
        mock_start.return_value = {"job": {"id": "job_1", "status": "running"}}
        result = asyncio.run(ai_job_service.start_paid_ai_job({"id": "user_1"}, 20, "scene", "desc", "outline", "minimax"))
        self.assertEqual(result["id"], "job_1")

    @patch("app.features.ai_job.db.start_paid_ai_job", new_callable=AsyncMock)
    def test_insufficient_points_raises(self, mock_start):
        mock_start.return_value = {"error": "insufficient_points"}
        with self.assertRaises(InsufficientPointsError):
            asyncio.run(ai_job_service.start_paid_ai_job({"id": "user_1"}, 999, "scene", "desc", "outline", "minimax"))


class CompleteAiJobTests(unittest.TestCase):
    @patch("app.features.ai_job.db.complete_ai_job", new_callable=AsyncMock)
    def test_success(self, mock_complete):
        mock_complete.return_value = {"id": "job_1", "status": "succeeded"}
        result = asyncio.run(ai_job_service.complete_ai_job("job_1", {"key": "value"}))
        self.assertEqual(result["status"], "succeeded")

    @patch("app.features.ai_job.db.complete_ai_job", new_callable=AsyncMock)
    def test_not_found_raises(self, mock_complete):
        mock_complete.return_value = None
        with self.assertRaises(NotFoundError):
            asyncio.run(ai_job_service.complete_ai_job("job_missing"))


class FailAiJobWithRefundTests(unittest.TestCase):
    @patch("app.features.ai_job.db.fail_ai_job_with_refund", new_callable=AsyncMock)
    def test_success(self, mock_fail):
        mock_fail.return_value = {"id": "job_1", "status": "failed"}
        result = asyncio.run(ai_job_service.fail_ai_job_with_refund("job_1", "timeout"))
        self.assertEqual(result["status"], "failed")

    @patch("app.features.ai_job.db.fail_ai_job_with_refund", new_callable=AsyncMock)
    def test_not_found_raises(self, mock_fail):
        mock_fail.return_value = None
        with self.assertRaises(NotFoundError):
            asyncio.run(ai_job_service.fail_ai_job_with_refund("job_missing", "err"))


class GetAiJobTests(unittest.TestCase):
    @patch("app.features.ai_job.db.get_ai_job", new_callable=AsyncMock)
    def test_success(self, mock_get):
        mock_get.return_value = {"id": "job_1", "user_id": "user_1"}
        result = asyncio.run(ai_job_service.get_ai_job({"id": "user_1"}, "job_1"))
        self.assertEqual(result["id"], "job_1")

    @patch("app.features.ai_job.db.get_ai_job", new_callable=AsyncMock)
    def test_not_found_raises(self, mock_get):
        mock_get.return_value = None
        with self.assertRaises(NotFoundError):
            asyncio.run(ai_job_service.get_ai_job({"id": "user_1"}, "job_missing"))

    @patch("app.features.ai_job.db.get_ai_job", new_callable=AsyncMock)
    def test_forbidden_raises(self, mock_get):
        mock_get.return_value = {"error": "forbidden"}
        with self.assertRaises(ForbiddenError):
            asyncio.run(ai_job_service.get_ai_job({"id": "user_1"}, "job_1"))


class ListProjectAiJobsTests(unittest.TestCase):
    @patch("app.features.ai_job.db.list_project_ai_jobs", new_callable=AsyncMock)
    def test_success(self, mock_list):
        mock_list.return_value = [{"id": "job_1"}]
        result = asyncio.run(ai_job_service.list_project_ai_jobs({"id": "user_1"}, "proj_1"))
        self.assertEqual(len(result), 1)

    @patch("app.features.ai_job.db.list_project_ai_jobs", new_callable=AsyncMock)
    def test_project_not_found_raises(self, mock_list):
        mock_list.return_value = None
        with self.assertRaises(NotFoundError):
            asyncio.run(ai_job_service.list_project_ai_jobs({"id": "user_1"}, "proj_missing"))


if __name__ == "__main__":
    unittest.main()
