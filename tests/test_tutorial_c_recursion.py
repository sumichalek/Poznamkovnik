from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.code_runner import DevelopmentCodeRunner
from backend.tutorial_c_examples import (
    GCD_COMPARISON, GCD_ITERATIVE, GCD_RECURSIVE,
    RECURSION_SUM, RECURSION_TRACE, RECURSION_TRACE_MAIN,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice


GCD_PLACEHOLDER = """    /* Replace this placeholder with a base case and a smaller recursive call. */
    (void) a;
    (void) b;
    return 0U;"""
GCD_SOLUTION = """    if (b == 0U) { return a; }
    return gcd_recursive(b, a % b);"""
GCD_LOOP_SOLUTION = """    while (b != 0U) {
        unsigned int remainder = a % b;
        a = b;
        b = remainder;
    }
    return a;"""
GCD_OUTPUT = "recursive=6 iterative=6\nleft-zero=18 right-zero=48 both-zero=0\n"
REQUIRE = '#include <stdlib.h>\n#define REQUIRE(test) do { if (!(test)) { exit(80); } } while (0)\n'


def trace_output(n: int) -> str:
    return "".join(f"enter n={value}\n" for value in range(n, -1, -1)) + "".join(
        f"leave n={value} sum={value * (value + 1) // 2}\n" for value in range(n + 1)
    )


class TutorialCRecursionContentTestCase(unittest.TestCase):
    def test_lesson_reuses_both_complete_programs_and_their_actual_trace(self) -> None:
        page = next(page for page in C_PAGES if page["key"] == "recursion")
        examples = [example for example in C_EXAMPLES if example["page_key"] == "recursion"]
        self.assertEqual(len(examples), 2)
        sources = [block["source"] for block in page["content"]["blocks"] if block["type"] == "code"]
        for example in examples:
            self.assertIn(example["source"], sources)
        self.assertIn(trace_output(3) + "total=6\n", sources)
        functions = next(page for page in C_PAGES if page["key"] == "functions")
        scope = next(page for page in C_PAGES if page["key"] == "scope")
        self.assertEqual(page["parent_key"], functions["parent_key"])
        self.assertLess(functions["position"], page["position"])
        self.assertLess(page["position"], scope["position"])


@unittest.skipUnless(shutil.which("gcc"), "C recursion examples require GCC")
class TutorialCRecursionNativeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-recursion-")
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

    def run_source(self, source: str, *flags: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(self.compile(source, *flags))], capture_output=True,
                              text=True, timeout=5, cwd=self.root)

    def test_examples_match_outputs_with_and_without_optimization(self) -> None:
        for source, expected in ((RECURSION_TRACE, trace_output(3) + "total=6\n"),
                                 (GCD_COMPARISON, GCD_OUTPUT)):
            for flags in (("-O0",), ("-O2", "-DNDEBUG")):
                with self.subTest(expected=expected, flags=flags):
                    result = self.run_source(source, *flags)
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ""))

    def test_trace_visits_every_frame_and_keeps_repeated_calls_independent(self) -> None:
        cases = [*range(11), 3, 0]
        main = "\nint main(void) {\n" + "".join(
            f"    REQUIRE(sum_to({n}U) == {n * (n + 1) // 2}U);\n" for n in cases
        ) + "    return 0;\n}\n"
        result = self.run_source(REQUIRE + RECURSION_SUM + main)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, "".join(trace_output(n) for n in cases), ""))

    def test_trace_rejects_excessive_depth_before_entering_any_frame(self) -> None:
        for n in ("11U", "UINT_MAX"):
            result = self.run_source("#include <limits.h>\n" + RECURSION_SUM +
                                     RECURSION_TRACE_MAIN.replace("sum_to(3U)", f"sum_to({n})"))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "Trace accepts only n <= 10.\n")

    def test_examples_report_failed_print_and_final_flush(self) -> None:
        failed_print = r"""#include <stdio.h>
static int failed_printf(const char *format, ...) { (void) format; return -1; }
#define printf failed_printf
"""
        failed_flush = r"""#include <stdio.h>
static int failed_fflush(FILE *stream) { (void) stream; return EOF; }
#define fflush failed_fflush
"""
        for source in (RECURSION_TRACE, GCD_COMPARISON):
            for prefix in (failed_print, failed_flush):
                result = self.run_source(prefix + source)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")
                if prefix == failed_print:
                    self.assertEqual(result.stdout, "")

    def test_gcd_matches_independent_oracle_for_all_small_input_pairs(self) -> None:
        rows = ",\n".join("{" + ",".join(f"{math.gcd(a, b)}U" for b in range(64)) + "}"
                          for a in range(64))
        source = REQUIRE + GCD_RECURSIVE + GCD_ITERATIVE + "\nstatic const unsigned int expected[64][64] = {\n" + rows + r"""
};
int main(void)
{
    for (unsigned int a = 0U; a < 64U; ++a) {
        for (unsigned int b = 0U; b < 64U; ++b) {
            REQUIRE(gcd_recursive(a, b) == expected[a][b]);
            REQUIRE(gcd_iterative(a, b) == expected[a][b]);
        }
    }
    return 0;
}
"""
        result = self.run_source(source)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_gcd_handles_unsigned_limits_zeros_and_equal_inputs(self) -> None:
        source = REQUIRE + "#include <limits.h>\n" + GCD_RECURSIVE + GCD_ITERATIVE + r"""
int main(void)
{
    const unsigned int cases[][3] = {
        {0U, 0U, 0U}, {0U, UINT_MAX, UINT_MAX}, {UINT_MAX, 0U, UINT_MAX},
        {UINT_MAX, UINT_MAX, UINT_MAX}, {UINT_MAX, UINT_MAX - 1U, 1U},
        {UINT_MAX - 1U, UINT_MAX, 1U}, {UINT_MAX, 1U, 1U},
        {UINT_MAX, 2U, 1U}, {UINT_MAX - 1U, 2U, 2U}, {46368U, 28657U, 1U}
    };
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        REQUIRE(gcd_recursive(cases[i][0], cases[i][1]) == cases[i][2]);
        REQUIRE(gcd_iterative(cases[i][0], cases[i][1]) == cases[i][2]);
    }
    return 0;
}
"""
        result = self.run_source(source)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_call_audit_requires_smaller_arguments_and_reaches_the_base_case(self) -> None:
        prefix = REQUIRE + "\nstatic unsigned int gcd_recursive(unsigned int a, unsigned int b);\n"
        audit = r"""
static unsigned int calls;
static unsigned int gcd_recursive(unsigned int a, unsigned int b)
{
    const unsigned int expected[][2] = {{48U, 18U}, {18U, 12U}, {12U, 6U}, {6U, 0U}};
    REQUIRE(calls < 4U);
    REQUIRE(a == expected[calls][0] && b == expected[calls][1]);
    ++calls;
    return gcd_implementation(a, b);
}
int main(void)
{
    REQUIRE(gcd_recursive(48U, 18U) == 6U);
    REQUIRE(calls == 4U);
    return 0;
}
"""
        self.assertIn(GCD_SOLUTION, GCD_RECURSIVE)
        for body, expected in ((GCD_SOLUTION, 0), (GCD_LOOP_SOLUTION, 80),
                               (GCD_SOLUTION.replace("gcd_recursive(b, a % b)", "gcd_recursive(a, b)"), 80)):
            source = GCD_RECURSIVE.replace(GCD_SOLUTION, body).replace(
                "static unsigned int gcd_recursive(", "static unsigned int gcd_implementation("
            )
            result = self.run_source(prefix + source + audit, "-O0")
            self.assertEqual((result.returncode, result.stderr), (expected, ""))

    def test_all_exercise_variants_accept_recursion_and_reject_wrong_base_cases(self) -> None:
        for variant in range(4):
            exercise = tutorial_practice("c", "recursion", variant)
            self.assertEqual(exercise["starterSource"].count(GCD_PLACEHOLDER), 1)
            for body, passed in ((GCD_SOLUTION, True), (GCD_PLACEHOLDER, False),
                                 (GCD_SOLUTION.replace("return a;", "return b;"), False)):
                result = self.run_source(exercise["starterSource"].replace(GCD_PLACEHOLDER, body))
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                evaluation = evaluate_tutorial_practice(exercise, {
                    "compiled": True, "run": {"exitCode": result.returncode, "stdout": result.stdout, "stderr": ""}
                }, "")
                self.assertEqual(evaluation["status"] == "passed", passed)

    def test_matching_exercise_output_alone_does_not_prove_recursion(self) -> None:
        exercise = tutorial_practice("c", "recursion", 0)
        result = self.run_source(exercise["starterSource"].replace(GCD_PLACEHOLDER, GCD_LOOP_SOLUTION))
        evaluation = evaluate_tutorial_practice(exercise, {
            "compiled": True, "run": {"exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        }, "")
        self.assertEqual(result.returncode, 0, result)
        self.assertEqual(evaluation["status"], "passed")


class TutorialCRecursionSandboxTestCase(unittest.TestCase):
    def test_both_examples_run_in_the_real_debug_sandbox(self) -> None:
        runner = DevelopmentCodeRunner()
        status = runner.status()["languages"]["c"]
        if not status["available"]:
            self.skipTest(status["message"])
        for source, expected in ((RECURSION_TRACE, trace_output(3) + "total=6\n"),
                                 (GCD_COMPARISON, GCD_OUTPUT)):
            result = runner.run("c", source, "")
            self.assertTrue(result["compiled"], result)
            self.assertEqual(result["buildProfile"], "debug")
            self.assertEqual(result["run"]["exitCode"], 0, result)
            self.assertEqual(result["run"]["stdout"], expected)
            self.assertEqual(result["run"]["stderr"], "")


if __name__ == "__main__":
    unittest.main()
