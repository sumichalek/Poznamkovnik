from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.tutorial_c_examples import (
    ASSERT_MAXIMUM, BOUNDARY_TESTS, CHECKED_DIVISION, COUNT_POSITIVE,
    DEBUG_POSITIVE, DIVIDE_INT, SAFE_INDEX,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice


@unittest.skipUnless(shutil.which("gcc"), "C safety lessons require GCC")
class TutorialCSafetyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-safety-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def compile(self, source: str, *flags: str) -> Path:
        path = self.root / "main.c"
        path.write_text(source, encoding="utf-8")
        program = self.root / "program"
        result = subprocess.run(
            ["gcc", "-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion",
             "-Wshadow", "-Wformat=2", "-Werror", "-O1", "-fsanitize=undefined",
             "-fno-sanitize-recover=all", *flags, str(path), "-o", str(program)],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return program

    def run_program(self, program: Path, stdin: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(program)], input=stdin, capture_output=True, text=True,
            timeout=5, cwd=self.root,
        )

    def test_index_accepts_only_complete_in_range_inputs(self) -> None:
        program = self.compile(SAFE_INDEX)
        for text, expected in (("0\n", 10), ("1", 20), (" +2 \n", 30), ("3\n", 40)):
            with self.subTest(text=text):
                result = self.run_program(program, text)
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (0, f"value: {expected}\n", ""))
        for text in ("-1", "4", "999", "-999", "", "\n", "2x", "2 3",
                     "9" * 60, "2" + " " * 63, "2\0x"):
            with self.subTest(text=text):
                result = self.run_program(program, text)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn(result.stderr, ("Index out of bounds.\n",
                                             "Expected one complete integer line.\n"))

    def test_division_checks_boundaries_before_operation_and_preserves_output(self) -> None:
        source = DIVIDE_INT + r"""
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    const int values[] = {INT_MIN, -INT_MAX, -7, -1, 0, 1, 2, 7, INT_MAX};
    const size_t count = sizeof values / sizeof values[0];
    for (size_t i = 0; i < count; ++i) {
        for (size_t j = 0; j < count; ++j) {
            int result = 99;
            int numerator = values[i];
            int denominator = values[j];
            DivideStatus expected = denominator == 0 ? DIVIDE_ZERO :
                (denominator == -1 && numerator < -INT_MAX ? DIVIDE_RANGE : DIVIDE_OK);
            DivideStatus actual = divide_int(numerator, denominator, &result);
            if (actual != expected) { return EXIT_FAILURE; }
            if (expected == DIVIDE_OK) {
                if (result != numerator / denominator) { return EXIT_FAILURE; }
            } else if (result != 99) { return EXIT_FAILURE; }
            if (divide_int(numerator, denominator, NULL) != DIVIDE_ARGUMENT) {
                return EXIT_FAILURE;
            }
        }
    }
    return EXIT_SUCCESS;
}
"""
        result = self.run_program(self.compile(source, "-DNDEBUG"))
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        demo = self.run_program(self.compile(CHECKED_DIVISION))
        self.assertEqual((demo.returncode, demo.stderr), (0, ""))
        self.assertEqual(demo.stdout, "7 / 2: status=0 value=3\n-7 / 2: status=0 value=-3\n"
                                    "0 / 2: status=0 value=0\n7 / 0: status=2 value=99\n")

    def test_assert_example_never_claims_disabled_tests_passed(self) -> None:
        result = self.run_program(self.compile(ASSERT_MAXIMUM))
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, "4 assertions passed.\n", ""))
        for flag in ("-DNDEBUG", "-DNDEBUG=0"):
            with self.subTest(flag=flag):
                result = self.run_program(self.compile(ASSERT_MAXIMUM, flag))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "Assertions disabled; tests not run.\n")

    def test_boundary_table_detects_predicate_and_loop_mutants_even_with_ndebug(self) -> None:
        for flags in ((), ("-DNDEBUG",)):
            with self.subTest(flags=flags):
                result = self.run_program(self.compile(BOUNDARY_TESTS, *flags))
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (0, "tests=7 failures=0\n", ""))
                for source, failures, name in (
                    (BOUNDARY_TESTS.replace("values[i] > 0", "values[i] >= 0"), 4, "zero"),
                    (BOUNDARY_TESTS.replace("size_t i = 0; i < count", "size_t i = 1; i < count"), 2, "first"),
                    (BOUNDARY_TESTS.replace("i < count", "i + 1 < count"), 3, "last"),
                ):
                    result = self.run_program(self.compile(source, *flags))
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, f"tests=7 failures={failures}\n")
                    self.assertIn(name + ": expected=", result.stderr)
                    self.assertNotIn("runtime error:", result.stderr)

    def test_empty_range_contract_accepts_null_without_dereference(self) -> None:
        source = COUNT_POSITIVE + "\nint main(void) { return count_positive(NULL, 0) != 0; }\n"
        result = self.run_program(self.compile(source))
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_debug_example_reproduces_logical_failure_and_one_line_repair(self) -> None:
        for predicate, output, success in ((">=", "2", False), (">", "1", True)):
            source = DEBUG_POSITIVE.replace("values[i] >= 0", f"values[i] {predicate} 0")
            result = self.run_program(self.compile(source))
            self.assertEqual(result.returncode == 0, success)
            self.assertEqual(result.stdout, f"expected=1 actual={output}\n")
            self.assertEqual(result.stderr, "")

    def test_undefined_overflow_is_checked_by_diagnostic_not_accidental_value(self) -> None:
        source = "#include <limits.h>\nint main(void) { volatile int value = INT_MAX; return value + 1; }\n"
        result = self.run_program(self.compile(source))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("signed integer overflow", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_safety_practice_variants_require_real_checks(self) -> None:
        placeholder = """    /* Replace this placeholder with checks before the array access. */
    (void) values;
    (void) count;
    (void) index;
    (void) result;
    return 0;"""
        solution = """    if (values == NULL || result == NULL || index < 0 ||
        (uintmax_t) index >= (uintmax_t) count) { return 0; }
    *result = values[(size_t) index];
    return 1;"""
        for variant in range(4):
            exercise = tutorial_practice("c", "safety", variant)
            self.assertIsNotNone(exercise)
            self.assertIn(placeholder, exercise["starterSource"])
            for replacement, expected in ((solution, "passed"), (placeholder, "output_mismatch")):
                with self.subTest(variant=variant, expected=expected):
                    result = self.run_program(self.compile(exercise["starterSource"].replace(placeholder, replacement)))
                    self.assertEqual((result.returncode, result.stderr), (0, ""))
                    evaluation = evaluate_tutorial_practice(exercise, {
                        "compiled": True, "run": {"exitCode": result.returncode, "stdout": result.stdout},
                    }, "")
                    self.assertEqual(evaluation["status"], expected)

    def test_testing_practice_checks_both_good_and_bad_implementations(self) -> None:
        placeholder = """    /* Replace this placeholder with an always-active comparison. */
    (void) actual;
    (void) expected;
    return 0;"""
        for variant in range(4):
            exercise = tutorial_practice("c", "testing", variant)
            self.assertIsNotNone(exercise)
            for flags in ((), ("-DNDEBUG",)):
                for replacement, passed in (("    return actual != expected;", True),
                                            ("    return actual == expected;", False),
                                            (placeholder, False)):
                    with self.subTest(variant=variant, flags=flags, replacement=replacement):
                        source = exercise["starterSource"].replace(placeholder, replacement)
                        result = self.run_program(self.compile(source, *flags))
                        self.assertEqual((result.returncode, result.stderr), (0, ""))
                        self.assertEqual(result.stdout == exercise["expectedOutput"], passed)


class TutorialCSafetyContentTestCase(unittest.TestCase):
    def test_guided_complete_programs_match_runnable_sources(self) -> None:
        for key in ("safety", "testing"):
            page = next(page for page in C_PAGES if page["key"] == key)
            blocks = page["content"]["blocks"]
            self.assertGreaterEqual(sum(block["type"] == "heading" for block in blocks), 6)
            self.assertTrue(any(block["type"] == "callout" for block in blocks))
            sources = [block["source"] for block in blocks if block["type"] == "code"]
            examples = [example for example in C_EXAMPLES if example["page_key"] == key]
            self.assertEqual(len(examples), 2 if key == "safety" else 3)
            for example in examples:
                self.assertIn(example["source"], sources)
