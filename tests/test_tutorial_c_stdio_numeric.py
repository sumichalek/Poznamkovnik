from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.tutorial_c_examples import (
    BINARY_ROUNDTRIP, CLASSIFY_BYTES, CONVERT_SIZES, FORMAT_RESULT,
    INTEGER_CONVERSIONS, INTEGER_LIMITS, SNPRINTF_MESSAGE,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice


FORMAT_PLACEHOLDER = """    /* Replace this placeholder with the three return-value checks. */
    (void) required;
    (void) capacity;
    return FORMAT_OK;"""
FORMAT_SOLUTION = """    if (required < 0) { return FORMAT_ERROR; }
    if ((uintmax_t) required >= (uintmax_t) capacity) { return FORMAT_TRUNCATED; }
    return FORMAT_OK;"""
CTYPE_PLACEHOLDER = """    /* Replace this placeholder with unsigned-byte classification. */
    (void) value;
    return 0;"""
CTYPE_SOLUTION = """    unsigned char byte = (unsigned char) value;
    if (isdigit(byte) != 0) { return 1; }
    if (isspace(byte) != 0) { return 2; }
    return 0;"""


@unittest.skipUnless(shutil.which("gcc"), "C stdio and numeric examples require GCC")
class TutorialCStdioNumericTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-stdio-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def compile_source(self, source: str, *flags: str) -> subprocess.CompletedProcess[str]:
        path = self.root / "main.c"
        path.write_text(source, encoding="utf-8")
        return subprocess.run(
            ["gcc", "-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion",
             "-Wshadow", "-Wformat=2", "-Werror", "-O1", "-fsanitize=undefined",
             "-fno-sanitize-recover=all", *flags, str(path), "-o", str(self.root / "program")],
            capture_output=True, text=True, timeout=15,
        )

    def run_source(self, source: str, *flags: str, stdin: bytes = b"") -> subprocess.CompletedProcess[bytes]:
        build = self.compile_source(source, *flags)
        self.assertEqual(build.returncode, 0, build.stderr)
        return subprocess.run(
            [str(self.root / "program")], input=stdin, capture_output=True, timeout=5, cwd=self.root,
        )

    def test_formatting_and_binary_examples_have_exact_outputs(self) -> None:
        for source, output in (
            (SNPRINTF_MESSAGE, b"capacity=9 required=8 status=0 text=[value=42]\n"
                               b"capacity=8 required=8 status=2 text=[value=4]\n"
                               b"capacity=1 required=8 status=2 text=[]\n"
                               b"capacity=0 required=8 status=2 text=[old]\n"),
            (BINARY_ROUNDTRIP, b"41 00 FF 0A\n"),
        ):
            with self.subTest(output=output):
                result = self.run_source(source, "-DNDEBUG")
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, output, b""))

    def test_format_result_checks_error_before_unsigned_comparison_and_exact_fit(self) -> None:
        result = self.run_source(FORMAT_RESULT + r"""
#include <limits.h>
#include <stdlib.h>
int main(void)
{
    const size_t capacities[] = {0, 1, 8, 9, SIZE_MAX};
    for (size_t i = 0; i < sizeof capacities / sizeof capacities[0]; ++i) {
        if (format_result(-1, capacities[i]) != FORMAT_ERROR ||
            format_result(INT_MIN, capacities[i]) != FORMAT_ERROR) { return EXIT_FAILURE; }
    }
    if (format_result(0, 0) != FORMAT_TRUNCATED || format_result(0, 1) != FORMAT_OK ||
        format_result(8, 8) != FORMAT_TRUNCATED || format_result(8, 9) != FORMAT_OK ||
        format_result(INT_MAX, 9) != FORMAT_TRUNCATED) { return EXIT_FAILURE; }
#if SIZE_MAX > INT_MAX
    if (format_result(INT_MAX, SIZE_MAX) != FORMAT_OK) { return EXIT_FAILURE; }
#endif
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, b""))

    def test_formatting_error_does_not_print_a_partially_written_buffer(self) -> None:
        result = self.run_source(r"""
#include <stdio.h>
#include <string.h>
static int fail_format(char *target, size_t capacity, const char *format, ...)
{
    (void) format;
    if (capacity != 0) { memset(target, 'X', capacity); }
    return -1;
}
#define snprintf fail_format
""" + SNPRINTF_MESSAGE)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((result.stdout, result.stderr), (b"", b"Formatting failed.\n"))

    def test_mismatched_variadic_format_types_are_compile_errors_not_runnable_examples(self) -> None:
        for expression in ('printf("%d", "wrong")', 'printf("%f", 42)', 'printf("%Lf", 1.0)'):
            with self.subTest(expression=expression):
                result = self.compile_source("#include <stdio.h>\nint main(void) { return " + expression + "; }\n")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("format", result.stderr)

    def test_binary_stream_failure_paths_close_once_and_never_report_success(self) -> None:
        wrappers = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int mode;
static int closes;
static FILE *active;
static FILE *controlled_tmpfile(void)
{
    if (mode == 1) { return NULL; }
    active = tmpfile();
    if (active == NULL) { abort(); }
    return active;
}
static size_t controlled_write(const void *ptr, size_t size, size_t count, FILE *file)
{
    return fwrite(ptr, size, mode == 2 || mode == 9 ? count - 1 : count, file);
}
static int controlled_flush(FILE *file)
{
    return mode == 3 && file == active ? EOF : fflush(file);
}
static int controlled_seek(FILE *file, long offset, int origin)
{
    return mode == 4 ? -1 : fseek(file, offset, origin);
}
static size_t controlled_read(void *ptr, size_t size, size_t count, FILE *file)
{
    size_t read = fread(ptr, size, count, file);
    if (mode == 5 || mode == 6) { return read == 0 ? 0 : read - 1; }
    if (mode == 7 && read != 0) { ((unsigned char *) ptr)[0] ^= 1; }
    return read;
}
static int controlled_error(FILE *file) { return mode == 6 ? 1 : ferror(file); }
static int controlled_close(FILE *file)
{
    if (file != active || closes != 0) { abort(); }
    ++closes;
    active = NULL;
    int result = fclose(file);
    return mode == 8 || mode == 9 ? EOF : result;
}
#define tmpfile controlled_tmpfile
#define fwrite controlled_write
#define fflush controlled_flush
#define fseek controlled_seek
#define fread controlled_read
#define ferror controlled_error
#define fclose controlled_close
#define main lesson_main
"""
        for mode, message in enumerate((
            "Cannot open temporary file.", "Write failed.", "Write failed.", "Seek failed.",
            "Unexpected end.", "Read failed.", "Data differs.", "Close failed.", "Write failed.\nClose failed.",
        ), 1):
            with self.subTest(mode=mode):
                source = wrappers + BINARY_ROUNDTRIP + "\n#undef main\nint main(void) {\n" + (
                    f"    mode = {mode};\n"
                    "    int result = lesson_main();\n"
                    f"    return result != EXIT_SUCCESS && closes == {0 if mode == 1 else 1} "
                    "&& active == NULL ? EXIT_SUCCESS : EXIT_FAILURE;\n}\n"
                )
                result = self.run_source(source)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", (message + "\n").encode()))

    def test_classification_reads_all_256_bytes_without_confusing_ff_and_eof(self) -> None:
        expected = "".join(
            f"{byte:02X} digit={int(48 <= byte <= 57)} space={int(byte in (9, 10, 11, 12, 13, 32))} "
            f"upper={byte - 32 if 97 <= byte <= 122 else byte:02X}\n"
            for byte in range(256)
        ).encode()
        for flag in ("-fsigned-char", "-funsigned-char"):
            with self.subTest(flag=flag):
                result = self.run_source(CLASSIFY_BYTES, flag, stdin=bytes(range(256)))
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, b""))

    def test_character_input_distinguishes_clean_eof_and_read_error(self) -> None:
        clean = self.run_source(CLASSIFY_BYTES)
        self.assertEqual((clean.returncode, clean.stdout, clean.stderr), (0, b"", b""))
        error = self.run_source(r"""
#include <stdio.h>
static int failed_get(FILE *file) { (void) file; return EOF; }
static int failed_error(FILE *file) { (void) file; return 1; }
#define fgetc failed_get
#define ferror failed_error
""" + CLASSIFY_BYTES)
        self.assertNotEqual(error.returncode, 0)
        self.assertEqual((error.stdout, error.stderr), (b"", b"Read failed.\n"))

    def test_limits_use_matching_formats_for_both_char_modes(self) -> None:
        for flag in ("-fsigned-char", "-funsigned-char"):
            with self.subTest(flag=flag):
                result = self.run_source(INTEGER_LIMITS, flag)
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                fields = dict(field.split("=") for field in result.stdout.decode().split())
                self.assertGreaterEqual(int(fields["CHAR_BIT"]), 8)
                self.assertGreaterEqual(int(fields["sizeof(int)"]), 1)
                self.assertLessEqual(int(fields["INT_MIN"]), -32767)
                self.assertGreaterEqual(int(fields["INT_MAX"]), 32767)
                self.assertGreaterEqual(int(fields["SIZE_MAX"]), 65535)
                self.assertEqual(fields["measurement"], "123456")
                self.assertEqual(fields["count"], "9000000000")
                self.assertEqual(int(fields["CHAR_MIN"]) < 0, flag == "-fsigned-char")

    def test_size_conversions_reject_out_of_range_before_writing_output(self) -> None:
        result = self.run_source(INTEGER_CONVERSIONS + r"""
#include <stdlib.h>
int main(void)
{
    size_t size = 77;
    int integer = 77;
    if (int_to_size(INT_MIN, &size) != CONVERT_RANGE || size != 77 ||
        int_to_size(-1, &size) != CONVERT_RANGE || size != 77 ||
        int_to_size(-1, NULL) != CONVERT_ARGUMENT ||
        size_to_int(SIZE_MAX, NULL) != CONVERT_ARGUMENT) { return EXIT_FAILURE; }
    for (int value = 0; value <= 100; ++value) {
        if (int_to_size(value, &size) != CONVERT_OK || size != (size_t) value ||
            size_to_int(size, &integer) != CONVERT_OK || integer != value) { return EXIT_FAILURE; }
    }
#if SIZE_MAX > INT_MAX
    integer = 77;
    if (size_to_int((size_t) INT_MAX + 1, &integer) != CONVERT_RANGE || integer != 77 ||
        size_to_int(SIZE_MAX, &integer) != CONVERT_RANGE || integer != 77 ||
        size_to_int((size_t) INT_MAX, &integer) != CONVERT_OK || integer != INT_MAX ||
        int_to_size(INT_MAX, &size) != CONVERT_OK || size != (size_t) INT_MAX) { return EXIT_FAILURE; }
#else
    size = 77;
#if SIZE_MAX < INT_MAX
    if (int_to_size((int) SIZE_MAX + 1, &size) != CONVERT_RANGE || size != 77) { return EXIT_FAILURE; }
#endif
    if (int_to_size((int) SIZE_MAX, &size) != CONVERT_OK || size != SIZE_MAX ||
        size_to_int(SIZE_MAX, &integer) != CONVERT_OK || integer != (int) SIZE_MAX) { return EXIT_FAILURE; }
#endif
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        demo = self.run_source(CONVERT_SIZES)
        self.assertEqual((demo.returncode, demo.stderr), (0, b""))
        self.assertTrue(demo.stdout.startswith(
            b"to-size -1: status=2 value=77\nto-size 0: status=0 value=0\nto-size 12: status=0 value=12\n"
            b"to-int case=0: status=0 value=0\nto-int case=1: status=0 value=12\n"
        ))

    def test_all_practice_variants_accept_solutions_and_reject_starters(self) -> None:
        for topic, placeholder, solution in (
            ("stdio-reference", FORMAT_PLACEHOLDER, FORMAT_SOLUTION),
            ("numeric-reference", CTYPE_PLACEHOLDER, CTYPE_SOLUTION),
        ):
            for variant in range(4):
                exercise = tutorial_practice("c", topic, variant)
                self.assertIsNotNone(exercise)
                self.assertIn(placeholder, exercise["starterSource"])
                for replacement, expected in ((solution, "passed"), (placeholder, "output_mismatch")):
                    with self.subTest(topic=topic, variant=variant, expected=expected):
                        result = self.run_source(exercise["starterSource"].replace(placeholder, replacement))
                        self.assertEqual((result.returncode, result.stderr), (0, b""))
                        evaluation = evaluate_tutorial_practice(exercise, {
                            "compiled": True, "run": {"exitCode": result.returncode, "stdout": result.stdout.decode()},
                        }, "")
                        self.assertEqual(evaluation["status"], expected)

    def test_ctype_solution_obeys_argument_domain_and_accepts_nonunit_true_values(self) -> None:
        guards = r"""
#include <ctype.h>
#include <limits.h>
#include <stdlib.h>
static int checked_digit(int ch)
{
    if (ch < 0 || ch > UCHAR_MAX) { exit(99); }
    return ch >= '0' && ch <= '9' ? 2048 : 0;
}
static int checked_space(int ch)
{
    if (ch < 0 || ch > UCHAR_MAX) { exit(99); }
    return ch == ' ' || ch == '\t' || ch == '\n' ? 8192 : 0;
}
#undef isdigit
#undef isspace
#define isdigit checked_digit
#define isspace checked_space
"""
        exercise = tutorial_practice("c", "numeric-reference", 3)
        for flag in ("-fsigned-char", "-funsigned-char"):
            result = self.run_source(guards + exercise["starterSource"].replace(CTYPE_PLACEHOLDER, CTYPE_SOLUTION), flag)
            self.assertEqual((result.returncode, result.stdout.decode(), result.stderr), (0, exercise["expectedOutput"], b""))
        mutant = CTYPE_SOLUTION.replace("unsigned char byte = (unsigned char) value;", "int byte = value;")
        invalid = self.run_source(guards + exercise["starterSource"].replace(CTYPE_PLACEHOLDER, mutant), "-fsigned-char")
        self.assertEqual(invalid.returncode, 99)
        nonunit = self.run_source(guards + exercise["starterSource"].replace(CTYPE_PLACEHOLDER, CTYPE_SOLUTION.replace("!= 0", "== 1")))
        self.assertEqual(nonunit.returncode, 0)
        self.assertNotEqual(nonunit.stdout.decode(), exercise["expectedOutput"])

    def test_reference_code_blocks_and_runnable_sources_stay_identical(self) -> None:
        for key in ("stdio-reference", "numeric-reference"):
            page = next(page for page in C_PAGES if page["key"] == key)
            self.assertEqual(page["kind"], "reference")
            sources = [block["source"] for block in page["content"]["blocks"] if block["type"] == "code"]
            examples = [example for example in C_EXAMPLES if example["page_key"] == key]
            self.assertEqual(len(examples), 3)
            for example in examples:
                self.assertIn(example["source"], sources)
