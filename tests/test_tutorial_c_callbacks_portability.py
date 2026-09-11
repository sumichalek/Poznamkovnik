from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.tutorial_c_examples import (
    CALLBACK_APPLY, CALLBACK_CONTEXT, CALLBACK_OPERATION, EXACT_WIDTH_ID,
    LIMIT_VISITOR, OCTET_CODEC, SEQUENCED_ARGUMENTS, VARIADIC_PASSES,
    VARIADIC_RANGE, WALK_VALUES, WIRE_ROUNDTRIP,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice


CALLBACK_PLACEHOLDER = """    /* Replace this placeholder with context checks and one accepted value. */
    (void) value;
    (void) context;
    return VISIT_CONTINUE;"""
CALLBACK_SOLUTION = """    if (context == NULL) { return VISIT_ERROR; }
    LimitState *state = context;
    if (value >= state->limit) { return VISIT_STOP; }
    if (state->accepted == SIZE_MAX) { return VISIT_ERROR; }
    ++state->accepted;
    state->last = value;
    return VISIT_CONTINUE;"""
CODEC_PLACEHOLDER = """    /* Replace this placeholder with validation and big-endian encoding. */
    (void) target;
    (void) capacity;
    (void) value;
    return CODEC_OK;"""
CODEC_SOLUTION = """    if (target == NULL) { return CODEC_ARGUMENT; }
    if (capacity < 2) { return CODEC_SIZE; }
    if (value > UINT32_C(65535)) { return CODEC_RANGE; }
    target[0] = (unsigned char) (value >> 8);
    target[1] = (unsigned char) (value & UINT32_C(255));
    return CODEC_OK;"""


class TutorialCCallbacksPortabilityContentTestCase(unittest.TestCase):
    def test_full_lesson_programs_match_the_runnable_examples(self) -> None:
        for key in ("callbacks", "portability"):
            page = next(item for item in C_PAGES if item["key"] == key)
            sources = [block["source"] for block in page["content"]["blocks"] if block["type"] == "code"]
            examples = [item for item in C_EXAMPLES if item["page_key"] == key]
            self.assertEqual(len(examples), 3)
            for example in examples:
                self.assertIn(example["source"], sources)


@unittest.skipUnless(shutil.which("gcc"), "Callback and portability examples require GCC")
class TutorialCCallbacksPortabilityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-callbacks-")
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

    def run_source(self, source: str, *flags: str) -> subprocess.CompletedProcess[str]:
        build = self.compile_source(source, *flags)
        self.assertEqual(build.returncode, 0, build.stderr)
        return subprocess.run([str(self.root / "program")], capture_output=True, text=True, timeout=5, cwd=self.root)

    def test_demonstrations_match_the_explained_outputs(self) -> None:
        for source, expected in (
            (CALLBACK_OPERATION, "ok=1 value=9\nmissing=0 value=77\n"),
            (CALLBACK_CONTEXT, "first: status=1 accepted=2 last=5\nsecond: status=0 accepted=4 last=1\nmissing=3 empty=0\n"),
            (VARIADIC_PASSES, "ok=1 min=-3 max=9\nempty=0 min=77 max=88\n"),
            (EXACT_WIDTH_ID, "exact=4000000000\nleast=4000000000\n"),
            (WIRE_ROUNDTRIP, "AB CD value=43981\nshort=2 range=3 bytes=AA BB\nread=2 value=77\n"),
        ):
            with self.subTest(expected=expected):
                result = self.run_source(source, "-DNDEBUG")
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ""))

    def test_apply_calls_once_and_preserves_output_when_arguments_are_missing(self) -> None:
        result = self.run_source(CALLBACK_APPLY + r"""
#include <limits.h>
#include <stdlib.h>
static int calls;
static int operation(int left, int right) { ++calls; return maximum(left, right); }
int main(void)
{
    int value = 77;
    if (apply(INT_MIN, INT_MAX, NULL, &value) != 0 || value != 77 ||
        apply(INT_MIN, INT_MAX, operation, NULL) != 0 || calls != 0 ||
        apply(0, 0, NULL, NULL) != 0) { return EXIT_FAILURE; }
    if (apply(INT_MIN, INT_MAX, operation, &value) != 1 || calls != 1 || value != INT_MAX ||
        apply(INT_MIN, INT_MIN, operation, &value) != 1 || calls != 2 || value != INT_MIN) { return EXIT_FAILURE; }
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_incompatible_callback_signature_is_rejected_without_executing_it(self) -> None:
        result = self.compile_source(CALLBACK_APPLY + r"""
static long wrong(long left, long right) { return left > right ? left : right; }
int main(void) { int result = 0; return apply(1, 2, maximum, &result) + apply(1, 2, wrong, &result); }
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("incompatible", result.stderr)

    def test_walk_visits_in_order_and_stops_at_each_stop_or_error_position(self) -> None:
        result = self.run_source(WALK_VALUES + r"""
#include <stdlib.h>
typedef struct { size_t calls; size_t stop; VisitAction action; int seen[4]; } Probe;
static VisitAction probe(int value, void *context)
{
    Probe *state = context;
    if (state->calls >= 4) { abort(); }
    size_t index = state->calls++;
    state->seen[index] = value;
    return index == state->stop ? state->action : VISIT_CONTINUE;
}
int main(void)
{
    const int values[] = {3, -2, 9, 1};
    const VisitAction actions[] = {VISIT_STOP, VISIT_ERROR, (VisitAction) 99};
    for (size_t count = 0; count <= 4; ++count) {
        for (size_t stop = 0; stop <= 4; ++stop) {
            for (size_t mode = 0; mode < 3; ++mode) {
                Probe state = {0, stop, actions[mode], {0}};
                WalkStatus expected = stop >= count ? WALK_DONE : (mode == 0 ? WALK_STOPPED : WALK_CALLBACK_ERROR);
                if (walk_values(values, count, probe, &state) != expected ||
                    state.calls != (stop < count ? stop + 1 : count)) { return EXIT_FAILURE; }
                for (size_t i = 0; i < state.calls; ++i) {
                    if (state.seen[i] != values[i]) { return EXIT_FAILURE; }
                }
            }
        }
    }
    Probe untouched = {0, 0, VISIT_STOP, {0}};
    if (walk_values(NULL, 0, probe, NULL) != WALK_DONE ||
        walk_values(NULL, 1, probe, &untouched) != WALK_ARGUMENT ||
        walk_values(values, 1, NULL, &untouched) != WALK_ARGUMENT ||
        walk_values(NULL, 0, NULL, NULL) != WALK_ARGUMENT || untouched.calls != 0) { return EXIT_FAILURE; }
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_context_limits_preserve_state_at_stop_and_overflow_and_remain_independent(self) -> None:
        result = self.run_source(LIMIT_VISITOR + r"""
#include <limits.h>
#include <stdlib.h>
int main(void)
{
    LimitState state = {INT_MAX, 0, 77};
    const int values[] = {INT_MIN, 0, INT_MAX, 1};
    if (walk_values(values, 4, accept_below, &state) != WALK_STOPPED ||
        state.accepted != 2 || state.last != 0 || state.limit != INT_MAX) { return EXIT_FAILURE; }
    LimitState second = {INT_MIN, 0, 77};
    if (walk_values(values, 4, accept_below, &second) != WALK_STOPPED ||
        second.accepted != 0 || second.last != 77 || state.accepted != 2) { return EXIT_FAILURE; }
    state.accepted = SIZE_MAX;
    state.last = 77;
    if (accept_below(0, &state) != VISIT_ERROR || state.accepted != SIZE_MAX || state.last != 77 ||
        accept_below(INT_MAX, &state) != VISIT_STOP || state.accepted != SIZE_MAX || state.last != 77 ||
        accept_below(0, NULL) != VISIT_ERROR) { return EXIT_FAILURE; }
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_variadic_range_handles_promoted_arguments_extremes_and_empty_calls(self) -> None:
        result = self.run_source(VARIADIC_RANGE + r"""
#include <limits.h>
#include <stdlib.h>
int main(void)
{
    IntRange range = {77, 88};
    short low = -3;
    _Bool one = 1;
    if (variadic_range(&range, 0U) != 0 || range.minimum != 77 || range.maximum != 88 ||
        variadic_range(NULL, 0U) != 0 || variadic_range(NULL, 1U, 0) != 0) { return EXIT_FAILURE; }
    if (!variadic_range(&range, 1U, INT_MIN) || range.minimum != INT_MIN || range.maximum != INT_MIN ||
        !variadic_range(&range, 4U, INT_MAX, 0, INT_MIN, INT_MAX) || range.minimum != INT_MIN || range.maximum != INT_MAX ||
        !variadic_range(&range, 4U, low, one, -9, 0) || range.minimum != -9 || range.maximum != 1 ||
        !variadic_range(&range, 3U, -3, -3, -3) || range.minimum != -3 || range.maximum != -3) { return EXIT_FAILURE; }
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_each_variadic_cursor_is_initialized_and_ended_even_on_repeated_calls(self) -> None:
        result = self.run_source(r"""
#include <stdarg.h>
static int starts;
static int copies;
static int ends;
#undef va_start
#undef va_copy
#undef va_end
#define va_start(args, last) (++starts, __builtin_va_start(args, last))
#define va_copy(target, source) (++copies, __builtin_va_copy(target, source))
#define va_end(args) (++ends, __builtin_va_end(args))
""" + VARIADIC_RANGE + r"""
#include <stdlib.h>
int main(void)
{
    IntRange range = {77, 88};
    for (int i = 0; i < 4; ++i) {
        if (!variadic_range(&range, 3U, i, -i, 0) || range.minimum != -i || range.maximum != i) { return EXIT_FAILURE; }
    }
    if (variadic_range(&range, 0U) != 0 || variadic_range(NULL, 1U, 0) != 0) { return EXIT_FAILURE; }
    return starts == 4 && copies == 4 && ends == 8 ? EXIT_SUCCESS : EXIT_FAILURE;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_optional_exact_width_branch_has_a_working_least_type_fallback(self) -> None:
        result = self.run_source("#include <inttypes.h>\n#include <stdint.h>\n#undef UINT32_MAX\n" + EXACT_WIDTH_ID)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "exact=unavailable\nleast=4000000000\n", ""))

    def test_every_u16_value_has_known_big_endian_bytes_and_roundtrips_at_byte_offsets(self) -> None:
        result = self.run_source(OCTET_CODEC + r"""
#include <stdlib.h>
int main(void)
{
    for (uint_least32_t value = 0; value <= UINT32_C(65535); ++value) {
        for (size_t offset = 1; offset <= 3; ++offset) {
            unsigned char bytes[6] = {0xA5, 0xA5, 0xA5, 0xA5, 0xA5, 0xA5};
            uint_least32_t decoded = UINT32_C(65536);
            if (encode_u16be(bytes + offset, 2, value) != CODEC_OK ||
                bytes[offset] != value / 256 || bytes[offset + 1] != value % 256 ||
                decode_u16be(bytes + offset, 2, &decoded) != CODEC_OK || decoded != value) { return EXIT_FAILURE; }
            for (size_t i = 0; i < sizeof bytes; ++i) {
                if ((i < offset || i > offset + 1) && bytes[i] != 0xA5) { return EXIT_FAILURE; }
            }
        }
    }
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_codec_failure_priority_and_preserved_outputs(self) -> None:
        result = self.run_source(OCTET_CODEC + r"""
#include <stdlib.h>
int main(void)
{
    unsigned char bytes[] = {0xAA, 0xBB, 0xCC};
    uint_least32_t value = 77;
    for (size_t size = 0; size < 2; ++size) {
        if (encode_u16be(bytes, size, UINT_LEAST32_MAX) != CODEC_SIZE || bytes[0] != 0xAA || bytes[1] != 0xBB ||
            decode_u16be(bytes, size, &value) != CODEC_SIZE || value != 77) { return EXIT_FAILURE; }
    }
    if (encode_u16be(NULL, 0, UINT_LEAST32_MAX) != CODEC_ARGUMENT ||
        encode_u16be(bytes, 3, UINT32_C(65536)) != CODEC_RANGE ||
        encode_u16be(bytes, 3, UINT_LEAST32_MAX) != CODEC_RANGE ||
        bytes[0] != 0xAA || bytes[1] != 0xBB || bytes[2] != 0xCC ||
        decode_u16be(NULL, 0, &value) != CODEC_ARGUMENT || value != 77 ||
        decode_u16be(bytes, 0, NULL) != CODEC_ARGUMENT) { return EXIT_FAILURE; }
    if (decode_u16be(bytes, 3, &value) != CODEC_OK || value != UINT32_C(43707) ||
        encode_u16be(bytes, 3, 1) != CODEC_OK || bytes[2] != 0xCC) { return EXIT_FAILURE; }
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_wire_format_explicitly_rejects_non_octet_byte_requirement(self) -> None:
        result = self.compile_source("#include <limits.h>\n#undef CHAR_BIT\n#define CHAR_BIT 16\n" + WIRE_ROUNDTRIP)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("This wire format requires 8-bit bytes", result.stderr)

    def test_separate_statements_have_one_order_and_argument_calls_allow_both(self) -> None:
        for flag in ("-O0", "-O2"):
            with self.subTest(flag=flag):
                result = self.run_source(SEQUENCED_ARGUMENTS, flag)
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                self.assertIn(result.stdout, (
                    "ordered=1,2\nunspecified=1,2\n", "ordered=1,2\nunspecified=2,1\n",
                ))
        invalid = self.compile_source('#include <stdio.h>\nint main(void) { int n = 0; return printf("%d,%d", n++, n++); }\n')
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("sequence-point", invalid.stderr)

    def test_practice_variants_accept_solutions_and_reject_starters_and_wrong_contracts(self) -> None:
        for topic, placeholder, solution, mutant in (
            ("callbacks", CALLBACK_PLACEHOLDER, CALLBACK_SOLUTION, CALLBACK_SOLUTION.replace("value >= state->limit", "value > state->limit")),
            ("portability", CODEC_PLACEHOLDER, CODEC_SOLUTION, CODEC_SOLUTION.replace("target[0]", "target[2]").replace("target[1]", "target[0]").replace("target[2]", "target[1]")),
        ):
            for variant in range(4):
                exercise = tutorial_practice("c", topic, variant)
                self.assertIsNotNone(exercise)
                self.assertIn(placeholder, exercise["starterSource"])
                for replacement, expected in ((solution, "passed"), (placeholder, "output_mismatch"), (mutant, "output_mismatch")):
                    with self.subTest(topic=topic, variant=variant, expected=expected):
                        result = self.run_source(exercise["starterSource"].replace(placeholder, replacement))
                        self.assertEqual((result.returncode, result.stderr), (0, ""))
                        evaluation = evaluate_tutorial_practice(exercise, {
                            "compiled": True, "run": {"exitCode": result.returncode, "stdout": result.stdout},
                        }, "")
                        self.assertEqual(evaluation["status"], expected)
