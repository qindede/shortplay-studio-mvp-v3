from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from app.features.errors import InsufficientPointsError, NotFoundError, ServiceUnavailableError
from app.features.storyboard import service as storyboard_service


class GenerateStoryboardTests(unittest.TestCase):
    @patch("app.features.storyboard.db.episode_generation_context")
    def test_episode_not_found_raises(self, mock_ctx):
        mock_ctx.return_value = None
        with self.assertRaises(NotFoundError):
            storyboard_service.generate_storyboard({"id": "user_1"}, "ep_missing")

    @patch("app.features.storyboard.service._run_paid_generation")
    @patch("app.features.storyboard.db.save_storyboard")
    @patch("app.features.storyboard.db.episode_generation_context")
    def test_storyboard_not_found_inside_work_raises(self, mock_ctx, mock_save, mock_run):
        mock_ctx.return_value = {
            "project": {"id": "proj_1"},
            "episode": {"id": "ep_1", "title": "test"},
            "assets": [],
        }
        mock_save.return_value = None

        def run_side_effect(user, cost, scene, desc, jtype, provider, work, **kwargs):
            return work({"id": "job_1"})

        mock_run.side_effect = run_side_effect

        with self.assertRaises(NotFoundError):
            storyboard_service.generate_storyboard({"id": "user_1"}, "ep_1")

    @patch("app.features.storyboard.service._run_paid_generation")
    @patch("app.features.storyboard.db.save_storyboard")
    @patch("app.features.storyboard.db.episode_generation_context")
    def test_insufficient_points_inside_work_raises(self, mock_ctx, mock_save, mock_run):
        mock_ctx.return_value = {
            "project": {"id": "proj_1"},
            "episode": {"id": "ep_1", "title": "test"},
            "assets": [],
        }
        mock_save.return_value = {"error": "insufficient_points"}

        def run_side_effect(user, cost, scene, desc, jtype, provider, work, **kwargs):
            return work({"id": "job_1"})

        mock_run.side_effect = run_side_effect

        with self.assertRaises(InsufficientPointsError):
            storyboard_service.generate_storyboard({"id": "user_1"}, "ep_1")


class PrepareStoryboardTests(unittest.TestCase):
    @patch("app.features.storyboard.db.episode_generation_context")
    def test_episode_not_found_raises(self, mock_ctx):
        mock_ctx.return_value = None
        with self.assertRaises(NotFoundError):
            storyboard_service.prepare_storyboard({"id": "user_1"}, "ep_missing")

    @patch("app.features.storyboard.db.episode_generation_context")
    @patch("app.features.points.db.user_has_points")
    def test_insufficient_points_raises(self, mock_has, mock_ctx):
        mock_ctx.return_value = {
            "project": {"id": "proj_1"},
            "episode": {"id": "ep_1"},
            "assets": [],
        }
        mock_has.return_value = False
        with self.assertRaises(InsufficientPointsError):
            storyboard_service.prepare_storyboard({"id": "user_1"}, "ep_1")


class OptimizePromptTests(unittest.TestCase):
    @patch("app.features.storyboard.service.ai_llm.optimize_prompt")
    def test_success(self, mock_optimize):
        mock_optimize.return_value = "优化后的提示词"
        result = storyboard_service.optimize_prompt("原始", "上下文", "项目名")
        self.assertEqual(result["optimized"], "优化后的提示词")

    @patch("app.features.storyboard.service.ai_llm.optimize_prompt")
    def test_ai_error_raises_service_unavailable(self, mock_optimize):
        from app.ai.errors import AIError

        class ProviderError(AIError):
            public_message = "服务不可用"

        mock_optimize.side_effect = ProviderError()
        with self.assertRaises(ServiceUnavailableError):
            storyboard_service.optimize_prompt("原始", "上下文", "项目名")


if __name__ == "__main__":
    unittest.main()
