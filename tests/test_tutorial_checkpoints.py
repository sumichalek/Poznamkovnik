from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from backend.auth import AuthService
from backend.database import Database
from backend.tutorial_checkpoints import TUTORIAL_CHECKPOINTS, evaluate_tutorial_checkpoint, tutorial_checkpoint_public
from backend.tutorial_content import C_CHECKPOINT_IDS


class TutorialCheckpointsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="poznamkovnik-checkpoints-", dir="/tmp"))
        self.database = Database(self.root / "poznamkovnik.sqlite3")
        self.database.initialize()
        self.user, _ = AuthService(self.database).setup("Tester", "testovacie-heslo")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_public_checkpoint_hides_solution_and_all_c_lessons_have_a_valid_question(self) -> None:
        available = {checkpoint["id"]: checkpoint for checkpoint in TUTORIAL_CHECKPOINTS["c"]}
        self.assertEqual(set(C_CHECKPOINT_IDS.values()), set(available))
        for checkpoint in available.values():
            public = tutorial_checkpoint_public(checkpoint)
            self.assertIsNotNone(public)
            assert public is not None
            self.assertNotIn("correctOptionId", public)
            self.assertNotIn("correctFeedback", public)
            self.assertNotIn("incorrectFeedback", public)
            self.assertGreaterEqual(len(public["options"]), 2)

    def test_checkpoint_answer_is_persisted_and_survives_backup_restore(self) -> None:
        language, page = self._page("Funkcie, rozsah a návratové hodnoty")
        self.assertEqual(page["checkpoint"]["id"], "c-pass-by-value")

        wrong = self.database.answer_tutorial_checkpoint(self.user["id"], page["id"], {"optionId": "b"})
        self.assertFalse(wrong["isCorrect"])
        self.assertEqual(wrong["attemptCount"], 1)
        correct = self.database.answer_tutorial_checkpoint(self.user["id"], page["id"], {"optionId": "a"})
        self.assertTrue(correct["isCorrect"])
        self.assertEqual(correct["attemptCount"], 2)

        refreshed = self._detail(language["id"])
        refreshed_page = next(item for item in refreshed["pages"] if item["id"] == page["id"])
        self.assertTrue(refreshed_page["checkpoint"]["isCorrect"])
        self.assertEqual(refreshed_page["checkpoint"]["lastOptionId"], "a")
        self.assertEqual(refreshed_page["checkpoint"]["attemptCount"], 2)

        snapshot = self.database.backup_snapshot(self.user["id"])
        self.assertEqual(snapshot["tutorialCheckpointAttempts"][0]["page_id"], page["id"])
        restored_database = Database(self.root / "restored.sqlite3")
        restored_database.initialize()
        restored_user, _ = AuthService(restored_database).setup("Obnovený tester", "testovacie-heslo")
        restored_database.restore_backup_snapshot(restored_user["id"], snapshot)
        restored_language = next(
            item for item in restored_database.list_tutorial_languages(restored_user["id"]) if item["code"] == "c"
        )
        restored_detail = restored_database.tutorial_language_detail(restored_user["id"], restored_language["id"])
        restored_page = next(item for item in restored_detail["pages"] if item["id"] == page["id"])
        self.assertTrue(restored_page["checkpoint"]["isCorrect"])
        self.assertEqual(restored_page["checkpoint"]["attemptCount"], 2)

    def test_invalid_option_is_rejected_and_correct_feedback_is_returned_only_after_answer(self) -> None:
        checkpoint = TUTORIAL_CHECKPOINTS["c"][0]
        result = evaluate_tutorial_checkpoint(checkpoint, "b")
        self.assertTrue(result["isCorrect"])
        self.assertIn("Správne", result["feedback"])
        with self.assertRaises(ValueError):
            evaluate_tutorial_checkpoint(checkpoint, "neexistuje")

    def _detail(self, language_id: str):
        return self.database.tutorial_language_detail(self.user["id"], language_id)

    def _page(self, title: str):
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "c")
        detail = self._detail(language["id"])
        return language, next(item for item in detail["pages"] if item["title"] == title)
