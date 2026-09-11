"""C17 programs shared by the lesson text and its runnable examples."""

FORMATTED_OUTPUT = r"""#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    const int count = 3;
    const size_t bytes = sizeof count;
    const double average = 7.0 / 2.0;
    const char label[] = "progress: 100%";

    if (printf("count: %d, bytes: %zu, average: %.2f\n",
               count, bytes, average) < 0 ||
        printf("%s\n", label) < 0 ||
        fflush(stdout) == EOF) {
        fputs("Output failed.\n", stderr);
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
"""

LINE_READER = r"""#include <stdio.h>

typedef enum {
    LINE_OK, LINE_END, LINE_TOO_LONG, LINE_INVALID, LINE_ERROR
} LineStatus;

/* stream and line are valid; capacity is at least 2.
   On success: a complete line without '\n'. Otherwise: an empty string. */
static LineStatus read_line(FILE *stream, char line[], size_t capacity)
{
    size_t used = 0;
    int seen = 0;
    int too_long = 0;
    int invalid = 0;
    int ch;
    line[0] = '\0';

    /* Consume the whole line even when it no longer fits. */
    while ((ch = fgetc(stream)) != EOF && ch != '\n') {
        seen = 1;
        if (ch == '\0') {
            invalid = 1;
        }
        if (used < capacity - 1) {
            line[used++] = (char) ch;
        } else {
            too_long = 1;
        }
    }
    if (ferror(stream)) {
        line[0] = '\0';
        return LINE_ERROR;
    }
    if (too_long || invalid) {
        line[0] = '\0';
        return too_long ? LINE_TOO_LONG : LINE_INVALID;
    }
    line[used] = '\0';
    return ch == EOF && !seen ? LINE_END : LINE_OK;
}
"""

READ_LINES = LINE_READER + r"""
#include <stdlib.h>

int main(void)
{
    char line[8];
    int result = EXIT_SUCCESS;
    for (;;) {
        LineStatus status = read_line(stdin, line, sizeof line);
        if (status == LINE_END) {
            break;
        }
        if (status == LINE_ERROR) {
            fputs("Read failed.\n", stderr);
            return EXIT_FAILURE;
        }
        if (status != LINE_OK) {
            fputs(status == LINE_TOO_LONG ? "Line too long.\n" :
                  "NUL byte rejected.\n", stderr);
            result = EXIT_FAILURE;
            continue;
        }
        if (printf("[%s]\n", line) < 0) {
            return EXIT_FAILURE;
        }
    }
    return fflush(stdout) == EOF ? EXIT_FAILURE : result;
}
"""

INT_PARSER = r"""#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdlib.h>

typedef enum {
    PARSE_OK, PARSE_ARGUMENT, PARSE_INVALID, PARSE_RANGE
} ParseStatus;

/* Decimal integer, optional sign and surrounding whitespace.
   A non-NULL text must be a terminated string; result must be writable.
   On failure, *result stays unchanged. Syntax is checked before range. */
static ParseStatus parse_int(const char text[], int *result)
{
    if (text == NULL || result == NULL) {
        return PARSE_ARGUMENT;
    }
    char *end = NULL;
    errno = 0;
    long value = strtol(text, &end, 10);
    int conversion_errno = errno;

    if (end == text) {
        return PARSE_INVALID;
    }
    while (isspace((unsigned char) *end)) {
        ++end;
    }
    if (*end != '\0') {
        return PARSE_INVALID;
    }
    if (conversion_errno == ERANGE || value < INT_MIN || value > INT_MAX) {
        return PARSE_RANGE;
    }
    *result = (int) value;
    return PARSE_OK;
}
"""

PARSE_NUMBER = LINE_READER + "\n" + INT_PARSER + r"""
#include <stdio.h>

int main(void)
{
    char line[64];
    int number = 0;
    LineStatus input = read_line(stdin, line, sizeof line);
    if (input != LINE_OK) {
        const char *message = input == LINE_END ? "No input.\n" :
            input == LINE_TOO_LONG ? "Line too long.\n" :
            input == LINE_INVALID ? "NUL byte rejected.\n" : "Read failed.\n";
        fputs(message, stderr);
        return EXIT_FAILURE;
    }
    ParseStatus status = parse_int(line, &number);
    if (status != PARSE_OK) {
        fputs(status == PARSE_RANGE ? "Number out of range.\n" :
              "Expected an integer.\n", stderr);
        return EXIT_FAILURE;
    }
    if (printf("value: %d\n", number) < 0 || fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
"""

POSITIVE_PARSER = r"""
static ParseStatus parse_positive(const char text[], int *result)
{
    if (result == NULL) {
        return PARSE_ARGUMENT;
    }
    int candidate = 0;
    ParseStatus status = parse_int(text, &candidate);
    if (status != PARSE_OK) {
        return status;
    }
    if (candidate <= 0) {
        return PARSE_INVALID;
    }
    *result = candidate;
    return PARSE_OK;
}
"""

PARSE_POSITIVE = INT_PARSER + POSITIVE_PARSER + r"""
#include <stdio.h>

static const char *status_name(ParseStatus status)
{
    switch (status) {
    case PARSE_OK: return "OK";
    case PARSE_ARGUMENT: return "ARGUMENT";
    case PARSE_INVALID: return "INVALID";
    case PARSE_RANGE: return "RANGE";
    }
    return "UNKNOWN";
}

int main(void)
{
    const char *cases[] = {"24", "", "   ", "12x", "0", "-2",
                          "999999999999999999999999999999999999"};
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        int value = 77;
        ParseStatus status = parse_positive(cases[i], &value);
        if (printf("\"%s\": %s, value=%d\n",
                   cases[i], status_name(status), value) < 0) {
            return EXIT_FAILURE;
        }
    }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

FILE_ROUNDTRIP = r"""#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    FILE *file = tmpfile();
    if (file == NULL) {
        fputs("Cannot open temporary file.\n", stderr);
        return EXIT_FAILURE;
    }
    int result = EXIT_FAILURE;
    char line[32];
    if (fprintf(file, "measurement=%d\n", 21) < 0 ||
        fflush(file) == EOF) {
        fputs("File write failed.\n", stderr);
        goto cleanup;
    }
    if (fseek(file, 0L, SEEK_SET) != 0) {
        fputs("Cannot seek to start.\n", stderr);
        goto cleanup;
    }
    if (fgets(line, sizeof line, file) == NULL) {
        fputs(ferror(file) ? "File read failed.\n" :
              "File unexpectedly empty.\n", stderr);
        goto cleanup;
    }
    result = EXIT_SUCCESS;

cleanup:
    /* fclose is called exactly once, including every failure path. */
    if (fclose(file) == EOF) {
        fputs("File close failed.\n", stderr);
        result = EXIT_FAILURE;
    }
    if (result == EXIT_SUCCESS &&
        (fputs(line, stdout) == EOF || fflush(stdout) == EOF)) {
        result = EXIT_FAILURE;
    }
    return result;
}
"""

BIT_MASKS = r"""#include <stdio.h>

int main(void)
{
    const unsigned int read = 1U << 0;
    const unsigned int write = 1U << 1;
    const unsigned int send = 1U << 2;
    unsigned int flags = read | send;

    printf("start: %u\n", flags);
    flags |= write;
    printf("set: %u\n", flags);
    flags &= ~send;
    printf("clear: %u\n", flags);
    flags ^= write;
    printf("toggle: %u\n", flags);

    const unsigned int required = read | write;
    printf("any: %d\n", (flags & required) != 0U);
    printf("all: %d\n", (flags & required) == required);
    return 0;
}
"""

CHECKED_ADD = r"""#include <limits.h>
#include <stdbool.h>
#include <stdio.h>

static bool checked_add(int left, int right, int *result)
{
    if ((right > 0 && left > INT_MAX - right) ||
        (right < 0 && left < INT_MIN - right)) {
        return false;
    }
    *result = left + right;
    return true;
}

int main(void)
{
    int result = 0;
    if (checked_add(12, 9, &result)) {
        printf("sum: %d\n", result);
    }
    if (!checked_add(INT_MAX, 1, &result)) {
        puts("overflow rejected");
    }
    return 0;
}
"""

GROW_BUFFER = r"""#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

/* On failure, both caller-owned values remain unchanged. */
static bool resize_values(int **values, size_t *capacity, size_t requested)
{
    if (requested == 0 || requested > SIZE_MAX / sizeof **values) {
        return false;
    }
    int *temporary = realloc(*values, requested * sizeof **values);
    if (temporary == NULL) {
        return false;
    }
    *values = temporary;
    *capacity = requested;
    return true;
}

int main(void)
{
    int *values = NULL;
    size_t capacity = 0;
    size_t count = 0;

    if (!resize_values(&values, &capacity, 3)) {
        fputs("allocation failed\n", stderr);
        return 1;
    }
    values[count++] = 10;
    values[count++] = 20;
    values[count++] = 30;

    if (!resize_values(&values, &capacity, 5)) {
        free(values);
        fputs("growth failed\n", stderr);
        return 1;
    }
    values[count++] = 40;
    values[count++] = 50;

    printf("count: %zu, capacity: %zu\n", count, capacity);
    for (size_t index = 0; index < count; ++index) {
        printf("%d%s", values[index], index + 1 == count ? "\n" : " ");
    }
    free(values);
    return 0;
}
"""

CONST_VIEWS = r"""#include <stdio.h>

int main(void)
{
    int values[] = {10, 20};
    const int *view = values;
    int *const fixed = values;
    const int *const fixed_view = values;

    *fixed = 15;
    printf("view: %d\n", *view);
    ++view;
    printf("next: %d\n", *view);
    printf("fixed view: %d\n", *fixed_view);
    return 0;
}
"""

RESTRICT_COPY = r"""#include <stddef.h>
#include <stdio.h>

/* The source and target ranges must not overlap. */
static void copy_values(int *restrict target,
                        const int *restrict source, size_t count)
{
    for (size_t index = 0; index < count; ++index) {
        target[index] = source[index];
    }
}

int main(void)
{
    const int source[] = {3, 1, 4};
    int target[3] = {0};
    copy_values(target, source, 3);
    printf("%d %d %d\n", target[0], target[1], target[2]);
    return 0;
}
"""

ATOMIC_COUNTER = r"""#include <stdatomic.h>
#include <stdio.h>

int main(void)
{
    atomic_uint completed;
    atomic_init(&completed, 0U);

    unsigned int previous = atomic_fetch_add(&completed, 1U);
    printf("previous: %u\n", previous);
    printf("current: %u\n", atomic_load(&completed));
    return 0;
}
"""

MACRO_PARENTHESES = r"""#include <stdio.h>

#define BAD_SQUARE(value) value * value
#define SQUARE(value) ((value) * (value))

int main(void)
{
    printf("without parentheses: %d\n", BAD_SQUARE(2 + 3));
    printf("with parentheses: %d\n", SQUARE(2 + 3));
    printf("whole expression: %d\n", 100 / SQUARE(2 + 3));
    return 0;
}
"""

MACRO_EXPANSION = """#define BAD_SQUARE(value) value * value
#define SQUARE(value) ((value) * (value))

int wrong = BAD_SQUARE(2 + 3);
int correct = SQUARE(2 + 3);
int quotient = 100 / SQUARE(2 + 3);
"""

MACRO_EXPANDED = """int wrong = 2 + 3 * 2 + 3;
int correct = ((2 + 3) * (2 + 3));
int quotient = 100 / ((2 + 3) * (2 + 3));
"""

SINGLE_EVALUATION = r"""#include <stdio.h>

static inline int square(int value)
{
    return value * value;
}

int main(void)
{
    int next = 3;
    int result = square(next++);
    printf("result: %d, next: %d\n", result, next);
    return 0;
}
"""

CONDITIONAL_BUILD = r"""#include <stdio.h>

#ifndef DEBUG_LOG
#define DEBUG_LOG 0
#endif

#if DEBUG_LOG != 0 && DEBUG_LOG != 1
#error DEBUG_LOG must be 0 or 1
#endif

int main(void)
{
#if DEBUG_LOG
    fputs("debug: computing average\n", stderr);
#endif
    printf("average: %.1f\n", (10.0 + 14.0) / 2.0);
    return 0;
}
"""

MEASUREMENTS_HEADER = """#ifndef POZNAMKOVNIK_MERANIA_H
#define POZNAMKOVNIK_MERANIA_H

#include <stddef.h>

typedef struct {
    double minimum;
    double maximum;
} Rozsah;

extern const unsigned int merania_verzia;
int merania_rozsah(const double values[], size_t count, Rozsah *result);

#endif
"""

MEASUREMENTS_SOURCE = """#include "merania.h"
#include <math.h>

const unsigned int merania_verzia = 1U;

static int meranie_je_platne(double value)
{
    return isfinite(value);
}

int merania_rozsah(const double values[], size_t count, Rozsah *result)
{
    if (values == NULL || result == NULL || count == 0) {
        return 0;
    }
    if (!meranie_je_platne(values[0])) {
        return 0;
    }
    Rozsah range = {values[0], values[0]};
    for (size_t index = 1; index < count; ++index) {
        if (!meranie_je_platne(values[index])) {
            return 0;
        }
        if (values[index] < range.minimum) {
            range.minimum = values[index];
        }
        if (values[index] > range.maximum) {
            range.maximum = values[index];
        }
    }
    *result = range;
    return 1;
}
"""

MEASUREMENTS_MAIN = r"""#include "merania.h"
#include <stdio.h>

int main(void)
{
    const double values[] = {12.5, 9.0, 14.0};
    Rozsah range = {0};
    const size_t count = sizeof values / sizeof values[0];

    if (!merania_rozsah(values, count, &range)) {
        fputs("invalid measurements\n", stderr);
        return 1;
    }
    printf("version: %u\n", merania_verzia);
    printf("minimum: %.1f, maximum: %.1f\n",
           range.minimum, range.maximum);
    return 0;
}
"""

MEASUREMENTS_FILES = {
    "merania.h": MEASUREMENTS_HEADER,
    "merania.c": MEASUREMENTS_SOURCE,
    "main.c": MEASUREMENTS_MAIN,
}

# The single-file playground uses the exact same implementation as the module.
MEASUREMENTS_SINGLE_FILE = (
    MEASUREMENTS_HEADER
    + "\n"
    + MEASUREMENTS_SOURCE.removeprefix('#include "merania.h"\n')
    + "\n"
    + MEASUREMENTS_MAIN.removeprefix('#include "merania.h"\n')
)

SAFE_INDEX = LINE_READER + "\n" + INT_PARSER + r"""
#include <stdint.h>

int main(void)
{
    const int values[] = {10, 20, 30, 40};
    const size_t count = sizeof values / sizeof values[0];
    char line[64];
    int requested = 0;
    if (read_line(stdin, line, sizeof line) != LINE_OK ||
        parse_int(line, &requested) != PARSE_OK) {
        fputs("Expected one complete integer line.\n", stderr);
        return EXIT_FAILURE;
    }
    if (requested < 0 || (uintmax_t) requested >= (uintmax_t) count) {
        fputs("Index out of bounds.\n", stderr);
        return EXIT_FAILURE;
    }
    if (printf("value: %d\n", values[(size_t) requested]) < 0 ||
        fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
"""

DIVIDE_INT = r"""#include <limits.h>
#include <stddef.h>

typedef enum { DIVIDE_OK, DIVIDE_ARGUMENT, DIVIDE_ZERO, DIVIDE_RANGE } DivideStatus;

/* A non-NULL result points to a writable int. Failure leaves it unchanged. */
static DivideStatus divide_int(int numerator, int denominator, int *result)
{
    if (result == NULL) {
        return DIVIDE_ARGUMENT;
    }
    if (denominator == 0) {
        return DIVIDE_ZERO;
    }
    if (denominator == -1 && numerator < -INT_MAX) {
        return DIVIDE_RANGE;
    }
    *result = numerator / denominator;
    return DIVIDE_OK;
}
"""

CHECKED_DIVISION = DIVIDE_INT + r"""
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    const int cases[][2] = {{7, 2}, {-7, 2}, {0, 2}, {7, 0}};
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        int value = 99;
        DivideStatus status = divide_int(cases[i][0], cases[i][1], &value);
        if (printf("%d / %d: status=%d value=%d\n",
                   cases[i][0], cases[i][1], (int) status, value) < 0) {
            return EXIT_FAILURE;
        }
    }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

ASSERT_MAXIMUM = r"""#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

#ifndef NDEBUG
static int maximum(int left, int right)
{
    return left > right ? left : right;
}
#endif

int main(void)
{
#ifdef NDEBUG
    fputs("Assertions disabled; tests not run.\n", stderr);
    return EXIT_FAILURE;
#else
    assert(maximum(2, 3) == 3);
    assert(maximum(5, 2) == 5);
    assert(maximum(5, 5) == 5);
    assert(maximum(-4, -1) == -1);
    if (puts("4 assertions passed.") == EOF || fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
#endif
}
"""

COUNT_POSITIVE = r"""#include <stddef.h>

/* values points to at least count readable ints; NULL is allowed for count=0. */
static size_t count_positive(const int values[], size_t count)
{
    size_t positive = 0;
    for (size_t i = 0; i < count; ++i) {
        if (values[i] > 0) {
            ++positive;
        }
    }
    return positive;
}
"""

BOUNDARY_TESTS = COUNT_POSITIVE + r"""
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    const struct {
        const char *name;
        int values[5];
        size_t count;
        size_t expected;
    } cases[] = {
        {"empty", {0}, 0, 0},
        {"zero", {0}, 1, 0},
        {"negative", {-3}, 1, 0},
        {"positive", {4}, 1, 1},
        {"first", {4, -1, 0}, 3, 1},
        {"last", {-2, 0, 3}, 3, 1},
        {"mixed", {-2, 0, 3, 0, 5}, 5, 2}
    };
    size_t failures = 0;
    const size_t total = sizeof cases / sizeof cases[0];
    for (size_t i = 0; i < total; ++i) {
        size_t actual = count_positive(cases[i].values, cases[i].count);
        if (actual != cases[i].expected) {
            ++failures;
            fprintf(stderr, "%s: expected=%zu actual=%zu\n",
                    cases[i].name, cases[i].expected, actual);
        }
    }
    if (printf("tests=%zu failures=%zu\n", total, failures) < 0 ||
        fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
"""

DEBUG_POSITIVE = r"""#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

/* Intentionally wrong predicate, but valid memory accesses. */
static size_t count_positive(const int values[], size_t count)
{
    size_t positive = 0;
    for (size_t i = 0; i < count; ++i) {
        if (values[i] >= 0) {
            ++positive;
        }
    }
    return positive;
}

int main(void)
{
    const int values[] = {-2, 0, 3};
    size_t actual = count_positive(values, sizeof values / sizeof values[0]);
    if (printf("expected=1 actual=%zu\n", actual) < 0 || fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return actual == 1 ? EXIT_SUCCESS : EXIT_FAILURE;
}
"""
