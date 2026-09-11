from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.tutorial_c_examples import (
    COMPARE_INTS, COMPARE_STRINGS, COPY_TEXT, COPY_TEXT_DEMO,
    GROW_BUFFER, INT_PARSER, MOVE_TEXT, SORT_SEARCH, STRTOL_REFERENCE,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice


@unittest.skipUnless(shutil.which("gcc"), "C reference examples require GCC")
class TutorialCReferenceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-reference-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def run_source(self, source: str, *flags: str) -> subprocess.CompletedProcess[str]:
        path = self.root / "main.c"
        path.write_text(source, encoding="utf-8")
        program = self.root / "program"
        build = subprocess.run(
            ["gcc", "-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion",
             "-Wshadow", "-Wformat=2", "-Werror", "-O1", "-fsanitize=undefined",
             "-fno-sanitize-recover=all", *flags, str(path), "-o", str(program)],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(build.returncode, 0, build.stderr)
        return subprocess.run([str(program)], capture_output=True, text=True, timeout=5, cwd=self.root)

    def test_all_reference_programs_match_the_explained_outputs(self) -> None:
        for source, output in (
            (COMPARE_STRINGS, "length=3 capacity=8\nequal=1 prefix=1 full=0 order=-1\n"),
            (COPY_TEXT_DEMO, "short: status=0 text=C17\nlong: status=3 text=C17\nraw: status=2 text=C17\n"),
            (MOVE_TEXT, "> ABCDE\nABCDE\n"),
            (STRTOL_REFERENCE, "integer: status=0 value=42\nzero: status=0 value=0\nspaces: status=0 value=-7\n"
                               "suffix: status=2 value=77\nempty: status=2 value=77\nrange: status=3 value=77\n"),
            (GROW_BUFFER, "count: 5, capacity: 5\n10 20 30 40 50\n"),
            (SORT_SEARCH, "-3 0 2 7 7\nfound=7 missing=1\n"),
        ):
            with self.subTest(output=output):
                result = self.run_source(source, "-DNDEBUG")
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, output, ""))

    def test_copy_checks_every_small_capacity_and_source_boundary(self) -> None:
        result = self.run_source(COPY_TEXT + r"""
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    for (size_t length = 0; length < 8; ++length) {
        char source[9];
        memset(source, '#', sizeof source);
        memcpy(source, "ABCDEFGH", length);
        source[length] = '\0';
        for (size_t limit = 0; limit <= sizeof source; ++limit) {
            for (size_t capacity = 0; capacity <= 10; ++capacity) {
                char target[10] = "keep";
                char expected[10];
                memcpy(expected, target, sizeof target);
                CopyStatus status = limit <= length ? COPY_UNTERMINATED :
                    (length >= capacity ? COPY_SPACE : COPY_OK);
                if (status == COPY_OK) { memcpy(expected, source, length + 1); }
                if (copy_text(target, capacity, source, limit) != status ||
                    memcmp(target, expected, sizeof target) != 0) {
                    fprintf(stderr, "length=%zu limit=%zu capacity=%zu\n", length, limit, capacity);
                    return EXIT_FAILURE;
                }
            }
        }
    }
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_copy_allows_overlap_in_both_directions_and_self_copy(self) -> None:
        result = self.run_source(COPY_TEXT + r"""
#include <stdlib.h>

int main(void)
{
    for (size_t source = 0; source < 7; ++source) {
        for (size_t target = 0; target < 7; ++target) {
            for (size_t length = 0; length < 6; ++length) {
                char buffer[16];
                char before[16];
                char expected[16];
                memset(buffer, '#', sizeof buffer);
                memcpy(buffer + source, "ABCDE", length);
                buffer[source + length] = '\0';
                memcpy(before, buffer, sizeof buffer);
                memcpy(expected, buffer, sizeof buffer);
                if (copy_text(buffer + target, length, buffer + source, sizeof buffer - source) != COPY_SPACE ||
                    memcmp(buffer, before, sizeof buffer) != 0) { return EXIT_FAILURE; }
                memcpy(expected + target, before + source, length + 1);
                if (copy_text(buffer + target, sizeof buffer - target,
                              buffer + source, sizeof buffer - source) != COPY_OK ||
                    memcmp(buffer, expected, sizeof buffer) != 0) { return EXIT_FAILURE; }
            }
        }
    }
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_copy_argument_priority_embedded_nul_and_unterminated_array(self) -> None:
        result = self.run_source(COPY_TEXT + r"""
#include <stdlib.h>

int main(void)
{
    char target[8] = "keep";
    const char raw[] = {'A', 'B', 'C'};
    const char embedded[] = {'A', '\0', 'B', '\0'};
    if (copy_text(NULL, 0, NULL, 0) != COPY_ARGUMENT ||
        copy_text(NULL, 0, "", 1) != COPY_ARGUMENT ||
        copy_text(target, sizeof target, NULL, 0) != COPY_ARGUMENT ||
        copy_text(target, 0, raw, sizeof raw) != COPY_UNTERMINATED ||
        copy_text(target, 0, "", 1) != COPY_SPACE || strcmp(target, "keep") != 0) {
        return EXIT_FAILURE;
    }
    if (copy_text(target, sizeof target, embedded, sizeof embedded) != COPY_OK ||
        memcmp(target, "A\0ep\0\0\0\0", sizeof target) != 0) { return EXIT_FAILURE; }
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_prefix_move_preserves_terminator_at_exact_capacity_and_rejects_short_target(self) -> None:
        for source, output, success in (
            (MOVE_TEXT.replace("text[12]", "text[8]"), "> ABCDE\nABCDE\n", True),
            (MOVE_TEXT.replace("text[12]", "text[7]"), "", False),
            (MOVE_TEXT.replace('"ABCDE"', '""'), "> \n\n", True),
            (MOVE_TEXT.replace('"ABCDE"', '"ABCDEFGHI"'), "> ABCDEFGHI\nABCDEFGHI\n", True),
            (MOVE_TEXT.replace('"ABCDE"', '"ABCDEFGHIJ"'), "", False),
        ):
            with self.subTest(output=output, success=success):
                result = self.run_source(source)
                self.assertEqual(result.returncode == 0, success)
                self.assertEqual(result.stdout, output)
                self.assertEqual(result.stderr, "" if success else "Not enough space.\n")

    def test_comparator_sort_and_search_handle_extremes_duplicates_and_empty_range(self) -> None:
        result = self.run_source(COMPARE_INTS + r"""
#include <limits.h>

int main(void)
{
    const int pairs[][3] = {
        {INT_MIN, INT_MAX, -1}, {INT_MAX, INT_MIN, 1}, {INT_MIN, INT_MIN, 0},
        {INT_MAX, INT_MAX, 0}, {-1, 0, -1}, {0, 1, -1}, {7, -2, 1}
    };
    for (size_t i = 0; i < sizeof pairs / sizeof pairs[0]; ++i) {
        int actual = compare_ints(&pairs[i][0], &pairs[i][1]);
        if ((actual > 0) - (actual < 0) != pairs[i][2]) { return EXIT_FAILURE; }
    }
    int values[] = {INT_MAX, 7, INT_MIN, -1, 7, 0};
    const int expected[] = {INT_MIN, -1, 0, 7, 7, INT_MAX};
    const size_t count = sizeof values / sizeof values[0];
    qsort(values, count, sizeof values[0], compare_ints);
    for (size_t i = 0; i < count; ++i) {
        if (values[i] != expected[i]) { return EXIT_FAILURE; }
        const int *found = bsearch(&expected[i], values, count, sizeof values[0], compare_ints);
        if (found == NULL || *found != expected[i]) { return EXIT_FAILURE; }
    }
    int missing = 2;
    if (bsearch(&missing, values, count, sizeof values[0], compare_ints) != NULL) { return EXIT_FAILURE; }
    qsort(values, 0, sizeof values[0], compare_ints);
    if (bsearch(&missing, values, 0, sizeof values[0], compare_ints) != NULL) { return EXIT_FAILURE; }
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_subtraction_mutant_triggers_a_diagnostic_instead_of_an_expected_numeric_value(self) -> None:
        source = COMPARE_INTS.replace("return (a > b) - (a < b);", "return a - b;") + r"""
#include <limits.h>
int main(void) { int a = INT_MIN; int b = INT_MAX; return compare_ints(&a, &b); }
"""
        result = self.run_source(source)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("signed integer overflow", result.stderr)

    def test_copy_practice_all_variants_accept_solution_and_reject_unmodified_starter(self) -> None:
        placeholder = """    /* Replace this placeholder with validation followed by one memmove. */
    (void) target;
    (void) capacity;
    (void) source;
    (void) source_size;
    return COPY_OK;"""
        solution = """    if (target == NULL || source == NULL) { return COPY_ARGUMENT; }
    if (source_size == 0 || memchr(source, '\\0', source_size) == NULL) { return COPY_UNTERMINATED; }
    size_t length = strlen(source);
    if (length >= capacity) { return COPY_SPACE; }
    memmove(target, source, length + 1);
    return COPY_OK;"""
        for variant in range(4):
            exercise = tutorial_practice("c", "string-reference", variant)
            self.assertIsNotNone(exercise)
            self.assertIn(placeholder, exercise["starterSource"])
            for replacement, expected in ((solution, "passed"), (placeholder, "output_mismatch")):
                with self.subTest(variant=variant, expected=expected):
                    result = self.run_source(exercise["starterSource"].replace(placeholder, replacement))
                    self.assertEqual((result.returncode, result.stderr), (0, ""))
                    evaluation = evaluate_tutorial_practice(exercise, {
                        "compiled": True, "run": {"exitCode": result.returncode, "stdout": result.stdout},
                    }, "")
                    self.assertEqual(evaluation["status"], expected)

    def test_sort_practice_accepts_any_correct_sign_and_rejects_zero_or_reversed_comparison(self) -> None:
        placeholder = """    /* Replace this placeholder with a comparison that cannot overflow. */
    (void) a;
    (void) b;
    return 0;"""
        for variant in range(4):
            exercise = tutorial_practice("c", "stdlib-reference", variant)
            self.assertIsNotNone(exercise)
            self.assertIn(placeholder, exercise["starterSource"])
            for replacement, passed in (
                ("    return (a > b) - (a < b);", True),
                ("    return a < b ? -17 : (a > b ? 19 : 0);", True),
                ("    return (a < b) - (a > b);", False),
                (placeholder, False),
            ):
                with self.subTest(variant=variant, replacement=replacement):
                    result = self.run_source(exercise["starterSource"].replace(placeholder, replacement), "-DNDEBUG")
                    self.assertEqual((result.returncode, result.stderr), (0, ""))
                    self.assertEqual(result.stdout == exercise["expectedOutput"], passed)


class TutorialCReferenceContentTestCase(unittest.TestCase):
    def test_guided_reference_programs_match_runnable_examples_and_reuse_existing_helpers(self) -> None:
        self.assertTrue(STRTOL_REFERENCE.startswith(INT_PARSER))
        for key in ("string-reference", "stdlib-reference"):
            page = next(page for page in C_PAGES if page["key"] == key)
            self.assertEqual(page["kind"], "reference")
            sources = [block["source"] for block in page["content"]["blocks"] if block["type"] == "code"]
            examples = [example for example in C_EXAMPLES if example["page_key"] == key]
            self.assertEqual(len(sources), 3)
            self.assertCountEqual(sources, [example["source"] for example in examples])
            self.assertTrue(any(block["type"] == "callout" for block in page["content"]["blocks"]))
