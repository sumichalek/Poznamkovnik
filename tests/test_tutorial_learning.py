from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from backend.auth import AuthService
from backend.database import Database
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import tutorial_practice_public


class TutorialLearningTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="poznamkovnik-tutorial-", dir="/tmp"))
        self.database = Database(self.root / "poznamkovnik.sqlite3")
        self.database.initialize()
        self.user, _ = AuthService(self.database).setup("Tester", "testovacie-heslo")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_page_progress_can_be_completed_reset_and_backed_up(self) -> None:
        language, page = self._c_lesson()
        self.assertEqual(page["progressStatus"], "not_started")

        saved = self.database.save_tutorial_page_progress(self.user["id"], page["id"], {"status": "completed"})
        self.assertEqual(saved["status"], "completed")
        refreshed = self._tutorial_page(language["id"], page["id"])
        self.assertEqual(refreshed["progressStatus"], "completed")

        snapshot = self.database.backup_snapshot(self.user["id"])
        self.assertEqual(snapshot["tutorialPageProgress"], [{
            "page_id": page["id"], "status": "completed", "updated_at": saved["updatedAt"]
        }])

        restored_database = Database(self.root / "restored.sqlite3")
        restored_database.initialize()
        restored_user, _ = AuthService(restored_database).setup("Obnovený tester", "testovacie-heslo")
        restored_database.restore_backup_snapshot(restored_user["id"], snapshot)
        restored_language = next(
            item for item in restored_database.list_tutorial_languages(restored_user["id"]) if item["code"] == "c"
        )
        restored_detail = restored_database.tutorial_language_detail(restored_user["id"], restored_language["id"])
        restored_page = next(item for item in restored_detail["pages"] if item["id"] == page["id"])
        self.assertEqual(restored_page["progressStatus"], "completed")

        reset = self.database.save_tutorial_page_progress(self.user["id"], page["id"], {"status": "not_started"})
        self.assertEqual(reset["status"], "not_started")
        self.assertEqual(self._tutorial_page(language["id"], page["id"])["progressStatus"], "not_started")

    def test_typed_content_blocks_are_normalized_for_future_lessons(self) -> None:
        language, _ = self._c_lesson()
        chapter = self.database.create_tutorial_page(
            self.user["id"],
            language["id"],
            {"id": "typed-chapter", "kind": "chapter", "title": "Bloková kapitola"},
        )
        lesson = self.database.create_tutorial_page(
            self.user["id"],
            language["id"],
            {
                "id": "typed-lesson",
                "kind": "lesson",
                "parentId": chapter["id"],
                "title": "Bloková lekcia",
                "content": {
                    "goals": ["Rozlíšiť odsek a blok kódu", ""],
                    "blocks": [
                        {"type": "heading", "text": "Malý nadpis"},
                        {"type": "paragraph", "text": "Vysvetlenie."},
                        {"type": "list", "items": ["Prvý krok", ""]},
                        {"type": "callout", "tone": "warning", "text": "Dávaj pozor."},
                        {"type": "code", "language": "c", "title": "Príklad", "source": "int main(void) { return 0; }"},
                        {"type": "checkpoint", "prompt": "Čo robí návratová hodnota?"},
                        {"type": "unknown", "text": "Toto sa nemá uložiť."},
                    ],
                },
            },
        )

        page = self._tutorial_page(language["id"], lesson["id"])
        self.assertEqual(page["content"]["goals"], ["Rozlíšiť odsek a blok kódu"])
        self.assertEqual(
            [block["type"] for block in page["content"]["blocks"]],
            ["heading", "paragraph", "list", "callout", "code", "checkpoint"],
        )
        self.assertEqual(page["content"]["blocks"][3]["tone"], "warning")
        self.assertEqual(page["content"]["blocks"][4]["language"], "c")
        self.assertEqual(page["content"]["sections"][0]["title"], "Malý nadpis")
        self.assertEqual(page["content"]["sections"][0]["paragraphs"], ["Vysvetlenie."])
        self.assertEqual(page["content"]["sections"][0]["bullets"], ["Prvý krok"])
        self.assertEqual(page["content"]["sections"][0]["callout"], "Dávaj pozor.")

    def test_builtin_c_lessons_expose_concrete_learning_goals(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "c")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        first_program = next(page for page in detail["pages"] if page["title"] == "Prvý program a preklad")
        self.assertGreaterEqual(len(first_program["content"]["goals"]), 2)

    def test_builtin_c_foundations_keep_explanatory_depth(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "c")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        values = next(page for page in detail["pages"] if page["title"] == "Typy, premenné a výrazy")
        paragraphs = [block["text"] for block in values["content"]["blocks"] if block["type"] == "paragraph"]

        self.assertGreaterEqual(len(paragraphs), 5)
        self.assertTrue(all(len(paragraph.split()) >= 12 for paragraph in paragraphs))

    def test_c_values_explains_type_families_and_when_to_use_them(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "c")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        values = next(page for page in detail["pages"] if page["title"] == "Typy, premenné a výrazy")
        blocks = values["content"]["blocks"]
        text = "\n".join(
            block.get("text", "") + "\n" + "\n".join(block.get("items", []))
            for block in blocks
        )

        for term in ("int", "unsigned", "double", "bool", "void", "size_t", "uint32_t"):
            self.assertIn(term, text)

    def test_builtin_c_first_unit_uses_guided_examples_before_practice(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "c")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        titles = {
            "Prvý program a preklad",
            "Typy, premenné a výrazy",
            "Operátory, priority a výrazy",
            "Podmienky a cykly",
            "Funkcie, rozsah a návratové hodnoty",
        }
        lessons = [page for page in detail["pages"] if page["title"] in titles]

        self.assertEqual({page["title"] for page in lessons}, titles)
        for page in lessons:
            block_types = [block["type"] for block in page["content"]["blocks"]]
            self.assertGreaterEqual(block_types.count("heading"), 3, page["title"])
            self.assertGreaterEqual(block_types.count("paragraph"), 3, page["title"])
            self.assertIn("code", block_types, page["title"])

    def test_builtin_c_data_foundations_explain_the_model_before_practice(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "c")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        titles = {
            "Rozsah, životnosť a const",
            "Polia a ukazovatele",
            "Ukazovatele a zmena objektov",
            "Reťazce",
            "struct, enum a typedef",
        }
        lessons = [page for page in detail["pages"] if page["title"] in titles]

        self.assertEqual({page["title"] for page in lessons}, titles)
        for page in lessons:
            block_types = [block["type"] for block in page["content"]["blocks"]]
            self.assertGreaterEqual(block_types.count("heading"), 4, page["title"])
            self.assertGreaterEqual(block_types.count("paragraph"), 5, page["title"])
            self.assertIn("code", block_types, page["title"])
            self.assertIn("callout", block_types, page["title"])

    def test_c_memory_update_preserves_notes_drafts_progress_and_all_content_blocks(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "c")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        memory = next(page for page in detail["pages"] if page["title"] == "Dynamická pamäť")
        example = next(item for item in detail["examples"] if item["title"] == "Alokácia a uvoľnenie poľa")
        draft = "#include <stdio.h>\nint main(void) { puts(\"My experiment\"); }\n"
        self.database.save_tutorial_note(self.user["id"], memory["id"], {"content": "My allocation notes."})
        self.database.save_tutorial_example_draft(self.user["id"], example["id"], {"source": draft, "stdin": "42\n"})
        self.database.save_tutorial_page_progress(self.user["id"], memory["id"], {"status": "completed"})
        self.database.answer_tutorial_checkpoint(self.user["id"], memory["id"], {"optionId": "b"})

        new_titles = {
            item["title"] for item in C_EXAMPLES
            if item["key"] in {"grow-buffer", "mask-operations", "checked-add", "const-views", "restrict-copy", "atomic-counter"}
        }
        with self.database.connect() as connection:
            # Simulate the previous seed, not the user's editable content.
            connection.execute(
                "UPDATE tutorial_pages SET content_json = ? WHERE id = ?",
                ('{"lead":"Previous short lesson."}', memory["id"]),
            )
            connection.executemany(
                "DELETE FROM tutorial_examples WHERE id = ?",
                [(item["id"],) for item in detail["examples"] if item["title"] in new_titles],
            )

        refreshed = self.database.tutorial_language_detail(self.user["id"], language["id"])
        repeated = self.database.tutorial_language_detail(self.user["id"], language["id"])
        self.assertEqual(refreshed, repeated)
        self.assertEqual(len(refreshed["examples"]), len(detail["examples"]))
        updated_memory = next(page for page in refreshed["pages"] if page["id"] == memory["id"])
        self.assertEqual(updated_memory["createdAt"], memory["createdAt"])
        self.assertEqual(updated_memory["note"], "My allocation notes.")
        self.assertEqual(updated_memory["progressStatus"], "completed")
        self.assertTrue(updated_memory["checkpoint"]["isCorrect"])
        self.assertEqual(updated_memory["checkpoint"]["attemptCount"], 1)
        updated_example = next(item for item in refreshed["examples"] if item["id"] == example["id"])
        self.assertEqual(updated_example["source"], example["source"])
        self.assertEqual(updated_example["draftSource"], draft)
        self.assertEqual(updated_example["draftStdin"], "42\n")

        for seed in C_PAGES:
            if seed["key"] not in {"bits", "memory", "qualifiers"}:
                continue
            page = next(item for item in refreshed["pages"] if item["title"] == seed["title"])
            expected = self.database._tutorial_content(seed["content"], "")["blocks"]
            self.assertEqual(page["content"]["blocks"], expected)
            code_sources = [
                block["source"] for block in page["content"]["blocks"] if block["type"] == "code"
            ]
            runnable_sources = [
                item["source"].strip() for item in refreshed["examples"] if item["pageId"] == page["id"]
            ]
            self.assertTrue(all(source in runnable_sources for source in code_sources))
        qualifiers = next(page for page in refreshed["pages"] if page["title"].startswith("const, volatile"))
        self.assertEqual(qualifiers["checkpoint"]["id"], "c-atomic-increment")

    def test_c_updated_lessons_reseed_without_losing_learning_state(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "c")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        seeds = [page for page in C_PAGES if page["key"] in {
            "preprocessor", "build", "io", "errors", "safety", "testing", "string-reference", "stdlib-reference",
        }]
        saved = []
        for seed in seeds:
            page = next(item for item in detail["pages"] if item["title"] == seed["title"])
            example = next(item for item in detail["examples"] if item["pageId"] == page["id"])
            note = "Notes for " + seed["key"]
            draft = example["source"] + "\n/* My experiment. */\n"
            self.database.save_tutorial_note(self.user["id"], page["id"], {"content": note})
            self.database.save_tutorial_example_draft(self.user["id"], example["id"], {"source": draft, "stdin": "input\n"})
            self.database.save_tutorial_page_progress(self.user["id"], page["id"], {"status": "completed"})
            correct = "b" if seed["key"] in {"preprocessor", "errors", "safety", "string-reference", "stdlib-reference"} else "a"
            answer = self.database.answer_tutorial_checkpoint(self.user["id"], page["id"], {"optionId": correct})
            self.assertTrue(answer["isCorrect"])
            with self.database.connect() as connection:
                connection.execute(
                    "UPDATE tutorial_pages SET content_json = ? WHERE id = ?",
                    ('{"lead":"Previous content."}', page["id"]),
                )
                connection.execute(
                    "UPDATE tutorial_examples SET source = ? WHERE id = ?",
                    ("/* Previous built-in example. */", example["id"]),
                )
            saved.append((seed, page, example, note, draft))

        refreshed = self.database.tutorial_language_detail(self.user["id"], language["id"])
        self.assertEqual(refreshed, self.database.tutorial_language_detail(self.user["id"], language["id"]))
        self.assertEqual(len(detail["examples"]), len(refreshed["examples"]))
        for seed, old_page, old_example, note, draft in saved:
            page = next(item for item in refreshed["pages"] if item["id"] == old_page["id"])
            example = next(item for item in refreshed["examples"] if item["id"] == old_example["id"])
            self.assertEqual(page["note"], note)
            self.assertEqual(page["progressStatus"], "completed")
            self.assertEqual(page["createdAt"], old_page["createdAt"])
            self.assertTrue(page["checkpoint"]["isCorrect"])
            self.assertEqual(page["checkpoint"]["attemptCount"], 1)
            self.assertEqual(example["source"], old_example["source"])
            self.assertEqual(example["draftSource"], draft)
            self.assertEqual(example["draftStdin"], "input\n")
            self.assertEqual(
                page["content"]["blocks"],
                self.database._tutorial_content(seed["content"], "")["blocks"],
            )
            practice = self.database.tutorial_page_practice(self.user["id"], page["id"], 0)
            self.assertEqual(practice["topic"], seed["key"])
            self.assertNotIn("expectedOutput", tutorial_practice_public(practice))

    def test_builtin_c_lessons_keep_a_complete_teaching_frame(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "c")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        lessons = [page for page in detail["pages"] if page["kind"] == "lesson"]

        self.assertGreaterEqual(len(lessons), 20)
        for page in lessons:
            pedagogy = page["content"]["pedagogy"]
            self.assertGreaterEqual(len(pedagogy["context"].split()), 8, page["title"])
            self.assertGreaterEqual(len(pedagogy["priorKnowledge"]), 1, page["title"])
            self.assertGreaterEqual(len(pedagogy["keyIdea"].split()), 8, page["title"])
            self.assertGreaterEqual(len(pedagogy["transfer"].split()), 8, page["title"])

    def test_c_includes_advanced_language_and_portability_lessons_with_examples(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "c")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        titles = {
            "Funkčné ukazovatele, callbacky a variadické funkcie",
            "const, volatile, restrict a atomické operácie",
            "Preprocesor, makrá a podmienený preklad",
            "Prenositeľnosť a presné pravidlá C",
        }
        lessons = [page for page in detail["pages"] if page["title"] in titles]

        self.assertEqual({page["title"] for page in lessons}, titles)
        self.assertTrue(all(len(page["content"]["goals"]) >= 2 for page in lessons))
        self.assertTrue(all(page["content"]["blocks"] for page in lessons))
        example_page_ids = {example["pageId"] for example in detail["examples"]}
        self.assertTrue(all(page["id"] in example_page_ids for page in lessons))

    def test_builtin_python_course_has_core_lessons_goals_and_examples(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "python")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        titles = {
            "Prvý program, spustenie a odsadenie",
            "Funkcie, parametre a rozsah mien",
            "list, tuple, dict a set",
            "Výnimky, súbory, cesty a JSON",
            "asyncio, úlohy a rušenie",
        }
        lessons = [page for page in detail["pages"] if page["title"] in titles]

        self.assertEqual({page["title"] for page in lessons}, titles)
        self.assertGreaterEqual(len(detail["pages"]), 16)
        self.assertTrue(all(len(page["content"]["goals"]) >= 2 for page in lessons))
        self.assertTrue(all(page["content"]["blocks"] for page in lessons))
        example_page_ids = {example["pageId"] for example in detail["examples"]}
        self.assertTrue(all(page["id"] in example_page_ids for page in lessons))
        example = next(item for item in detail["examples"] if item["title"] == "Pozdrav ako spustiteľný skript")
        self.assertEqual(example["language"], "python")
        self.assertEqual(self.database.tutorial_example(self.user["id"], example["id"])["language"], "python")

    def test_builtin_javascript_course_has_core_lessons_goals_and_examples(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "javascript")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        titles = {
            "Hodnoty, konverzie a porovnanie",
            "let, const, scope a closures",
            "Array, Map, Set a Object",
            "Event loop, Promise a async/await",
            "Testy, ladenie, bezpečnosť a výkon",
        }
        lessons = [page for page in detail["pages"] if page["title"] in titles]

        self.assertEqual({page["title"] for page in lessons}, titles)
        self.assertGreaterEqual(len(detail["pages"]), 15)
        self.assertTrue(all(len(page["content"]["goals"]) >= 2 for page in lessons))
        self.assertTrue(all(page["content"]["blocks"] for page in lessons))
        example_page_ids = {example["pageId"] for example in detail["examples"]}
        self.assertTrue(all(page["id"] in example_page_ids for page in lessons))
        example = next(item for item in detail["examples"] if item["title"] == "Dve nezávislé asynchrónne úlohy")
        self.assertEqual(example["language"], "javascript")
        self.assertEqual(self.database.tutorial_example(self.user["id"], example["id"])["language"], "javascript")

    def test_builtin_cpp_course_has_core_lessons_goals_and_examples(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "cpp")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        titles = {
            "RAII, move a smart pointery",
            "Kontajnery a dátové modely",
            "Algoritmy, iterátory a ranges",
            "Triedy, invariants a polymorfizmus",
            "CMake, testy a sanitizéry",
        }
        lessons = [page for page in detail["pages"] if page["title"] in titles]

        self.assertEqual({page["title"] for page in lessons}, titles)
        self.assertGreaterEqual(len(detail["pages"]), 16)
        self.assertTrue(all(len(page["content"]["goals"]) >= 2 for page in lessons))
        self.assertTrue(all(page["content"]["blocks"] for page in lessons))
        example_page_ids = {example["pageId"] for example in detail["examples"]}
        self.assertTrue(all(page["id"] in example_page_ids for page in lessons if page["title"] != "CMake, testy a sanitizéry"))
        example = next(item for item in detail["examples"] if item["title"] == "Jediný vlastník dynamického objektu")
        self.assertEqual(example["language"], "cpp")
        self.assertEqual(self.database.tutorial_example(self.user["id"], example["id"])["language"], "cpp")

    def test_builtin_csharp_course_has_core_lessons_goals_and_examples(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "csharp")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        titles = {
            "Typy, nullability a pattern matching",
            "Triedy, records, structy a enumy",
            "Rozhrania, generiká a polymorfizmus",
            "Kolekcie, LINQ a odložené vykonanie",
            "Task, async/await a rušenie",
        }
        lessons = [page for page in detail["pages"] if page["title"] in titles]

        self.assertEqual({page["title"] for page in lessons}, titles)
        self.assertGreaterEqual(len(detail["pages"]), 15)
        self.assertTrue(all(len(page["content"]["goals"]) >= 2 for page in lessons))
        self.assertTrue(all(page["content"]["blocks"] for page in lessons))
        example_page_ids = {example["pageId"] for example in detail["examples"]}
        self.assertTrue(all(page["id"] in example_page_ids for page in lessons))
        example = next(item for item in detail["examples"] if item["title"] == "Filter a transformácia cez LINQ")
        self.assertEqual(example["language"], "csharp")
        self.assertEqual(self.database.tutorial_example(self.user["id"], example["id"])["language"], "csharp")

    def test_builtin_ruby_course_has_core_lessons_goals_and_examples(self) -> None:
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "ruby")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        titles = {
            "Metódy, keyword argumenty a bloky",
            "Triedy, stav a invarianty",
            "Moduly, mixiny a hľadanie metód",
            "Array, Hash a Enumerable",
            "Výnimky, súbory a bezpečné hranice",
        }
        lessons = [page for page in detail["pages"] if page["title"] in titles]

        self.assertEqual({page["title"] for page in lessons}, titles)
        self.assertGreaterEqual(len(detail["pages"]), 13)
        self.assertTrue(all(len(page["content"]["goals"]) >= 2 for page in lessons))
        self.assertTrue(all(page["content"]["blocks"] for page in lessons))
        example_page_ids = {example["pageId"] for example in detail["examples"]}
        self.assertTrue(all(page["id"] in example_page_ids for page in lessons))
        example = next(item for item in detail["examples"] if item["title"] == "Mixin s pomenovanou schopnosťou")
        self.assertEqual(example["language"], "ruby")
        self.assertEqual(self.database.tutorial_example(self.user["id"], example["id"])["language"], "ruby")

    def _c_lesson(self):
        language = next(item for item in self.database.list_tutorial_languages(self.user["id"]) if item["code"] == "c")
        detail = self.database.tutorial_language_detail(self.user["id"], language["id"])
        return language, next(page for page in detail["pages"] if page["kind"] == "lesson")

    def _tutorial_page(self, language_id: str, page_id: str):
        detail = self.database.tutorial_language_detail(self.user["id"], language_id)
        return next(page for page in detail["pages"] if page["id"] == page_id)
