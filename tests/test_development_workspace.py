from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.api import _development_test_result_data
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

    def test_project_can_start_with_supplied_entry_content(self) -> None:
        source = '#include <stdio.h>\n\nint main(void) {\n  puts("Z učebnice");\n}\n'
        tutorial_link = {
            "languageId": "tutorial-c",
            "pageId": "tutorial-c-start",
            "exampleId": "tutorial-c-hello",
        }
        project = self.database.create_development_project(
            self.user["id"],
            {
                "id": "tutorial-example",
                "title": "Príklad: Pozdrav",
                "language": "c",
                "entryContent": source,
                "tutorialLink": tutorial_link,
            },
        )

        self.assertEqual(project["files"][0]["content"], source)
        self.assertEqual(project["tutorialLink"], tutorial_link)
        entry = self.database.development_entry_file(self.user["id"], project["id"])
        self.assertEqual(entry["source"], source)

    def test_tutorial_example_reuses_its_linked_development_project(self) -> None:
        tutorial_link = {
            "languageId": "tutorial-c",
            "pageId": "tutorial-c-start",
            "exampleId": "tutorial-c-hello",
        }
        project = self.database.create_development_project(
            self.user["id"],
            {
                "id": "linked-example",
                "title": "Príklad: Pozdrav",
                "language": "c",
                "entryContent": "int main(void) { return 0; }\n",
                "tutorialLink": tutorial_link,
            },
        )
        updated = self.database.update_development_file(
            self.user["id"],
            project["id"],
            project["entryFileId"],
            {"content": "int main(void) { return 7; }\n"},
        )

        reused = self.database.development_project_for_tutorial(
            self.user["id"],
            tutorial_link["languageId"],
            tutorial_link["pageId"],
            tutorial_link["exampleId"],
        )

        self.assertIsNotNone(reused)
        assert reused is not None
        self.assertEqual(reused["id"], project["id"])
        self.assertEqual(reused["files"][0]["content"], updated["files"][0]["content"])
        self.assertIsNone(
            self.database.development_project_for_tutorial(
                self.user["id"], "tutorial-c", "tutorial-c-start", "missing-example"
            )
        )

    def test_project_symbol_rename_changes_code_but_not_comments_or_strings(self) -> None:
        project = self.database.create_development_project(
            self.user["id"],
            {
                "id": "rename-symbol",
                "title": "Premenovanie",
                "language": "c",
                "entryContent": (
                    '#include <stdio.h>\n\nint value = 1; // value v komentári\n'
                    'int main(void) {\n  printf("value v texte: %d\\n", value);\n  return value;\n}\n'
                ),
            },
        )
        project = self.database.create_development_file(
            self.user["id"], project["id"], {"id": "rename-header", "title": "pomoc.h", "content": "int value;\n"}
        )

        result = self.database.rename_development_symbol(
            self.user["id"], project["id"], {"oldName": "value", "newName": "number"}
        )

        self.assertEqual(result["replacements"], 4)
        files = {item["title"]: item["content"] for item in result["project"]["files"]}
        self.assertIn("int number = 1; // value v komentári", files["main.c"])
        self.assertIn('"value v texte: %d\\n", number', files["main.c"])
        self.assertIn("return number;", files["main.c"])
        self.assertEqual(files["pomoc.h"], "int number;")

    def test_project_symbol_rename_skips_python_comments_and_triple_strings(self) -> None:
        project = self.database.create_development_project(
            self.user["id"],
            {
                "id": "rename-python-symbol",
                "title": "Premenovanie Python",
                "language": "python",
                "entryContent": 'value = 1\n# value v komentári\ntext = """value v texte"""\nprint(value)\n',
            },
        )

        result = self.database.rename_development_symbol(
            self.user["id"], project["id"], {"oldName": "value", "newName": "number"}
        )

        self.assertEqual(result["replacements"], 2)
        source = result["project"]["files"][0]["content"]
        self.assertIn("number = 1", source)
        self.assertIn("# value v komentári", source)
        self.assertIn('"""value v texte"""', source)
        self.assertIn("print(number)", source)

    def test_symbol_rename_preview_is_non_mutating_and_can_be_confirmed(self) -> None:
        project = self.database.create_development_project(
            self.user["id"],
            {
                "id": "rename-preview",
                "title": "Náhľad premenovania",
                "language": "c",
                "entryContent": "int value = 1; // value v komentári\nint main(void) { return value; }\n",
            },
        )
        project = self.database.create_development_file(
            self.user["id"], project["id"], {"id": "preview-header", "title": "value.h", "content": "extern int value;\n"}
        )

        preview = self.database.preview_development_symbol_rename(
            self.user["id"], project["id"], {"oldName": "value", "newName": "number"}
        )

        self.assertEqual(preview["replacements"], 3)
        self.assertEqual(preview["files"], 2)
        self.assertEqual(
            self.database.development_entry_file(self.user["id"], project["id"])["source"],
            "int value = 1; // value v komentári\nint main(void) { return value; }\n",
        )

        selected_edit = {**preview["workspaceEdits"][0]["edits"][0], "newText": "custom_value"}
        result = self.database.apply_development_text_edits(
            self.user["id"], project["id"], {"workspaceEdits": [{"path": "main.c", "edits": [selected_edit]}]}
        )

        self.assertEqual(result["replacements"], 1)
        files = {item["title"]: item["content"] for item in result["project"]["files"]}
        self.assertIn("int custom_value = 1; // value v komentári", files["main.c"])
        self.assertIn("return value;", files["main.c"])
        self.assertEqual(files["value.h"], "extern int value;")

    def test_confirmed_language_service_edits_apply_exact_ranges_only(self) -> None:
        project = self.database.create_development_project(
            self.user["id"],
            {
                "id": "lsp-edits",
                "title": "Sémantické premenovanie",
                "language": "c",
                "entryContent": "int greet(void) { return 1; }\nint main(void) { return greet(); }\n",
            },
        )
        project = self.database.create_development_file(
            self.user["id"], project["id"], {"id": "lsp-header", "title": "greet.h", "content": "int greet(void);\n"}
        )

        result = self.database.apply_development_text_edits(
            self.user["id"],
            project["id"],
            {
                "workspaceEdits": [
                    {
                        "path": "main.c",
                        "edits": [
                            {"startLine": 1, "startColumn": 5, "endLine": 1, "endColumn": 10, "newText": "welcome"},
                            {"startLine": 2, "startColumn": 25, "endLine": 2, "endColumn": 30, "newText": "welcome"},
                        ],
                    },
                    {
                        "path": "greet.h",
                        "edits": [
                            {"startLine": 1, "startColumn": 5, "endLine": 1, "endColumn": 10, "newText": "welcome"},
                        ],
                    },
                ]
            },
        )
        self.assertEqual(result["replacements"], 3)
        self.assertEqual(result["files"], 2)
        files = {item["title"]: item["content"] for item in result["project"]["files"]}
        self.assertEqual(files["main.c"], "int welcome(void) { return 1; }\nint main(void) { return welcome(); }\n")
        self.assertEqual(files["greet.h"], "int welcome(void);")

    def test_language_service_edits_reject_overlapping_ranges(self) -> None:
        project = self.database.create_development_project(
            self.user["id"], {"id": "lsp-overlap", "title": "Prekrývanie", "language": "c", "entryContent": "int value;\n"}
        )
        with self.assertRaises(ValidationError):
            self.database.apply_development_text_edits(
                self.user["id"],
                project["id"],
                {
                    "workspaceEdits": [{
                        "path": "main.c",
                        "edits": [
                            {"startLine": 1, "startColumn": 5, "endLine": 1, "endColumn": 10, "newText": "number"},
                            {"startLine": 1, "startColumn": 7, "endLine": 1, "endColumn": 10, "newText": "n"},
                        ],
                    }]
                },
            )

    def test_existing_test_case_table_gets_last_result_columns(self) -> None:
        legacy_path = self.root / "legacy-development.sqlite3"
        with sqlite3.connect(legacy_path) as connection:
            connection.execute(
                """
                CREATE TABLE development_test_cases (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    stdin TEXT NOT NULL DEFAULT '',
                    arguments TEXT NOT NULL DEFAULT '',
                    expected_output TEXT NOT NULL DEFAULT '',
                    position INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        Database(legacy_path).initialize()
        with sqlite3.connect(legacy_path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(development_test_cases)")}
        self.assertTrue({"last_status", "last_run_at", "last_duration_ms", "last_exit_code"}.issubset(columns))

    def test_existing_project_table_gets_tutorial_link_columns(self) -> None:
        legacy_path = self.root / "legacy-development-project.sqlite3"
        with sqlite3.connect(legacy_path) as connection:
            connection.execute(
                """
                CREATE TABLE development_projects (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'c',
                    project_kind TEXT NOT NULL DEFAULT 'program',
                    firmware_target_id TEXT NOT NULL DEFAULT '',
                    build_profile TEXT NOT NULL DEFAULT 'debug',
                    run_arguments TEXT NOT NULL DEFAULT '',
                    entry_file_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        Database(legacy_path).initialize()
        with sqlite3.connect(legacy_path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(development_projects)")}
        self.assertTrue({"tutorial_language_id", "tutorial_page_id", "tutorial_example_id", "firmware_serial_baud"}.issubset(columns))

    def test_project_template_is_applied_only_when_creating_a_project(self) -> None:
        project = self.database.create_development_project(
            self.user["id"],
            {"id": "project-template", "title": "Vstup", "language": "python", "templateId": "input-output"},
        )
        self.assertIn("input().strip()", project["files"][0]["content"])
        with self.assertRaises(ValidationError):
            self.database.create_development_project(
                self.user["id"],
                {"title": "Neplatná šablóna", "language": "c", "templateId": "neexistuje"},
            )

    def test_project_keeps_build_profile_and_default_run_arguments(self) -> None:
        project = self.database.create_development_project(
            self.user["id"],
            {
                "id": "project-profile",
                "title": "Profil",
                "language": "c",
                "buildProfile": "release",
                "runArguments": '--meno "Ján Novák"',
            },
        )
        self.assertEqual(project["buildProfile"], "release")
        self.assertEqual(project["buildProfileLabel"], "Vydanie")
        self.assertEqual(project["runArguments"], '--meno "Ján Novák"')

        updated = self.database.update_development_project(
            self.user["id"], project["id"], {"buildProfile": "debug", "runArguments": "--podrobne"}
        )
        self.assertEqual(updated["buildProfile"], "debug")
        self.assertEqual(updated["runArguments"], "--podrobne")
        entry = self.database.development_entry_file(self.user["id"], project["id"])
        self.assertEqual(entry["buildProfile"], "debug")
        with self.assertRaises(ValidationError):
            self.database.update_development_project(
                self.user["id"], project["id"], {"buildProfile": "neplatny"}
            )

    def test_project_test_cases_keep_input_arguments_and_expected_output(self) -> None:
        project = self.database.create_development_project(
            self.user["id"], {"id": "project-tests", "title": "Testy", "language": "python"}
        )
        test_case = self.database.create_development_test_case(
            self.user["id"],
            project["id"],
            {
                "id": "hello-test",
                "title": "Pozdrav",
                "arguments": '--meno "Ján Novák"',
                "stdin": "Ahoj\n",
                "expectedOutput": "Ahoj, Ján!\n",
            },
        )
        self.assertEqual(test_case["arguments"], '--meno "Ján Novák"')
        self.assertEqual(test_case["stdin"], "Ahoj\n")
        self.assertEqual(test_case["expectedOutput"], "Ahoj, Ján!\n")
        self.assertEqual(
            [item["id"] for item in self.database.list_development_test_cases(self.user["id"], project["id"])],
            ["hello-test"],
        )

        updated = self.database.update_development_test_case(
            self.user["id"], project["id"], "hello-test", {"title": "Pozdrav upravený", "stdin": "Čau\n"}
        )
        self.assertEqual(updated["title"], "Pozdrav upravený")
        self.assertEqual(updated["stdin"], "Čau\n")
        self.assertEqual(updated["expectedOutput"], "Ahoj, Ján!\n")
        recorded = self.database.record_development_test_result(
            self.user["id"], project["id"], "hello-test", {"status": "output_mismatch", "durationMs": 42, "exitCode": 0}
        )
        self.assertEqual(recorded["lastResult"]["status"], "output_mismatch")
        self.assertEqual(recorded["lastResult"]["durationMs"], 42)
        persisted = self.database.list_development_test_cases(self.user["id"], project["id"])
        self.assertEqual(persisted[0]["lastResult"]["exitCode"], 0)
        self.database.delete_development_test_case(self.user["id"], project["id"], "hello-test")
        self.assertEqual(self.database.list_development_test_cases(self.user["id"], project["id"]), [])

    def test_test_run_result_metadata_distinguishes_build_runtime_and_output_failures(self) -> None:
        test_case = {"expectedOutput": "Ahoj\n"}
        passed = _development_test_result_data(
            test_case,
            {
                "compiled": True,
                "compile": {"durationMs": 3},
                "run": {"stdout": "Ahoj\n", "stderr": "", "exitCode": 0, "durationMs": 4},
            },
        )
        self.assertEqual(passed, {"status": "passed", "durationMs": 7, "exitCode": 0})
        mismatch = _development_test_result_data(
            test_case,
            {"compiled": True, "compile": {}, "run": {"stdout": "Čau\n", "stderr": "", "exitCode": 0}},
        )
        self.assertEqual(mismatch["status"], "output_mismatch")
        compile_error = _development_test_result_data(
            test_case,
            {"compiled": False, "compile": {"durationMs": 5}, "run": None},
        )
        self.assertEqual(compile_error["status"], "compile_error")

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

    def test_c_project_runner_links_nested_implementation_files(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["c"]["available"]:
            self.skipTest("Bezpečná skúšobňa C nie je v tomto prostredí dostupná.")
        main = (
            '#include <stdio.h>\n'
            '#include "math/pomoc.h"\n\n'
            'int main(void) {\n'
            '  printf("%d\\n", pomoc(7));\n'
            '  return 0;\n'
            '}\n'
        )
        result = runner.run(
            "c",
            main,
            "",
            files=[
                {"title": "main.c", "content": main},
                {"title": "math/pomoc.h", "content": "int pomoc(int hodnota);\n"},
                {
                    "title": "math/pomoc.c",
                    "content": '#include "pomoc.h"\nint pomoc(int hodnota) { return hodnota * 6; }\n',
                },
            ],
            entry_filename="main.c",
        )
        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "42\n")

    def test_cpp_project_runner_links_nested_implementation_files(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["cpp"]["available"]:
            self.skipTest("Bezpečná skúšobňa C++ nie je v tomto prostredí dostupná.")
        main = (
            '#include <iostream>\n'
            '#include "lib/pozdrav.hpp"\n\n'
            'int main() {\n'
            '  std::cout << pozdrav(4) << "\\n";\n'
            '}\n'
        )
        result = runner.run(
            "cpp",
            main,
            "",
            files=[
                {"title": "main.cpp", "content": main},
                {"title": "lib/pozdrav.hpp", "content": "int pozdrav(int hodnota);\n"},
                {
                    "title": "lib/pozdrav.cpp",
                    "content": '#include "pozdrav.hpp"\nint pozdrav(int hodnota) { return hodnota + 9; }\n',
                },
            ],
            entry_filename="main.cpp",
        )
        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "13\n")

    def test_cpp_runner_compiles_a_standard_library_raii_example(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["cpp"]["available"]:
            self.skipTest("Bezpečná skúšobňa C++ nie je v tomto prostredí dostupná.")
        source = (
            "#include <iostream>\n"
            "#include <memory>\n\n"
            "int main() {\n"
            "  auto value = std::make_unique<int>(42);\n"
            "  std::cout << *value << \"\\n\";\n"
            "}\n"
        )

        result = runner.run("cpp", source, "")

        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "42\n")

    def test_c_project_can_be_compiled_without_running(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["c"]["available"]:
            self.skipTest("Bezpečná skúšobňa C nie je v tomto prostredí dostupná.")
        result = runner.run("c", "int main(void) { return 0; }\n", "", execute=False)
        self.assertTrue(result["compiled"])
        self.assertIsNone(result["run"])

    def test_ruby_runner_checks_and_executes_a_program(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["ruby"]["available"]:
            self.skipTest("Bezpečná skúšobňa Ruby nie je v tomto prostredí dostupná.")
        result = runner.run("ruby", 'puts "Ahoj z Ruby"\n', "")
        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "Ahoj z Ruby\n")

    def test_perl_runner_checks_and_executes_a_program(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["perl"]["available"]:
            self.skipTest("Bezpečná skúšobňa Perlu nie je v tomto prostredí dostupná.")
        result = runner.run("perl", 'print "Ahoj z Perlu\\n";\n', "")
        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "Ahoj z Perlu\n")

    def test_c_project_can_be_built_with_release_profile(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["c"]["available"]:
            self.skipTest("Bezpečná skúšobňa C nie je v tomto prostredí dostupná.")
        result = runner.run("c", "int main(void) { return 0; }\n", "", execute=False, build_profile="release")
        self.assertTrue(result["compiled"])
        self.assertEqual(result["buildProfile"], "release")

    def test_native_build_provides_binary_inspection(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["c"]["available"]:
            self.skipTest("Bezpečná skúšobňa C nie je v tomto prostredí dostupná.")
        if not runner.status()["binaryInspection"]["available"]:
            self.skipTest("Nástroje na rozbor binárky nie sú v tomto prostredí dostupné.")
        result = runner.run(
            "c",
            "int helper(void) { return 7; }\nint main(void) { return helper() == 7 ? 0 : 1; }\n",
            "",
            execute=False,
        )
        self.assertTrue(result["compiled"])
        inspection = result["inspection"]
        self.assertTrue(inspection["available"])
        self.assertGreater(inspection["memory"]["total"], 0)
        self.assertTrue(any(symbol["name"] == "main" for symbol in inspection["symbols"]))

    def test_c_debug_profile_reports_undefined_behavior(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["c"]["available"]:
            self.skipTest("Bezpečná skúšobňa C nie je v tomto prostredí dostupná.")
        source = (
            "#include <limits.h>\n"
            "int main(void) { volatile int value = INT_MAX; return value + 1; }\n"
        )
        result = runner.run("c", source, "", build_profile="debug")
        self.assertTrue(result["compiled"])
        self.assertIn("runtime error", result["run"]["stderr"])

    def test_project_runner_passes_quoted_command_arguments_without_a_shell(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["c"]["available"]:
            self.skipTest("Bezpečná skúšobňa C nie je v tomto prostredí dostupná.")
        source = """#include <stdio.h>
int main(int argc, char **argv) {
  if (argc > 2) puts(argv[2]);
  return 0;
}
"""
        result = runner.run("c", source, "", arguments='prvy "druhy parameter"')
        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "druhy parameter\n")

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

    def test_project_file_or_folder_can_move_without_creating_a_cycle(self) -> None:
        project = self.database.create_development_project(
            self.user["id"], {"id": "project-move", "title": "Presun", "language": "c"}
        )
        project = self.database.create_development_file(
            self.user["id"], "project-move", {"id": "src", "kind": "folder", "title": "src"}
        )
        project = self.database.create_development_file(
            self.user["id"], "project-move", {"id": "include", "kind": "folder", "title": "include", "parentId": "src"}
        )
        project = self.database.create_development_file(
            self.user["id"], "project-move", {"id": "helper", "title": "helper.c", "content": "void helper(void) {}\n"}
        )

        project = self.database.move_development_file(self.user["id"], "project-move", "helper", {"parentId": "src"})
        helper = next(item for item in project["files"] if item["id"] == "helper")
        self.assertEqual(helper["parentId"], "src")
        entry = self.database.development_entry_file(self.user["id"], "project-move")
        self.assertIn("src/helper.c", {item["title"] for item in entry["files"]})

        with self.assertRaises(ValidationError):
            self.database.move_development_file(self.user["id"], "project-move", "src", {"parentId": "include"})

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

    def test_workspace_offers_all_planned_language_profiles(self) -> None:
        language_ids = {item["id"] for item in self.database.development_languages()}
        self.assertTrue(
            {
                "c",
                "cpp",
                "python",
                "javascript",
                "ruby",
                "perl",
                "php",
                "csharp",
                "asm",
                "bash",
                "rust",
                "go",
                "java",
            }.issubset(language_ids)
        )

    def test_firmware_project_keeps_its_target_and_is_not_a_host_program(self) -> None:
        workspace = self.database.development_workspace(self.user["id"])
        targets = {target["id"]: target for target in workspace["firmwareTargets"]}
        self.assertTrue(
            {"avr-atmega328p", "pic16f18855", "samd21", "stm32f103", "esp32", "rp2040"}.issubset(targets)
        )

        project = self.database.create_development_project(
            self.user["id"],
            {
                "id": "firmware-avr",
                "title": "Meranie napätia",
                "kind": "firmware",
                "language": "c",
                "firmwareTargetId": "avr-atmega328p",
                "firmwareProgrammerId": "avr-arduino",
                "firmwareSerialPort": "/dev/ttyUSB0",
                "buildProfile": "debug",
            },
        )
        self.assertEqual(project["kind"], "firmware")
        self.assertEqual(project["firmwareTarget"]["label"], "ATmega328P")
        self.assertEqual(project["firmwareProgrammerId"], "avr-arduino")
        self.assertEqual(project["firmwareSerialPort"], "/dev/ttyUSB0")
        self.assertEqual(project["firmwareSerialBaud"], 115200)
        self.assertEqual(project["buildProfile"], "debug")
        self.assertIn("ATmega328P", project["files"][0]["content"])

        entry = self.database.development_entry_file(self.user["id"], project["id"])
        self.assertEqual(entry["projectKind"], "firmware")
        self.assertEqual(entry["firmwareTargetId"], "avr-atmega328p")
        self.assertEqual(entry["firmwareProgrammerId"], "avr-arduino")
        self.assertEqual(entry["firmwareSerialPort"], "/dev/ttyUSB0")
        self.assertEqual(entry["firmwareSerialBaud"], 115200)

        project = self.database.update_development_project(
            self.user["id"],
            project["id"],
            {
                "firmwareTargetId": "stm32f103",
                "firmwareProgrammerId": "stm32-uart",
                "firmwareSerialPort": "/dev/ttyACM0",
                "firmwareSerialBaud": 57600,
            },
        )
        self.assertEqual(project["firmwareProgrammerId"], "stm32-uart")
        self.assertEqual(project["firmwareSerialPort"], "/dev/ttyACM0")
        self.assertEqual(project["firmwareSerialBaud"], 57600)

        with self.assertRaises(ValidationError):
            self.database.create_development_project(
                self.user["id"],
                {
                    "title": "Neplatný firmvér",
                    "kind": "firmware",
                    "language": "python",
                    "firmwareTargetId": "avr-atmega328p",
                },
            )

    def test_project_transfer_restores_a_nested_firmware_project(self) -> None:
        imported = self.database.import_development_project(
            self.user["id"],
            {
                "project": {
                    "title": "Prenesené meranie",
                    "language": "c",
                    "kind": "firmware",
                    "firmwareTargetId": "avr-atmega328p",
                    "firmwareProgrammerId": "avr-arduino",
                    "firmwareSerialPort": "/dev/ttyUSB0",
                    "firmwareSerialBaud": 230400,
                    "buildProfile": "release",
                    "entryPath": "src/main.c",
                    "files": [
                        {"path": "src", "kind": "folder", "position": 10},
                        {"path": "src/include", "kind": "folder", "position": 20},
                        {"path": "src/include/config.h", "kind": "file", "content": "#define PORT 7\n", "position": 30},
                        {"path": "src/main.c", "kind": "file", "content": "int main(void) { return PORT; }\n", "position": 40},
                    ],
                }
            },
        )
        self.assertEqual(imported["title"], "Prenesené meranie")
        self.assertEqual(imported["kind"], "firmware")
        self.assertEqual(imported["firmwareTarget"]["label"], "ATmega328P")
        self.assertEqual(imported["firmwareProgrammerId"], "avr-arduino")
        self.assertEqual(imported["firmwareSerialPort"], "/dev/ttyUSB0")
        self.assertEqual(imported["firmwareSerialBaud"], 230400)
        self.assertEqual(imported["buildProfile"], "release")
        self.assertEqual(len(imported["files"]), 4)

        entry = self.database.development_entry_file(self.user["id"], imported["id"])
        self.assertEqual(entry["filename"], "src/main.c")
        self.assertEqual({file["title"] for file in entry["files"]}, {"src/main.c", "src/include/config.h"})

    def test_project_transfer_restores_saved_test_cases(self) -> None:
        imported = self.database.import_development_project(
            self.user["id"],
            {
                "project": {
                    "title": "Prenesené testy",
                    "language": "python",
                    "tutorialLink": {
                        "languageId": "tutorial-python",
                        "pageId": "tutorial-python-start",
                        "exampleId": "tutorial-python-hello",
                    },
                    "entryPath": "main.py",
                    "files": [{"path": "main.py", "kind": "file", "content": "print('Ahoj')\n"}],
                    "tests": [
                        {
                            "title": "Základný výpis",
                            "stdin": "vstup\n",
                            "arguments": '--meno "Ján Novák"',
                            "expectedOutput": "Ahoj\n",
                            "position": 20,
                        }
                    ],
                }
            },
        )
        tests = self.database.list_development_test_cases(self.user["id"], imported["id"])
        self.assertEqual(len(tests), 1)
        self.assertEqual(tests[0]["title"], "Základný výpis")
        self.assertEqual(tests[0]["stdin"], "vstup\n")
        self.assertEqual(tests[0]["arguments"], '--meno "Ján Novák"')
        self.assertEqual(tests[0]["expectedOutput"], "Ahoj\n")
        self.assertEqual(
            imported["tutorialLink"],
            {
                "languageId": "tutorial-python",
                "pageId": "tutorial-python-start",
                "exampleId": "tutorial-python-hello",
            },
        )

    def test_bash_and_assembler_projects_run_in_the_sandbox(self) -> None:
        runner = DevelopmentCodeRunner()
        status = runner.status()["languages"]
        for language, source, filename in (
            ("bash", """printf 'Bash funguje\\n'
""", "main.sh"),
            (
                "asm",
                """.global _start
.section .text
_start:
  mov $60, %rax
  xor %rdi, %rdi
  syscall
""",
                "main.s",
            ),
        ):
            if not status[language]["available"]:
                self.skipTest(f"Skúšobňa {language} nie je v tomto prostredí dostupná.")
            result = runner.run(language, source, "", files=[{"title": filename, "content": source}], entry_filename=filename)
            self.assertTrue(result["compiled"])
            self.assertEqual(result["run"]["exitCode"], 0)

    def test_javascript_project_runs_in_the_sandbox(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["javascript"]["available"]:
            self.skipTest("Bezpečná skúšobňa JavaScriptu nie je v tomto prostredí dostupná.")
        result = runner.run("javascript", "console.log(6 * 7);\n", "")
        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "42\n")
        self.assertFalse(result["run"]["timedOut"])

    def test_rust_project_runs_in_the_sandbox(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["rust"]["available"]:
            self.skipTest("Bezpečná skúšobňa Rustu nie je v tomto prostredí dostupná.")
        result = runner.run("rust", 'fn main() { println!("Rust funguje"); }\n', "")
        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "Rust funguje\n")

    def test_go_project_runs_in_the_sandbox(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["go"]["available"]:
            self.skipTest("Bezpečná skúšobňa Go nie je v tomto prostredí dostupná.")
        result = runner.run("go", 'package main\n\nimport "fmt"\n\nfunc main() { fmt.Println("Go funguje") }\n', "")
        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "Go funguje\n")

    def test_java_project_runs_in_the_sandbox(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["java"]["available"]:
            self.skipTest("Bezpečná skúšobňa Javy nie je v tomto prostredí dostupná.")
        result = runner.run(
            "java",
            'class Main { public static void main(String[] args) { System.out.println("Java funguje"); } }\n',
            "",
        )
        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "Java funguje\n")

    def test_csharp_project_runs_in_the_sandbox(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["csharp"]["available"]:
            self.skipTest("Bezpečná skúšobňa C# nie je v tomto prostredí dostupná.")
        result = runner.run("csharp", 'Console.WriteLine("C# funguje");\n', "")
        self.assertTrue(result["compiled"])
        self.assertEqual(result["run"]["stdout"], "C# funguje\n")
