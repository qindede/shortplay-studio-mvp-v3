from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.features.errors import BadRequestError, InsufficientPointsError, NotFoundError
from app.features.asset import service as asset_service


class ListAssetsTests(unittest.TestCase):
    @patch("app.features.asset.db.list_assets", new_callable=AsyncMock)
    def test_project_not_found_raises(self, mock_list):
        mock_list.return_value = None
        with self.assertRaises(NotFoundError):
            asyncio.run(asset_service.list_assets({"id": "user_1"}, "proj_missing"))


class GetAssetTests(unittest.TestCase):
    @patch("app.features.asset.db.get_asset", new_callable=AsyncMock)
    def test_not_found_raises(self, mock_get):
        mock_get.return_value = None
        with self.assertRaises(NotFoundError):
            asyncio.run(asset_service.get_asset({"id": "user_1"}, "asset_missing"))


class CreateAssetTests(unittest.TestCase):
    @patch("app.features.asset.db.create_asset", new_callable=AsyncMock)
    def test_project_not_found_raises(self, mock_create):
        mock_create.return_value = None
        with self.assertRaises(NotFoundError):
            payload = MagicMock()
            payload.type = "character"
            payload.name = "角色A"
            asyncio.run(asset_service.create_asset({"id": "user_1"}, "proj_missing", payload))

    @patch("app.features.asset.db.create_asset", new_callable=AsyncMock)
    def test_insufficient_points_raises(self, mock_create):
        mock_create.return_value = {"error": "insufficient_points"}
        with self.assertRaises(InsufficientPointsError):
            payload = MagicMock()
            payload.type = "character"
            payload.name = "角色A"
            asyncio.run(asset_service.create_asset({"id": "user_1"}, "proj_1", payload))


class StartVoiceCloneTests(unittest.TestCase):
    def test_no_consent_raises(self):
        payload = MagicMock()
        payload.consent = False
        with self.assertRaises(BadRequestError):
            asyncio.run(asset_service.start_voice_clone({"id": "user_1"}, "asset_1", payload))

    @patch("app.features.asset.service.get_asset", new_callable=AsyncMock)
    def test_no_voice_url_raises(self, mock_get):
        mock_get.return_value = {"id": "asset_1", "voice_url": None}
        payload = MagicMock()
        payload.consent = True
        payload.voice_url = None
        with self.assertRaises(BadRequestError):
            asyncio.run(asset_service.start_voice_clone({"id": "user_1"}, "asset_1", payload))

    @patch("app.features.asset.service.get_asset", new_callable=AsyncMock)
    def test_non_upload_voice_url_raises(self, mock_get):
        mock_get.return_value = {"id": "asset_1", "voice_url": "https://external.com/voice.wav"}
        payload = MagicMock()
        payload.consent = True
        payload.voice_url = None
        with self.assertRaises(BadRequestError):
            asyncio.run(asset_service.start_voice_clone({"id": "user_1"}, "asset_1", payload))


class UpdateAssetTests(unittest.TestCase):
    @patch("app.features.asset.db.update_asset", new_callable=AsyncMock)
    def test_not_found_raises(self, mock_update):
        mock_update.return_value = None
        payload = MagicMock()
        payload.model_dump.return_value = {}
        with self.assertRaises(NotFoundError):
            asyncio.run(asset_service.update_asset({"id": "user_1"}, "asset_missing", payload))


class DeleteAssetTests(unittest.TestCase):
    @patch("app.features.asset.db.delete_asset", new_callable=AsyncMock)
    def test_not_found_raises(self, mock_delete):
        mock_delete.return_value = False
        with self.assertRaises(NotFoundError):
            asyncio.run(asset_service.delete_asset({"id": "user_1"}, "asset_missing"))


if __name__ == "__main__":
    unittest.main()
