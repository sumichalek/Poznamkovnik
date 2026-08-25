from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from backend.auth import AuthService
from backend.code_runner import DevelopmentCodeRunner
from backend.database import Database, ValidationError


class DevelopmentWorkspaceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="poznamkovnik-development-", dir="/tmp"))
        self.database = Database(self.root / "poznamkovnik.sqlite3")
        self.database.initialize()
        self.user, _ = AuthService(self.database).setup("Tester", "testovacie-heslo")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_project_keeps_files_and_entry_source(self) -> None:
        project = self.database.create_development_project(
            self.user["id"], {"id": "project-c", "title": "Skúška C", "language": "c"}
        )
        self.assertEqual(project["title"], "Skúška C")
        self.assertEqual(project["language"], "c")
        self.assertEqual(project["files"][0]["title"], "main.c")
        self.assertIn("int main", project["files"][0]["content"])

        project = self.database.update_development_file(
            self.user["id"],
            "project-c",
            project["entryFileId"],
            {"content": "int main(void) { return 0; }\n", "title": "program.c"},
        )
        entry = self.database.development_entry_file(self.user["id"], "project-c")
        self.assertEqual(entry["filename"], "program.c")
        self.assertEqual(entry["source"], "int main(void) { return 0; }\n")

        project = self.database.create_development_file(
            self.user["id"], "project-c", {"id": "helper", "title": "pomoc.c", "content": "void pomoc(void) {}"}
        )
        self.assertEqual(len(project["files"]), 2)
        entry = self.database.development_entry_file(self.user["id"], "project-c")
        self.assertEqual({file["title"] for file in entry["files"]}, {"program.c", "pomoc.c"})

        project = self.database.delete_development_file(self.user["id"], "project-c", "helper")
        self.assertEqual(len(project["files"]), 1)
        with self.assertRaises(ValidationError):
            self.database.delete_development_file(self.user["id"], "project-c", project["entryFileId"])

    def test_c_project_runner_includes_project_headers(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["c"]["available"]:
            self.skipTest("Bezpečná skúšobňa C nie je v tomto prostredí dostupná.")
        main = '#include <stdio.h>\n#include "hlavicka.h"\nint main(void) { puts(AHOJ); }\n'
        result = runner.run(
            "c",
            main,
            "",
            files=[
                {"title": "main.c", "content": main},
                {"title": "hlavicka.h", "content": '#define AHOJ "Ahoj, svet!"\n'},
            ],
            entry_filename="main.c",
        )
        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "Ahoj, svet!\n")

    def test_project_files_can_be_grouped_in_folders_and_removed_as_a_branch(self) -> None:
        project = self.database.create_development_project(
            self.user["id"], {"id": "project-folders", "title": "Priečinky", "language": "c"}
        )
        project = self.database.create_development_file(
            self.user["id"], "project-folders", {"id": "src", "kind": "folder", "title": "src"}
        )
        project = self.database.create_development_file(
            self.user["id"], "project-folders", {"id": "include", "kind": "folder", "title": "include", "parentId": "src"}
        )
        project = self.database.create_development_file(
            self.user["id"],
            "project-folders",
            {"id": "config", "title": "config.h", "content": "#define VALUE 7\n", "parentId": "include"},
        )
        entry = self.database.development_entry_file(self.user["id"], "project-folders", project["entryFileId"])
        self.assertEqual(entry["filename"], "main.c")
        self.assertIn("src/include/config.h", {item["title"] for item in entry["files"]})

        project = self.database.delete_development_file(self.user["id"], "project-folders", "src")
        self.assertEqual({item["title"] for item in project["files"]}, {"main.c"})

    def test_c_runner_preserves_nested_project_paths(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["c"]["available"]:
            self.skipTest("Bezpečná skúšobňa C nie je v tomto prostredí dostupná.")
        main = '#include <stdio.h>\n#include "config.h"\nint main(void) { puts(POZDRAV); }\n'
        result = runner.run(
            "c",
            main,
            "",
            files=[
                {"title": "src/main.c", "content": main},
                {"title": "src/include/config.h", "content": '#define POZDRAV "Vnorený projekt"\n'},
            ],
            entry_filename="src/main.c",
        )
        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "Vnorený projekt\n")

    def test_project_can_be_deleted_with_its_files(self) -> None:
        self.database.create_development_project(
            self.user["id"], {"id": "project-delete", "title": "Dočasný projekt", "language": "c"}
        )
        self.database.create_development_file(
            self.user["id"], "project-delete", {"id": "helper", "title": "pomoc.c", "content": "void pomoc(void) {}"}
        )
        self.database.delete_development_project(self.user["id"], "project-delete")
        workspace = self.database.development_workspace(self.user["id"])
        self.assertEqual(workspace["projects"], [])

    def test_selected_file_can_be_used_as_project_entry(self) -> None:
        project = self.database.create_development_project(
            self.user["id"], {"id": "project-python", "title": "Skripty", "language": "python"}
        )
        project = self.database.create_development_file(
            self.user["id"],
            "project-python",
            {"id": "second-script", "title": "druhy.py", "content": "print('druhy')\n"},
        )
        entry = self.database.development_entry_file(self.user["id"], "project-python", "second-script")
        self.assertEqual(entry["fileId"], "second-script")
        self.assertEqual(entry["filename"], "druhy.py")
        self.assertEqual(entry["source"], "print('druhy')")
