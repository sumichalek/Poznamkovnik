from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.tutorial_c_examples import (
    ATOMIC_WORKERS, MAILBOX_PUBLICATION, MAXIMUM_JOB, MUTEX_TOTALS,
    MUTEX_WORKERS, ONCE_MAILBOX, SPLIT_ATOMIC_UPDATE, THREAD_JOIN, THREAD_LIFETIME,
)
from backend.tutorial_content import C_EXAMPLES, C_PAGES
from backend.tutorial_exercises import evaluate_tutorial_practice, tutorial_practice


THREAD_PLACEHOLDER = """    /* Replace this placeholder with validation and a worker-owned result. */
    (void) context;
    return EXIT_FAILURE;"""
THREAD_SOLUTION = """    if (context == NULL) { return EXIT_FAILURE; }
    MaximumJob *job = context;
    if (job->values == NULL || job->count == 0) { return EXIT_FAILURE; }
    int maximum = job->values[0];
    for (size_t i = 1; i < job->count; ++i) {
        if (job->values[i] > maximum) { maximum = job->values[i]; }
    }
    job->maximum = maximum;
    return EXIT_SUCCESS;"""
MAILBOX_PLACEHOLDER = """    /* Replace this placeholder with acquire-before-payload access. */
    (void) box;
    (void) result;
    return 0;"""
MAILBOX_SOLUTION = """    if (box == NULL || result == NULL) { return 0; }
    if (!atomic_load_explicit(&box->ready, memory_order_acquire)) { return 0; }
    *result = box->value;
    return 1;"""

PROGRAMS = (
    (THREAD_LIFETIME, "maximum=9\n", 1),
    (MUTEX_WORKERS, "count=200 total=1000\n", 2),
    (ATOMIC_WORKERS, "count=4000\n", 2),
    (MAILBOX_PUBLICATION, "before=0 value=77\nreceived=1 value=42\n", 1),
)

# These wrappers retain real native threads, joins and mutexes. Only the selected call fails.
LIFECYCLE_AUDIT = r"""
#include <threads.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned int attempts, created, joined, initialized, destroyed;
static thrd_t handles[2];
static int failed_worker(void *context) { (void) context; return EXIT_FAILURE; }
static int audited_create(thrd_t *thread, thrd_start_t function, void *context)
{
    ++attempts;
    if (attempts == FAIL_CREATE) { return thrd_error; }
    if (created >= 2) { abort(); }
    int status = thrd_create(thread, FAIL_WORKER ? failed_worker : function, context);
    if (status == thrd_success) { handles[created++] = *thread; }
    return status;
}
static int audited_join(thrd_t thread, int *result)
{
    if (joined >= created || !thrd_equal(thread, handles[joined])) { abort(); }
    if (FAIL_JOIN) { return thrd_error; }
    int status = thrd_join(thread, result);
    if (status == thrd_success) { ++joined; }
    return status;
}
#if WITH_MUTEX
static int audited_init(mtx_t *mutex, int type)
{
    if (FAIL_INIT) { return thrd_error; }
    int status = mtx_init(mutex, type);
    if (status == thrd_success) { ++initialized; }
    return status;
}
static void audited_destroy(mtx_t *mutex)
{
    if (joined != created || initialized != 1 || destroyed != 0) { abort(); }
    ++destroyed;
    mtx_destroy(mutex);
}
static int audited_lock(mtx_t *mutex) { return FAIL_LOCK ? thrd_error : mtx_lock(mutex); }
static int audited_unlock(mtx_t *mutex)
{
    if (FAIL_LOCK) { abort(); }
    int status = mtx_unlock(mutex);
    return FAIL_UNLOCK ? thrd_error : status;
}
#define mtx_init audited_init
#define mtx_destroy audited_destroy
#define mtx_lock audited_lock
#define mtx_unlock audited_unlock
#endif
static _Noreturn void audited_exit(int status)
{
    if (destroyed != 0) { abort(); }
    fputs("fatal-without-cleanup\n", stderr);
    (void) fflush(stderr);
    _Exit(status);
}
#define _Exit audited_exit
#define thrd_create audited_create
#define thrd_join audited_join
#define main lesson_main
"""

ORDER_AUDIT = r"""
#include <stdatomic.h>
#include <stdbool.h>
#include <stdlib.h>
static bool checked_load(atomic_bool *object, memory_order order)
{
    if (order != memory_order_acquire) { exit(91); }
    return atomic_load_explicit(object, order);
}
static void checked_store(atomic_bool *object, bool value, memory_order order)
{
    if (order != memory_order_release) { exit(92); }
    atomic_store_explicit(object, value, order);
}
static void checked_init(atomic_bool *object, bool value)
{
    /* GCC can expand atomic_init through a relaxed store; it is not publication. */
    atomic_init(object, value);
}
#undef atomic_load_explicit
#undef atomic_store_explicit
#undef atomic_init
#define atomic_load_explicit checked_load
#define atomic_store_explicit checked_store
#define atomic_init checked_init
"""


class TutorialCConcurrencyContentTestCase(unittest.TestCase):
    def test_new_lessons_have_exactly_the_guided_programs(self) -> None:
        for key, count in (("threads", 2), ("atomics", 3)):
            page = next(item for item in C_PAGES if item["key"] == key)
            self.assertEqual(page["kind"], "lesson")
            sources = [block["source"] for block in page["content"]["blocks"] if block["type"] == "code"]
            examples = [item for item in C_EXAMPLES if item["page_key"] == key]
            self.assertEqual(len(examples), count)
            for example in examples:
                self.assertIn(example["source"], sources)


@unittest.skipUnless(shutil.which("gcc"), "C concurrency examples require GCC")
class TutorialCConcurrencyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory(prefix="poznamkovnik-thread-support-") as temporary:
            root = Path(temporary)
            source = root / "probe.c"
            source.write_text(
                '#if (defined(__STDC_NO_THREADS__) && __STDC_NO_THREADS__) || '
                '(defined(__STDC_NO_ATOMICS__) && __STDC_NO_ATOMICS__)\n#error "Unsupported C concurrency"\n#endif\n'
                '#include <threads.h>\n#include <stdatomic.h>\n'
                'int main(void) { thrd_t t = thrd_current(); atomic_int n; atomic_init(&n, 0); '
                'return thrd_equal(t, t) ? atomic_load(&n) : 1; }\n', encoding="ascii",
            )
            build = subprocess.run(["gcc", "-std=c17", "-pthread", str(source), "-o", str(root / "probe")], capture_output=True, text=True, timeout=15)
            if build.returncode != 0:
                raise unittest.SkipTest("C threads/atomics are unavailable: " + build.stderr)

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-c-threads-")
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

    def audit_source(self, source: str, **failures: int) -> str:
        flags = {name: 0 for name in ("FAIL_CREATE", "FAIL_JOIN", "FAIL_INIT", "FAIL_LOCK", "FAIL_UNLOCK", "FAIL_WORKER")}
        flags.update(WITH_MUTEX=int(source == MUTEX_WORKERS), **failures)
        return "".join(f"#define {name} {value}\n" for name, value in flags.items()) + LIFECYCLE_AUDIT + source + r"""
#undef main
int main(void)
{
    int result = lesson_main();
    fprintf(stderr, "audit created=%u joined=%u initialized=%u destroyed=%u\n", created, joined, initialized, destroyed);
    return result;
}
"""

    def test_threaded_programs_repeat_with_expected_results(self) -> None:
        for source, output, _ in PROGRAMS:
            with self.subTest(output=output):
                build = self.compile_source(source, "-O2", "-DNDEBUG")
                self.assertEqual(build.returncode, 0, build.stderr)
                for attempt in range(10):
                    result = self.execute()
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, output, ""), attempt)

    def test_successful_lifecycles_join_every_worker_before_destroy(self) -> None:
        for source, output, count in PROGRAMS:
            result = self.run_source(self.audit_source(source))
            mutex = int(source == MUTEX_WORKERS)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (
                0, output, f"audit created={count} joined={count} initialized={mutex} destroyed={mutex}\n",
            ))

    def test_creation_failure_joins_only_started_workers_and_reports_no_success(self) -> None:
        for source, _, count in PROGRAMS:
            for fail_at in range(1, count + 1):
                with self.subTest(count=count, fail_at=fail_at, mutex=source == MUTEX_WORKERS):
                    result = self.run_source(self.audit_source(source, FAIL_CREATE=fail_at))
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    mutex = int(source == MUTEX_WORKERS)
                    self.assertEqual(result.stderr, "Cannot create thread.\n" +
                                     f"audit created={fail_at - 1} joined={fail_at - 1} initialized={mutex} destroyed={mutex}\n")

    def test_worker_failure_still_joins_every_started_worker(self) -> None:
        for source, _, count in PROGRAMS:
            result = self.run_source(self.audit_source(source, FAIL_WORKER=1))
            mutex = int(source == MUTEX_WORKERS)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "Worker failed.\n" * count +
                             f"audit created={count} joined={count} initialized={mutex} destroyed={mutex}\n")

    def test_failed_join_terminates_without_returning_to_borrowed_data_cleanup(self) -> None:
        for source, _, _ in PROGRAMS:
            result = self.run_source(self.audit_source(source, FAIL_JOIN=1))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((result.stdout, result.stderr), ("", "Cannot join thread.\nfatal-without-cleanup\n"))

    def test_mutex_initialization_lock_and_unlock_failures_have_distinct_cleanup(self) -> None:
        for failure, message in (
            ("FAIL_INIT", "Cannot initialize mutex.\naudit created=0 joined=0 initialized=0 destroyed=0\n"),
            ("FAIL_LOCK", "Worker failed.\nWorker failed.\naudit created=2 joined=2 initialized=1 destroyed=1\n"),
            ("FAIL_UNLOCK", "Cannot unlock mutex.\nfatal-without-cleanup\n"),
        ):
            with self.subTest(failure=failure):
                result = self.run_source(self.audit_source(MUTEX_WORKERS, **{failure: 1}))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                if failure == "FAIL_UNLOCK":
                    # Both workers can report the fatal condition before process termination.
                    self.assertIn(message, result.stderr)
                    self.assertNotIn("audit created", result.stderr)
                else:
                    self.assertEqual(result.stderr, message)

    def test_maximum_worker_checks_boundaries_and_preserves_output(self) -> None:
        result = self.run_source(MAXIMUM_JOB + r"""
#include <limits.h>
int main(void)
{
    const int values[] = {INT_MIN, -7, -1, INT_MAX};
    MaximumJob job = {values, 0, 77};
    if (find_maximum(NULL) != EXIT_FAILURE || find_maximum(&job) != EXIT_FAILURE || job.maximum != 77) { return 1; }
    job.count = 1;
    if (find_maximum(&job) != EXIT_SUCCESS || job.maximum != INT_MIN) { return 1; }
    job.count = 3;
    if (find_maximum(&job) != EXIT_SUCCESS || job.maximum != -1) { return 1; }
    job.count = 4;
    if (find_maximum(&job) != EXIT_SUCCESS || job.maximum != INT_MAX) { return 1; }
    job.values = NULL;
    if (find_maximum(&job) != EXIT_FAILURE || job.maximum != INT_MAX) { return 1; }
    return 0;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_mutex_rejects_overflow_without_partial_mutation_or_retaining_lock(self) -> None:
        result = self.run_source(MUTEX_TOTALS + r"""
int main(void)
{
    Totals state;
    if (mtx_init(&state.mutex, mtx_plain) != thrd_success) { return 1; }
    state.count = UINT_MAX;
    state.total = 77;
    if (record_total(NULL, 1) || record_total(&state, 0) || state.count != UINT_MAX || state.total != 77) { return 1; }
    state.count = 5;
    state.total = UINT_MAX;
    if (record_total(&state, 1) || state.count != 5 || state.total != UINT_MAX ||
        !record_total(&state, 0) || state.count != 6 || state.total != UINT_MAX) { return 1; }
    state.count = UINT_MAX - 1;
    state.total = UINT_MAX - 1;
    if (!record_total(&state, 1) || state.count != UINT_MAX || state.total != UINT_MAX || record_total(&state, 0)) { return 1; }
    mtx_destroy(&state.mutex);
    return 0;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_split_atomic_update_remains_wrong_even_with_seq_cst(self) -> None:
        for order in ("memory_order_relaxed", "memory_order_seq_cst"):
            result = self.run_source(SPLIT_ATOMIC_UPDATE.replace("memory_order_relaxed", order))
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "split=1 rmw=2\n", ""))
        empty = self.run_source(ATOMIC_WORKERS.replace("{&counter, 2000}", "{&counter, 0}"))
        self.assertEqual((empty.returncode, empty.stdout, empty.stderr), (0, "count=0\n", ""))

    def test_mailbox_contract_for_not_ready_nulls_and_extreme_payloads(self) -> None:
        result = self.run_source(ONCE_MAILBOX + r"""
#include <limits.h>
int main(void)
{
    const int values[] = {INT_MIN, -1, 0, INT_MAX};
    for (size_t i = 0; i < sizeof values / sizeof values[0]; ++i) {
        Mailbox box;
        atomic_init(&box.ready, false);
        box.value = 0;
        int output = 77;
        if (try_read(NULL, &output) || try_read(&box, NULL) || try_read(&box, &output) || output != 77) { return 1; }
        publish_once(&box, values[i]);
        if (!try_read(&box, &output) || output != values[i]) { return 1; }
        output = 77;
        if (!try_read(&box, &output) || output != values[i]) { return 1; }
    }
    return 0;
}
""")
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_mailbox_is_read_before_join_while_publisher_is_still_alive(self) -> None:
        result = self.run_source(THREAD_JOIN + ONCE_MAILBOX + r"""
typedef struct { Mailbox box; atomic_bool finish; } Exchange;
static int publish_and_wait(void *context)
{
    Exchange *exchange = context;
    publish_once(&exchange->box, 42);
    /* Test-only handshake, bounded by the subprocess timeout; no timing assumptions. */
    while (!atomic_load_explicit(&exchange->finish, memory_order_relaxed)) { thrd_yield(); }
    return EXIT_SUCCESS;
}
int main(void)
{
    for (int round = 0; round < 8; ++round) {
        Exchange exchange;
        atomic_init(&exchange.box.ready, false);
        exchange.box.value = 0;
        atomic_init(&exchange.finish, false);
        thrd_t thread;
        if (thrd_create(&thread, publish_and_wait, &exchange) != thrd_success) { return EXIT_FAILURE; }
        int value = 77;
        while (!try_read(&exchange.box, &value)) { thrd_yield(); }
        atomic_store_explicit(&exchange.finish, true, memory_order_relaxed);
        int worker_result = EXIT_FAILURE;
        join_or_exit(thread, &worker_result);
        if (worker_result != EXIT_SUCCESS || value != 42) { return EXIT_FAILURE; }
    }
    return EXIT_SUCCESS;
}
""")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_optional_support_is_reported_by_compile_time_diagnostic(self) -> None:
        for source, macro, message in (
            (THREAD_LIFETIME, "__STDC_NO_THREADS__", "This example requires C threads"),
            (SPLIT_ATOMIC_UPDATE, "__STDC_NO_ATOMICS__", "This example requires C atomics"),
        ):
            build = self.compile_source(source, f"-D{macro}=1")
            self.assertNotEqual(build.returncode, 0)
            self.assertIn(message, build.stderr)

    def test_all_practice_variants_accept_solutions_and_reject_safe_starters(self) -> None:
        for topic, placeholder, solution in (
            ("threads", THREAD_PLACEHOLDER, THREAD_SOLUTION),
            ("atomics", MAILBOX_PLACEHOLDER, MAILBOX_SOLUTION),
        ):
            for variant in range(4):
                exercise = tutorial_practice("c", topic, variant)
                self.assertIsNotNone(exercise)
                self.assertIn(placeholder, exercise["starterSource"])
                for replacement, expected in ((solution, "passed"), (placeholder, "output_mismatch")):
                    with self.subTest(topic=topic, variant=variant, expected=expected):
                        result = self.run_source(exercise["starterSource"].replace(placeholder, replacement))
                        self.assertEqual((result.returncode, result.stderr), (0, ""))
                        evaluation = evaluate_tutorial_practice(exercise, {
                            "compiled": True, "run": {"exitCode": result.returncode, "stdout": result.stdout},
                        }, "")
                        self.assertEqual(evaluation["status"], expected)

    def test_sequential_output_does_not_prove_acquire_but_order_audit_rejects_relaxed(self) -> None:
        for variant in range(4):
            exercise = tutorial_practice("c", "atomics", variant)
            source = exercise["starterSource"].replace(MAILBOX_PLACEHOLDER, MAILBOX_SOLUTION)
            valid = self.run_source(ORDER_AUDIT + source)
            self.assertEqual((valid.returncode, valid.stdout, valid.stderr), (0, exercise["expectedOutput"], ""))
            relaxed = source.replace("memory_order_acquire", "memory_order_relaxed")
            sequential = self.run_source(relaxed)
            self.assertEqual((sequential.returncode, sequential.stdout), (0, exercise["expectedOutput"]))
            self.assertEqual(self.run_source(ORDER_AUDIT + relaxed).returncode, 91)
            self.assertEqual(self.run_source(ORDER_AUDIT + source.replace("memory_order_release", "memory_order_relaxed")).returncode, 92)

    def test_worker_practice_rejects_zero_initial_maximum_for_every_variant(self) -> None:
        for variant in range(4):
            exercise = tutorial_practice("c", "threads", variant)
            mutant = THREAD_SOLUTION.replace("int maximum = job->values[0];", "int maximum = 0;")
            result = self.run_source(exercise["starterSource"].replace(THREAD_PLACEHOLDER, mutant))
            self.assertEqual((result.returncode, result.stderr), (0, ""))
            self.assertNotEqual(result.stdout, exercise["expectedOutput"])
