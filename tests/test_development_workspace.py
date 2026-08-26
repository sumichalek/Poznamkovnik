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
        self.database.delete_development_test_case(self.user["id"], project["id"], "hello-test")
        self.assertEqual(self.database.list_development_test_cases(self.user["id"], project["id"]), [])

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

    def test_c_project_can_be_compiled_without_running(self) -> None:
        runner = DevelopmentCodeRunner()
        if not runner.status()["languages"]["c"]["available"]:
            self.skipTest("Bezpečná skúšobňa C nie je v tomto prostredí dostupná.")
        result = runner.run("c", "int main(void) { return 0; }\n", "", execute=False)
        self.assertTrue(result["compiled"])
        self.assertIsNone(result["run"])

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
                "buildProfile": "debug",
            },
        )
        self.assertEqual(project["kind"], "firmware")
        self.assertEqual(project["firmwareTarget"]["label"], "ATmega328P")
        self.assertEqual(project["buildProfile"], "debug")
        self.assertIn("ATmega328P", project["files"][0]["content"])

        entry = self.database.development_entry_file(self.user["id"], project["id"])
        self.assertEqual(entry["projectKind"], "firmware")
        self.assertEqual(entry["firmwareTargetId"], "avr-atmega328p")

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
