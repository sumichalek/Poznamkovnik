from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.code_runner import DevelopmentCodeRunner
from backend.tutorial_c_examples import (
    MATRIX_ACCESS, MATRIX_ACCESS_MAIN, MATRIX_DECLARATIONS, MATRIX_GET,
    MATRIX_SUPPORT, MATRIX_WALK,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice


MATRIX_PLACEHOLDER = """    /* Validate both indices and pointers before accessing the matrix. */
    (void) matrix;
    (void) rows;
    (void) row;
    (void) column;
    (void) result;
    return false;"""
MATRIX_SOLUTION = """    if (matrix == NULL || result == NULL || row >= rows || column >= MATRIX_COLUMNS) {
        return false;
    }
    *result = matrix[row][column];
    return true;"""
WALK_OUTPUT = "rows=2 columns=3\n[0][0]=3\n[0][1]=1\n[0][2]=4\n[1][0]=1\n[1][1]=5\n[1][2]=9\n"
ACCESS_OUTPUT = ("first: ok=1 value=3 matched=1\nlast: ok=1 value=9 matched=1\n"
                 "row: ok=0 value=77 matched=1\ncolumn: ok=0 value=77 matched=1\nempty: ok=0 value=77 matched=1\n")
DECLARATIONS_OUTPUT = "matrix[1]: 40 5 60\nselected: 60 1 9\nrow-elements=3 pointer-count=3\nrow-step=1 cell-step=1\n"
PROGRAMS = ((MATRIX_WALK, WALK_OUTPUT), (MATRIX_ACCESS, ACCESS_OUTPUT), (MATRIX_DECLARATIONS, DECLARATIONS_OUTPUT))
REQUIRE = '#include <stdlib.h>\n#define REQUIRE(test) do { if (!(test)) { exit(80); } } while (0)\n'


class TutorialCMultidimensionalContentTestCase(unittest.TestCase):
    def test_lesson_uses_three_complete_programs_after_pointers(self) -> None:
        page = next(item for item in C_PAGES if item["key"] == "multidimensional")
        examples = [item for item in C_EXAMPLES if item["page_key"] == page["key"]]
        sources = [block["source"] for block in page["content"]["blocks"]
                   if block["type"] == "code" and block["language"] == "c"]
        self.assertEqual(sources, [source for source, _ in PROGRAMS])
        self.assertEqual([example["source"] for example in examples], sources)
        self.assertEqual(page["parent_key"], "data")
        positions = {item["key"]: item["position"] for item in C_PAGES}
        self.assertLess(positions["pointers"], page["position"])
        self.assertLess(page["position"], positions["strings"])


@unittest.skipUnless(shutil.which("gcc"), "Matrix examples require GCC")
class TutorialCMultidimensionalNativeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-matrix-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def compile(self, source: str, *flags: str, success: bool = True) -> Path:
        path = self.root / "main.c"
        path.write_text(source, encoding="utf-8")
        program = self.root / "program"
        result = subprocess.run(
            ["gcc", "-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion",
             "-Wshadow", "-Wformat=2", "-Wvla", "-Werror", "-O1", "-fsanitize=undefined",
             "-fno-sanitize-recover=all", *flags, str(path), "-o", str(program)],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode == 0, success, result.stderr)
        if not success:
            self.assertIn("error:", result.stderr)
        return program

    def run_source(self, source: str, *flags: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(self.compile(source, *flags))], capture_output=True,
                              text=True, timeout=5, cwd=self.root)

    def test_examples_match_outputs_at_o0_and_o2_with_ndebug(self) -> None:
        for source, output in PROGRAMS:
            for flags in (("-O0",), ("-O2", "-DNDEBUG")):
                with self.subTest(output=output, flags=flags):
                    result = self.run_source(source, *flags)
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, output, ""))

    def test_walk_preserves_each_coordinate_in_several_rectangular_shapes(self) -> None:
        for rows, columns in ((1, 1), (1, 4), (4, 1), (2, 3), (5, 3)):
            values = [[r * 10 + c - 5 for c in range(columns)] for r in range(rows)]
            initializer = ", ".join("{" + ", ".join(map(str, row)) + "}" for row in values)
            source = MATRIX_WALK.replace("MATRIX_COLUMNS = 3", f"MATRIX_COLUMNS = {columns}")
            source = source.replace("{3, 1, 4}, {1, 5, 9}", initializer)
            result = self.run_source(source)
            output = f"rows={rows} columns={columns}\n" + "".join(
                f"[{r}][{c}]={values[r][c]}\n" for r in range(rows) for c in range(columns)
            )
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, output, ""))

    def test_get_covers_all_prefixes_indices_and_preserves_output_at_both_bounds(self) -> None:
        main = r"""
int main(void)
{
    const int matrix[5][MATRIX_COLUMNS] = {{-5, -4, -3}, {5, 6, 7}, {15, 16, 17}, {25, 26, 27}, {35, 36, 37}};
    for (size_t rows = 0; rows <= 5; ++rows) {
        for (size_t r = 0; r <= 5; ++r) {
            for (size_t c = 0; c <= MATRIX_COLUMNS; ++c) {
                int value = 77;
                bool expected = r < rows && c < MATRIX_COLUMNS;
                REQUIRE(matrix_get(matrix, rows, r, c, &value) == expected);
                REQUIRE(value == (expected ? (int) r * 10 + (int) c - 5 : 77));
            }
        }
    }
    return 0;
}
"""
        result = self.run_source(REQUIRE + MATRIX_SUPPORT + MATRIX_GET + main)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_get_handles_nulls_size_max_int_limits_and_offset_row_views(self) -> None:
        main = r"""
#include <stdint.h>
#include <limits.h>
int main(void)
{
    const int matrix[2][MATRIX_COLUMNS] = {{INT_MIN, 0, INT_MAX}, {5, 6, 7}};
    int value = 77;
    REQUIRE(!matrix_get(NULL, 2, 0, 0, &value) && value == 77);
    REQUIRE(!matrix_get(matrix, 2, 0, 0, NULL));
    REQUIRE(!matrix_get(NULL, 0, 0, 0, &value) && value == 77);
    REQUIRE(!matrix_get(matrix, 2, SIZE_MAX, 0, &value) && value == 77);
    REQUIRE(!matrix_get(matrix, 2, 0, SIZE_MAX, &value) && value == 77);
    REQUIRE(matrix_get(matrix, 2, 0, 0, &value) && value == INT_MIN);
    REQUIRE(matrix_get(matrix, 2, 0, 2, &value) && value == INT_MAX);
    REQUIRE(matrix_get(matrix, 2, 0, 1, &value) && value == 0);
    REQUIRE(matrix_get(matrix + 1, 1, 0, 2, &value) && value == 7);
    REQUIRE(!matrix_get(matrix + 1, 0, 0, 0, &value) && value == 7);
    return 0;
}
"""
        result = self.run_source(REQUIRE + MATRIX_SUPPORT + MATRIX_GET + main)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_type_assertions_distinguish_whole_matrix_row_cell_and_pointer_array(self) -> None:
        source = MATRIX_SUPPORT + REQUIRE + r"""
int main(void)
{
    int matrix[2][MATRIX_COLUMNS] = {{0}};
    int *cells[3] = {&matrix[0][0], &matrix[1][0], &matrix[1][2]};
    typedef int Row[MATRIX_COLUMNS];
    Row *row = matrix;
    _Static_assert(_Generic(matrix, int (*)[MATRIX_COLUMNS]: 1, default: 0), "row pointer");
    _Static_assert(_Generic(&matrix, int (*)[2][MATRIX_COLUMNS]: 1, default: 0), "whole matrix pointer");
    _Static_assert(_Generic(matrix[0], int *: 1, default: 0), "cell pointer");
    _Static_assert(_Generic(cells, int **: 1, default: 0), "pointer array conversion");
    _Static_assert(_Generic(row, int (*)[MATRIX_COLUMNS]: 1, default: 0), "typedef row");
    _Static_assert(sizeof matrix == 2 * MATRIX_COLUMNS * sizeof(int), "matrix size");
    _Static_assert(sizeof *row == MATRIX_COLUMNS * sizeof(int), "row size");
    REQUIRE(row + 1 == &matrix[1]);
    REQUIRE(cells + 1 == &cells[1]);
    return 0;
}
"""
        result = self.run_source(source)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_equivalent_pointer_to_row_parameter_accepts_the_same_program(self) -> None:
        source = MATRIX_SUPPORT + MATRIX_GET.replace(
            "const int matrix[][MATRIX_COLUMNS]", "const int (*matrix)[MATRIX_COLUMNS]"
        ) + MATRIX_ACCESS_MAIN
        result = self.run_source(source)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, ACCESS_OUTPUT, ""))

    def test_wrong_width_double_pointer_and_nested_const_are_compile_errors_in_c17(self) -> None:
        for declaration in (
            "const int matrix[2][4] = {{0}};",
            "const int value = 1; const int *matrix[2] = {&value, &value};",
            "int matrix[2][MATRIX_COLUMNS] = {{0}};",
        ):
            source = MATRIX_SUPPORT + MATRIX_GET + "\nint main(void) { " + declaration + "\n" + (
                "int result = 0; return matrix_get(matrix, 2, 0, 0, &result) ? 0 : 1; }\n"
            )
            with self.subTest(declaration=declaration):
                self.compile(source, success=False)

    def test_guard_mutations_are_caught_before_any_out_of_bounds_read(self) -> None:
        audited_read = r"""
static int checked_read(const int matrix[][MATRIX_COLUMNS], size_t rows, size_t row, size_t column)
{
    REQUIRE(matrix != NULL && row < rows && column < MATRIX_COLUMNS);
    return matrix[row][column];
}
"""
        main = r"""
int main(void)
{
    const int matrix[2][MATRIX_COLUMNS] = {{1, 2, 3}, {4, 5, 6}};
    int value = 77;
    REQUIRE(!matrix_get(matrix, 2, 2, 0, &value) && value == 77);
    REQUIRE(!matrix_get(matrix, 2, 0, MATRIX_COLUMNS, &value) && value == 77);
    REQUIRE(!matrix_get(matrix, 0, 0, 0, &value) && value == 77);
    return 0;
}
"""
        for body, code in (
            (MATRIX_GET, 0),
            (MATRIX_GET.replace("row >= rows", "row > rows"), 80),
            (MATRIX_GET.replace("column >= MATRIX_COLUMNS", "column > MATRIX_COLUMNS"), 80),
            (MATRIX_GET.replace("    if (matrix == NULL", "    *result = 0;\n    if (matrix == NULL"), 80),
        ):
            body = body.replace("matrix[row][column]", "checked_read(matrix, rows, row, column)")
            result = self.run_source(REQUIRE + MATRIX_SUPPORT + audited_read + body + main)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (code, "", ""))

    def test_all_exercise_variants_reject_starter_wrong_value_and_overstrict_bound(self) -> None:
        for variant in range(4):
            exercise = tutorial_practice("c", "multidimensional", variant)
            self.assertEqual(exercise["starterSource"].count(MATRIX_PLACEHOLDER), 1)
            for body, passed in (
                (MATRIX_SOLUTION, True), (MATRIX_PLACEHOLDER, False),
                (MATRIX_SOLUTION.replace("matrix[row][column]", "matrix[row][0]"), False),
                (MATRIX_SOLUTION.replace("column >= MATRIX_COLUMNS", "column >= MATRIX_COLUMNS - 1"), False),
            ):
                result = self.run_source(exercise["starterSource"].replace(MATRIX_PLACEHOLDER, body))
                self.assertEqual(result.stderr, "")
                self.assertEqual(result.returncode == 0, passed)
                evaluation = evaluate_tutorial_practice(exercise, {
                    "compiled": True, "run": {"exitCode": result.returncode, "stdout": result.stdout, "stderr": ""}
                }, "")
                self.assertEqual(evaluation["status"] == "passed", passed)

    def test_programs_report_failed_print_and_final_flush(self) -> None:
        prefixes = (r"""#include <stdio.h>
static int failed_printf(const char *format, ...) { (void) format; return -1; }
#define printf failed_printf
""", r"""#include <stdio.h>
static int failed_fflush(FILE *stream) { (void) stream; return EOF; }
#define fflush failed_fflush
""")
        for source, _ in PROGRAMS:
            for prefix in prefixes:
                result = self.run_source(prefix + source)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")


class TutorialCMultidimensionalSandboxTestCase(unittest.TestCase):
    def test_three_examples_run_in_the_real_debug_sandbox(self) -> None:
        runner = DevelopmentCodeRunner()
        status = runner.status()["languages"]["c"]
        if not status["available"]:
            self.skipTest(status["message"])
        for source, expected in PROGRAMS:
            result = runner.run("c", source, "")
            self.assertTrue(result["compiled"], result)
            self.assertEqual(result["buildProfile"], "debug")
            self.assertEqual(result["run"]["exitCode"], 0, result)
            self.assertEqual((result["run"]["stdout"], result["run"]["stderr"]), (expected, ""))


if __name__ == "__main__":
    unittest.main()
