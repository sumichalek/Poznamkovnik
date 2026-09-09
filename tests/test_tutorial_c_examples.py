from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.tutorial_c_examples import CHECKED_ADD, GROW_BUFFER
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice


@unittest.skipUnless(shutil.which("gcc"), "C examples require GCC")
class TutorialCExamplesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-examples-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def compile_and_run(self, source: str) -> subprocess.CompletedProcess[str]:
        source_path = self.root / "example.c"
        program_path = self.root / "example"
        source_path.write_text(source, encoding="utf-8")
        compiled = subprocess.run(
            [
                "gcc", "-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion",
                "-Wshadow", "-Wformat=2", "-Werror", "-O1", "-g",
                "-fsanitize=undefined", "-fno-sanitize-recover=all",
                str(source_path), "-o", str(program_path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        result = subprocess.run([str(program_path)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_guided_programs_match_the_runnable_examples_and_explained_outputs(self) -> None:
        expected_outputs = {
            "mask-operations": "start: 5\nset: 7\nclear: 3\ntoggle: 1\nany: 1\nall: 0\n",
            "checked-add": "sum: 21\noverflow rejected\n",
            "grow-buffer": "count: 5, capacity: 5\n10 20 30 40 50\n",
            "const-views": "view: 15\nnext: 20\nfixed view: 15\n",
            "restrict-copy": "3 1 4\n",
            "atomic-counter": "previous: 0\ncurrent: 1\n",
            "macro-parentheses": "without parentheses: 11\nwith parentheses: 25\nwhole expression: 4\n",
            "macro-single-evaluation": "result: 9, next: 4\n",
            "conditional-diagnostics": "average: 12.0\n",
        }
        examples = {example["key"]: example for example in C_EXAMPLES}
        pages = {page["key"]: page for page in C_PAGES}
        for key, expected in expected_outputs.items():
            with self.subTest(example=key):
                example = examples[key]
                displayed_sources = [
                    block["source"]
                    for block in pages[example["page_key"]]["content"]["blocks"]
                    if block["type"] == "code"
                ]
                self.assertIn(example["source"], displayed_sources)
                result = self.compile_and_run(example["source"])
                self.assertEqual(result.stdout, expected)
                self.assertEqual(result.stderr, "")

    def test_checked_add_handles_both_limits_without_changing_output_on_failure(self) -> None:
        source = "#define main lesson_main\n" + CHECKED_ADD + r"""
#undef main
#include <assert.h>

int main(void)
{
    int value = 42;
    assert(!checked_add(INT_MAX, 1, &value) && value == 42);
    assert(!checked_add(INT_MIN, -1, &value) && value == 42);
    assert(!checked_add(INT_MAX, INT_MAX, &value) && value == 42);
    assert(!checked_add(INT_MIN, INT_MIN, &value) && value == 42);
    assert(checked_add(INT_MAX, 0, &value) && value == INT_MAX);
    assert(checked_add(INT_MIN, 0, &value) && value == INT_MIN);
    assert(checked_add(INT_MAX, -1, &value) && value == INT_MAX - 1);
    assert(checked_add(0, INT_MIN, &value) && value == INT_MIN);
    assert(checked_add(20, -20, &value) && value == 0);
    return 0;
}
"""
        result = self.compile_and_run(source)
        self.assertEqual(result.stderr, "")

    def test_resize_preserves_ownership_and_main_releases_memory_on_failure(self) -> None:
        # Fail allocations deterministically; exhausting real RAM is not a test.
        source = r"""#include <assert.h>
#include <stdlib.h>

static unsigned int calls = 0;
static unsigned int fail_at = 0;
static unsigned int live_blocks = 0;

static void *controlled_realloc(void *pointer, size_t size)
{
    ++calls;
    if (calls == fail_at) {
        return NULL;
    }
    int is_new = pointer == NULL;
    void *result = realloc(pointer, size);
    if (result != NULL && is_new) {
        ++live_blocks;
    }
    return result;
}

static void controlled_free(void *pointer)
{
    if (pointer != NULL) {
        assert(live_blocks > 0);
        --live_blocks;
    }
    free(pointer);
}

#define realloc controlled_realloc
#define free controlled_free
#define main lesson_main
""" + GROW_BUFFER + r"""
#undef main

int main(void)
{
    int *values = NULL;
    size_t capacity = 0;
    fail_at = 1;
    assert(!resize_values(&values, &capacity, 3));
    assert(values == NULL && capacity == 0 && live_blocks == 0);
    fail_at = 0;
    assert(resize_values(&values, &capacity, 3));
    assert(capacity == 3 && live_blocks == 1);
    values[0] = 10;
    values[1] = 20;
    values[2] = 30;

    int *original = values;
    fail_at = calls + 1;
    assert(!resize_values(&values, &capacity, 5));
    assert(values == original && capacity == 3 && values[2] == 30);
    unsigned int before = calls;
    assert(!resize_values(&values, &capacity, 0));
    if (sizeof *values > 1) {
        assert(!resize_values(&values, &capacity, SIZE_MAX / sizeof *values + 1));
    }
    assert(calls == before && values == original && capacity == 3);

    fail_at = 0;
    assert(resize_values(&values, &capacity, 5));
    assert(capacity == 5 && values[0] == 10 && values[2] == 30);
    assert(resize_values(&values, &capacity, 2));
    assert(capacity == 2 && values[0] == 10 && values[1] == 20);
    free(values);
    assert(live_blocks == 0);

    calls = 0;
    fail_at = 1;
    assert(lesson_main() == 1 && live_blocks == 0);
    calls = 0;
    fail_at = 2;
    assert(lesson_main() == 1 && live_blocks == 0);
    return 0;
}
"""
        result = self.compile_and_run(source)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "allocation failed\ngrowth failed\n")

    def test_bit_exercises_check_the_whole_mask_in_all_four_variants(self) -> None:
        operations = (
            "flags |= FEATURE_WRITE;",
            "flags &= ~(unsigned int) FEATURE_WRITE;",
            "flags ^= FEATURE_WRITE;",
            "flags ^= FEATURE_WRITE;",
        )
        for variant, operation in enumerate(operations):
            with self.subTest(variant=variant):
                exercise = tutorial_practice("c", "bits", variant)
                assert exercise is not None
                starter = self.compile_and_run(exercise["starterSource"])
                self.assertNotEqual(starter.stdout, exercise["expectedOutput"])
                solved_source = exercise["starterSource"].replace(
                    '    printf("%u\\n", flags);',
                    operation + '\n    printf("%u\\n", flags);',
                )
                result = self.compile_and_run(solved_source)
                self.assertEqual(result.stdout, exercise["expectedOutput"])
                evaluated = evaluate_tutorial_practice(
                    exercise,
                    {"compiled": True, "compile": {}, "run": {"exitCode": 0, "stdout": result.stdout}},
                    "",
                )
                self.assertEqual(evaluated["status"], "passed")
                # Merely setting the requested bit must not pass by losing READ/SEND.
                rejected = evaluate_tutorial_practice(
                    exercise,
                    {"compiled": True, "compile": {}, "run": {"exitCode": 0, "stdout": "2\n"}},
                    "",
                )
                self.assertEqual(rejected["status"], "output_mismatch")
