from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from backend.auth import AuthService
from backend.database import Database
from backend.tutorial_content import C_EXERCISE_TOPICS
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice, tutorial_practice_public


class TutorialExercisesTestCase(unittest.TestCase):
    def test_each_c_topic_has_a_deterministic_practice_variant(self) -> None:
        for topic in set(C_EXERCISE_TOPICS.values()):
            first = tutorial_practice("c", topic, 3)
            repeated = tutorial_practice("c", topic, 3)
            self.assertIsNotNone(first, topic)
            self.assertEqual(first, repeated)
            assert first is not None
            self.assertTrue(first["starterSource"])
            self.assertIn("expectedOutput", first)

    def test_public_practice_hides_expected_output_and_evaluation_uses_server_value(self) -> None:
        exercise = tutorial_practice("c", "arrays", 1)
        assert exercise is not None
        public = tutorial_practice_public(exercise)
        self.assertNotIn("expectedOutput", public)

        correct = evaluate_tutorial_practice(
            exercise,
            {"compiled": True, "compile": {}, "run": {"exitCode": 0, "stdout": exercise["expectedOutput"]}},
            exercise["stdin"],
        )
        self.assertEqual(correct["status"], "passed")
        incorrect = evaluate_tutorial_practice(
            exercise,
            {"compiled": True, "compile": {}, "run": {"exitCode": 0, "stdout": "0\n"}},
            exercise["stdin"],
        )
        self.assertEqual(incorrect["status"], "output_mismatch")
        other_input = evaluate_tutorial_practice(
            exercise,
            {"compiled": True, "compile": {}, "run": {"exitCode": 0, "stdout": exercise["expectedOutput"]}},
            "iný vstup\n",
        )
        self.assertEqual(other_input["status"], "unchecked")

    def test_builtin_c_page_resolves_its_practice_from_the_content_topic(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="poznamkovnik-practice-", dir="/tmp"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        database = Database(root / "poznamkovnik.sqlite3")
        database.initialize()
        user, _ = AuthService(database).setup("Tester", "testovacie-heslo")
        language = next(item for item in database.list_tutorial_languages(user["id"]) if item["code"] == "c")
        detail = database.tutorial_language_detail(user["id"], language["id"])
        page = next(item for item in detail["pages"] if item["title"] == "Polia a ukazovatele")

        practice = database.tutorial_page_practice(user["id"], page["id"], 2)

        self.assertEqual(practice["pageId"], page["id"])
        self.assertEqual(practice["topic"], "arrays")
        self.assertEqual(practice["variant"], 2)

