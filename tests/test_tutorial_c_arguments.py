from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.code_runner import DevelopmentCodeRunner
from backend.tutorial_c_examples import (
    ARGUMENT_CASES, ARGUMENT_LIST, ARGUMENT_LIST_FUNCTION,
    ARGUMENT_NUMBER, ARGUMENT_PARSER, INT_PARSER,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice


ARGUMENT_PLACEHOLDER = """    /* Check the count before indexing; delegate conversion to parse_int. */
    (void) argc;
    (void) argv;
    return parse_int(NULL, result);"""
ARGUMENT_SOLUTION = """    if (argc != 2 || argv == NULL) { return PARSE_ARGUMENT; }
    return parse_int(argv[1], result);"""
USAGE = "Usage: number INTEGER\n"
INVALID = "Expected one complete decimal integer.\n"
RANGE = "Integer out of range.\n"
CASES_OUTPUT = ("valid: matched=1 value=42\nmissing: matched=1 value=77\n"
                "extra: matched=1 value=77\ninvalid: matched=1 value=77\nempty: matched=1 value=77\n")
REQUIRE = '#include <stdlib.h>\n#define REQUIRE(test) do { if (!(test)) { exit(80); } } while (0)\n'


class TutorialCArgumentsContentTestCase(unittest.TestCase):
    def test_lesson_has_three_complete_programs_between_io_and_errors(self) -> None:
        page = next(page for page in C_PAGES if page["key"] == "arguments")
        examples = [item for item in C_EXAMPLES if item["page_key"] == "arguments"]
        self.assertEqual(len(examples), 3)
        sources = [block["source"] for block in page["content"]["blocks"] if block["type"] == "code"]
        for example in examples:
            self.assertIn(example["source"], sources)
        self.assertEqual(page["parent_key"], "tooling")
        positions = {page["key"]: page["position"] for page in C_PAGES}
        self.assertLess(positions["io"], positions["arguments"])
        self.assertLess(positions["arguments"], positions["errors"])


@unittest.skipUnless(shutil.which("gcc"), "C argument examples require GCC")
class TutorialCArgumentsNativeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-arguments-")
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

    def run_program(self, program: Path, arguments: tuple[str, ...] = (), stdin: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(program), *arguments], input=stdin, capture_output=True,
                              text=True, timeout=5, cwd=self.root)

    def test_list_preserves_argument_boundaries_empty_strings_and_literal_data(self) -> None:
        program = self.compile(ARGUMENT_LIST)
        for arguments in ((), ("dve slova", "", "%s", "$HOME", "*.c", ";", "$(echo ignored)")):
            result = self.run_program(program, arguments, "42\n")
            expected = f"arguments={len(arguments)}\n" + "".join(
                f"argv[{index}]=[{value}]\n" for index, value in enumerate(arguments, 1)
            )
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ""))

    def test_list_handles_zero_count_empty_program_name_and_rejects_invalid_interface(self) -> None:
        main = r"""
int main(void)
{
    char *zero[] = {NULL};
    char *unnamed[] = {"", NULL};
    REQUIRE(show_arguments(0, zero) == EXIT_SUCCESS);
    REQUIRE(show_arguments(1, unnamed) == EXIT_SUCCESS);
    REQUIRE(show_arguments(-1, zero) == EXIT_FAILURE);
    REQUIRE(show_arguments(0, NULL) == EXIT_FAILURE);
    return 0;
}
"""
        result = self.run_program(self.compile(REQUIRE + ARGUMENT_LIST_FUNCTION + main))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "arguments=0\narguments=0\n", ""))

    def test_cli_accepts_decimal_signs_zero_and_surrounding_whitespace(self) -> None:
        program = self.compile(ARGUMENT_NUMBER)
        for text, number in (("42", 42), ("-7", -7), ("0", 0), ("+42", 42), ("  +42\t", 42), ("010", 10)):
            with self.subTest(text=text):
                result = self.run_program(program, (text,), "999\n")
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, f"value={number}\n", ""))

    def test_cli_distinguishes_wrong_count_invalid_text_and_range(self) -> None:
        program = self.compile(ARGUMENT_NUMBER)
        cases = [((), USAGE), (("42", "9"), USAGE)]
        cases += [((text,), INVALID) for text in ("", " ", "+", "-", "42x", "0x10", "1 2", "--help", "--")]
        cases += [(("9" * 100,), RANGE), (("-" + "9" * 100,), RANGE)]
        for arguments, diagnostic in cases:
            with self.subTest(arguments=arguments):
                result = self.run_program(program, arguments, "42\n")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((result.stdout, result.stderr), ("", diagnostic))

    def test_cli_checks_int_limits_before_narrowing(self) -> None:
        limits = self.run_program(self.compile('#include <limits.h>\n#include <stdio.h>\n'
                                              'int main(void) { printf("%d %d\\n", INT_MIN, INT_MAX); return 0; }\n'))
        self.assertEqual(limits.returncode, 0, limits.stderr)
        minimum, maximum = map(int, limits.stdout.split())
        program = self.compile(ARGUMENT_NUMBER)
        for number in (minimum - 1, minimum, maximum, maximum + 1):
            result = self.run_program(program, (str(number),))
            if minimum <= number <= maximum:
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, f"value={number}\n", ""))
            else:
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((result.stdout, result.stderr), ("", RANGE))

    def test_helper_checks_count_before_access_and_preserves_output_on_every_failure(self) -> None:
        main = r"""
int main(void)
{
    char *short_vector[] = {NULL};
    char *valid[] = {"", "42", NULL};
    char *null_text[] = {"number", NULL, NULL};
    char *invalid[] = {"number", "42x", NULL};
    char *range[] = {"number", "99999999999999999999999999999999999999999999999999", NULL};
    int value = 77;
    const int counts[] = {-1, 0, 1, 3, INT_MAX};
    for (size_t i = 0; i < sizeof counts / sizeof counts[0]; ++i) {
        REQUIRE(parse_number_argument(counts[i], short_vector, &value) == PARSE_ARGUMENT);
        REQUIRE(value == 77);
    }
    REQUIRE(parse_number_argument(2, NULL, &value) == PARSE_ARGUMENT);
    REQUIRE(value == 77);
    REQUIRE(parse_number_argument(2, null_text, &value) == PARSE_ARGUMENT);
    REQUIRE(value == 77);
    REQUIRE(parse_number_argument(2, invalid, &value) == PARSE_INVALID);
    REQUIRE(value == 77);
    REQUIRE(parse_number_argument(2, range, &value) == PARSE_RANGE);
    REQUIRE(value == 77);
    REQUIRE(parse_number_argument(2, valid, NULL) == PARSE_ARGUMENT);
    REQUIRE(parse_number_argument(2, valid, &value) == PARSE_OK);
    REQUIRE(value == 42);
    return 0;
}
"""
        result = self.run_program(self.compile(REQUIRE + INT_PARSER + ARGUMENT_PARSER + main))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_fixture_program_is_identical_with_optimization_and_ndebug(self) -> None:
        for flags in (("-O0",), ("-O2", "-DNDEBUG")):
            result = self.run_program(self.compile(ARGUMENT_CASES, *flags))
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, CASES_OUTPUT, ""))

    def test_examples_fail_on_output_errors(self) -> None:
        failed_print = r"""#include <stdio.h>
static int failed_printf(const char *format, ...) { (void) format; return -1; }
#define printf failed_printf
"""
        failed_flush = r"""#include <stdio.h>
static int failed_fflush(FILE *stream) { (void) stream; return EOF; }
#define fflush failed_fflush
"""
        for source, arguments in ((ARGUMENT_LIST, ("one",)), (ARGUMENT_NUMBER, ("42",)), (ARGUMENT_CASES, ())):
            for prefix in (failed_print, failed_flush):
                result = self.run_program(self.compile(prefix + source), arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")

    def test_all_exercise_variants_accept_solution_and_reject_wrong_guards_or_index(self) -> None:
        for variant in range(4):
            exercise = tutorial_practice("c", "arguments", variant)
            self.assertEqual(exercise["starterSource"].count(ARGUMENT_PLACEHOLDER), 1)
            for body, passed in (
                (ARGUMENT_SOLUTION, True), (ARGUMENT_PLACEHOLDER, False),
                (ARGUMENT_SOLUTION.replace("argc != 2", "argc < 2"), False),
                (ARGUMENT_SOLUTION.replace("argv[1]", "argv[0]"), False),
            ):
                with self.subTest(variant=variant, body=body):
                    result = self.run_program(self.compile(exercise["starterSource"].replace(ARGUMENT_PLACEHOLDER, body)))
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(result.returncode == 0, passed)
                    evaluation = evaluate_tutorial_practice(exercise, {
                        "compiled": True, "run": {"exitCode": result.returncode, "stdout": result.stdout, "stderr": ""}
                    }, "")
                    self.assertEqual(evaluation["status"] == "passed", passed)


class TutorialCArgumentsSandboxTestCase(unittest.TestCase):
    def test_default_examples_have_documented_outcomes_in_debug_sandbox(self) -> None:
        runner = DevelopmentCodeRunner()
        status = runner.status()["languages"]["c"]
        if not status["available"]:
            self.skipTest(status["message"])
        for source, success, stdout, stderr in (
            (ARGUMENT_LIST, True, "arguments=0\n", ""),
            (ARGUMENT_NUMBER, False, "", USAGE),
            (ARGUMENT_CASES, True, CASES_OUTPUT, ""),
        ):
            result = runner.run("c", source, "42\n")
            self.assertTrue(result["compiled"], result)
            self.assertEqual(result["buildProfile"], "debug")
            self.assertEqual(result["run"]["exitCode"] == 0, success, result)
            self.assertEqual((result["run"]["stdout"], result["run"]["stderr"]), (stdout, stderr))


if __name__ == "__main__":
    unittest.main()
