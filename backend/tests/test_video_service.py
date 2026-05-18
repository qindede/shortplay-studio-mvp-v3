from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from app.features.errors import BadRequestError, NotFoundError, ServiceUnavailableError
from app.features.video import service as video_service


class GenerateVideoForShotTests(unittest.TestCase):
    @patch("app.features.shot.db.shot_generation_context")
    def test_shot_not_found_raises(self, mock_ctx):
        mock_ctx.return_value = None
        with self.assertRaises(NotFoundError):
            video_service.generate_video_for_shot({"id": "user_1"}, "shot_missing")


class GenerateVideosForEpisodeTests(unittest.TestCase):
    @patch("app.features.storyboard.db.episode_generation_context")
    def test_episode_not_found_raises(self, mock_ctx):
        mock_ctx.return_value = None
        with self.assertRaises(NotFoundError):
            video_service.generate_videos_for_episode({"id": "user_1"}, "ep_missing")

    @patch("app.features.storyboard.db.episode_generation_context")
    def test_no_shots_raises(self, mock_ctx):
        mock_ctx.return_value = {"project": {}, "episode": {}, "shots": []}
        with self.assertRaises(NotFoundError):
            video_service.generate_videos_for_episode({"id": "user_1"}, "ep_1")


class ComposeEpisodeTests(unittest.TestCase):
    @patch("app.features.video.db.compose_context")
    def test_episode_not_found_raises(self, mock_ctx):
        mock_ctx.return_value = None
        with self.assertRaises(NotFoundError):
            video_service.compose_episode({"id": "user_1"}, "ep_missing", MagicMock(), lambda _: "url")

    @patch("app.features.video.db.compose_context")
    def test_no_shots_raises(self, mock_ctx):
        mock_ctx.return_value = {"episode": {}, "project": {}, "shots": [], "video_jobs": []}
        with self.assertRaises(BadRequestError):
            video_service.compose_episode({"id": "user_1"}, "ep_1", MagicMock(), lambda _: "url")

    @patch("app.features.video.db.compose_context")
    def test_incomplete_shots_raises(self, mock_ctx):
        mock_ctx.return_value = {
            "episode": {"title": "test"},
            "project": {"id": "proj_1"},
            "shots": [{"id": "s1", "no": 1, "status": "generating"}],
            "video_jobs": [],
        }
        with self.assertRaises(BadRequestError):
            video_service.compose_episode({"id": "user_1"}, "ep_1", MagicMock(), lambda _: "url")


class ComposeVideoFileTests(unittest.TestCase):
    def test_missing_video_url_raises(self):
        tasks = [{"video_url": None}]
        with self.assertRaises(BadRequestError):
            video_service.compose_video_file(tasks)

    def test_non_upload_url_raises(self):
        tasks = [{"video_url": "https://external.com/video.mp4"}]
        with self.assertRaises(BadRequestError):
            video_service.compose_video_file(tasks)

    @patch("app.features.video.service.FFMPEG_PATH", "/nonexistent/ffmpeg")
    @patch("app.features.video.service.storage.get_object")
    def test_ffmpeg_not_found_raises(self, mock_get):
        mock_get.return_value = (b"fake video data", "video/mp4")
        tasks = [{"video_url": "/uploads/test.mp4"}]
        with self.assertRaises(ServiceUnavailableError):
            video_service.compose_video_file(tasks)


class ListVideoJobsWithPollTests(unittest.TestCase):
    @patch("app.features.video.service.SessionLocal")
    def test_episode_not_found_raises(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.scalar.return_value = None
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        with self.assertRaises(NotFoundError):
            video_service.list_video_jobs_with_poll({"id": "user_1"}, "ep_missing")


class GenerateVideoNoDoubleChargeTests(unittest.TestCase):
    """Regression: generate_video_for_shot must create exactly one AiJob and deduct points once."""

    @patch("app.features.video.db.update_job_for_video_shot")
    @patch("app.ai.video.create_video_task", return_value="task_abc")
    @patch("app.features.shot.db.shot_generation_context")
    @patch("app.features.ai_job.db.SessionLocal")
    def test_single_job_single_deduction(self, mock_session_cls, mock_ctx, mock_create, mock_update):
        mock_ctx.return_value = {
            "shot": {"id": "s1", "no": 1, "title": "开场", "duration": 3, "episode_id": "ep1"},
            "episode": {"project_id": "proj1"},
            "assets": [],
        }
        mock_update.return_value = {
            "id": "job_1", "episode_id": "ep1", "shot_id": "s1",
            "title": "开场", "duration": 3, "progress": 0,
            "status": "generating", "provider": "seedance",
            "provider_task_id": "task_abc",
            "preview_url": None, "video_url": None,
            "error": None, "updated_at": "2026-05-18T00:00:00",
        }

        mock_session = MagicMock()
        mock_user = MagicMock()
        mock_user.points = 1000
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

        added = []
        mock_session.add.side_effect = lambda obj: added.append(obj)

        result = video_service.generate_video_for_shot({"id": "user_1"}, "s1")

        # Exactly one AiJob + one PointLedger = 2 adds
        from app.models import AiJob, PointLedger
        jobs = [o for o in added if isinstance(o, AiJob)]
        ledgers = [o for o in added if isinstance(o, PointLedger)]
        self.assertEqual(len(jobs), 1, "must create exactly one AiJob")
        self.assertEqual(len(ledgers), 1, "must create exactly one deduction ledger")
        job = jobs[0]
        self.assertEqual(job.type, "video_shot")
        self.assertEqual(job.status, "running")
        self.assertEqual(job.cost_points, 30)  # 3s * 10 pts/s

        # update_job_for_video_shot called once with the created job
        mock_update.assert_called_once()
        self.assertEqual(mock_update.call_args[0][0], job.id)

        # Returned status is UI-semantic
        self.assertEqual(result["status"], "generating")


if __name__ == "__main__":
    unittest.main()
