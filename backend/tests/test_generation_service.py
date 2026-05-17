from __future__ import annotations

import unittest
from unittest.mock import patch

from app.ai.errors import AIError
from app.services import generation_service


class FakeStorage:
    jobs: list[dict] = []
    completed: list[tuple[str, dict]] = []
    refunded: list[tuple[str, str]] = []

    @classmethod
    def reset(cls) -> None:
        cls.jobs = []
        cls.completed = []
        cls.refunded = []

    @classmethod
    def start_paid_ai_job(cls, user: dict, cost: int, scene: str, description: str, job_type: str, provider: str, **links) -> dict:
        job = {
            "id": f"job_{len(cls.jobs) + 1}",
            "user_id": user["id"],
            "cost_points": cost,
            "scene": scene,
            "description": description,
            "type": job_type,
            "provider": provider,
            **links,
        }
        cls.jobs.append(job)
        return job

    @classmethod
    def complete_ai_job(cls, job_id: str, output: dict | None = None) -> dict:
        cls.completed.append((job_id, output or {}))
        return {"id": job_id, "status": "succeeded", "output_json": output or {}}

    @classmethod
    def fail_ai_job_with_refund(cls, job_id: str, error: str) -> dict:
        cls.refunded.append((job_id, error))
        return {"id": job_id, "status": "failed", "error": error}


class PaidGenerationLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeStorage.reset()
        self.patches = [
            patch("app.features.ai_job.service.start_paid_ai_job", FakeStorage.start_paid_ai_job),
            patch("app.features.ai_job.service.complete_ai_job", FakeStorage.complete_ai_job),
            patch("app.features.ai_job.service.fail_ai_job_with_refund", FakeStorage.fail_ai_job_with_refund),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()

    def test_success_completes_paid_job(self) -> None:
        def work(job: dict):
            return {"ok": True, "job_id": job["id"]}, {"items": 2}

        result = generation_service._run_paid_generation(
            {"id": "user_1"},
            20,
            "测试场景",
            "测试描述",
            "outline",
            "minimax",
            work,
            project_id="proj_1",
        )

        self.assertEqual(result, {"ok": True, "job_id": "job_1"})
        self.assertEqual(len(FakeStorage.jobs), 1)
        self.assertEqual(FakeStorage.jobs[0]["project_id"], "proj_1")
        self.assertEqual(FakeStorage.completed, [("job_1", {"items": 2})])
        self.assertEqual(FakeStorage.refunded, [])

    def test_ai_error_refunds_and_does_not_complete(self) -> None:
        class ProviderDown(AIError):
            public_message = "供应商不可用"

        def work(job: dict):
            raise ProviderDown()

        with self.assertRaises(ProviderDown):
            generation_service._run_paid_generation(
                {"id": "user_1"},
                20,
                "测试场景",
                "测试描述",
                "outline",
                "minimax",
                work,
            )

        self.assertEqual(FakeStorage.completed, [])
        self.assertEqual(FakeStorage.refunded, [("job_1", "供应商不可用")])

    def test_unexpected_error_refunds_with_fallback_message(self) -> None:
        def work(job: dict):
            raise RuntimeError()

        with self.assertRaises(RuntimeError):
            generation_service._run_paid_generation(
                {"id": "user_1"},
                20,
                "测试场景",
                "测试描述",
                "compose",
                "ffmpeg",
                work,
                failure_message="合成失败",
            )

        self.assertEqual(FakeStorage.completed, [])
        self.assertEqual(FakeStorage.refunded, [("job_1", "合成失败")])

    def test_running_generation_can_skip_completion(self) -> None:
        def work(job: dict):
            return {"task_id": "task_1"}, {"ignored": True}

        result = generation_service._run_paid_generation(
            {"id": "user_1"},
            30,
            "生成镜头视频",
            "测试视频",
            "video_shot",
            "seedance",
            work,
            complete=False,
        )

        self.assertEqual(result, {"task_id": "task_1"})
        self.assertEqual(len(FakeStorage.jobs), 1)
        self.assertEqual(FakeStorage.completed, [])
        self.assertEqual(FakeStorage.refunded, [])


if __name__ == "__main__":
    unittest.main()
