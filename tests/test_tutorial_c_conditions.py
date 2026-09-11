from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.tutorial_c_examples import (
    BOUNDED_QUEUE, CONDITION_GATE, GATE_MAIN, GATE_SUPPORT, GATE_WAIT,
    PRODUCER_CONSUMER, QUEUE_CLOSE, QUEUE_DRAIN, QUEUE_OPERATIONS, QUEUE_SUPPORT,
    THREAD_JOIN,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice


GATE_PLACEHOLDER = """    /* Replace this placeholder with a predicate loop under the mutex. */
    (void) gate;
    return 77;"""
GATE_SOLUTION = """    check_sync(mtx_lock(&gate->mutex), "Cannot lock gate.\\n");
    while (!gate->ready) {
        check_sync(cnd_wait(&gate->changed, &gate->mutex), "Cannot wait on gate.\\n");
    }
    int value = gate->value;
    check_sync(mtx_unlock(&gate->mutex), "Cannot unlock gate.\\n");
    return value;"""
CLOSE_PLACEHOLDER = """    /* Replace this placeholder with close and both broadcasts under the mutex. */
    (void) queue;
    _Exit(EXIT_FAILURE);"""
CLOSE_SOLUTION = """    check_sync(mtx_lock(&queue->mutex), "Cannot lock queue.\\n");
    queue->closed = true;
    check_sync(cnd_broadcast(&queue->not_empty), "Cannot wake consumers.\\n");
    check_sync(cnd_broadcast(&queue->not_full), "Cannot wake producers.\\n");
    check_sync(mtx_unlock(&queue->mutex), "Cannot unlock queue.\\n");"""

REQUIRE = r"""
#include <stdlib.h>
#define REQUIRE(test) do { if (!(test)) { exit(80); } } while (0)
"""

# Counts are accessed only by the owner, never by the native workers.
LIFECYCLE_AUDIT = REQUIRE + r"""
#include <threads.h>
#include <stdio.h>
static unsigned int attempts, created, joined, initialized, destroyed, condition_attempts;
static unsigned int live_conditions, live_mutex;
static cnd_t *conditions[2];
static thrd_t handles[2];
static int audited_mutex_init(mtx_t *mutex, int type)
{
    if (FAIL_INIT == 1) { return thrd_error; }
    int result = mtx_init(mutex, type);
    if (result == thrd_success) { ++initialized; ++live_mutex; }
    return result;
}
static int audited_condition_init(cnd_t *condition)
{
    ++condition_attempts;
    if (FAIL_INIT == condition_attempts + 1) { return thrd_error; }
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
    REQUIRE(created == joined && live_conditions > 0);
    REQUIRE(conditions[--live_conditions] == condition);
    ++destroyed;
    cnd_destroy(condition);
}
static void audited_mutex_destroy(mtx_t *mutex)
{
    REQUIRE(created == joined && live_conditions == 0 && live_mutex == 1);
    --live_mutex;
    ++destroyed;
    mtx_destroy(mutex);
}
static int audited_create(thrd_t *thread, thrd_start_t function, void *context)
{
    ++attempts;
    if (FAIL_CREATE == attempts) { return thrd_error; }
    int result = thrd_create(thread, function, context);
    if (result == thrd_success) { REQUIRE(created < 2); handles[created++] = *thread; }
    return result;
}
static int audited_join(thrd_t thread, int *result)
{
    REQUIRE(joined < created && thrd_equal(thread, handles[joined]));
    if (FAIL_JOIN) { return thrd_error; }
    int status = thrd_join(thread, result);
    if (status == thrd_success) { ++joined; }
    return status;
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
#define thrd_create audited_create
#define thrd_join audited_join
#define _Exit audited_exit
#define main lesson_main
"""
AUDIT_MAIN = r"""
#undef main
int main(void)
{
    int result = lesson_main();
    REQUIRE(live_conditions == 0 && live_mutex == 0);
    fprintf(stderr, "audit created=%u joined=%u init=%u destroyed=%u\n",
            created, joined, initialized, destroyed);
    return result;
}
"""

# The first wake changes nothing. The second changes the predicate with the real mutex.
QUEUE_WAIT_MODEL = r"""
static Queue *model_queue;
static int model_push, model_close;
static unsigned int waits;
static int queue_push(Queue *queue, int value);
static int queue_pop(Queue *queue, int *result);
static int model_wait(cnd_t *condition, mtx_t *mutex)
{
    REQUIRE(mutex == &model_queue->mutex);
    REQUIRE(condition == (model_push ? &model_queue->not_full : &model_queue->not_empty));
    REQUIRE(++waits <= 2);
    REQUIRE(mtx_unlock(mutex) == thrd_success);
    if (waits == 2) {
        if (model_close) { queue_close(model_queue); }
        else if (model_push) { int value; REQUIRE(queue_pop(model_queue, &value) == 1 && value == 1); }
        else { REQUIRE(queue_push(model_queue, 42) == 1); }
    }
    return mtx_lock(mutex);
}
#define cnd_wait model_wait
"""
QUEUE_WAIT_MAIN = r"""
#undef cnd_wait
int main(void)
{
    for (model_push = 0; model_push <= 1; ++model_push) {
        for (model_close = 0; model_close <= 1; ++model_close) {
            Queue queue;
            REQUIRE(queue_init(&queue));
            model_queue = &queue;
            waits = 0;
            for (size_t i = 0; i < QUEUE_CAPACITY; ++i) { queue.items[i] = 0; }
            if (model_push) {
                for (int i = 1; i <= QUEUE_CAPACITY; ++i) { REQUIRE(queue_push(&queue, i)); }
            }
            int value = 77;
            int result = model_push ? queue_push(&queue, 42) : queue_pop(&queue, &value);
            REQUIRE(waits == 2 && result == !model_close);
            if (!model_push) { REQUIRE(value == (model_close ? 77 : 42) && queue.count == 0); }
            else {
                REQUIRE(queue.count == QUEUE_CAPACITY);
                REQUIRE(queue.items[0] == (model_close ? 1 : 42));
            }
            queue_close(&queue);
            queue_destroy(&queue);
        }
    }
    return EXIT_SUCCESS;
}
"""

# Announce each native waiter once while it still owns the queue mutex. Main can
# acquire that mutex to close only after the final waiter has entered cnd_wait.
NATIVE_WAIT_HANDSHAKE = r"""
#include <threads.h>
static mtx_t audit_mutex;
static cnd_t audit_changed;
static cnd_t *watched_condition;
static unsigned int entered;
static _Thread_local int announced;
static int observed_wait(cnd_t *condition, mtx_t *mutex)
{
    if (condition == watched_condition && !announced) {
        REQUIRE(mtx_lock(&audit_mutex) == thrd_success);
        ++entered;
        announced = 1;
        REQUIRE(cnd_broadcast(&audit_changed) == thrd_success);
        REQUIRE(mtx_unlock(&audit_mutex) == thrd_success);
    }
    return cnd_wait(condition, mutex);
}
#define cnd_wait observed_wait
"""
NATIVE_WAIT_MAIN = r"""
#undef cnd_wait
typedef struct { Queue *queue; int result, value; } WaitJob;
static int wait_worker(void *context)
{
    WaitJob *job = context;
    job->result = WAITING_PRODUCERS ? queue_push(job->queue, 99) : queue_pop(job->queue, &job->value);
    return EXIT_SUCCESS;
}
int main(void)
{
    Queue queue;
    REQUIRE(queue_init(&queue));
    REQUIRE(mtx_init(&audit_mutex, mtx_plain) == thrd_success);
    REQUIRE(cnd_init(&audit_changed) == thrd_success);
    watched_condition = WAITING_PRODUCERS ? &queue.not_full : &queue.not_empty;
    if (WAITING_PRODUCERS) {
        for (int i = 1; i <= QUEUE_CAPACITY; ++i) { REQUIRE(queue_push(&queue, i)); }
    }
    WaitJob jobs[] = {{&queue, -1, 77}, {&queue, -1, 77}};
    thrd_t threads[2];
    for (size_t i = 0; i < 2; ++i) {
        if (thrd_create(&threads[i], wait_worker, &jobs[i]) != thrd_success) { _Exit(81); }
    }
    REQUIRE(mtx_lock(&audit_mutex) == thrd_success);
    while (entered < 2) { REQUIRE(cnd_wait(&audit_changed, &audit_mutex) == thrd_success); }
    REQUIRE(mtx_unlock(&audit_mutex) == thrd_success);
    queue_close(&queue);
    queue_close(&queue);
    for (size_t i = 0; i < 2; ++i) {
        int result;
        join_or_exit(threads[i], &result);
        REQUIRE(result == EXIT_SUCCESS && jobs[i].result == 0 && jobs[i].value == 77);
    }
    REQUIRE(entered == 2 && queue.count == (WAITING_PRODUCERS ? QUEUE_CAPACITY : 0));
    int value = 77;
    if (WAITING_PRODUCERS) {
        for (int i = 1; i <= QUEUE_CAPACITY; ++i) { REQUIRE(queue_pop(&queue, &value) && value == i); }
    }
    value = 77;
    REQUIRE(queue_pop(&queue, &value) == 0 && value == 77);
    queue_destroy(&queue);
    cnd_destroy(&audit_changed);
    mtx_destroy(&audit_mutex);
    return EXIT_SUCCESS;
}
"""


class TutorialCConditionContentTestCase(unittest.TestCase):
    def test_examples_match_both_lessons(self) -> None:
        for key, count in (("conditions", 1), ("queues", 2)):
            page = next(page for page in C_PAGES if page["key"] == key)
            examples = [example for example in C_EXAMPLES if example["page_key"] == key]
            self.assertEqual(len(examples), count)
            blocks = [block["source"] for block in page["content"]["blocks"] if block["type"] == "code"]
            self.assertGreaterEqual(len(blocks), 3)
            for example in examples:
                self.assertIn(example["source"], blocks)


@unittest.skipUnless(shutil.which("gcc"), "GCC is unavailable")
class TutorialCConditionNativeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory(prefix="poznamkovnik-cnd-probe-") as directory:
            root = Path(directory)
            source = root / "probe.c"
            source.write_text("#include <threads.h>\nint main(void) { cnd_t c; if (cnd_init(&c) != thrd_success) return 1; cnd_destroy(&c); return 0; }\n")
            build = subprocess.run(["gcc", "-std=c17", "-pthread", str(source), "-o", str(root / "probe")], capture_output=True, text=True, timeout=15)
            if build.returncode != 0:
                raise unittest.SkipTest("C condition variables are unavailable: " + build.stderr)

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-conditions-")
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

    def assert_success(self, source: str, *flags: str) -> None:
        result = self.run_source(source, *flags)
        self.assertEqual((result.returncode, result.stderr), (0, ""), result)

    def audit_source(self, source: str, **failures: int) -> str:
        flags = dict(FAIL_INIT=0, FAIL_CREATE=0, FAIL_JOIN=0)
        flags.update(failures)
        return "".join(f"#define {key} {value}\n" for key, value in flags.items()) + LIFECYCLE_AUDIT + source + AUDIT_MAIN

    def test_examples_repeat_with_expected_output(self) -> None:
        for source, expected in (
            (CONDITION_GATE, "received=42\n"), (PRODUCER_CONSUMER, "count=12 total=78\n"),
            (QUEUE_DRAIN, "rejected=1 first=1:10 second=1:-2 end=0:77\n"),
        ):
            self.assertEqual(self.compile_source(source, "-O2", "-DNDEBUG").returncode, 0)
            for attempt in range(10):
                result = self.execute()
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ""), attempt)

    def test_gate_published_before_start_does_not_wait(self) -> None:
        main = GATE_MAIN.replace("    gate_open(&gate, 42);\n", "")
        main = main.replace("    thrd_t thread;", "    gate_open(&gate, 42);\n    thrd_t thread;")
        source = THREAD_JOIN + GATE_SUPPORT + "\n#define cnd_wait(c, m) (exit(82), thrd_error)\n" + GATE_WAIT + main
        result = self.run_source(source)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "received=42\n", ""))

    def gate_wait_model(self, wait_source: str) -> str:
        return REQUIRE + GATE_SUPPORT + r"""
static Gate *model_gate;
static unsigned int waits;
static int model_wait(cnd_t *condition, mtx_t *mutex)
{
    REQUIRE(condition == &model_gate->changed && mutex == &model_gate->mutex);
    REQUIRE(++waits <= 2);
    REQUIRE(mtx_unlock(mutex) == thrd_success);
    if (waits == 2) { gate_open(model_gate, 42); }
    return mtx_lock(mutex);
}
#define cnd_wait model_wait
""" + wait_source + r"""
int main(void)
{
    Gate gate;
    REQUIRE(gate_init(&gate));
    model_gate = &gate;
    REQUIRE(await_gate(&gate) == 42 && waits == 2);
    gate_destroy(&gate);
    return EXIT_SUCCESS;
}
"""

    def test_gate_rechecks_after_spurious_wake_and_rejects_if(self) -> None:
        self.assert_success(self.gate_wait_model(GATE_WAIT))
        result = self.run_source(self.gate_wait_model(GATE_WAIT.replace("while (!gate->ready)", "if (!gate->ready)")))
        self.assertEqual(result.returncode, 80)

    def test_queue_rechecks_both_waits_and_both_close_predicates(self) -> None:
        prefix = REQUIRE + QUEUE_SUPPORT + QUEUE_CLOSE + QUEUE_WAIT_MODEL
        self.assert_success(prefix + QUEUE_OPERATIONS + QUEUE_WAIT_MAIN)
        for predicate in ("queue->count == 0 && !queue->closed", "queue->count == QUEUE_CAPACITY && !queue->closed"):
            for changed in (
                QUEUE_OPERATIONS.replace(f"while ({predicate})", f"if ({predicate})"),
                QUEUE_OPERATIONS.replace(predicate, predicate.removesuffix(" && !queue->closed")),
            ):
                result = self.run_source(prefix + changed + QUEUE_WAIT_MAIN)
                self.assertEqual(result.returncode, 80)

    def test_close_wakes_two_native_consumers_already_waiting(self) -> None:
        source = REQUIRE + NATIVE_WAIT_HANDSHAKE + THREAD_JOIN + BOUNDED_QUEUE + NATIVE_WAIT_MAIN
        self.assert_success(source, "-DWAITING_PRODUCERS=0")

    def test_close_wakes_two_native_producers_already_waiting(self) -> None:
        source = REQUIRE + NATIVE_WAIT_HANDSHAKE + THREAD_JOIN + BOUNDED_QUEUE + NATIVE_WAIT_MAIN
        self.assert_success(source, "-DWAITING_PRODUCERS=1")

    def test_queue_fifo_wraparound_extremes_and_end_preserve_output(self) -> None:
        self.assert_success(REQUIRE + BOUNDED_QUEUE + r"""
#include <limits.h>
int main(void)
{
    Queue queue;
    REQUIRE(queue_init(&queue));
    const int values[] = {INT_MIN, 0, INT_MAX};
    for (unsigned int round = 0; round < 100; ++round) {
        for (size_t i = 0; i < 3; ++i) { REQUIRE(queue_push(&queue, values[i])); }
        int value;
        REQUIRE(queue_pop(&queue, &value) && value == INT_MIN);
        REQUIRE(queue_push(&queue, -7));
        REQUIRE(queue.count == 3);
        REQUIRE(queue_pop(&queue, &value) && value == 0);
        REQUIRE(queue_pop(&queue, &value) && value == INT_MAX);
        REQUIRE(queue_pop(&queue, &value) && value == -7);
        REQUIRE(queue.count == 0 && queue.head < QUEUE_CAPACITY);
    }
    queue_close(&queue);
    queue_close(&queue);
    int value = 77;
    REQUIRE(queue_push(&queue, 42) == 0);
    REQUIRE(queue_pop(&queue, &value) == 0 && value == 77);
    queue_destroy(&queue);
    return EXIT_SUCCESS;
}
""")

    def test_success_and_partial_start_join_before_destroy(self) -> None:
        for source, resources, workers in ((CONDITION_GATE, 2, 1), (PRODUCER_CONSUMER, 3, 2)):
            for failure in range(workers + 1):
                result = self.run_source(self.audit_source(source, FAIL_CREATE=failure))
                started = workers if failure == 0 else failure - 1
                self.assertEqual(result.returncode == 0, failure == 0, result)
                self.assertIn(f"audit created={started} joined={started} init={resources} destroyed={resources}\n", result.stderr)
                if failure:
                    self.assertEqual(result.stdout, "")

    def test_initialization_rollback_destroys_only_successful_objects(self) -> None:
        for source, resources in ((CONDITION_GATE, 2), (PRODUCER_CONSUMER, 3)):
            for failure in range(1, resources + 1):
                result = self.run_source(self.audit_source(source, FAIL_INIT=failure))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, f"audit created=0 joined=0 init={failure - 1} destroyed={failure - 1}\n")

    def test_consumer_error_closes_queue_before_join(self) -> None:
        for changed in (
            PRODUCER_CONSUMER.replace("int value = 1; value <= 12", "int value = -1; value <= 12"),
            PRODUCER_CONSUMER.replace("ConsumerJob job = {&queue, 0, 0}", "ConsumerJob job = {&queue, UINT_MAX, 0}"),
            PRODUCER_CONSUMER.replace("ConsumerJob job = {&queue, 0, 0}", "ConsumerJob job = {&queue, 0, UINT_MAX}"),
        ):
            result = self.run_source(self.audit_source(changed))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "audit created=2 joined=2 init=3 destroyed=3\n")

    def test_join_failure_is_fatal_without_normal_cleanup(self) -> None:
        for source in (CONDITION_GATE, PRODUCER_CONSUMER):
            result = self.run_source(self.audit_source(source, FAIL_JOIN=1))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "Cannot join thread.\nfatal-without-return\n")

    def test_runtime_sync_errors_are_fatal_not_end_of_queue(self) -> None:
        for function, args, message in (
            ("mtx_lock", "m", "Cannot lock queue."),
            ("mtx_unlock", "m", "Cannot unlock queue."),
            ("cnd_wait", "c, m", "Cannot wait for item."),
            ("cnd_signal", "c", "Cannot signal item."),
            ("cnd_broadcast", "c", "Cannot wake consumers."),
        ):
            prefix = "#include <threads.h>\n" + f"#define {function}({args}) thrd_error\n"
            source = prefix + BOUNDED_QUEUE + r"""
int main(void)
{
    Queue queue;
    if (!queue_init(&queue)) { return 90; }
    int value = 77;
""" + ("    (void) queue_pop(&queue, &value);\n" if function == "cnd_wait" else "    (void) queue_push(&queue, 42);\n    queue_close(&queue);\n    (void) queue_pop(&queue, &value);\n") + r"""
    (void) queue_push(&queue, 99);
    queue_close(&queue);
    queue_destroy(&queue);
    fputs("incorrect cleanup\n", stderr);
    return EXIT_SUCCESS;
}
"""
            result = self.run_source(source)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr, message + "\n")

    def test_all_exercise_variants_accept_solution_and_reject_starter(self) -> None:
        for topic, placeholder, solution in (("conditions", GATE_PLACEHOLDER, GATE_SOLUTION), ("queues", CLOSE_PLACEHOLDER, CLOSE_SOLUTION)):
            for variant in range(4):
                exercise = tutorial_practice("c", topic, variant)
                self.assertEqual(exercise["starterSource"].count(placeholder), 1)
                source = exercise["starterSource"].replace(placeholder, solution)
                result = self.run_source(source)
                self.assertEqual(result.returncode, 0, result)
                self.assertEqual(result.stderr, "")
                self.assertEqual(evaluate_tutorial_practice(exercise, {"compiled": True, "run": {"exitCode": 0, "stdout": result.stdout, "stderr": ""}}, "")["status"], "passed")
                starter = self.run_source(exercise["starterSource"])
                self.assertTrue(starter.returncode != 0 or starter.stdout != exercise["expectedOutput"])

    def test_exercise_solutions_have_the_same_protocol_as_examples(self) -> None:
        self.assertIn(GATE_SOLUTION, GATE_WAIT)
        self.assertIn(CLOSE_SOLUTION, QUEUE_CLOSE)
        self.assert_success(self.gate_wait_model("static int await_gate(Gate *gate) {\n" + GATE_SOLUTION + "\n}\n"))
        close = "static void queue_close(Queue *queue) {\n" + CLOSE_SOLUTION + "\n}\n"
        source = REQUIRE + NATIVE_WAIT_HANDSHAKE + THREAD_JOIN + QUEUE_SUPPORT + close + QUEUE_OPERATIONS + NATIVE_WAIT_MAIN
        for producers in (0, 1):
            self.assert_success(source, f"-DWAITING_PRODUCERS={producers}")

    def test_close_broadcasts_both_conditions_under_lock_even_when_repeated(self) -> None:
        prefix = REQUIRE + QUEUE_SUPPORT + r"""
static Queue *audited_queue;
static unsigned int broadcasts, mask;
static int locked;
static int checked_lock(mtx_t *mutex)
{
    REQUIRE(!locked && mutex == &audited_queue->mutex);
    int status = mtx_lock(mutex);
    if (status == thrd_success) { locked = 1; mask = 0; }
    return status;
}
static int checked_broadcast(cnd_t *condition)
{
    REQUIRE(locked && audited_queue->closed);
    unsigned int bit = condition == &audited_queue->not_empty ? 1U : 2U;
    REQUIRE(condition == &audited_queue->not_empty || condition == &audited_queue->not_full);
    REQUIRE((mask & bit) == 0);
    mask |= bit;
    ++broadcasts;
    return cnd_broadcast(condition);
}
static int checked_unlock(mtx_t *mutex)
{
    REQUIRE(locked && mask == 3 && mutex == &audited_queue->mutex);
    locked = 0;
    return mtx_unlock(mutex);
}
#define mtx_lock checked_lock
#define mtx_unlock checked_unlock
#define cnd_broadcast checked_broadcast
#define cnd_signal(c) (exit(83), thrd_error)
"""
        suffix = r"""
#undef mtx_lock
#undef mtx_unlock
#undef cnd_broadcast
#undef cnd_signal
int main(void)
{
    Queue queue;
    REQUIRE(queue_init(&queue));
    audited_queue = &queue;
    queue_close(&queue);
    queue_close(&queue);
    REQUIRE(broadcasts == 4 && !locked);
    queue_destroy(&queue);
    return EXIT_SUCCESS;
}
"""
        self.assert_success(prefix + QUEUE_CLOSE + suffix)
        for condition in ("not_empty", "not_full"):
            changed = QUEUE_CLOSE.replace(f"cnd_broadcast(&queue->{condition})", f"cnd_signal(&queue->{condition})")
            self.assertEqual(self.run_source(prefix + changed + suffix).returncode, 83)
        changed = QUEUE_CLOSE.replace("queue->closed = true;", "queue->closed = false;")
        self.assertEqual(self.run_source(prefix + changed + suffix).returncode, 80)

    def test_closed_queue_does_not_discard_pending_items(self) -> None:
        changed = QUEUE_DRAIN.replace("if (queue->count == 0)", "if (queue->closed)")
        result = self.run_source(changed)
        self.assertEqual(result.returncode, 0)
        self.assertNotEqual(result.stdout, "rejected=1 first=1:10 second=1:-2 end=0:77\n")


if __name__ == "__main__":
    unittest.main()
