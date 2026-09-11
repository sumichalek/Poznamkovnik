from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from backend.tutorial_c_examples import (
    COOPERATIVE_JOBS, COOPERATIVE_PRODUCER, COOPERATIVE_SHUTDOWN,
    QUEUE_CLOSE, QUEUE_PUSH, QUEUE_SUPPORT, THREAD_JOIN,
    TIMED_QUEUE, TIMED_QUEUE_POP, TIMED_QUEUE_STATES, TIMED_QUEUE_TYPES,
    TIMED_QUEUE_WAIT, TIMEOUT_SHUTDOWN,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice
from tests.test_tutorial_c_conditions import AUDIT_MAIN, LIFECYCLE_AUDIT, REQUIRE


DEADLINE_PLACEHOLDER = """    /* Replace this placeholder with a loop and state checks after timeout. */
    (void) queue;
    (void) deadline;
    return QUEUE_TIMEOUT;"""
DEADLINE_SOLUTION = """    while (queue->count == 0 && !queue->closed) {
        int status = cnd_timedwait(&queue->not_empty, &queue->mutex, deadline);
        if (status == thrd_timedout) {
            if (queue->count == 0 && !queue->closed) { return QUEUE_TIMEOUT; }
        } else {
            check_sync(status, "Cannot timed-wait for item.\\n");
        }
    }
    return queue->count != 0 ? QUEUE_ITEM : QUEUE_END;"""
STOP_PLACEHOLDER = """    /* Replace this placeholder with counted pushes and cooperative stopping. */
    (void) queue_push;
    ProducerJob *job = context;
    queue_close(job->queue);
    return EXIT_FAILURE;"""
STOP_SOLUTION = """    ProducerJob *job = context;
    for (int value = 1; value <= 12; ++value) {
        if (!queue_push(job->queue, value)) {
            job->stopped = true;
            return EXIT_SUCCESS;
        }
        ++job->accepted;
    }
    queue_close(job->queue);
    return EXIT_SUCCESS;"""
STATES_OUTPUT = "timeout=1 unchanged=1 accepted=1\nitem=1 value=42\nend=1 unchanged=1\n"
STOP_OUTPUT = "stopped=1 drained=1 bounded=1\n"

# Real mutexes surround simulated wake reasons; no wall-clock timing assumptions.
TIMED_MODEL = r"""
static Queue *model_queue;
static unsigned int waits, locks, unlocks, signals;
static int locked, state_change, wake_status;
static int checked_lock(mtx_t *mutex)
{
    REQUIRE(!locked && mutex == &model_queue->mutex);
    int result = mtx_lock(mutex);
    if (result == thrd_success) { locked = 1; ++locks; }
    return result;
}
static int checked_unlock(mtx_t *mutex)
{
    REQUIRE(locked && mutex == &model_queue->mutex);
    locked = 0;
    ++unlocks;
    return mtx_unlock(mutex);
}
static int checked_signal(cnd_t *condition)
{
    REQUIRE(locked && condition == &model_queue->not_full && model_queue->count == 0);
    ++signals;
    return cnd_signal(condition);
}
static int model_wait(cnd_t *condition, mtx_t *mutex, const struct timespec *deadline)
{
    REQUIRE(locked && condition == &model_queue->not_empty && mutex == &model_queue->mutex);
    REQUIRE(deadline->tv_sec == 100 && deadline->tv_nsec == 123456789L);
    REQUIRE(++waits <= 4);
    if (FORCE_WAIT_ERROR) { return thrd_error; }
    REQUIRE(checked_unlock(mutex) == thrd_success);
    if (waits == 3) {
        if (state_change & 1) { REQUIRE(queue_push(model_queue, -42)); }
        if (state_change & 2) { queue_close(model_queue); }
    }
    REQUIRE(checked_lock(mutex) == thrd_success);
    if (waits < 3) { return thrd_success; }
    return waits == 4 ? thrd_timedout : wake_status;
}
#define mtx_lock checked_lock
#define mtx_unlock checked_unlock
#define cnd_signal checked_signal
#define cnd_timedwait model_wait
#define timespec_get(t, b) ((void) (t), (void) (b), exit(84), 0)
"""
TIMED_MODEL_MAIN = r"""
int main(void)
{
    const struct timespec deadline = {100, 123456789L};
    const int statuses[] = {thrd_success, thrd_timedout};
    for (size_t i = 0; i < 2; ++i) {
        wake_status = statuses[i];
        for (state_change = 0; state_change < 4; ++state_change) {
            Queue queue;
            REQUIRE(queue_init(&queue));
            model_queue = &queue;
            waits = locks = unlocks = signals = 0;
            int value = 77;
            QueueRead result = queue_pop_until(&queue, &value, &deadline);
            QueueRead expected = (state_change & 1) ? QUEUE_ITEM : state_change ? QUEUE_END : QUEUE_TIMEOUT;
            REQUIRE(result == expected && value == (expected == QUEUE_ITEM ? -42 : 77));
            REQUIRE(waits == ((state_change == 0 && wake_status == thrd_success) ? 4U : 3U));
            REQUIRE(!locked && locks == waits + 1 && locks == unlocks);
            REQUIRE(signals == (expected == QUEUE_ITEM ? 1U : 0U));
            REQUIRE(queue.count == 0 && queue.closed == ((state_change & 2) != 0));
            REQUIRE(deadline.tv_sec == 100 && deadline.tv_nsec == 123456789L);
            queue_close(&queue);
            queue_destroy(&queue);
        }
    }
    return EXIT_SUCCESS;
}
"""

NATIVE_TIMER = r"""
#include <threads.h>
#include <time.h>
static mtx_t audit_mutex;
static cnd_t audit_ready;
static int entered;
static int observed_wait(cnd_t *condition, mtx_t *mutex, const struct timespec *deadline)
{
    REQUIRE(mtx_lock(&audit_mutex) == thrd_success);
    entered = 1;
    REQUIRE(cnd_signal(&audit_ready) == thrd_success);
    REQUIRE(mtx_unlock(&audit_mutex) == thrd_success);
    return cnd_timedwait(condition, mutex, deadline);
}
#define cnd_timedwait observed_wait
"""
NATIVE_TIMER_MAIN = r"""
typedef struct { Queue *queue; const struct timespec *deadline; QueueRead status; int value; } NativeJob;
static int native_reader(void *context)
{
    NativeJob *job = context;
    job->status = queue_pop_until(job->queue, &job->value, job->deadline);
    return EXIT_SUCCESS;
}
int main(void)
{
    Queue queue;
    REQUIRE(queue_init(&queue));
    REQUIRE(mtx_init(&audit_mutex, mtx_plain) == thrd_success);
    REQUIRE(cnd_init(&audit_ready) == thrd_success);
    const struct timespec deadline = {(time_t) HOST_DEADLINE, 0};
    NativeJob job = {&queue, &deadline, QUEUE_TIMEOUT, 77};
    thrd_t thread;
    if (thrd_create(&thread, native_reader, &job) != thrd_success) { _Exit(81); }
    REQUIRE(mtx_lock(&audit_mutex) == thrd_success);
    while (!entered) { REQUIRE(cnd_wait(&audit_ready, &audit_mutex) == thrd_success); }
    REQUIRE(mtx_unlock(&audit_mutex) == thrd_success);
    /* The waiter still held queue.mutex when it announced entry. */
    if (CLOSE_INSTEAD) { queue_close(&queue); }
    else { REQUIRE(queue_push(&queue, 42)); }
    int result;
    join_or_exit(thread, &result);
    REQUIRE(result == EXIT_SUCCESS);
    REQUIRE(job.status == (CLOSE_INSTEAD ? QUEUE_END : QUEUE_ITEM));
    REQUIRE(job.value == (CLOSE_INSTEAD ? 77 : 42));
    queue_close(&queue);
    queue_destroy(&queue);
    cnd_destroy(&audit_ready);
    mtx_destroy(&audit_mutex);
    return EXIT_SUCCESS;
}
"""

PRODUCER_MODEL = REQUIRE + r"""
#include <stdbool.h>
typedef struct { unsigned int accepted, attempts, closed, limit; } Queue;
static int queue_push(Queue *queue, int value)
{
    REQUIRE(!queue->closed && value == (int) queue->attempts + 1);
    ++queue->attempts;
    if (queue->accepted == queue->limit) { queue->closed = 1; return 0; }
    ++queue->accepted;
    return 1;
}
static void queue_close(Queue *queue) { REQUIRE(!queue->closed); queue->closed = 1; }
"""
PRODUCER_MODEL_MAIN = r"""
int main(void)
{
    for (unsigned int limit = 0; limit <= 12; ++limit) {
        Queue queue = {0, 0, 0, limit};
        ProducerJob job = {&queue, 0, false};
        REQUIRE(produce_until_closed(&job) == EXIT_SUCCESS);
        REQUIRE(job.accepted == limit && queue.accepted == limit && queue.closed);
        REQUIRE(job.stopped == (limit < 12));
        REQUIRE(queue.attempts == (limit < 12 ? limit + 1 : 12));
    }
    return EXIT_SUCCESS;
}
"""


class TutorialCDeadlineContentTestCase(unittest.TestCase):
    def test_examples_match_both_lessons(self) -> None:
        for key, count in (("deadlines", 1), ("cancellation", 2)):
            page = next(page for page in C_PAGES if page["key"] == key)
            sources = [block["source"] for block in page["content"]["blocks"] if block["type"] == "code"]
            self.assertGreaterEqual(len(sources), 3)
            examples = [example for example in C_EXAMPLES if example["page_key"] == key]
            self.assertEqual(len(examples), count)
            for example in examples:
                self.assertIn(example["source"], sources)


@unittest.skipUnless(shutil.which("gcc"), "GCC is unavailable")
class TutorialCDeadlineNativeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory(prefix="poznamkovnik-timed-probe-") as directory:
            root = Path(directory)
            source = root / "probe.c"
            source.write_text("#include <threads.h>\n#include <time.h>\nint main(void) { struct timespec t; return timespec_get(&t, TIME_UTC) != TIME_UTC || cnd_timedwait == 0; }\n")
            result = subprocess.run(["gcc", "-std=c17", "-pthread", str(source), "-o", str(root / "probe")], capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                raise unittest.SkipTest("C timed waits are unavailable: " + result.stderr)

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-deadlines-")
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

    def model_source(self, wait_source: str = TIMED_QUEUE_WAIT, pop_source: str = TIMED_QUEUE_POP) -> str:
        return REQUIRE + QUEUE_SUPPORT + QUEUE_CLOSE + QUEUE_PUSH + TIMED_QUEUE_TYPES + TIMED_MODEL + wait_source + pop_source + TIMED_MODEL_MAIN

    def audit_source(self, source: str, **failures: int) -> str:
        flags = dict(FAIL_INIT=0, FAIL_CREATE=0, FAIL_JOIN=0)
        flags.update(failures)
        return "".join(f"#define {key} {value}\n" for key, value in flags.items()) + LIFECYCLE_AUDIT + source + AUDIT_MAIN

    def test_examples_repeat_with_immediate_timeout_and_bounded_stop(self) -> None:
        for source, output in ((TIMED_QUEUE_STATES, STATES_OUTPUT), (TIMEOUT_SHUTDOWN, "timeout=1 closed=1\n"), (COOPERATIVE_SHUTDOWN, STOP_OUTPUT)):
            build = self.compile_source(source, "-O2", "-DNDEBUG")
            self.assertEqual(build.returncode, 0, build.stderr)
            for attempt in range(10):
                result = self.execute()
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, output, ""), attempt)

    def test_spurious_wakes_keep_deadline_and_timeout_rechecks_all_states(self) -> None:
        self.assert_success(self.model_source(), "-DFORCE_WAIT_ERROR=0")

    def test_wait_mutations_do_not_hide_behind_expected_output(self) -> None:
        changes = (
            TIMED_QUEUE_WAIT.replace("while (queue->count == 0 && !queue->closed)", "if (queue->count == 0 && !queue->closed)"),
            TIMED_QUEUE_WAIT.replace("if (queue->count == 0 && !queue->closed) { return QUEUE_TIMEOUT; }", "return QUEUE_TIMEOUT;"),
            TIMED_QUEUE_WAIT.replace("return queue->count != 0 ? QUEUE_ITEM : QUEUE_END;", "return queue->closed ? QUEUE_END : QUEUE_ITEM;"),
        )
        for changed in changes:
            result = self.run_source(self.model_source(changed), "-DFORCE_WAIT_ERROR=0")
            self.assertEqual(result.returncode, 80)
        reset = TIMED_QUEUE_WAIT.replace("int status = cnd_timedwait", "struct timespec renewed;\n        if (timespec_get(&renewed, TIME_UTC) != TIME_UTC) { return QUEUE_TIMEOUT; }\n        int status = cnd_timedwait")
        self.assertEqual(self.run_source(self.model_source(reset), "-DFORCE_WAIT_ERROR=0").returncode, 84)

    def test_timedwait_error_is_fatal_and_not_timeout(self) -> None:
        result = self.run_source(self.model_source(), "-DFORCE_WAIT_ERROR=1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "Cannot timed-wait for item.\n")

    def test_pop_preserves_output_and_notifies_the_producer(self) -> None:
        changed = TIMED_QUEUE_POP.replace("QueueRead status = wait_for_item_until", "*result = 0;\n    QueueRead status = wait_for_item_until")
        self.assertEqual(self.run_source(self.model_source(pop_source=changed), "-DFORCE_WAIT_ERROR=0").returncode, 80)
        changed = TIMED_QUEUE_POP.replace("cnd_signal(&queue->not_full)", "cnd_signal(&queue->not_empty)")
        self.assertEqual(self.run_source(self.model_source(pop_source=changed), "-DFORCE_WAIT_ERROR=0").returncode, 80)

    def test_native_future_deadline_wakes_for_item_or_close(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("This host-clock probe uses the Linux TIME_UTC/POSIX epoch")
        # Only the host probe uses a POSIX epoch literal; lesson sources do not.
        deadline = int(time.time()) + 60
        source = REQUIRE + NATIVE_TIMER + THREAD_JOIN + TIMED_QUEUE + QUEUE_PUSH + NATIVE_TIMER_MAIN
        for closed in (0, 1):
            self.assert_success(source, f"-DHOST_DEADLINE={deadline}LL", f"-DCLOSE_INSTEAD={closed}")

    def test_ready_or_closed_state_never_waits_even_with_old_deadline(self) -> None:
        prefix = "#include <threads.h>\n#define cnd_timedwait(c, m, t) ((void) (c), (void) (m), (void) (t), exit(86), thrd_error)\n"
        source = prefix + REQUIRE + TIMED_QUEUE + QUEUE_PUSH + r"""
int main(void)
{
    Queue queue;
    REQUIRE(queue_init(&queue));
    const struct timespec deadline = {0, 0};
    int value = 77;
    for (unsigned int round = 0; round < 100; ++round) {
        for (int i = 1; i <= QUEUE_CAPACITY; ++i) { REQUIRE(queue_push(&queue, i)); }
        for (int i = 1; i <= QUEUE_CAPACITY; ++i) {
            REQUIRE(queue_pop_until(&queue, &value, &deadline) == QUEUE_ITEM && value == i);
        }
        REQUIRE(queue.count == 0 && queue.head < QUEUE_CAPACITY);
    }
    REQUIRE(queue_push(&queue, 0));
    REQUIRE(queue_pop_until(&queue, &value, &deadline) == QUEUE_ITEM && value == 0);
    REQUIRE(queue_push(&queue, -42));
    queue_close(&queue);
    REQUIRE(queue_pop_until(&queue, &value, &deadline) == QUEUE_ITEM && value == -42);
    value = 77;
    REQUIRE(queue_pop_until(&queue, &value, &deadline) == QUEUE_END && value == 77);
    queue_destroy(&queue);
    return EXIT_SUCCESS;
}
"""
        self.assert_success(source)

    def test_clock_failure_never_initializes_queue_or_uses_deadline(self) -> None:
        prefix = r"""
#include <threads.h>
#include <time.h>
static int failed_clock(struct timespec *value, int base)
{
    (void) base;
    value->tv_nsec = -1;
    return 0;
}
#define timespec_get failed_clock
#define mtx_init(m, t) (exit(85), thrd_error)
#define cnd_timedwait(c, m, t) ((void) (c), (void) (m), (void) (t), exit(86), thrd_error)
"""
        for source in (TIMED_QUEUE_STATES, TIMEOUT_SHUTDOWN):
            result = self.run_source(prefix + source)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(result.returncode, (85, 86))
            self.assertEqual(result.stderr, "Cannot read clock.\n")

    def test_startup_and_initialization_failures_preserve_lifecycle(self) -> None:
        for source, workers in ((TIMEOUT_SHUTDOWN, 1), (COOPERATIVE_SHUTDOWN, 2)):
            for failed in range(workers + 1):
                result = self.run_source(self.audit_source(source, FAIL_CREATE=failed))
                started = workers if failed == 0 else failed - 1
                self.assertEqual(result.returncode == 0, failed == 0, result)
                self.assertIn(f"audit created={started} joined={started} init=3 destroyed=3\n", result.stderr)
            for failed in range(1, 4):
                result = self.run_source(self.audit_source(source, FAIL_INIT=failed))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, f"audit created=0 joined=0 init={failed - 1} destroyed={failed - 1}\n")

    def test_failed_join_does_not_return_to_normal_cleanup(self) -> None:
        for source in (TIMEOUT_SHUTDOWN, COOPERATIVE_SHUTDOWN):
            result = self.run_source(self.audit_source(source, FAIL_JOIN=1))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "Cannot join thread.\nfatal-without-return\n")

    def test_timeout_itself_does_not_close_but_worker_policy_does(self) -> None:
        changed = TIMEOUT_SHUTDOWN.replace("        queue_close(job->queue);", "        (void) queue_close;")
        result = self.run_source(changed)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "timeout=1 closed=0\n", ""))
        self.assertEqual(self.run_source(TIMED_QUEUE_STATES).stdout, STATES_OUTPUT)

    def test_producer_counts_only_accepted_items_at_every_rejection(self) -> None:
        prefix = PRODUCER_MODEL + COOPERATIVE_JOBS
        self.assert_success(prefix + COOPERATIVE_PRODUCER + PRODUCER_MODEL_MAIN)
        changed = COOPERATIVE_PRODUCER.replace("        ++job->accepted;\n", "")
        changed = changed.replace("        if (!queue_push", "        ++job->accepted;\n        if (!queue_push")
        self.assertEqual(self.run_source(prefix + changed + PRODUCER_MODEL_MAIN).returncode, 80)

    def test_stop_requested_before_native_workers_start_is_observed(self) -> None:
        self.assert_success(REQUIRE + "\n#define main lesson_main\n" + COOPERATIVE_SHUTDOWN + r"""
#undef main
int main(void)
{
    Queue queue;
    REQUIRE(queue_init(&queue));
    queue_close(&queue);
    ProducerJob producer = {&queue, 0, false};
    DrainJob consumer = {&queue, 0};
    thrd_t threads[2];
    if (thrd_create(&threads[0], drain_and_stop, &consumer) != thrd_success) { _Exit(81); }
    if (thrd_create(&threads[1], produce_until_closed, &producer) != thrd_success) { _Exit(81); }
    for (size_t i = 0; i < 2; ++i) {
        int result;
        join_or_exit(threads[i], &result);
        REQUIRE(result == EXIT_SUCCESS);
    }
    REQUIRE(producer.stopped && producer.accepted == 0 && consumer.consumed == 0);
    queue_destroy(&queue);
    return EXIT_SUCCESS;
}
""")

    def test_consumer_drains_items_already_queued_at_stop(self) -> None:
        suffix = r"""
#undef main
int main(void)
{
    Queue queue;
    REQUIRE(queue_init(&queue));
    for (int i = 1; i <= QUEUE_CAPACITY; ++i) { REQUIRE(queue_push(&queue, i)); }
    DrainJob job = {&queue, 0};
    REQUIRE(drain_and_stop(&job) == EXIT_SUCCESS);
    REQUIRE(job.consumed == QUEUE_CAPACITY && queue.count == 0 && queue.closed);
    queue_destroy(&queue);
    return EXIT_SUCCESS;
}
"""
        source = COOPERATIVE_SHUTDOWN.replace("STOP_AFTER = 3", "STOP_AFTER = 1")
        self.assert_success(REQUIRE + "\n#define main lesson_main\n" + source + suffix)
        changed = source.replace("{ queue_close(job->queue); }", "{ queue_close(job->queue); break; }")
        self.assertEqual(self.run_source(REQUIRE + "\n#define main lesson_main\n" + changed + suffix).returncode, 80)

    def test_all_exercise_variants_accept_solutions_and_reject_starters(self) -> None:
        for topic, placeholder, solution in (("deadlines", DEADLINE_PLACEHOLDER, DEADLINE_SOLUTION), ("cancellation", STOP_PLACEHOLDER, STOP_SOLUTION)):
            for variant in range(4):
                exercise = tutorial_practice("c", topic, variant)
                self.assertEqual(exercise["starterSource"].count(placeholder), 1)
                result = self.run_source(exercise["starterSource"].replace(placeholder, solution))
                self.assertEqual(result.returncode, 0, result)
                self.assertEqual(result.stderr, "")
                evaluation = evaluate_tutorial_practice(exercise, {"compiled": True, "run": {"exitCode": result.returncode, "stdout": result.stdout, "stderr": ""}}, "")
                self.assertEqual(evaluation["status"], "passed")
                starter = self.run_source(exercise["starterSource"])
                self.assertTrue(starter.returncode != 0 or starter.stdout != exercise["expectedOutput"])

    def test_solutions_pass_the_same_protocol_models_as_examples(self) -> None:
        wait = "static QueueRead wait_for_item_until(Queue *queue, const struct timespec *deadline) {\n" + DEADLINE_SOLUTION + "\n}\n"
        self.assert_success(self.model_source(wait), "-DFORCE_WAIT_ERROR=0")
        producer = "static int produce_until_closed(void *context) {\n" + STOP_SOLUTION + "\n}\n"
        self.assert_success(PRODUCER_MODEL + COOPERATIVE_JOBS + producer + PRODUCER_MODEL_MAIN)


if __name__ == "__main__":
    unittest.main()
