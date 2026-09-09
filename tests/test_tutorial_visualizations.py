from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from backend.auth import AuthService
from backend.database import Database
from backend.tutorial_curriculum import language_curriculum
from backend.tutorial_visualizations import visualization_models_for_language


class TutorialVisualizationsTestCase(unittest.TestCase):
    def test_c_models_cover_the_declared_visualization_candidates(self) -> None:
        candidates = {item["id"] for item in language_curriculum("c")["visualizations"]}
        models = visualization_models_for_language("c")

        self.assertEqual({model["id"] for model in models}, candidates)
        for model in models:
            self.assertTrue(model["title"])
            self.assertTrue(model["summary"])
            self.assertTrue(model["simplification"])
            self.assertGreaterEqual(len(model["steps"]), 3)
            for step in model["steps"]:
                self.assertTrue(step["title"])
                self.assertTrue(step["code"])
                self.assertTrue(step["explanation"])
                self.assertTrue(step["groups"])
                self.assertTrue(all(group["label"] and group["rows"] for group in step["groups"]))

    def test_c_pointer_page_exposes_its_model_in_the_reader_payload(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="poznamkovnik-visualizations-", dir="/tmp"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        database = Database(root / "poznamkovnik.sqlite3")
        database.initialize()
        user, _ = AuthService(database).setup("Tester", "testovacie-heslo")
        language = next(item for item in database.list_tutorial_languages(user["id"]) if item["code"] == "c")

        detail = database.tutorial_language_detail(user["id"], language["id"])
        pointer_page = next(page for page in detail["pages"] if page["title"] == "Polia a ukazovatele")

        self.assertEqual(pointer_page["content"]["visualizationIds"], ["c-memory-lifetime"])
        self.assertEqual(
            {model["id"] for model in detail["curriculum"]["visualizationModels"]},
            {"c-memory-lifetime", "c-call-stack"},
        )

    def test_javascript_models_cover_candidates_and_are_bound_to_lessons(self) -> None:
        candidates = {item["id"] for item in language_curriculum("javascript")["visualizations"]}
        models = visualization_models_for_language("javascript")

        self.assertEqual({model["id"] for model in models}, candidates)
        self.assertTrue(all(model["simplification"] and len(model["steps"]) >= 3 for model in models))

        root = Path(tempfile.mkdtemp(prefix="poznamkovnik-js-visualizations-", dir="/tmp"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        database = Database(root / "poznamkovnik.sqlite3")
        database.initialize()
        user, _ = AuthService(database).setup("Tester", "testovacie-heslo")
        language = next(item for item in database.list_tutorial_languages(user["id"]) if item["code"] == "javascript")
        detail = database.tutorial_language_detail(user["id"], language["id"])

        async_page = next(page for page in detail["pages"] if page["title"] == "Event loop, Promise a async/await")
        closure_page = next(page for page in detail["pages"] if page["title"] == "let, const, scope a closures")
        self.assertEqual(async_page["content"]["visualizationIds"], ["js-event-loop"])
        self.assertEqual(closure_page["content"]["visualizationIds"], ["js-scope-closures"])

    def test_python_models_cover_candidates_and_are_bound_to_lessons(self) -> None:
        candidates = {item["id"] for item in language_curriculum("python")["visualizations"]}
        models = visualization_models_for_language("python")

        self.assertEqual({model["id"] for model in models}, candidates)
        self.assertTrue(all(model["simplification"] and len(model["steps"]) >= 3 for model in models))

        root = Path(tempfile.mkdtemp(prefix="poznamkovnik-python-visualizations-", dir="/tmp"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        database = Database(root / "poznamkovnik.sqlite3")
        database.initialize()
        user, _ = AuthService(database).setup("Tester", "testovacie-heslo")
        language = next(item for item in database.list_tutorial_languages(user["id"]) if item["code"] == "python")
        detail = database.tutorial_language_detail(user["id"], language["id"])

        values_page = next(page for page in detail["pages"] if page["title"] == "Hodnoty, mená a porovnanie")
        iteration_page = next(page for page in detail["pages"] if page["title"] == "Iterátory, generátory a context managers")
        self.assertEqual(values_page["content"]["visualizationIds"], ["python-object-references"])
        self.assertEqual(iteration_page["content"]["visualizationIds"], ["python-generator-flow"])

    def test_csharp_models_cover_candidates_and_are_bound_to_lessons(self) -> None:
        candidates = {item["id"] for item in language_curriculum("csharp")["visualizations"]}
        models = visualization_models_for_language("csharp")

        self.assertEqual({model["id"] for model in models}, candidates)
        self.assertTrue(all(model["simplification"] and len(model["steps"]) >= 3 for model in models))

        root = Path(tempfile.mkdtemp(prefix="poznamkovnik-csharp-visualizations-", dir="/tmp"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        database = Database(root / "poznamkovnik.sqlite3")
        database.initialize()
        user, _ = AuthService(database).setup("Tester", "testovacie-heslo")
        language = next(item for item in database.list_tutorial_languages(user["id"]) if item["code"] == "csharp")
        detail = database.tutorial_language_detail(user["id"], language["id"])

        linq_page = next(page for page in detail["pages"] if page["title"] == "Kolekcie, LINQ a odložené vykonanie")
        async_page = next(page for page in detail["pages"] if page["title"] == "Task, async/await a rušenie")
        self.assertEqual(linq_page["content"]["visualizationIds"], ["csharp-linq-deferred"])
        self.assertEqual(async_page["content"]["visualizationIds"], ["csharp-async-task"])

    def test_ruby_model_covers_its_candidate_and_is_bound_to_its_lesson(self) -> None:
        candidates = {item["id"] for item in language_curriculum("ruby")["visualizations"]}
        models = visualization_models_for_language("ruby")

        self.assertEqual({model["id"] for model in models}, candidates)
        self.assertTrue(all(model["simplification"] and len(model["steps"]) >= 3 for model in models))

        root = Path(tempfile.mkdtemp(prefix="poznamkovnik-ruby-visualizations-", dir="/tmp"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        database = Database(root / "poznamkovnik.sqlite3")
        database.initialize()
        user, _ = AuthService(database).setup("Tester", "testovacie-heslo")
        language = next(item for item in database.list_tutorial_languages(user["id"]) if item["code"] == "ruby")
        detail = database.tutorial_language_detail(user["id"], language["id"])

        module_page = next(page for page in detail["pages"] if page["title"] == "Moduly, mixiny a hľadanie metód")
        self.assertEqual(module_page["content"]["visualizationIds"], ["ruby-method-lookup"])

    def test_cpp_models_cover_candidates_and_are_bound_to_lessons(self) -> None:
        candidates = {item["id"] for item in language_curriculum("cpp")["visualizations"]}
        models = visualization_models_for_language("cpp")

        self.assertEqual({model["id"] for model in models}, candidates)
        self.assertTrue(all(model["simplification"] and len(model["steps"]) >= 3 for model in models))

        root = Path(tempfile.mkdtemp(prefix="poznamkovnik-cpp-visualizations-", dir="/tmp"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        database = Database(root / "poznamkovnik.sqlite3")
        database.initialize()
        user, _ = AuthService(database).setup("Tester", "testovacie-heslo")
        language = next(item for item in database.list_tutorial_languages(user["id"]) if item["code"] == "cpp")
        detail = database.tutorial_language_detail(user["id"], language["id"])

        raii_page = next(page for page in detail["pages"] if page["title"] == "RAII, move a smart pointery")
        iterator_page = next(page for page in detail["pages"] if page["title"] == "Invalidácia iterátorov a referencií")
        self.assertEqual(raii_page["content"]["visualizationIds"], ["cpp-raii-lifetime"])
        self.assertEqual(iterator_page["content"]["visualizationIds"], ["cpp-iterator-invalidation"])

    def test_models_are_returned_as_independent_data(self) -> None:
        first = visualization_models_for_language("c")
        first[0]["steps"][0]["title"] = "zmenené"

        second = visualization_models_for_language("c")

        self.assertNotEqual(second[0]["steps"][0]["title"], "zmenené")
