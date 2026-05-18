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


if __name__ == "__main__":
    unittest.main()
