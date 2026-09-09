from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.tutorial_c_examples import (
    CONDITIONAL_BUILD,
    MACRO_EXPANDED,
    MACRO_EXPANSION,
    MEASUREMENTS_FILES,
    MEASUREMENTS_SINGLE_FILE,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice


@unittest.skipUnless(shutil.which("gcc"), "C build lessons require GCC")
class TutorialCBuildTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-build-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, filename: str, source: str) -> None:
        (self.root / filename).write_text(source, encoding="utf-8")

    def gcc(self, *args: str, succeeds: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["gcc", "-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion",
             "-Wshadow", "-Werror", "-fno-common", "-O0", *args],
            cwd=self.root, capture_output=True, text=True, timeout=15,
        )
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, "Expected this build step to fail")
        return result

    def run_program(self, name: str = "program") -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [str(self.root / name)], capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def prepare_modules(self) -> None:
        for filename, source in MEASUREMENTS_FILES.items():
            self.write(filename, source)
        self.gcc("-c", "main.c", "-o", "main.o")
        self.gcc("-c", "merania.c", "-o", "merania.o")

    def test_macro_expansion_matches_the_textbook_output(self) -> None:
        self.write("makra.c", MACRO_EXPANSION)
        result = self.gcc("-E", "-P", "makra.c")
        self.assertEqual(result.stdout.split(), MACRO_EXPANDED.split())

    def test_conditional_build_accepts_both_modes_and_rejects_invalid_configuration(self) -> None:
        self.write("main.c", CONDITIONAL_BUILD)
        for mode in (0, 1):
            with self.subTest(mode=mode):
                self.gcc(f"-DDEBUG_LOG={mode}", "main.c", "-o", "program")
                result = self.run_program()
                self.assertEqual(result.stdout, "average: 12.0\n")
                self.assertEqual(result.stderr, "debug: computing average\n" if mode else "")
        invalid = self.gcc("-DDEBUG_LOG=2", "-c", "main.c", "-o", "invalid.o", succeeds=False)
        self.assertIn("DEBUG_LOG must be 0 or 1", invalid.stderr)

    def test_three_file_and_single_file_examples_agree(self) -> None:
        self.prepare_modules()
        self.gcc("main.o", "merania.o", "-o", "program")
        result = self.run_program()
        self.assertEqual(result.stdout, "version: 1\nminimum: 9.0, maximum: 14.0\n")
        self.assertEqual(result.stderr, "")

        self.write("single.c", MEASUREMENTS_SINGLE_FILE)
        self.gcc("single.c", "-o", "single")
        single_result = self.run_program("single")
        self.assertEqual((single_result.stdout, single_result.stderr), (result.stdout, result.stderr))
        example = next(item for item in C_EXAMPLES if item["key"] == "measurements-single-file")
        self.assertEqual(example["source"], MEASUREMENTS_SINGLE_FILE)
        page = next(item for item in C_PAGES if item["key"] == "build")
        displayed = {item["title"].split(":")[0]: item["source"]
                     for item in page["content"]["blocks"] if item["type"] == "code"}
        for name, source in MEASUREMENTS_FILES.items():
            self.assertEqual(displayed[name], source)

    def test_missing_and_duplicate_definitions_fail_only_at_link_time(self) -> None:
        self.prepare_modules()
        missing = self.gcc("main.o", "-o", "missing", succeeds=False)
        self.assertIn("merania_rozsah", missing.stderr)

        self.write("duplicate.c", '#include "merania.h"\nconst unsigned int merania_verzia = 2U;\n')
        self.gcc("-c", "duplicate.c", "-o", "duplicate.o")
        duplicate = self.gcc("main.o", "merania.o", "duplicate.o", "-o", "duplicate", succeeds=False)
        self.assertIn("merania_verzia", duplicate.stderr)

    def test_header_is_self_contained_guarded_and_checks_implementation_types(self) -> None:
        self.prepare_modules()
        self.write("header_check.c", '#include "merania.h"\n#include "merania.h"\n')
        self.gcc("-c", "header_check.c", "-o", "header_check.o")
        source = MEASUREMENTS_FILES["merania.c"].replace(
            "int merania_rozsah(", "double merania_rozsah(",
        )
        self.write("wrong_type.c", source)
        invalid = self.gcc("-c", "wrong_type.c", "-o", "wrong_type.o", succeeds=False)
        self.assertIn("merania_rozsah", invalid.stderr)

    def test_private_helper_is_not_available_to_another_translation_unit(self) -> None:
        self.prepare_modules()
        self.write("outsider.c", "int meranie_je_platne(double value);\n"
                   "int main(void) { return meranie_je_platne(1.0); }\n")
        self.gcc("-c", "outsider.c", "-o", "outsider.o")
        result = self.gcc("outsider.o", "merania.o", "-o", "outsider", succeeds=False)
        self.assertIn("meranie_je_platne", result.stderr)

    def test_measurement_contract_including_failure_preserves_output(self) -> None:
        self.prepare_modules()
        self.write("contracts.c", r"""#include "merania.h"
#include <assert.h>
#include <math.h>

int main(void)
{
    Rozsah output = {123.0, 456.0};
    const double negative[] = {-10.0, -2.0, -8.0};
    const double same[] = {5.0, 5.0, 5.0};
    const double invalid[] = {1.0, NAN};
    const double infinite[] = {INFINITY};
    assert(!merania_rozsah(NULL, 1, &output));
    assert(!merania_rozsah(negative, 0, &output));
    assert(!merania_rozsah(negative, 3, NULL));
    assert(!merania_rozsah(invalid, 2, &output));
    assert(!merania_rozsah(infinite, 1, &output));
    assert(output.minimum == 123.0 && output.maximum == 456.0);
    assert(merania_rozsah(negative, 3, &output));
    assert(output.minimum == -10.0 && output.maximum == -2.0);
    assert(merania_rozsah(same, 3, &output));
    assert(output.minimum == 5.0 && output.maximum == 5.0);
    assert(merania_rozsah(negative, 1, &output));
    assert(output.minimum == -10.0 && output.maximum == -10.0);
    return 0;
}
""")
        self.gcc("-fsanitize=undefined", "-fno-sanitize-recover=all",
                 "contracts.c", "merania.c", "-o", "program")
        self.assertEqual(self.run_program().stderr, "")

    def test_practice_variants_distinguish_macro_compile_and_link_errors(self) -> None:
        for variant in range(4):
            for topic in ("preprocessor", "build"):
                with self.subTest(topic=topic, variant=variant):
                    exercise = tutorial_practice("c", topic, variant)
                    assert exercise is not None
                    starter = exercise["starterSource"]
                    self.write("exercise.c", starter)
                    if topic == "preprocessor":
                        self.gcc("exercise.c", "-o", "program")
                        self.assertNotEqual(self.run_program().stdout, exercise["expectedOutput"])
                        solved = starter.replace("value * value", "((value) * (value))")
                    elif variant % 2 == 0:
                        self.gcc("-c", "exercise.c", "-o", "exercise.o", succeeds=False)
                        solved = starter.replace(
                            "/* Doplň prototyp funkcie priemer_dvoch. */",
                            "double priemer_dvoch(double left, double right);",
                        )
                    else:
                        self.gcc("-c", "exercise.c", "-o", "exercise.o")
                        self.gcc("exercise.o", "-o", "program", succeeds=False)
                        solved = starter.replace(
                            "/* Doplň definíciu funkcie maximum. */",
                            "int maximum(int left, int right) { return left > right ? left : right; }",
                        )
                    self.write("exercise.c", solved)
                    self.gcc("exercise.c", "-o", "program")
                    result = self.run_program()
                    self.assertEqual(result.stdout, exercise["expectedOutput"])
                    evaluation = evaluate_tutorial_practice(
                        exercise,
                        {"compiled": True, "compile": {},
                         "run": {"exitCode": 0, "stdout": result.stdout}},
                        "",
                    )
                    self.assertEqual(evaluation["status"], "passed")
