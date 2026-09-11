from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.code_runner import DevelopmentCodeRunner
from backend.tutorial_c_examples import (
    BOUNDED_QUEUE, GROUP_FINISH, GROUP_MAIN, GROUP_PIPELINE,
    GROUP_WORKERS, PRODUCER_GROUP, PRODUCER_GROUP_FAILURE,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice
from tests.test_tutorial_c_conditions import REQUIRE


GROUP_PLACEHOLDER = """    /* Replace this cancellation-only placeholder with coordinated completion. */
    (void) result;
    queue_close(queue);
    for (size_t i = 0; i < started; ++i) {
        int worker_result;
        join_or_exit(producers[i], &worker_result);
    }
    int consumer_result;
    join_or_exit(consumer, &consumer_result);
    return EXIT_FAILURE;"""
GROUP_SOLUTION = """    if (result != EXIT_SUCCESS) { queue_close(queue); }
    for (size_t i = 0; i < started; ++i) {
        int worker_result = EXIT_FAILURE;
        join_or_exit(producers[i], &worker_result);
        if (worker_result != EXIT_SUCCESS) {
            result = EXIT_FAILURE;
            queue_close(queue);
        }
    }
    queue_close(queue);
    int consumer_result = EXIT_FAILURE;
    join_or_exit(consumer, &consumer_result);
    if (consumer_result != EXIT_SUCCESS) { result = EXIT_FAILURE; }
    return result;"""

NORMAL_OUTPUT = "accepted=12 consumed=12 total=1110\n"
FAILURE_OUTPUT = "empty=0:0:0\nfailed=1 unchanged=1\n"

# The model uses symbolic handles; separate tests below retain real native threads.
FINISH_MODEL = REQUIRE + r"""
#include <stddef.h>
typedef unsigned int thrd_t;
typedef struct { int closed; } Queue;
static Queue *model_queue;
static unsigned int count, next, consumer_joined, failure_at;
static int prior_failed, consumer_failed;
static void queue_close(Queue *queue) { REQUIRE(queue == model_queue); queue->closed = 1; }
static void join_or_exit(thrd_t thread, int *result)
{
    if (thread == 0) {
        REQUIRE(model_queue->closed && next == count && !consumer_joined);
        consumer_joined = 1;
        *result = consumer_failed ? EXIT_FAILURE : EXIT_SUCCESS;
        return;
    }
    REQUIRE(thread == next + 1 && next < count && !consumer_joined);
    if (prior_failed || (failure_at != 0 && thread > failure_at)) { REQUIRE(model_queue->closed); }
    if (!prior_failed && failure_at == 0) { REQUIRE(!model_queue->closed); }
    ++next;
    *result = thread == failure_at ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""
FINISH_MODEL_MAIN = r"""
int main(void)
{
    thrd_t producers[] = {1, 2, 3};
    for (count = 0; count <= 3; ++count) {
        for (failure_at = 0; failure_at <= count; ++failure_at) {
            for (prior_failed = 0; prior_failed <= 1; ++prior_failed) {
                for (consumer_failed = 0; consumer_failed <= 1; ++consumer_failed) {
                    Queue queue = {0};
                    model_queue = &queue;
                    next = consumer_joined = 0;
                    int result = finish_group(&queue, producers, count, 0,
                                              prior_failed ? EXIT_FAILURE : EXIT_SUCCESS);
                    REQUIRE(next == count && consumer_joined && queue.closed);
                    REQUIRE((result != EXIT_SUCCESS) == (prior_failed || consumer_failed || failure_at != 0));
                }
            }
        }
    }
    return EXIT_SUCCESS;
}
"""

# Owner-only counters never race workers. Worker rendezvous uses its own mutex;
# it never holds that mutex while invoking lesson callbacks or joining threads.
GROUP_AUDIT = REQUIRE + r"""
#include <threads.h>
#include <stdbool.h>
#include <stdio.h>
typedef struct { thrd_start_t function; void *context; bool finished, consumer; } Slot;
static Slot slots[8];
static thrd_t owner, handles[8];
static bool joined_flags[8], owner_locked;
static unsigned int attempts, created, joined, live, initialized, destroyed, init_attempts;
static unsigned int live_mutex, live_conditions;
static char order[9];
static mtx_t event_mutex;
static cnd_t event_changed;
static bool producer_blocked;
static cnd_t *conditions[2];

static void audit_init(void)
{
    owner = thrd_current();
    REQUIRE(mtx_init(&event_mutex, mtx_plain) == thrd_success);
    REQUIRE(cnd_init(&event_changed) == thrd_success);
}
static void audit_destroy(void)
{
    cnd_destroy(&event_changed);
    mtx_destroy(&event_mutex);
}
static int trampoline(void *context)
{
    Slot *slot = context;
    if (HOLD_CONSUMER) {
        REQUIRE(mtx_lock(&event_mutex) == thrd_success);
        if (slot->consumer) {
            while (!slots[2].finished) { REQUIRE(cnd_wait(&event_changed, &event_mutex) == thrd_success); }
        } else if (slot == &slots[2] || slot == &slots[3]) {
            while (!producer_blocked) { REQUIRE(cnd_wait(&event_changed, &event_mutex) == thrd_success); }
        }
        REQUIRE(mtx_unlock(&event_mutex) == thrd_success);
    }
    int result = slot->function(slot->context);
    REQUIRE(mtx_lock(&event_mutex) == thrd_success);
    slot->finished = true;
    REQUIRE(cnd_broadcast(&event_changed) == thrd_success);
    REQUIRE(mtx_unlock(&event_mutex) == thrd_success);
    return result;
}
static int audited_create(thrd_t *thread, thrd_start_t function, void *context)
{
    REQUIRE(thrd_equal(thrd_current(), owner));
    if (++attempts == FAIL_CREATE) { return thrd_error; }
    REQUIRE(created < 8);
    Slot *slot = &slots[created];
    slot->function = function;
    slot->context = context;
    slot->consumer = live == 0;
    int status = thrd_create(thread, trampoline, slot);
    if (status == thrd_success) {
        handles[created++] = *thread;
        ++live;
        if (WAIT_FIRST && attempts == 2) {
            REQUIRE(mtx_lock(&event_mutex) == thrd_success);
            while (!slot->finished) { REQUIRE(cnd_wait(&event_changed, &event_mutex) == thrd_success); }
            REQUIRE(mtx_unlock(&event_mutex) == thrd_success);
        }
    }
    return status;
}
static int audited_join(thrd_t thread, int *result)
{
    REQUIRE(thrd_equal(thrd_current(), owner) && !owner_locked);
    unsigned int index = 0;
    while (index < created && (joined_flags[index] || !thrd_equal(thread, handles[index]))) { ++index; }
    REQUIRE(index < created);
    if (FAIL_JOIN == joined + 1) { return thrd_error; }
    int status = thrd_join(thread, result);
    if (status == thrd_success) {
        joined_flags[index] = true;
        order[joined++] = (char) ('0' + index);
        --live;
    }
    return status;
}
static int audited_mutex_init(mtx_t *mutex, int type)
{
    if (++init_attempts == FAIL_INIT) { return thrd_error; }
    int result = mtx_init(mutex, type);
    if (result == thrd_success) { ++initialized; ++live_mutex; }
    return result;
}
static int audited_condition_init(cnd_t *condition)
{
    if (++init_attempts == FAIL_INIT) { return thrd_error; }
    int result = cnd_init(condition);
    if (result == thrd_success) {
        REQUIRE(live_conditions < 2);
        conditions[live_conditions++] = condition;
        ++initialized;
    }
    return result;
}
static void audited_condition_destroy(cnd_t *condition)
{
    REQUIRE(live == 0 && created == joined && live_conditions > 0 && !owner_locked);
    REQUIRE(conditions[--live_conditions] == condition);
    ++destroyed;
    cnd_destroy(condition);
}
static void audited_mutex_destroy(mtx_t *mutex)
{
    REQUIRE(live == 0 && created == joined && live_conditions == 0 && live_mutex == 1 && !owner_locked);
    --live_mutex;
    ++destroyed;
    mtx_destroy(mutex);
}
static int audited_lock(mtx_t *mutex)
{
    bool is_owner = thrd_equal(thrd_current(), owner);
    if (is_owner) { REQUIRE(!owner_locked); }
    int status = mtx_lock(mutex);
    if (is_owner && status == thrd_success) { owner_locked = true; }
    return status;
}
static int audited_unlock(mtx_t *mutex)
{
    if (thrd_equal(thrd_current(), owner)) { REQUIRE(owner_locked); owner_locked = false; }
    return mtx_unlock(mutex);
}
static int audited_wait(cnd_t *condition, mtx_t *mutex)
{
    if (HOLD_CONSUMER && condition == conditions[1]) {
        REQUIRE(mtx_lock(&event_mutex) == thrd_success);
        producer_blocked = true;
        REQUIRE(cnd_broadcast(&event_changed) == thrd_success);
        REQUIRE(mtx_unlock(&event_mutex) == thrd_success);
    }
    return cnd_wait(condition, mutex);
}
static _Noreturn void audited_exit(int status)
{
    fputs("fatal-without-return\n", stderr);
    (void) fflush(stderr);
    _Exit(status);
}
#define mtx_init audited_mutex_init
#define cnd_init audited_condition_init
#define mtx_destroy audited_mutex_destroy
#define cnd_destroy audited_condition_destroy
#define mtx_lock audited_lock
#define mtx_unlock audited_unlock
#define cnd_wait audited_wait
#define thrd_create audited_create
#define thrd_join audited_join
#define _Exit audited_exit
#define main lesson_main
"""
CLOSE_AUDIT = r"""
#undef queue_close
static void queue_close(Queue *queue)
{
    if (!ALLOW_ERROR) {
        REQUIRE(thrd_equal(thrd_current(), owner));
        REQUIRE(live == 1);
    }
    original_queue_close(queue);
}
"""
AUDIT_MAIN = r"""
#undef main
int main(void)
{
    audit_init();
    int result = lesson_main();
    REQUIRE(live == 0 && live_mutex == 0 && live_conditions == 0 && created == joined);
    fprintf(stderr, "audit created=%u joined=%u order=%s init=%u destroyed=%u\n",
            created, joined, order, initialized, destroyed);
    audit_destroy();
    return result;
}
"""


class TutorialCGroupContentTestCase(unittest.TestCase):
    def test_examples_match_group_lesson(self) -> None:
        page = next(page for page in C_PAGES if page["key"] == "producer-groups")
        sources = [block["source"] for block in page["content"]["blocks"] if block["type"] == "code"]
        self.assertGreaterEqual(len(sources), 3)
        examples = [example for example in C_EXAMPLES if example["page_key"] == "producer-groups"]
        self.assertEqual(len(examples), 2)
        for example in examples:
            self.assertIn(example["source"], sources)


class TutorialCGroupSandboxTestCase(unittest.TestCase):
    def test_group_examples_run_with_debug_checks_in_the_real_sandbox(self) -> None:
        runner = DevelopmentCodeRunner()
        status = runner.status()["languages"]["c"]
        if not status["available"]:
            self.skipTest(status["message"])
        for source, expected in ((PRODUCER_GROUP, NORMAL_OUTPUT), (PRODUCER_GROUP_FAILURE, FAILURE_OUTPUT)):
            result = runner.run("c", source, "")
            self.assertTrue(result["compiled"], result)
            self.assertEqual(result["buildProfile"], "debug")
            self.assertEqual(result["run"]["exitCode"], 0, result)
            self.assertEqual(result["run"]["stdout"], expected)
            self.assertEqual(result["run"]["stderr"], "")


@unittest.skipUnless(shutil.which("gcc"), "GCC is unavailable")
class TutorialCGroupNativeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory(prefix="poznamkovnik-group-probe-") as directory:
            root = Path(directory)
            source = root / "probe.c"
            source.write_text("#include <threads.h>\nint main(void) { cnd_t c; if (cnd_init(&c) != thrd_success) return 1; cnd_destroy(&c); return 0; }\n")
            result = subprocess.run(["gcc", "-std=c17", "-pthread", str(source), "-o", str(root / "probe")], capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                raise unittest.SkipTest("C threads are unavailable: " + result.stderr)

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-groups-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def compile_source(self, source: str, *flags: str) -> subprocess.CompletedProcess[str]:
        path = self.root / "main.c"
        path.write_text(source, encoding="utf-8")
        return subprocess.run(
            ["gcc", "-std=c17", "-pthread", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion",
             "-Wshadow", "-Wformat=2", "-Werror", "-O1", "-fsanitize=undefined",
             "-fno-sanitize-recover=all", *flags, str(path), "-o", str(self.root / "program")],
            capture_output=True, text=True, timeout=15,
        )

    def execute(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(self.root / "program")], capture_output=True, text=True, timeout=5, cwd=self.root)

    def run_source(self, source: str, *flags: str) -> subprocess.CompletedProcess[str]:
        build = self.compile_source(source, *flags)
        self.assertEqual(build.returncode, 0, build.stderr)
        return self.execute()

    def assert_success(self, source: str) -> None:
        result = self.run_source(source)
        self.assertEqual((result.returncode, result.stderr), (0, ""), result)

    def audited(self, source: str = PRODUCER_GROUP, **settings: int) -> str:
        flags = dict(FAIL_CREATE=0, FAIL_JOIN=0, FAIL_INIT=0, WAIT_FIRST=0, HOLD_CONSUMER=0, ALLOW_ERROR=0)
        flags.update(settings)
        self.assertEqual(source.count(BOUNDED_QUEUE), 1)
        source = source.replace(BOUNDED_QUEUE, "\n#define queue_close original_queue_close\n" + BOUNDED_QUEUE + CLOSE_AUDIT)
        return "".join(f"#define {key} {value}\n" for key, value in flags.items()) + GROUP_AUDIT + source + AUDIT_MAIN

    def test_examples_repeat_and_report_expected_failure_as_checked_case(self) -> None:
        for source, output in ((PRODUCER_GROUP, NORMAL_OUTPUT), (PRODUCER_GROUP_FAILURE, FAILURE_OUTPUT)):
            build = self.compile_source(source, "-O2", "-DNDEBUG")
            self.assertEqual(build.returncode, 0, build.stderr)
            for attempt in range(10):
                result = self.execute()
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, output, ""), attempt)

    def test_finish_model_covers_all_counts_and_worker_errors(self) -> None:
        self.assert_success(FINISH_MODEL + GROUP_FINISH + FINISH_MODEL_MAIN)
        self.assertIn(GROUP_SOLUTION, GROUP_FINISH)
        source = "static int finish_group(Queue *queue, thrd_t *producers, size_t started, thrd_t consumer, int result) {\n" + GROUP_SOLUTION + "\n}\n"
        self.assert_success(FINISH_MODEL + source + FINISH_MODEL_MAIN)

    def test_finish_model_rejects_early_close_missing_error_and_early_return(self) -> None:
        for changed in (
            GROUP_FINISH.replace("if (result != EXIT_SUCCESS) { queue_close(queue); }", "queue_close(queue);"),
            GROUP_FINISH.replace("if (consumer_result != EXIT_SUCCESS) { result = EXIT_FAILURE; }", "(void) consumer_result;"),
            GROUP_FINISH.replace("result = EXIT_FAILURE;\n            queue_close(queue);", "return EXIT_FAILURE;"),
            GROUP_FINISH.replace("if (result != EXIT_SUCCESS) { queue_close(queue); }", "(void) result;"),
        ):
            self.assertEqual(self.run_source(FINISH_MODEL + changed + FINISH_MODEL_MAIN).returncode, 80)

    def test_first_producer_finishes_before_later_producers_start_without_closing(self) -> None:
        result = self.run_source(self.audited(WAIT_FIRST=1))
        self.assertEqual((result.returncode, result.stdout), (0, NORMAL_OUTPUT))
        self.assertEqual(result.stderr, "audit created=4 joined=4 order=1230 init=3 destroyed=3\n")
        changed_workers = GROUP_WORKERS.replace("    /* Finishing one batch must not close the queue for the other producers. */", "    queue_close(job->queue);")
        changed = PRODUCER_GROUP.replace(GROUP_WORKERS, changed_workers)
        self.assertEqual(self.run_source(self.audited(changed, WAIT_FIRST=1)).returncode, 80)

    def test_every_creation_failure_joins_only_created_handles(self) -> None:
        for failed, expected_order in ((1, ""), (2, "0"), (3, "10"), (4, "120")):
            result = self.run_source(self.audited(FAIL_CREATE=failed, ALLOW_ERROR=1))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            started = failed - 1
            self.assertEqual(result.stderr, f"audit created={started} joined={started} order={expected_order} init=3 destroyed=3\n")

    def test_initialization_failure_rolls_back_only_created_objects(self) -> None:
        for failed in (1, 2, 3):
            result = self.run_source(self.audited(FAIL_INIT=failed))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr, f"audit created=0 joined=0 order= init={failed - 1} destroyed={failed - 1}\n")

    def test_join_failure_never_returns_to_destruction(self) -> None:
        for failed in range(1, 5):
            result = self.run_source(self.audited(FAIL_JOIN=failed))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "Cannot join thread.\nfatal-without-return\n")

    def test_invalid_second_worker_wakes_blocked_first_before_owner_can_join_it(self) -> None:
        changed = PRODUCER_GROUP.replace("{second, 4}", "{NULL, 1}")
        changed = changed.replace("const int second[] = {10, 20, 30, 40};", "")
        result = self.run_source(self.audited(changed, HOLD_CONSUMER=1, ALLOW_ERROR=1))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "audit created=4 joined=4 order=1230 init=3 destroyed=3\n")

    def test_consumer_errors_stop_all_producers_and_preserve_summary(self) -> None:
        checked_main = GROUP_MAIN.replace(
            "if (run_group(batches, 3, &summary) != EXIT_SUCCESS) { return EXIT_FAILURE; }",
            "int result = run_group(batches, 3, &summary);\n    REQUIRE(result != EXIT_SUCCESS && summary.accepted == 77 && summary.consumed == 77 && summary.total == 77);\n    return EXIT_SUCCESS;",
        )
        for changed in (
            (GROUP_PIPELINE + checked_main).replace("first[] = {1, 2, 3, 4}", "first[] = {-1, 2, 3, 4}"),
            (GROUP_PIPELINE + checked_main).replace("GroupConsumer consumer = {&queue, 0, 0}", "GroupConsumer consumer = {&queue, SIZE_MAX, 0}"),
            (GROUP_PIPELINE + checked_main).replace("GroupConsumer consumer = {&queue, 0, 0}", "GroupConsumer consumer = {&queue, 0, UINT_MAX}"),
        ):
            result = self.run_source(self.audited(changed, ALLOW_ERROR=1))
            self.assertEqual((result.returncode, result.stdout), (0, ""))
            self.assertEqual(result.stderr, "audit created=4 joined=4 order=1230 init=3 destroyed=3\n")

    def test_argument_errors_and_empty_batches_preserve_output_contract(self) -> None:
        self.assert_success(REQUIRE + GROUP_PIPELINE + r"""
int main(void)
{
    GroupSummary summary = {77, 88, 99};
    const int values[] = {0, 1};
    const Batch batches[] = {{NULL, 0}, {values, 0}, {NULL, 0}};
    REQUIRE(run_group(NULL, 1, &summary) != EXIT_SUCCESS);
    REQUIRE(run_group(batches, PRODUCER_LIMIT + 1, &summary) != EXIT_SUCCESS);
    REQUIRE(run_group(batches, SIZE_MAX, &summary) != EXIT_SUCCESS);
    REQUIRE(run_group(batches, 1, NULL) != EXIT_SUCCESS);
    REQUIRE(summary.accepted == 77 && summary.consumed == 88 && summary.total == 99);
    REQUIRE(run_group(NULL, 0, &summary) == EXIT_SUCCESS);
    REQUIRE(summary.accepted == 0 && summary.consumed == 0 && summary.total == 0);
    REQUIRE(run_group(batches, 3, &summary) == EXIT_SUCCESS);
    REQUIRE(summary.accepted == 0 && summary.consumed == 0 && summary.total == 0);
    const Batch repeated[] = {{values, 2}, {values, 2}, {values, 2}};
    REQUIRE(run_group(repeated, 3, &summary) == EXIT_SUCCESS);
    REQUIRE(summary.accepted == 6 && summary.consumed == 6 && summary.total == 3);
    return EXIT_SUCCESS;
}
""")

    def test_each_value_arrives_once_and_each_batch_keeps_its_order(self) -> None:
        capture = r"""
static int received[12];
static size_t received_count;
static int queue_pop(Queue *queue, int *value)
{
    int result = original_pop(queue, value);
    if (result) { REQUIRE(received_count < 12); received[received_count++] = *value; }
    return result;
}
"""
        queue = BOUNDED_QUEUE.replace("static int queue_pop(", "static int original_pop(") + capture
        source = REQUIRE + "\n#define main lesson_main\n" + PRODUCER_GROUP.replace(BOUNDED_QUEUE, queue) + r"""
#undef main
int main(void)
{
    REQUIRE(lesson_main() == EXIT_SUCCESS && received_count == 12);
    const int expected[3][4] = {{1, 2, 3, 4}, {10, 20, 30, 40}, {100, 200, 300, 400}};
    size_t next[3] = {0, 0, 0};
    for (size_t i = 0; i < received_count; ++i) {
        int value = received[i];
        size_t batch = value < 10 ? 0 : value < 100 ? 1 : 2;
        REQUIRE(next[batch] < 4 && value == expected[batch][next[batch]]);
        ++next[batch];
    }
    REQUIRE(next[0] == 4 && next[1] == 4 && next[2] == 4);
    return EXIT_SUCCESS;
}
"""
        build = self.compile_source(source)
        self.assertEqual(build.returncode, 0, build.stderr)
        for _ in range(10):
            result = self.execute()
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, NORMAL_OUTPUT, ""))

    def test_all_practice_variants_accept_solution_and_reject_starter(self) -> None:
        for variant in range(4):
            exercise = tutorial_practice("c", "producer-groups", variant)
            self.assertEqual(exercise["starterSource"].count(GROUP_PLACEHOLDER), 1)
            result = self.run_source(exercise["starterSource"].replace(GROUP_PLACEHOLDER, GROUP_SOLUTION))
            self.assertEqual(result.returncode, 0, result)
            self.assertEqual(result.stderr, "")
            evaluation = evaluate_tutorial_practice(exercise, {"compiled": True, "run": {"exitCode": result.returncode, "stdout": result.stdout, "stderr": ""}}, "")
            self.assertEqual(evaluation["status"], "passed")
            starter = self.run_source(exercise["starterSource"])
            self.assertNotEqual(starter.returncode, 0)


if __name__ == "__main__":
    unittest.main()
