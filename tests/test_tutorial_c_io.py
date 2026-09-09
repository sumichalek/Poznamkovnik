from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.tutorial_c_examples import (
    FILE_ROUNDTRIP, FORMATTED_OUTPUT, INT_PARSER, LINE_READER,
    PARSE_NUMBER, PARSE_POSITIVE, POSITIVE_PARSER, READ_LINES,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice


@unittest.skipUnless(shutil.which("gcc"), "C input lessons require GCC")
class TutorialCIOTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-io-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def compile(self, source: str) -> Path:
        path = self.root / "main.c"
        path.write_text(source, encoding="utf-8")
        program = self.root / "program"
        result = subprocess.run(
            ["gcc", "-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion",
             "-Wshadow", "-Wformat=2", "-Werror", "-O1", "-fsanitize=undefined",
             "-fno-sanitize-recover=all", str(path), "-o", str(program)],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return program

    def run_program(self, program: Path, stdin: str = "", *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(program), *args], input=stdin, capture_output=True,
            text=True, timeout=5, cwd=self.root,
        )

    def test_number_input_distinguishes_empty_invalid_range_and_truncated_lines(self) -> None:
        program = self.compile(PARSE_NUMBER)
        for text, expected in (("21\n", 21), ("  +24 \t\n", 24), ("0", 0),
                               ("-12\n", -12), ("7" + " " * 62, 7)):
            with self.subTest(text=text):
                result = self.run_program(program, text)
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (0, f"value: {expected}\n", ""))
        for text, error in (
            ("", "No input."), ("\n", "Expected an integer."),
            ("   \t\n", "Expected an integer."), ("21abc\n", "Expected an integer."),
            ("1 2\n", "Expected an integer."), ("+\n", "Expected an integer."),
            ("9" * 60 + "\n", "Number out of range."),
            ("7" + " " * 63 + "\n", "Line too long."),
            ("7" + " " * 80 + "x\n", "Line too long."),
            ("21\0abc\n", "NUL byte rejected."),
        ):
            with self.subTest(text=text):
                result = self.run_program(program, text)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, error + "\n")

    def test_lines_recover_after_rejection_and_accept_exact_boundary_and_final_eof(self) -> None:
        program = self.compile(READ_LINES)
        for text, output, error in (
            ("", "", ""),
            ("\n", "[]\n", ""),
            ("1234567\nOK", "[1234567]\n[OK]\n", ""),
            ("1234567", "[1234567]\n", ""),
            ("12345678", "", "Line too long.\n"),
            ("12345678\nOK\n", "[OK]\n", "Line too long.\n"),
            ("ab\0cd\nOK", "[OK]\n", "NUL byte rejected.\n"),
            ("x" * 10000 + "\n\nOK", "[]\n[OK]\n", "Line too long.\n"),
        ):
            with self.subTest(text=text[:30]):
                result = self.run_program(program, text)
                self.assertEqual(result.stdout, output)
                self.assertEqual(result.stderr, error)
                self.assertEqual(result.returncode == 0, not error)

    def test_parser_boundaries_nulls_errno_and_unchanged_outputs(self) -> None:
        source = INT_PARSER + POSITIVE_PARSER + r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    int value = 77;
    const char *invalid[] = {"", " ", "\t\r\n", "+", "-", "12x", "1 2", "0x10"};
    for (size_t i = 0; i < sizeof invalid / sizeof invalid[0]; ++i) {
        assert(parse_int(invalid[i], &value) == PARSE_INVALID);
        assert(value == 77);
    }
    assert(parse_int(NULL, &value) == PARSE_ARGUMENT && value == 77);
    assert(parse_int("24", NULL) == PARSE_ARGUMENT);
    assert(parse_positive(NULL, &value) == PARSE_ARGUMENT && value == 77);
    assert(parse_positive("24", NULL) == PARSE_ARGUMENT);
    assert(parse_positive("0", &value) == PARSE_INVALID && value == 77);
    assert(parse_positive("-1", &value) == PARSE_INVALID && value == 77);

    char text[sizeof(long) * CHAR_BIT + 5];
    assert(snprintf(text, sizeof text, "%d", INT_MIN) > 0);
    assert(parse_int(text, &value) == PARSE_OK && value == INT_MIN);
    assert(snprintf(text, sizeof text, "%d", INT_MAX) > 0);
    assert(parse_int(text, &value) == PARSE_OK && value == INT_MAX);
#if LONG_MAX > INT_MAX
    assert(snprintf(text, sizeof text, "%ld", (long) INT_MAX + 1L) > 0);
    value = 77;
    assert(parse_int(text, &value) == PARSE_RANGE && value == 77);
    assert(snprintf(text, sizeof text, "%ld", (long) INT_MIN - 1L) > 0);
    assert(parse_int(text, &value) == PARSE_RANGE && value == 77);
#endif
    memset(text, '9', sizeof text - 1);
    text[sizeof text - 1] = '\0';
    value = 77;
    assert(parse_int(text, &value) == PARSE_RANGE && value == 77);
    text[0] = '-';
    assert(parse_positive(text, &value) == PARSE_RANGE && value == 77);
    text[sizeof text - 2] = 'x';
    assert(parse_int(text, &value) == PARSE_INVALID && value == 77);
    errno = ERANGE;
    assert(parse_int("  +12 \t", &value) == PARSE_OK && value == 12);
    assert(parse_int("0", &value) == PARSE_OK && value == 0);
    assert(parse_int("012", &value) == PARSE_OK && value == 12);
    assert(parse_positive("24", &value) == PARSE_OK && value == 24);
    return 0;
}
"""
        result = self.run_program(self.compile(source))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_partial_read_error_clears_output_instead_of_returning_a_partial_line(self) -> None:
        source = r"""#include <stdio.h>
static int fake_getc(FILE *stream)
{
    static int calls = 0;
    (void) stream;
    return calls++ == 0 ? 'A' : EOF;
}
static int fake_error(FILE *stream) { (void) stream; return 1; }
#define fgetc fake_getc
#define ferror fake_error
""" + LINE_READER + r"""
#include <assert.h>
int main(void)
{
    char line[2] = "x";
    assert(read_line(stdin, line, sizeof line) == LINE_ERROR);
    assert(line[0] == '\0');
    return 0;
}
"""
        result = self.run_program(self.compile(source))
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_file_example_closes_exactly_once_on_every_failure_path(self) -> None:
        source = r"""#include <stdio.h>
#include <stdarg.h>
#include <assert.h>
static int fail_stage;
static int closes;
static FILE *fake_tmpfile(void) { return fail_stage == 1 ? NULL : tmpfile(); }
static int fake_fprintf(FILE *file, const char *format, ...)
{
    if (fail_stage == 2) { return -1; }
    va_list args;
    va_start(args, format);
    int result = vfprintf(file, format, args);
    va_end(args);
    return result;
}
static int fake_fflush(FILE *file)
{
    if ((fail_stage == 3 && file != stdout) ||
        (fail_stage == 8 && file == stdout)) { return EOF; }
    return fflush(file);
}
static int fake_fseek(FILE *file, long offset, int origin)
{
    return fail_stage == 4 ? -1 : fseek(file, offset, origin);
}
static char *fake_fgets(char *line, int capacity, FILE *file)
{
    return fail_stage == 5 || fail_stage == 6 ? NULL : fgets(line, capacity, file);
}
static int fake_ferror(FILE *file)
{
    return fail_stage == 6 ? 1 : ferror(file);
}
static int fake_fclose(FILE *file)
{
    ++closes;
    int result = fclose(file);
    return fail_stage == 7 ? EOF : result;
}
#define tmpfile fake_tmpfile
#define fprintf fake_fprintf
#define fflush fake_fflush
#define fseek fake_fseek
#define fgets fake_fgets
#define ferror fake_ferror
#define fclose fake_fclose
#define main lesson_main
""" + FILE_ROUNDTRIP + r"""
#undef main
int main(int argc, char **argv)
{
    assert(argc == 2);
    fail_stage = argv[1][0] - '0';
    int result = lesson_main();
    assert(closes == (fail_stage == 1 ? 0 : 1));
    return result;
}
"""
        program = self.compile(source)
        messages = ("", "Cannot open temporary file.", "File write failed.",
                    "File write failed.", "Cannot seek to start.",
                    "File unexpectedly empty.", "File read failed.",
                    "File close failed.", "")
        for stage, message in enumerate(messages):
            with self.subTest(stage=stage):
                result = self.run_program(program, "", str(stage))
                self.assertEqual(result.returncode == 0, stage == 0)
                self.assertEqual(result.stderr, message + "\n" if message else "")
                self.assertEqual(result.stdout, "measurement=21\n" if stage in {0, 8} else "")

    def test_runnable_examples_are_the_same_programs_as_the_worked_examples(self) -> None:
        for key, source in (("formatted-output", FORMATTED_OUTPUT),
                            ("whole-lines", READ_LINES), ("file-roundtrip", FILE_ROUNDTRIP),
                            ("parse-positive", PARSE_POSITIVE)):
            with self.subTest(key=key):
                example = next(item for item in C_EXAMPLES if item["key"] == key)
                self.assertEqual(example["source"], source)
                page = next(item for item in C_PAGES if item["key"] == example["page_key"])
                self.assertIn(source, [b["source"] for b in page["content"]["blocks"] if b["type"] == "code"])
                result = self.run_program(self.compile(source), example["stdin"])
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                if key == "file-roundtrip":
                    self.assertEqual(result.stdout, "measurement=21\n")
                elif key == "formatted-output":
                    self.assertRegex(result.stdout, r"^count: 3, bytes: \d+, average: 3\.50\nprogress: 100%\n$")
                elif key == "whole-lines":
                    self.assertEqual(result.stdout, "[abc]\n[1234567]\n[OK]\n")
                else:
                    self.assertEqual(result.stdout.splitlines()[:6], [
                        '"24": OK, value=24', '"": INVALID, value=77',
                        '"   ": INVALID, value=77', '"12x": INVALID, value=77',
                        '"0": INVALID, value=77', '"-2": INVALID, value=77',
                    ])
                    self.assertTrue(result.stdout.endswith('": RANGE, value=77\n'))

    def test_all_practice_variants_run_real_solutions(self) -> None:
        replacements = {
            "io": (
                "/* Replace this placeholder with handling of all five states. */\n        (void) status;\n        break;",
                "if (status == LINE_END) break;\n"
                "        if (status == LINE_ERROR) return EXIT_FAILURE;\n"
                "        if (status == LINE_OK) ++accepted; else ++rejected;",
            ),
            "errors": (
                "/* Replace this placeholder with checks and one final assignment. */\n    (void) requested;\n    (void) result;\n    return SET_OK;",
                "if (result == NULL) return SET_ARGUMENT;\n"
                "    if (requested < 1 || requested > 5) return SET_RANGE;\n"
                "    *result = requested;\n    return SET_OK;",
            ),
        }
        for topic, (placeholder, solution) in replacements.items():
            for variant in range(5 if topic == "io" else 4):
                with self.subTest(topic=topic, variant=variant):
                    exercise = tutorial_practice("c", topic, variant)
                    self.assertIn(placeholder, exercise["starterSource"])
                    source = exercise["starterSource"].replace(placeholder, solution)
                    result = self.run_program(self.compile(source), exercise["stdin"])
                    self.assertEqual((result.returncode, result.stderr), (0, ""))
                    self.assertEqual(result.stdout, exercise["expectedOutput"])
                    evaluation = evaluate_tutorial_practice(exercise, {
                        "compiled": True, "run": {"exitCode": result.returncode, "stdout": result.stdout},
                    }, exercise["stdin"])
                    self.assertEqual(evaluation["status"], "passed")
