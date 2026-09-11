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

COMPARE_STRINGS = r"""#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void)
{
    const char text[8] = "C17";
    const char longer[] = "C17 notes";
    int order = strcmp(text, longer);
    if (printf("length=%zu capacity=%zu\n", strlen(text), sizeof text) < 0 ||
        printf("equal=%d prefix=%d full=%d order=%d\n",
               strcmp(text, "C17") == 0,
               strncmp(text, longer, strlen(text)) == 0,
               strcmp(text, longer) == 0, (order > 0) - (order < 0)) < 0 ||
        fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
"""

COPY_TEXT = r"""#include <string.h>

typedef enum { COPY_OK, COPY_ARGUMENT, COPY_UNTERMINATED, COPY_SPACE } CopyStatus;

/* Non-NULL pointers cover capacity writable and source_size readable bytes.
   Failure leaves the destination unchanged. Overlap is allowed. */
static CopyStatus copy_text(char *target, size_t capacity,
                            const char *source, size_t source_size)
{
    if (target == NULL || source == NULL) {
        return COPY_ARGUMENT;
    }
    if (source_size == 0 || memchr(source, '\0', source_size) == NULL) {
        return COPY_UNTERMINATED;
    }
    size_t length = strlen(source);
    if (length >= capacity) {
        return COPY_SPACE;
    }
    memmove(target, source, length + 1);
    return COPY_OK;
}
"""

COPY_TEXT_DEMO = COPY_TEXT + r"""
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    char target[5] = "old";
    const char raw[] = {'C', '1', '7'};
    CopyStatus status = copy_text(target, sizeof target, "C17", sizeof "C17");
    if (printf("short: status=%d text=%s\n", (int) status, target) < 0) {
        return EXIT_FAILURE;
    }
    status = copy_text(target, sizeof target, "longer", sizeof "longer");
    if (printf("long: status=%d text=%s\n", (int) status, target) < 0) {
        return EXIT_FAILURE;
    }
    status = copy_text(target, sizeof target, raw, sizeof raw);
    if (printf("raw: status=%d text=%s\n", (int) status, target) < 0 ||
        fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
"""

MOVE_TEXT = r"""#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void)
{
    char text[12] = "ABCDE";
    const char prefix[] = "> ";
    const size_t prefix_length = sizeof prefix - 1;
    size_t length = strlen(text);
    if (sizeof prefix > sizeof text || length > sizeof text - sizeof prefix) {
        fputs("Not enough space.\n", stderr);
        return EXIT_FAILURE;
    }
    memmove(text + prefix_length, text, length + 1);
    memcpy(text, prefix, prefix_length);
    if (puts(text) == EOF) {
        return EXIT_FAILURE;
    }
    memmove(text, text + prefix_length, strlen(text + prefix_length) + 1);
    if (puts(text) == EOF || fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
"""

STRTOL_REFERENCE = INT_PARSER + r"""
#include <stdio.h>

int main(void)
{
    char beyond[sizeof(int) * CHAR_BIT + 3];
    int written = snprintf(beyond, sizeof beyond, "%d0", INT_MAX);
    if (written < 0 || (size_t) written >= sizeof beyond) {
        return EXIT_FAILURE;
    }
    const struct { const char *name; const char *text; } cases[] = {
        {"integer", "42"}, {"zero", "0"}, {"spaces", "  -7  "},
        {"suffix", "42x"}, {"empty", ""}, {"range", beyond}
    };
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        int value = 77;
        ParseStatus status = parse_int(cases[i].text, &value);
        if (printf("%s: status=%d value=%d\n", cases[i].name, (int) status, value) < 0) {
            return EXIT_FAILURE;
        }
    }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

COMPARE_INTS = r"""#include <stdlib.h>

/* Arguments point to readable ints. Only the sign of the result matters. */
static int compare_ints(const void *left, const void *right)
{
    int a = *(const int *) left;
    int b = *(const int *) right;
    return (a > b) - (a < b);
}
"""

SORT_SEARCH = COMPARE_INTS + r"""
#include <stdio.h>

int main(void)
{
    int values[] = {7, -3, 7, 0, 2};
    const size_t count = sizeof values / sizeof values[0];
    qsort(values, count, sizeof values[0], compare_ints);
    for (size_t i = 0; i < count; ++i) {
        if (printf("%d%s", values[i], i + 1 == count ? "\n" : " ") < 0) {
            return EXIT_FAILURE;
        }
    }
    int key = 7;
    const int *found = bsearch(&key, values, count, sizeof values[0], compare_ints);
    if (found == NULL) {
        fputs("Expected key not found.\n", stderr);
        return EXIT_FAILURE;
    }
    key = 9;
    const int *missing = bsearch(&key, values, count, sizeof values[0], compare_ints);
    if (printf("found=%d missing=%d\n", *found, missing == NULL) < 0 ||
        fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
"""

FORMAT_RESULT = r"""#include <stddef.h>
#include <stdint.h>

typedef enum { FORMAT_OK, FORMAT_ERROR, FORMAT_TRUNCATED } FormatStatus;

static FormatStatus format_result(int required, size_t capacity)
{
    if (required < 0) {
        return FORMAT_ERROR;
    }
    if ((uintmax_t) required >= (uintmax_t) capacity) {
        return FORMAT_TRUNCATED;
    }
    return FORMAT_OK;
}
"""

SNPRINTF_MESSAGE = FORMAT_RESULT + r"""
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    const size_t capacities[] = {9, 8, 1, 0};
    for (size_t i = 0; i < sizeof capacities / sizeof capacities[0]; ++i) {
        char text[9] = "old";
        size_t capacity = capacities[i];
        int required = snprintf(capacity == 0 ? NULL : text, capacity, "value=%d", 42);
        FormatStatus status = format_result(required, capacity);
        if (status == FORMAT_ERROR) {
            fputs("Formatting failed.\n", stderr);
            return EXIT_FAILURE;
        }
        if (printf("capacity=%zu required=%d status=%d text=[%s]\n",
                   capacity, required, (int) status, text) < 0) {
            return EXIT_FAILURE;
        }
    }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

BINARY_ROUNDTRIP = r"""#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void)
{
    const unsigned char original[] = {0x41, 0x00, 0xFF, 0x0A};
    unsigned char restored[sizeof original] = {0};
    FILE *file = tmpfile();
    if (file == NULL) {
        fputs("Cannot open temporary file.\n", stderr);
        return EXIT_FAILURE;
    }
    int result = EXIT_FAILURE;
    if (fwrite(original, 1, sizeof original, file) != sizeof original ||
        fflush(file) == EOF) {
        fputs("Write failed.\n", stderr);
        goto cleanup;
    }
    if (fseek(file, 0L, SEEK_SET) != 0) {
        fputs("Seek failed.\n", stderr);
        goto cleanup;
    }
    if (fread(restored, 1, sizeof restored, file) != sizeof restored) {
        fputs(ferror(file) ? "Read failed.\n" : "Unexpected end.\n", stderr);
        goto cleanup;
    }
    if (memcmp(original, restored, sizeof original) != 0) {
        fputs("Data differs.\n", stderr);
        goto cleanup;
    }
    result = EXIT_SUCCESS;

cleanup:
    if (fclose(file) == EOF) {
        fputs("Close failed.\n", stderr);
        result = EXIT_FAILURE;
    }
    if (result != EXIT_SUCCESS) {
        return result;
    }
    for (size_t i = 0; i < sizeof restored; ++i) {
        if (printf("%02X%s", (unsigned int) restored[i],
                   i + 1 == sizeof restored ? "\n" : " ") < 0) {
            return EXIT_FAILURE;
        }
    }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

CLASSIFY_BYTES = r"""#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    int ch;
    while ((ch = fgetc(stdin)) != EOF) {
        unsigned char byte = (unsigned char) ch;
        if (printf("%02X digit=%d space=%d upper=%02X\n", (unsigned int) byte,
                   isdigit(byte) != 0, isspace(byte) != 0,
                   (unsigned int) toupper(byte)) < 0) {
            return EXIT_FAILURE;
        }
    }
    if (ferror(stdin)) {
        fputs("Read failed.\n", stderr);
        return EXIT_FAILURE;
    }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

INTEGER_LIMITS = r"""#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    const int_least32_t measurement = INT32_C(123456);
    const uint_least64_t count = UINT64_C(9000000000);
    if (printf("CHAR_BIT=%d sizeof(int)=%zu\n", CHAR_BIT, sizeof(int)) < 0 ||
        printf("INT_MIN=%d INT_MAX=%d\n", INT_MIN, INT_MAX) < 0 ||
        printf("CHAR_MIN=%jd CHAR_MAX=%ju\n", (intmax_t) CHAR_MIN, (uintmax_t) CHAR_MAX) < 0 ||
        printf("SIZE_MAX=%zu\n", (size_t) SIZE_MAX) < 0 ||
        printf("measurement=%" PRIdLEAST32 " count=%" PRIuLEAST64 "\n", measurement, count) < 0 ||
        fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
"""

INTEGER_CONVERSIONS = r"""#include <limits.h>
#include <stddef.h>
#include <stdint.h>

typedef enum { CONVERT_OK, CONVERT_ARGUMENT, CONVERT_RANGE } ConvertStatus;

/* Non-NULL output points to a writable object; failure preserves its value. */
static ConvertStatus int_to_size(int value, size_t *result)
{
    if (result == NULL) {
        return CONVERT_ARGUMENT;
    }
    if (value < 0 || (uintmax_t) value > (uintmax_t) SIZE_MAX) {
        return CONVERT_RANGE;
    }
    *result = (size_t) value;
    return CONVERT_OK;
}

static ConvertStatus size_to_int(size_t value, int *result)
{
    if (result == NULL) {
        return CONVERT_ARGUMENT;
    }
    if ((uintmax_t) value > (uintmax_t) INT_MAX) {
        return CONVERT_RANGE;
    }
    *result = (int) value;
    return CONVERT_OK;
}
"""

CONVERT_SIZES = INTEGER_CONVERSIONS + r"""
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    const int counts[] = {-1, 0, 12};
    for (size_t i = 0; i < sizeof counts / sizeof counts[0]; ++i) {
        size_t value = 77;
        ConvertStatus status = int_to_size(counts[i], &value);
        if (printf("to-size %d: status=%d value=%zu\n", counts[i], (int) status, value) < 0) {
            return EXIT_FAILURE;
        }
    }
    const size_t sizes[] = {0, 12, SIZE_MAX};
    for (size_t i = 0; i < sizeof sizes / sizeof sizes[0]; ++i) {
        int value = 77;
        ConvertStatus status = size_to_int(sizes[i], &value);
        if (printf("to-int case=%zu: status=%d value=%d\n", i, (int) status, value) < 0) {
            return EXIT_FAILURE;
        }
    }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

CALLBACK_APPLY = r"""#include <stddef.h>

typedef int (*BinaryOperation)(int left, int right);

/* The result points to a writable int; operation must accept both values. */
static int apply(int left, int right, BinaryOperation operation, int *result)
{
    if (operation == NULL || result == NULL) {
        return 0;
    }
    *result = operation(left, right);
    return 1;
}

static int maximum(int left, int right)
{
    return left > right ? left : right;
}
"""

CALLBACK_OPERATION = CALLBACK_APPLY + r"""
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    int result = 77;
    int ok = apply(4, 9, maximum, &result);
    if (printf("ok=%d value=%d\n", ok, result) < 0) { return EXIT_FAILURE; }
    result = 77;
    ok = apply(4, 9, NULL, &result);
    if (printf("missing=%d value=%d\n", ok, result) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

WALK_VALUES = r"""#include <stddef.h>

typedef enum { VISIT_CONTINUE, VISIT_STOP, VISIT_ERROR } VisitAction;
typedef VisitAction (*Visitor)(int value, void *context);
typedef enum { WALK_DONE, WALK_STOPPED, WALK_ARGUMENT, WALK_CALLBACK_ERROR } WalkStatus;

/* Synchronous, borrowed inputs: no callback or pointer is retained. */
static WalkStatus walk_values(const int *values, size_t count, Visitor visit, void *context)
{
    if (visit == NULL || (count != 0 && values == NULL)) {
        return WALK_ARGUMENT;
    }
    for (size_t i = 0; i < count; ++i) {
        VisitAction action = visit(values[i], context);
        if (action == VISIT_STOP) { return WALK_STOPPED; }
        if (action != VISIT_CONTINUE) { return WALK_CALLBACK_ERROR; }
    }
    return WALK_DONE;
}
"""

LIMIT_VISITOR = WALK_VALUES + r"""
#include <stdint.h>

typedef struct { int limit; size_t accepted; int last; } LimitState;

/* Non-NULL context points to a live, writable LimitState. */
static VisitAction accept_below(int value, void *context)
{
    if (context == NULL) { return VISIT_ERROR; }
    LimitState *state = context;
    if (value >= state->limit) { return VISIT_STOP; }
    if (state->accepted == SIZE_MAX) { return VISIT_ERROR; }
    ++state->accepted;
    state->last = value;
    return VISIT_CONTINUE;
}
"""

CALLBACK_CONTEXT = LIMIT_VISITOR + r"""
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    const int values[] = {3, 5, 9, 1};
    const size_t count = sizeof values / sizeof values[0];
    LimitState first = {8, 0, 77};
    LimitState second = {10, 0, 77};
    WalkStatus stopped = walk_values(values, count, accept_below, &first);
    WalkStatus done = walk_values(values, count, accept_below, &second);
    WalkStatus missing = walk_values(values, count, accept_below, NULL);
    WalkStatus empty = walk_values(NULL, 0, accept_below, NULL);
    if (printf("first: status=%d accepted=%zu last=%d\n", (int) stopped, first.accepted, first.last) < 0 ||
        printf("second: status=%d accepted=%zu last=%d\n", (int) done, second.accepted, second.last) < 0 ||
        printf("missing=%d empty=%d\n", (int) missing, (int) empty) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

VARIADIC_RANGE = r"""#include <stdarg.h>
#include <stddef.h>

typedef struct { int minimum; int maximum; } IntRange;

/* count >= 1, followed by exactly count remaining arguments of promoted type int. */
static int scan_extreme(unsigned int count, va_list args, int want_maximum)
{
    int best = va_arg(args, int);
    for (unsigned int i = 1; i < count; ++i) {
        int value = va_arg(args, int);
        if (want_maximum ? value > best : value < best) { best = value; }
    }
    return best;
}

/* A nonempty call supplies exactly count ints; failure preserves *result. */
static int variadic_range(IntRange *result, unsigned int count, ...)
{
    if (result == NULL || count == 0) { return 0; }
    va_list args;
    va_list copy;
    va_start(args, count);
    va_copy(copy, args);
    int minimum = scan_extreme(count, args, 0);
    int maximum = scan_extreme(count, copy, 1);
    va_end(copy);
    va_end(args);
    *result = (IntRange) {minimum, maximum};
    return 1;
}
"""

VARIADIC_PASSES = VARIADIC_RANGE + r"""
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    short low = -3;
    IntRange range = {77, 88};
    int ok = variadic_range(&range, 4U, 7, low, 0, 9);
    if (printf("ok=%d min=%d max=%d\n", ok, range.minimum, range.maximum) < 0) { return EXIT_FAILURE; }
    range = (IntRange) {77, 88};
    ok = variadic_range(&range, 0U);
    if (printf("empty=%d min=%d max=%d\n", ok, range.minimum, range.maximum) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

EXACT_WIDTH_ID = r"""#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
#ifdef UINT32_MAX
    uint32_t identifier = UINT32_C(4000000000);
    if (printf("exact=%" PRIu32 "\n", identifier) < 0) { return EXIT_FAILURE; }
#else
    if (puts("exact=unavailable") == EOF) { return EXIT_FAILURE; }
#endif
    uint_least32_t portable = UINT32_C(4000000000);
    if (printf("least=%" PRIuLEAST32 "\n", portable) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

OCTET_CODEC = r"""#include <limits.h>
#include <stddef.h>
#include <stdint.h>

_Static_assert(CHAR_BIT == 8, "This wire format requires 8-bit bytes");
typedef enum { CODEC_OK, CODEC_ARGUMENT, CODEC_SIZE, CODEC_RANGE } CodecStatus;

/* Valid objects cover their declared capacities; failure never writes output. */
static CodecStatus encode_u16be(unsigned char *target, size_t capacity, uint_least32_t value)
{
    if (target == NULL) { return CODEC_ARGUMENT; }
    if (capacity < 2) { return CODEC_SIZE; }
    if (value > UINT32_C(65535)) { return CODEC_RANGE; }
    target[0] = (unsigned char) (value >> 8);
    target[1] = (unsigned char) (value & UINT32_C(255));
    return CODEC_OK;
}

static CodecStatus decode_u16be(const unsigned char *source, size_t length, uint_least32_t *result)
{
    if (source == NULL || result == NULL) { return CODEC_ARGUMENT; }
    if (length < 2) { return CODEC_SIZE; }
    *result = ((uint_least32_t) source[0] << 8) | (uint_least32_t) source[1];
    return CODEC_OK;
}
"""

WIRE_ROUNDTRIP = OCTET_CODEC + r"""
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    unsigned char bytes[2] = {0xAA, 0xBB};
    uint_least32_t value = 77;
    if (encode_u16be(bytes, sizeof bytes, UINT32_C(43981)) != CODEC_OK ||
        decode_u16be(bytes, sizeof bytes, &value) != CODEC_OK) { return EXIT_FAILURE; }
    if (printf("%02X %02X value=%" PRIuLEAST32 "\n", (unsigned int) bytes[0],
               (unsigned int) bytes[1], value) < 0) { return EXIT_FAILURE; }
    bytes[0] = 0xAA;
    bytes[1] = 0xBB;
    CodecStatus short_target = encode_u16be(bytes, 1, 1);
    CodecStatus range = encode_u16be(bytes, sizeof bytes, UINT32_C(65536));
    value = 77;
    CodecStatus short_source = decode_u16be(bytes, 1, &value);
    if (printf("short=%d range=%d bytes=%02X %02X\n", (int) short_target, (int) range,
               (unsigned int) bytes[0], (unsigned int) bytes[1]) < 0 ||
        printf("read=%d value=%" PRIuLEAST32 "\n", (int) short_source, value) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

SEQUENCED_ARGUMENTS = r"""#include <stdio.h>
#include <stdlib.h>

static int sequence = 0;

static int next_number(void)
{
    return ++sequence;
}

int main(void)
{
    int first = next_number();
    int second = next_number();
    if (printf("ordered=%d,%d\n", first, second) < 0) { return EXIT_FAILURE; }
    sequence = 0;
    if (printf("unspecified=%d,%d\n", next_number(), next_number()) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

THREAD_JOIN = r"""#if defined(__STDC_NO_THREADS__) && __STDC_NO_THREADS__
#error "This example requires C threads"
#endif
#include <threads.h>
#include <stdio.h>
#include <stdlib.h>

static void join_or_exit(thrd_t thread, int *result)
{
    if (thrd_join(thread, result) != thrd_success) {
        /* Without a successful join, borrowed objects may still be in use. */
        fputs("Cannot join thread.\n", stderr);
        (void) fflush(stderr);
        _Exit(EXIT_FAILURE);
    }
}
"""

MAXIMUM_JOB = r"""#include <stddef.h>
#include <stdlib.h>

typedef struct { const int *values; size_t count; int maximum; } MaximumJob;

/* The owner keeps the job and input alive until the worker has been joined. */
static int find_maximum(void *context)
{
    if (context == NULL) { return EXIT_FAILURE; }
    MaximumJob *job = context;
    if (job->values == NULL || job->count == 0) { return EXIT_FAILURE; }
    int maximum = job->values[0];
    for (size_t i = 1; i < job->count; ++i) {
        if (job->values[i] > maximum) { maximum = job->values[i]; }
    }
    job->maximum = maximum;
    return EXIT_SUCCESS;
}
"""

THREAD_LIFETIME = THREAD_JOIN + MAXIMUM_JOB + r"""
int main(void)
{
    const int values[] = {3, -2, 9, 1};
    MaximumJob job = {values, sizeof values / sizeof values[0], 77};
    thrd_t thread;
    if (thrd_create(&thread, find_maximum, &job) != thrd_success) {
        fputs("Cannot create thread.\n", stderr);
        return EXIT_FAILURE;
    }
    int worker_result = EXIT_FAILURE;
    join_or_exit(thread, &worker_result);
    if (worker_result != EXIT_SUCCESS) {
        fputs("Worker failed.\n", stderr);
        return EXIT_FAILURE;
    }
    if (printf("maximum=%d\n", job.maximum) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

MUTEX_TOTALS = r"""#include <limits.h>
#include <threads.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct { mtx_t mutex; unsigned int count; unsigned int total; } Totals;

/* A non-NULL totals has an initialized mutex; all concurrent access uses it. */
static int record_total(Totals *totals, unsigned int value)
{
    if (totals == NULL || mtx_lock(&totals->mutex) != thrd_success) { return 0; }
    int ok = totals->count < UINT_MAX && value <= UINT_MAX - totals->total;
    if (ok) {
        ++totals->count;
        totals->total += value;
    }
    if (mtx_unlock(&totals->mutex) != thrd_success) {
        /* Lock ownership is uncertain; do not leave other workers waiting. */
        fputs("Cannot unlock mutex.\n", stderr);
        (void) fflush(stderr);
        _Exit(EXIT_FAILURE);
    }
    return ok;
}
"""

MUTEX_WORKERS = THREAD_JOIN + MUTEX_TOTALS + r"""
typedef struct { Totals *totals; unsigned int value; unsigned int iterations; } RecordJob;

static int record_worker(void *context)
{
    RecordJob *job = context;
    for (unsigned int i = 0; i < job->iterations; ++i) {
        if (!record_total(job->totals, job->value)) { return EXIT_FAILURE; }
    }
    return EXIT_SUCCESS;
}

int main(void)
{
    Totals totals;
    totals.count = 0;
    totals.total = 0;
    if (mtx_init(&totals.mutex, mtx_plain) != thrd_success) {
        fputs("Cannot initialize mutex.\n", stderr);
        return EXIT_FAILURE;
    }
    RecordJob jobs[] = {{&totals, 3, 100}, {&totals, 7, 100}};
    thrd_t threads[2];
    size_t started = 0;
    int result = EXIT_SUCCESS;
    for (size_t i = 0; i < 2; ++i) {
        if (thrd_create(&threads[i], record_worker, &jobs[i]) != thrd_success) {
            fputs("Cannot create thread.\n", stderr);
            result = EXIT_FAILURE;
            break;
        }
        ++started;
    }
    for (size_t i = 0; i < started; ++i) {
        int worker_result = EXIT_FAILURE;
        join_or_exit(threads[i], &worker_result);
        if (worker_result != EXIT_SUCCESS) {
            fputs("Worker failed.\n", stderr);
            result = EXIT_FAILURE;
        }
    }
    mtx_destroy(&totals.mutex);
    if (result != EXIT_SUCCESS) { return result; }
    if (printf("count=%u total=%u\n", totals.count, totals.total) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

ATOMIC_SUPPORT = r"""#if defined(__STDC_NO_ATOMICS__) && __STDC_NO_ATOMICS__
#error "This example requires C atomics"
#endif
#include <stdatomic.h>
"""

ATOMIC_WORKERS = THREAD_JOIN + ATOMIC_SUPPORT + r"""
typedef struct { atomic_uint *counter; unsigned int iterations; } CounterJob;

static int count_worker(void *context)
{
    CounterJob *job = context;
    for (unsigned int i = 0; i < job->iterations; ++i) {
        atomic_fetch_add_explicit(job->counter, 1U, memory_order_relaxed);
    }
    return EXIT_SUCCESS;
}

int main(void)
{
    atomic_uint counter;
    atomic_init(&counter, 0U);
    CounterJob job = {&counter, 2000};
    thrd_t threads[2];
    size_t started = 0;
    int result = EXIT_SUCCESS;
    for (size_t i = 0; i < 2; ++i) {
        if (thrd_create(&threads[i], count_worker, &job) != thrd_success) {
            fputs("Cannot create thread.\n", stderr);
            result = EXIT_FAILURE;
            break;
        }
        ++started;
    }
    for (size_t i = 0; i < started; ++i) {
        int worker_result = EXIT_FAILURE;
        join_or_exit(threads[i], &worker_result);
        if (worker_result != EXIT_SUCCESS) {
            fputs("Worker failed.\n", stderr);
            result = EXIT_FAILURE;
        }
    }
    if (result != EXIT_SUCCESS) { return result; }
    unsigned int value = atomic_load_explicit(&counter, memory_order_relaxed);
    if (printf("count=%u\n", value) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

SPLIT_ATOMIC_UPDATE = ATOMIC_SUPPORT + r"""
#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    atomic_uint counter;
    atomic_init(&counter, 0U);
    /* One-thread model of two readers followed by two writers, not a data race. */
    unsigned int first = atomic_load_explicit(&counter, memory_order_relaxed);
    unsigned int second = atomic_load_explicit(&counter, memory_order_relaxed);
    atomic_store_explicit(&counter, first + 1U, memory_order_relaxed);
    atomic_store_explicit(&counter, second + 1U, memory_order_relaxed);
    unsigned int split = atomic_load_explicit(&counter, memory_order_relaxed);
    atomic_store_explicit(&counter, 0U, memory_order_relaxed);
    atomic_fetch_add_explicit(&counter, 1U, memory_order_relaxed);
    atomic_fetch_add_explicit(&counter, 1U, memory_order_relaxed);
    unsigned int combined = atomic_load_explicit(&counter, memory_order_relaxed);
    if (printf("split=%u rmw=%u\n", split, combined) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

ONCE_MAILBOX = ATOMIC_SUPPORT + r"""
#include <stdbool.h>
#include <stddef.h>

typedef struct { atomic_bool ready; int value; } Mailbox;

/* Exactly one publication per initialized mailbox; value stays immutable after it. */
static void publish_once(Mailbox *box, int value)
{
    box->value = value;
    atomic_store_explicit(&box->ready, true, memory_order_release);
}

/* A live box and a separate writable result; unavailable input preserves *result. */
static int try_read(Mailbox *box, int *result)
{
    if (box == NULL || result == NULL) { return 0; }
    if (!atomic_load_explicit(&box->ready, memory_order_acquire)) { return 0; }
    *result = box->value;
    return 1;
}
"""

MAILBOX_PUBLICATION = THREAD_JOIN + ONCE_MAILBOX + r"""
static int publisher(void *context)
{
    publish_once(context, 42);
    return EXIT_SUCCESS;
}

int main(void)
{
    Mailbox box;
    atomic_init(&box.ready, false);
    box.value = 0;
    int value = 77;
    int before = try_read(&box, &value);
    int original = value;
    thrd_t thread;
    if (thrd_create(&thread, publisher, &box) != thrd_success) {
        fputs("Cannot create thread.\n", stderr);
        return EXIT_FAILURE;
    }
    int received = try_read(&box, &value);
    int worker_result = EXIT_FAILURE;
    join_or_exit(thread, &worker_result);
    if (worker_result != EXIT_SUCCESS) {
        fputs("Worker failed.\n", stderr);
        return EXIT_FAILURE;
    }
    if (!received) { received = try_read(&box, &value); }
    if (!received) { return EXIT_FAILURE; }
    if (printf("before=%d value=%d\nreceived=%d value=%d\n", before, original, received, value) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

SYNC_CHECK = r"""#if defined(__STDC_NO_THREADS__) && __STDC_NO_THREADS__
#error "This example requires C threads"
#endif
#include <threads.h>
#include <stdio.h>
#include <stdlib.h>

/* These standalone demos cannot recover safely from a failed synchronization. */
static void check_sync(int status, const char *message)
{
    if (status != thrd_success) {
        fputs(message, stderr);
        (void) fflush(stderr);
        _Exit(EXIT_FAILURE);
    }
}
"""

GATE_SUPPORT = SYNC_CHECK + r"""
#include <stdbool.h>
typedef struct { mtx_t mutex; cnd_t changed; bool ready; int value; } Gate;

static int gate_init(Gate *gate)
{
    gate->ready = false;
    gate->value = 0;
    if (mtx_init(&gate->mutex, mtx_plain) != thrd_success) { return 0; }
    if (cnd_init(&gate->changed) != thrd_success) {
        mtx_destroy(&gate->mutex);
        return 0;
    }
    return 1;
}

static void gate_destroy(Gate *gate)
{
    cnd_destroy(&gate->changed);
    mtx_destroy(&gate->mutex);
}

/* One publication, while gate is alive; ready is never reset. */
static void gate_open(Gate *gate, int value)
{
    check_sync(mtx_lock(&gate->mutex), "Cannot lock gate.\n");
    gate->value = value;
    gate->ready = true;
    check_sync(cnd_broadcast(&gate->changed), "Cannot broadcast gate.\n");
    check_sync(mtx_unlock(&gate->mutex), "Cannot unlock gate.\n");
}
"""

GATE_WAIT = r"""
static int await_gate(Gate *gate)
{
    check_sync(mtx_lock(&gate->mutex), "Cannot lock gate.\n");
    while (!gate->ready) {
        check_sync(cnd_wait(&gate->changed, &gate->mutex), "Cannot wait on gate.\n");
    }
    int value = gate->value;
    check_sync(mtx_unlock(&gate->mutex), "Cannot unlock gate.\n");
    return value;
}
"""

GATE_MAIN = r"""
typedef struct { Gate *gate; int result; } GateJob;
static int gate_worker(void *context)
{
    GateJob *job = context;
    job->result = await_gate(job->gate);
    return EXIT_SUCCESS;
}

int main(void)
{
    Gate gate;
    if (!gate_init(&gate)) { return EXIT_FAILURE; }
    GateJob job = {&gate, 77};
    thrd_t thread;
    if (thrd_create(&thread, gate_worker, &job) != thrd_success) {
        gate_destroy(&gate);
        return EXIT_FAILURE;
    }
    gate_open(&gate, 42);
    int result = EXIT_FAILURE;
    join_or_exit(thread, &result);
    gate_destroy(&gate);
    if (result != EXIT_SUCCESS) { return EXIT_FAILURE; }
    if (printf("received=%d\n", job.result) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

CONDITION_GATE = THREAD_JOIN + GATE_SUPPORT + GATE_WAIT + GATE_MAIN

QUEUE_SUPPORT = SYNC_CHECK + r"""
#include <stdbool.h>
#include <stddef.h>

enum { QUEUE_CAPACITY = 3 };
typedef struct {
    mtx_t mutex;
    cnd_t not_empty, not_full;
    int items[QUEUE_CAPACITY];
    size_t head, count;
    bool closed;
} Queue;

static int queue_init(Queue *queue)
{
    queue->head = 0;
    queue->count = 0;
    queue->closed = false;
    if (mtx_init(&queue->mutex, mtx_plain) != thrd_success) { return 0; }
    if (cnd_init(&queue->not_empty) != thrd_success) {
        mtx_destroy(&queue->mutex);
        return 0;
    }
    if (cnd_init(&queue->not_full) != thrd_success) {
        cnd_destroy(&queue->not_empty);
        mtx_destroy(&queue->mutex);
        return 0;
    }
    return 1;
}

/* Only after every user has finished, including every successful thread join. */
static void queue_destroy(Queue *queue)
{
    cnd_destroy(&queue->not_full);
    cnd_destroy(&queue->not_empty);
    mtx_destroy(&queue->mutex);
}
"""

QUEUE_CLOSE = r"""
static void queue_close(Queue *queue)
{
    check_sync(mtx_lock(&queue->mutex), "Cannot lock queue.\n");
    queue->closed = true;
    check_sync(cnd_broadcast(&queue->not_empty), "Cannot wake consumers.\n");
    check_sync(cnd_broadcast(&queue->not_full), "Cannot wake producers.\n");
    check_sync(mtx_unlock(&queue->mutex), "Cannot unlock queue.\n");
}
"""

QUEUE_PUSH = r"""
/* Non-NULL, initialized, live queue. Returns 0 only when closed. */
static int queue_push(Queue *queue, int value)
{
    check_sync(mtx_lock(&queue->mutex), "Cannot lock queue.\n");
    while (queue->count == QUEUE_CAPACITY && !queue->closed) {
        check_sync(cnd_wait(&queue->not_full, &queue->mutex), "Cannot wait for space.\n");
    }
    if (queue->closed) {
        check_sync(mtx_unlock(&queue->mutex), "Cannot unlock queue.\n");
        return 0;
    }
    size_t tail = (queue->head + queue->count) % QUEUE_CAPACITY;
    queue->items[tail] = value;
    ++queue->count;
    check_sync(cnd_signal(&queue->not_empty), "Cannot signal item.\n");
    check_sync(mtx_unlock(&queue->mutex), "Cannot unlock queue.\n");
    return 1;
}
"""

QUEUE_POP = r"""
/* Separate writable result. Closed and empty returns 0 without changing it. */
static int queue_pop(Queue *queue, int *result)
{
    check_sync(mtx_lock(&queue->mutex), "Cannot lock queue.\n");
    while (queue->count == 0 && !queue->closed) {
        check_sync(cnd_wait(&queue->not_empty, &queue->mutex), "Cannot wait for item.\n");
    }
    if (queue->count == 0) {
        check_sync(mtx_unlock(&queue->mutex), "Cannot unlock queue.\n");
        return 0;
    }
    *result = queue->items[queue->head];
    queue->head = (queue->head + 1) % QUEUE_CAPACITY;
    --queue->count;
    check_sync(cnd_signal(&queue->not_full), "Cannot signal space.\n");
    check_sync(mtx_unlock(&queue->mutex), "Cannot unlock queue.\n");
    return 1;
}
"""

QUEUE_OPERATIONS = QUEUE_PUSH + QUEUE_POP
BOUNDED_QUEUE = QUEUE_SUPPORT + QUEUE_CLOSE + QUEUE_OPERATIONS

QUEUE_DRAIN_MAIN = r"""
int main(void)
{
    Queue queue;
    if (!queue_init(&queue)) { return EXIT_FAILURE; }
    (void) queue_push(&queue, 10);
    (void) queue_push(&queue, -2);
    queue_close(&queue);
    queue_close(&queue);
    int rejected = !queue_push(&queue, 99);
    int values[] = {77, 77, 77};
    int first = queue_pop(&queue, &values[0]);
    int second = queue_pop(&queue, &values[1]);
    int end = queue_pop(&queue, &values[2]);
    queue_destroy(&queue);
    if (printf("rejected=%d first=%d:%d second=%d:%d end=%d:%d\n",
               rejected, first, values[0], second, values[1], end, values[2]) < 0) {
        return EXIT_FAILURE;
    }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

QUEUE_DRAIN = BOUNDED_QUEUE + QUEUE_DRAIN_MAIN

QUEUE_WORKERS = r"""
#include <limits.h>
typedef struct { Queue *queue; unsigned int count, total; } ConsumerJob;

static int produce(void *context)
{
    Queue *queue = context;
    for (int value = 1; value <= 12; ++value) {
        if (!queue_push(queue, value)) { return EXIT_FAILURE; }
    }
    queue_close(queue);
    return EXIT_SUCCESS;
}

static int consume(void *context)
{
    ConsumerJob *job = context;
    int value;
    while (queue_pop(job->queue, &value)) {
        if (value < 0 || job->count == UINT_MAX ||
            (unsigned int) value > UINT_MAX - job->total) {
            /* A worker error must wake its peer before anybody joins it. */
            queue_close(job->queue);
            return EXIT_FAILURE;
        }
        ++job->count;
        job->total += (unsigned int) value;
    }
    return EXIT_SUCCESS;
}

int main(void)
{
    Queue queue;
    if (!queue_init(&queue)) { return EXIT_FAILURE; }
    ConsumerJob job = {&queue, 0, 0};
    thrd_t threads[2];
    size_t started = 0;
    int result = EXIT_SUCCESS;
    if (thrd_create(&threads[0], consume, &job) == thrd_success) {
        ++started;
        if (thrd_create(&threads[1], produce, &queue) == thrd_success) {
            ++started;
        } else { result = EXIT_FAILURE; }
    } else { result = EXIT_FAILURE; }
    if (result != EXIT_SUCCESS) {
        fputs("Cannot create thread.\n", stderr);
        queue_close(&queue);
    }
    for (size_t i = 0; i < started; ++i) {
        int worker_result = EXIT_FAILURE;
        join_or_exit(threads[i], &worker_result);
        if (worker_result != EXIT_SUCCESS) { result = EXIT_FAILURE; }
    }
    queue_destroy(&queue);
    if (result != EXIT_SUCCESS) { return result; }
    if (printf("count=%u total=%u\n", job.count, job.total) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

PRODUCER_CONSUMER = THREAD_JOIN + BOUNDED_QUEUE + QUEUE_WORKERS

TIMED_QUEUE_TYPES = r"""
#include <time.h>
typedef enum { QUEUE_ITEM, QUEUE_END, QUEUE_TIMEOUT } QueueRead;
"""

TIMED_QUEUE_WAIT = r"""
/* Caller owns queue->mutex. The same valid TIME_UTC deadline stays alive. */
static QueueRead wait_for_item_until(Queue *queue, const struct timespec *deadline)
{
    while (queue->count == 0 && !queue->closed) {
        int status = cnd_timedwait(&queue->not_empty, &queue->mutex, deadline);
        if (status == thrd_timedout) {
            /* State may have changed while the wait reacquired the mutex. */
            if (queue->count == 0 && !queue->closed) { return QUEUE_TIMEOUT; }
        } else {
            check_sync(status, "Cannot timed-wait for item.\n");
        }
    }
    return queue->count != 0 ? QUEUE_ITEM : QUEUE_END;
}
"""

TIMED_QUEUE_POP = r"""
/* Live queue, valid deadline and separate writable result; neither may be NULL. */
static QueueRead queue_pop_until(Queue *queue, int *result, const struct timespec *deadline)
{
    check_sync(mtx_lock(&queue->mutex), "Cannot lock queue.\n");
    QueueRead status = wait_for_item_until(queue, deadline);
    if (status == QUEUE_ITEM) {
        *result = queue->items[queue->head];
        queue->head = (queue->head + 1) % QUEUE_CAPACITY;
        --queue->count;
        check_sync(cnd_signal(&queue->not_full), "Cannot signal space.\n");
    }
    check_sync(mtx_unlock(&queue->mutex), "Cannot unlock queue.\n");
    return status;
}
"""

TIMED_QUEUE = QUEUE_SUPPORT + QUEUE_CLOSE + TIMED_QUEUE_TYPES + TIMED_QUEUE_WAIT + TIMED_QUEUE_POP

TIMED_QUEUE_MAIN = r"""
int main(void)
{
    struct timespec deadline;
    if (timespec_get(&deadline, TIME_UTC) != TIME_UTC) {
        fputs("Cannot read clock.\n", stderr);
        return EXIT_FAILURE;
    }
    /* Deliberately immediate expiry: no unchecked arithmetic on time_t. */
    Queue queue;
    if (!queue_init(&queue)) { return EXIT_FAILURE; }
    int value = 77;
    QueueRead empty = queue_pop_until(&queue, &value, &deadline);
    int unchanged = value == 77;
    int accepted = queue_push(&queue, 42);
    queue_close(&queue);
    QueueRead item = queue_pop_until(&queue, &value, &deadline);
    int received = value;
    value = 77;
    QueueRead end = queue_pop_until(&queue, &value, &deadline);
    queue_destroy(&queue);
    if (printf("timeout=%d unchanged=%d accepted=%d\nitem=%d value=%d\nend=%d unchanged=%d\n",
               empty == QUEUE_TIMEOUT, unchanged, accepted, item == QUEUE_ITEM, received,
               end == QUEUE_END, value == 77) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

TIMED_QUEUE_STATES = TIMED_QUEUE + QUEUE_PUSH + TIMED_QUEUE_MAIN

TIMEOUT_WORKER = r"""
typedef struct { Queue *queue; const struct timespec *deadline; QueueRead status; } TimedJob;
static int timed_worker(void *context)
{
    TimedJob *job = context;
    int value = 77;
    job->status = queue_pop_until(job->queue, &value, job->deadline);
    if (job->status == QUEUE_TIMEOUT) {
        /* This worker chooses to stop; cnd_timedwait did not stop it. */
        queue_close(job->queue);
    }
    return EXIT_SUCCESS;
}

int main(void)
{
    struct timespec deadline;
    if (timespec_get(&deadline, TIME_UTC) != TIME_UTC) {
        fputs("Cannot read clock.\n", stderr);
        return EXIT_FAILURE;
    }
    Queue queue;
    if (!queue_init(&queue)) { return EXIT_FAILURE; }
    TimedJob job = {&queue, &deadline, QUEUE_ITEM};
    thrd_t thread;
    if (thrd_create(&thread, timed_worker, &job) != thrd_success) {
        queue_destroy(&queue);
        return EXIT_FAILURE;
    }
    int result = EXIT_FAILURE;
    join_or_exit(thread, &result);
    int closed = queue.closed;
    queue_destroy(&queue);
    if (result != EXIT_SUCCESS) { return EXIT_FAILURE; }
    if (printf("timeout=%d closed=%d\n", job.status == QUEUE_TIMEOUT, closed) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

TIMEOUT_SHUTDOWN = THREAD_JOIN + TIMED_QUEUE + TIMEOUT_WORKER

COOPERATIVE_JOBS = r"""
enum { STOP_AFTER = 3 };
typedef struct { Queue *queue; unsigned int accepted; bool stopped; } ProducerJob;
typedef struct { Queue *queue; unsigned int consumed; } DrainJob;
"""

COOPERATIVE_PRODUCER = r"""
static int produce_until_closed(void *context)
{
    ProducerJob *job = context;
    for (int value = 1; value <= 12; ++value) {
        if (!queue_push(job->queue, value)) {
            job->stopped = true;
            return EXIT_SUCCESS;
        }
        ++job->accepted;
    }
    queue_close(job->queue);
    return EXIT_SUCCESS;
}
"""

COOPERATIVE_MAIN = r"""
static int drain_and_stop(void *context)
{
    DrainJob *job = context;
    int value;
    while (queue_pop(job->queue, &value)) {
        ++job->consumed;
        if (job->consumed == STOP_AFTER) { queue_close(job->queue); }
    }
    return EXIT_SUCCESS;
}

int main(void)
{
    Queue queue;
    if (!queue_init(&queue)) { return EXIT_FAILURE; }
    ProducerJob producer = {&queue, 0, false};
    DrainJob consumer = {&queue, 0};
    thrd_t threads[2];
    size_t started = 0;
    int result = EXIT_SUCCESS;
    if (thrd_create(&threads[0], drain_and_stop, &consumer) == thrd_success) {
        ++started;
        if (thrd_create(&threads[1], produce_until_closed, &producer) == thrd_success) {
            ++started;
        } else { result = EXIT_FAILURE; }
    } else { result = EXIT_FAILURE; }
    if (result != EXIT_SUCCESS) {
        fputs("Cannot create thread.\n", stderr);
        queue_close(&queue);
    }
    for (size_t i = 0; i < started; ++i) {
        int worker_result = EXIT_FAILURE;
        join_or_exit(threads[i], &worker_result);
        if (worker_result != EXIT_SUCCESS) { result = EXIT_FAILURE; }
    }
    queue_destroy(&queue);
    if (result != EXIT_SUCCESS) { return result; }
    int drained = producer.accepted == consumer.consumed;
    int bounded = consumer.consumed >= STOP_AFTER && consumer.consumed <= STOP_AFTER + QUEUE_CAPACITY;
    if (printf("stopped=%d drained=%d bounded=%d\n", producer.stopped, drained, bounded) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

COOPERATIVE_SHUTDOWN = THREAD_JOIN + BOUNDED_QUEUE + COOPERATIVE_JOBS + COOPERATIVE_PRODUCER + COOPERATIVE_MAIN

GROUP_TYPES = r"""
#include <limits.h>
#include <stdint.h>
enum { PRODUCER_LIMIT = 3 };
typedef struct { const int *values; size_t count; } Batch;
typedef struct { Queue *queue; Batch batch; size_t accepted; } BatchJob;
typedef struct { Queue *queue; size_t count; unsigned int total; } GroupConsumer;
typedef struct { size_t accepted, consumed; unsigned int total; } GroupSummary;
"""

GROUP_WORKERS = r"""
/* The coordinator supplies a live job and keeps the borrowed batch alive. */
static int group_producer(void *context)
{
    BatchJob *job = context;
    if (job->batch.values == NULL && job->batch.count != 0) {
        queue_close(job->queue);
        return EXIT_FAILURE;
    }
    for (size_t i = 0; i < job->batch.count; ++i) {
        if (!queue_push(job->queue, job->batch.values[i])) { return EXIT_FAILURE; }
        ++job->accepted;
    }
    /* Finishing one batch must not close the queue for the other producers. */
    return EXIT_SUCCESS;
}

static int group_consumer(void *context)
{
    GroupConsumer *job = context;
    int value;
    while (queue_pop(job->queue, &value)) {
        if (value < 0 || job->count == SIZE_MAX ||
            (unsigned int) value > UINT_MAX - job->total) {
            queue_close(job->queue);
            return EXIT_FAILURE;
        }
        ++job->count;
        job->total += (unsigned int) value;
    }
    return EXIT_SUCCESS;
}
"""

GROUP_FINISH = r"""
/* No queue mutex is held. Consumer is running; only started producer handles exist. */
static int finish_group(Queue *queue, thrd_t *producers, size_t started,
                        thrd_t consumer, int result)
{
    if (result != EXIT_SUCCESS) { queue_close(queue); }
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
    return result;
}
"""

GROUP_RUN = r"""
/* 0..PRODUCER_LIMIT borrowed batches; separate writable output changes only on success. */
static int run_group(const Batch *batches, size_t count, GroupSummary *output)
{
    if (output == NULL || count > PRODUCER_LIMIT || (count != 0 && batches == NULL)) {
        return EXIT_FAILURE;
    }
    Queue queue;
    if (!queue_init(&queue)) { return EXIT_FAILURE; }
    GroupConsumer consumer = {&queue, 0, 0};
    thrd_t consumer_thread;
    if (thrd_create(&consumer_thread, group_consumer, &consumer) != thrd_success) {
        queue_destroy(&queue);
        return EXIT_FAILURE;
    }
    BatchJob jobs[PRODUCER_LIMIT];
    thrd_t producers[PRODUCER_LIMIT];
    size_t started = 0;
    int result = EXIT_SUCCESS;
    for (size_t i = 0; i < count; ++i) {
        jobs[i] = (BatchJob) {&queue, batches[i], 0};
        if (thrd_create(&producers[i], group_producer, &jobs[i]) != thrd_success) {
            result = EXIT_FAILURE;
            break;
        }
        ++started;
    }
    result = finish_group(&queue, producers, started, consumer_thread, result);
    queue_destroy(&queue);
    if (result != EXIT_SUCCESS) { return result; }
    size_t accepted = 0;
    for (size_t i = 0; i < started; ++i) {
        if (jobs[i].accepted > SIZE_MAX - accepted) { return EXIT_FAILURE; }
        accepted += jobs[i].accepted;
    }
    if (accepted != consumer.count) { return EXIT_FAILURE; }
    *output = (GroupSummary) {accepted, consumer.count, consumer.total};
    return EXIT_SUCCESS;
}
"""

GROUP_PIPELINE = THREAD_JOIN + BOUNDED_QUEUE + GROUP_TYPES + GROUP_WORKERS + GROUP_FINISH + GROUP_RUN

GROUP_MAIN = r"""
int main(void)
{
    const int first[] = {1, 2, 3, 4};
    const int second[] = {10, 20, 30, 40};
    const int third[] = {100, 200, 300, 400};
    const Batch batches[] = {{first, 4}, {second, 4}, {third, 4}};
    GroupSummary summary = {77, 77, 77};
    if (run_group(batches, 3, &summary) != EXIT_SUCCESS) { return EXIT_FAILURE; }
    if (printf("accepted=%zu consumed=%zu total=%u\n", summary.accepted,
               summary.consumed, summary.total) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

PRODUCER_GROUP = GROUP_PIPELINE + GROUP_MAIN

GROUP_FAILURE_MAIN = r"""
int main(void)
{
    GroupSummary empty = {77, 77, 77};
    if (run_group(NULL, 0, &empty) != EXIT_SUCCESS) { return EXIT_FAILURE; }
    const int values[] = {1, 2, 3, 4, 5};
    const Batch batches[] = {{values, 5}, {NULL, 1}, {values, 5}};
    GroupSummary summary = {77, 88, 99};
    int failed = run_group(batches, 3, &summary) != EXIT_SUCCESS;
    int unchanged = summary.accepted == 77 && summary.consumed == 88 && summary.total == 99;
    if (printf("empty=%zu:%zu:%u\nfailed=%d unchanged=%d\n",
               empty.accepted, empty.consumed, empty.total, failed, unchanged) < 0) {
        return EXIT_FAILURE;
    }
    if (!failed || !unchanged) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""

PRODUCER_GROUP_FAILURE = GROUP_PIPELINE + GROUP_FAILURE_MAIN
