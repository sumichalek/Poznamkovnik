"""Deterministické, malé zadania pre učebnicu programovania.

Zadanie je odvodené iba z jazyka, témy a čísla variantu. Rovnaký variant teda
vždy vznikne rovnako a server môže skontrolovať výstup bez dôvery v klienta.
Prvé zadania sú vedome malé: slúžia na precvičenie jedného pojmu popri výklade,
nie ako náhrada za samostatný projekt vo Vývoji.
"""

from __future__ import annotations

import re
from typing import Any

from backend.tutorial_c_examples import (
    ATOMIC_SUPPORT, BOUNDED_QUEUE, COOPERATIVE_JOBS, COOPERATIVE_MAIN, COUNT_POSITIVE,
    GATE_MAIN, GATE_SUPPORT, LINE_READER, QUEUE_CLOSE, QUEUE_DRAIN_MAIN,
    GROUP_MAIN, GROUP_RUN, GROUP_TYPES, GROUP_WORKERS,
    QUEUE_OPERATIONS, QUEUE_PUSH, QUEUE_SUPPORT, THREAD_JOIN,
    TIMED_QUEUE_MAIN, TIMED_QUEUE_POP, TIMED_QUEUE_TYPES, WALK_VALUES,
)


MAX_PRACTICE_VARIANT = 10_000


def _variant(value: Any) -> int:
    try:
        return max(0, min(int(value), MAX_PRACTICE_VARIANT))
    except (TypeError, ValueError):
        return 0


def _pick(values: tuple[Any, ...], variant: int) -> Any:
    return values[variant % len(values)]


def _c_practice(topic: str, variant: int) -> dict[str, Any] | None:
    variant = _variant(variant)
    if topic == "program":
        name = _pick(("Ada", "Marek", "Zora", "Ján"), variant)
        return {
            "title": "Presný výpis",
            "description": f"Doplň program tak, aby vypísal presne „Ahoj, {name}!" + "“.",
            "starterSource": "#include <stdio.h>\n\nint main(void)\n{\n    /* Doplň výpis. */\n    return 0;\n}\n",
            "stdin": "",
            "expectedOutput": f"Ahoj, {name}!\n",
            "hints": ("puts automaticky pridá nový riadok.",),
        }
    if topic in {"values", "operators"}:
        left, right = _pick(((7, 5), (12, 9), (18, 4), (23, 6)), variant)
        operation = "súčet" if topic == "values" else "rozdiel"
        result = left + right if topic == "values" else left - right
        expression = "left + right" if topic == "values" else "left - right"
        return {
            "title": "Výraz a výsledok",
            "description": f"Vypočítaj {operation} dvoch hodnôt a vypíš ho.",
            "starterSource": f"#include <stdio.h>\n\nint main(void)\n{{\n    const int left = {left};\n    const int right = {right};\n    int result = 0;\n\n    /* Priraď do result výraz {expression}. */\n    printf(\"%d\\n\", result);\n    return 0;\n}}\n",
            "stdin": "",
            "expectedOutput": f"{result}\n",
            "hints": ("Výraz môžeš napísať priamo na pravú stranu priradenia.",),
        }
    if topic == "flow":
        value = _pick((-8, 0, 13, -2), variant)
        label = "záporné" if value < 0 else "nula" if value == 0 else "kladné"
        return {
            "title": "Trojcestná podmienka",
            "description": "Načítaj celé číslo a vypíš, či je záporné, nula alebo kladné.",
            "starterSource": "#include <stdio.h>\n\nint main(void)\n{\n    int value = 0;\n\n    if (scanf(\"%d\", &value) != 1) {\n        return 1;\n    }\n\n    /* Doplň vetvy a vypíš jednu z troch správ. */\n    return 0;\n}\n",
            "stdin": f"{value}\n",
            "expectedOutput": f"{label}\n",
            "hints": ("Najprv rozlíš value < 0, potom value == 0; zvyšok je kladný.",),
        }
    if topic == "preprocessor":
        left, right = _pick(((2, 3), (1, 4), (3, 1), (2, 4)), variant)
        total = left + right
        return {
            "title": "Oprav zoskupenie v makre",
            "description": "Oprav iba definíciu SQUARE. Musí správne umocniť súčet aj zachovať celý výsledok pri delení. Výpisy a argumenty ponechaj bez zmeny.",
            "starterSource": f"#include <stdio.h>\n\n#define SQUARE(value) value * value\n\nint main(void)\n{{\n    printf(\"%d\\n\", SQUARE({left} + {right}));\n    printf(\"%d\\n\", 3600 / SQUARE({left} + {right}));\n    return 0;\n}}\n",
            "stdin": "",
            "expectedOutput": f"{total * total}\n{3600 // (total * total)}\n",
            "hints": (
                "Uzavri do zátvoriek každý výskyt argumentu aj celú náhradu makra.",
                "Všetky argumenty v tejto úlohe sú čisté výrazy bez vedľajších účinkov.",
            ),
        }
    if topic == "build":
        left, right = _pick(((4, 10), (3, 9), (-2, 5), (-8, -3)), variant)
        if variant % 2 == 0:
            return {
                "title": "Deklarácia pred volaním",
                "description": "Funkcia priemer_dvoch je definovaná až za main. Doplň jej presný prototyp na označené miesto, bez presúvania alebo zmeny tiel funkcií.",
                "starterSource": f"#include <stdio.h>\n\n/* Doplň prototyp funkcie priemer_dvoch. */\n\nint main(void)\n{{\n    printf(\"%.1f\\n\", priemer_dvoch({left}.0, {right}.0));\n    return 0;\n}}\n\ndouble priemer_dvoch(double left, double right)\n{{\n    return (left + right) / 2.0;\n}}\n",
                "stdin": "",
                "expectedOutput": f"{(left + right) / 2:.1f}\n",
                "hints": (
                    "Prototyp zopakuje návratový typ a typy parametrov; namiesto tela má bodkočiarku.",
                    "V rozdelenom projekte by tento prototyp patril do spoločnej hlavičky.",
                ),
            }
        return {
            "title": "Deklarácia bez definície",
            "description": "Program pozná prototyp maximum, ale pri linkovaní chýba jeho definícia. Doplň telo funkcie na označené miesto; main ani prototyp nemeň.",
            "starterSource": f"#include <stdio.h>\n\nint maximum(int left, int right);\n\nint main(void)\n{{\n    printf(\"%d\\n\", maximum({left}, {right}));\n    return 0;\n}}\n\n/* Doplň definíciu funkcie maximum. */\n",
            "stdin": "",
            "expectedOutput": f"{max(left, right)}\n",
            "hints": (
                "Samotný prototyp nevytvorí telo funkcie. Telo musí mať rovnaký návratový typ aj typy parametrov.",
                "V rozdelenom projekte by už existujúca definícia vyžadovala pripojenie príslušného .o súboru.",
            ),
        }
    if topic in {"functions", "scope"}:
        left, right = _pick(((4, 9), (17, 3), (-2, -5), (8, 8)), variant)
        return {
            "title": "Malá pomocná funkcia",
            "description": "Doplň funkciu maximum tak, aby vrátila väčšiu z dvoch hodnôt.",
            "starterSource": f"#include <stdio.h>\n\nstatic int maximum(int left, int right)\n{{\n    /* Vráť väčšiu hodnotu. */\n    return 0;\n}}\n\nint main(void)\n{{\n    printf(\"%d\\n\", maximum({left}, {right}));\n    return 0;\n}}\n",
            "stdin": "",
            "expectedOutput": f"{max(left, right)}\n",
            "hints": ("Podmienkový výraz alebo if sú rovnako platné riešenia.",),
        }
    if topic == "arrays":
        values = _pick(((3, 5, 2), (10, -4, 7), (8, 1, 1, 2)), variant)
        initializer = ", ".join(str(value) for value in values)
        return {
            "title": "Súčet poľa",
            "description": "Prejdi celé pole a vypíš súčet jeho prvkov.",
            "starterSource": f"#include <stddef.h>\n#include <stdio.h>\n\nint main(void)\n{{\n    const int values[] = {{{initializer}}};\n    const size_t count = sizeof values / sizeof values[0];\n    int total = 0;\n\n    /* Doplň cyklus, ktorý pripočíta každý prvok. */\n    printf(\"%d\\n\", total);\n    return 0;\n}}\n",
            "stdin": "",
            "expectedOutput": f"{sum(values)}\n",
            "hints": ("Použi size_t pre index, ktorý porovnávaš s count.",),
        }
    if topic == "pointers":
        value = _pick((3, 10, -4, 21), variant)
        return {
            "title": "Zmena cez ukazovateľ",
            "description": "Doplň funkciu increment tak, aby zvýšila hodnotu volajúceho o jedna.",
            "starterSource": f"#include <stdio.h>\n\nstatic void increment(int *value)\n{{\n    if (value != NULL) {{\n        /* Zmeň objekt, na ktorý value ukazuje. */\n    }}\n}}\n\nint main(void)\n{{\n    int value = {value};\n\n    increment(&value);\n    printf(\"%d\\n\", value);\n    return 0;\n}}\n",
            "stdin": "",
            "expectedOutput": f"{value + 1}\n",
            "hints": ("*value je samotné celé číslo, nie adresa.",),
        }
    if topic == "strings":
        text, target = _pick((("banan", "a"), ("program", "r"), ("mississippi", "s")), variant)
        expected = text.count(target)
        return {
            "title": "Počet znakov v texte",
            "description": f"Prejdi reťazec a spočítaj výskyty znaku '{target}'.",
            "starterSource": f"#include <stdio.h>\n\nint main(void)\n{{\n    const char text[] = \"{text}\";\n    int count = 0;\n\n    /* Prejdi text až po koncový znak '\\0'. */\n    printf(\"%d\\n\", count);\n    return 0;\n}}\n",
            "stdin": "",
            "expectedOutput": f"{expected}\n",
            "hints": ("Reťazec sa končí nulovým znakom, nie posledným viditeľným písmenom.",),
        }
    if topic == "types":
        x, y = _pick(((2, 5), (-3, 9), (7, -2)), variant)
        return {
            "title": "Údaj v štruktúre",
            "description": "Doplň výpočet súčtu súradníc štruktúry Point.",
            "starterSource": f"#include <stdio.h>\n\ntypedef struct {{\n    int x;\n    int y;\n}} Point;\n\nint main(void)\n{{\n    const Point point = {{{x}, {y}}};\n    int total = 0;\n\n    /* Pracuj s point.x a point.y. */\n    printf(\"%d\\n\", total);\n    return 0;\n}}\n",
            "stdin": "",
            "expectedOutput": f"{x + y}\n",
            "hints": ("Pri hodnote struct používaj na prístup k členom bodku.",),
        }
    if topic == "bits":
        initial, instruction, expected, hint = _pick((
            (5, "Zapni", 7, "Operátor |= pridá bity masky a ostatné zachová."),
            (7, "Vypni", 5, "Operátor &= s obrátenou maskou vypne iba vybrané bity."),
            (1, "Prepni", 3, "Operátor ^= zmení vybraný bit na opačný stav."),
            (7, "Prepni", 5, "Prepnutie nie je zapnutie: už zapnutý bit musí zhasnúť."),
        ), variant)
        return {
            "title": f"{instruction} bitový príznak",
            "description": f"{instruction} príznak FEATURE_WRITE vo flags s počiatočnou hodnotou {initial}. Zachovaj ostatné bity aj pripravený výpis celej masky.",
            "starterSource": f"#include <stdio.h>\n\nenum {{\n    FEATURE_READ = 1U << 0,\n    FEATURE_WRITE = 1U << 1,\n    FEATURE_SEND = 1U << 2\n}};\n\nint main(void)\n{{\n    unsigned int flags = {initial}U;\n\n    /* {instruction} FEATURE_WRITE bitovým operátorom. */\n    printf(\"%u\\n\", flags);\n    return 0;\n}}\n",
            "stdin": "",
            "expectedOutput": f"{expected}\n",
            "hints": (hint,),
        }
    if topic == "memory":
        values = _pick(((2, 4, 6), (5, -2, 9), (1, 1, 1, 1)), variant)
        initializer = ", ".join(str(value) for value in values)
        return {
            "title": "Dynamické pole",
            "description": "Skopíruj hodnoty do dynamického poľa, spočítaj ich a uvoľni pamäť.",
            "starterSource": f"#include <stddef.h>\n#include <stdio.h>\n#include <stdlib.h>\n\nint main(void)\n{{\n    const int initial[] = {{{initializer}}};\n    const size_t count = sizeof initial / sizeof initial[0];\n    int *values = malloc(count * sizeof *values);\n    int total = 0;\n\n    if (values == NULL) {{\n        return 1;\n    }}\n\n    /* Skopíruj prvky, spočítaj ich a pred návratom zavolaj free. */\n    printf(\"%d\\n\", total);\n    return 0;\n}}\n",
            "stdin": "",
            "expectedOutput": f"{sum(values)}\n",
            "hints": ("Ak existuje jeden malloc, v úspešnej ceste má byť aj jedno free.",),
        }
    if topic == "io":
        sample, expected = _pick((
            ("1234567\nOK\n", "accepted=2 rejected=0\n"),
            ("12345678\nOK\n", "accepted=1 rejected=1\n"),
            ("\nlast", "accepted=2 rejected=0\n"),
            ("abcdefghijk\n12345678\nOK", "accepted=1 rejected=2\n"),
            ("", "accepted=0 rejected=0\n"),
        ), variant)
        return {
            "title": "Celý riadok alebo odmietnutie",
            "description": "Použi pripravené read_line s poľom na 8 bajtov. Doplň rozlíšenie stavov: LINE_OK zvýši accepted, LINE_TOO_LONG alebo LINE_INVALID zvýši rejected, LINE_END ukončí cyklus a LINE_ERROR skončí s EXIT_FAILURE. Výpis ani pomocnú funkciu nemeň. Úlohou programu je spočítať prijaté a odmietnuté riadky, preto pri bežnom konci vstupu vráti úspech.",
            "starterSource": LINE_READER + r"""
#include <stdlib.h>

int main(void)
{
    char line[8];
    unsigned int accepted = 0;
    unsigned int rejected = 0;
    for (;;) {
        LineStatus status = read_line(stdin, line, sizeof line);
        /* Replace this placeholder with handling of all five states. */
        (void) status;
        break;
    }
    if (printf("accepted=%u rejected=%u\n", accepted, rejected) < 0 ||
        fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
""",
            "stdin": sample,
            "expectedOutput": expected,
            "hints": (
                "Prázdny riadok je LINE_OK; prázdny vstup je LINE_END.",
                "read_line už zahodilo zvyšok príliš dlhého riadka. Ďalší riadok čítaj novým volaním.",
            ),
        }
    if topic == "errors":
        requested = _pick((3, 0, 6, -2), variant)
        return {
            "title": "Pri chybe zachovaj nastavenie",
            "description": "Doplň set_attempts: NULL vráti SET_ARGUMENT, číslo mimo 1 až 5 vráti SET_RANGE bez zmeny objektu a platné číslo sa zapíše cez result s návratom SET_OK. Výpis v main nemeň. Testovací program kontroluje všetky prípady; čísla stavov sú SET_OK=0, SET_ARGUMENT=1 a SET_RANGE=2.",
            "starterSource": r"""#include <stdio.h>
#include <stdlib.h>

typedef enum { SET_OK, SET_ARGUMENT, SET_RANGE } SetStatus;

static SetStatus set_attempts(int requested, int *result)
{
    /* Replace this placeholder with checks and one final assignment. */
    (void) requested;
    (void) result;
    return SET_OK;
}

int main(void)
{
    const int cases[] = {""" + f"{requested}, 1, 5, 0, 6" + r"""};
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        int value = 2;
        SetStatus status = set_attempts(cases[i], &value);
        if (printf("%d:%d\n", (int) status, value) < 0) {
            return EXIT_FAILURE;
        }
    }
    if (printf("null:%d\n", (int) set_attempts(3, NULL)) < 0 ||
        fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
""",
            "stdin": "",
            "expectedOutput": "".join(
                f"0:{value}\n" if 1 <= value <= 5 else "2:2\n"
                for value in (requested, 1, 5, 0, 6)
            ) + "null:1\n",
            "hints": (
                "Najprv over result, potom rozsah requested. Pri chybe sa vráť ešte pred priradením.",
                "Jediný zápis *result = requested patrí na úspešnú cestu.",
            ),
        }
    if topic == "safety":
        values = _pick(((10, 20), (-4, 0, 9), (7, 8, 9, 10), (0, -2, 4, 6, 8)), variant)
        return {
            "title": "Over index pred čítaním",
            "description": "Doplň get_value: NULL vstup alebo výstup a index mimo 0 až count-1 odmietni návratom 0 bez zmeny výsledku. Pri úspechu zapíš prvok a vráť 1. Nenulové values podľa kontraktu odkazuje na aspoň count čitateľných prvkov. Zachovaj main, ktorý skúša hranice, prázdny rozsah aj NULL; nevytváraj ani nečítaj neplatný prvok pred kontrolami.",
            "starterSource": r"""#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static int get_value(const int values[], size_t count, int index, int *result)
{
    /* Replace this placeholder with checks before the array access. */
    (void) values;
    (void) count;
    (void) index;
    (void) result;
    return 0;
}

int main(void)
{
    const int values[] = {""" + ", ".join(map(str, values)) + r"""};
    const size_t count = sizeof values / sizeof values[0];
    const int indices[] = {-1, 0, """ + f"{len(values) - 1}, {len(values)}" + r""", INT_MIN, INT_MAX};
    for (size_t i = 0; i < sizeof indices / sizeof indices[0]; ++i) {
        int value = 77;
        int ok = get_value(values, count, indices[i], &value);
        if (printf("%d:%d\n", ok, value) < 0) {
            return EXIT_FAILURE;
        }
    }
    int value = 77;
    int empty = get_value(values, 0, 0, &value);
    int missing = get_value(NULL, count, 0, &value);
    int output = get_value(values, count, 0, NULL);
    if (printf("empty=%d null=%d output=%d value=%d\n",
               empty, missing, output, value) < 0 || fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
""",
            "stdin": "",
            "expectedOutput": f"0:77\n1:{values[0]}\n1:{values[-1]}\n0:77\n0:77\n0:77\nempty=0 null=0 output=0 value=77\n",
            "hints": (
                "NULL a záporný index odmietni ako prvé. Na porovnanie nezáporného indexu a count môžeš použiť uintmax_t.",
                "Rovnosť indexu s count už nie je platná. Jediný zápis *result patrí až za všetky kontroly.",
            ),
        }
    if topic == "string-reference":
        capacity = _pick((4, 1, 5, 3), variant)
        return {
            "title": "Kopírovanie s dohodnutou chybovou cestou",
            "description": "Doplň copy_text podľa kontraktu referencie. Najprv odmietni NULL ako COPY_ARGUMENT, potom zdroj bez nuly v source_size bajtoch ako COPY_UNTERMINATED a nedostatočnú kapacitu ako COPY_SPACE. Iba pri úspechu prenes celý text vrátane nuly pomocou memmove a vráť COPY_OK. Pri chybe nemeň cieľ. Číselné stavy sú 0, 1, 2, 3 v poradí enumu. Kapacity a zdrojové rozsahy poskytuje pripravený main; ten nemeň.",
            "starterSource": r"""#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef enum { COPY_OK, COPY_ARGUMENT, COPY_UNTERMINATED, COPY_SPACE } CopyStatus;

static CopyStatus copy_text(char *target, size_t capacity,
                            const char *source, size_t source_size)
{
    /* Replace this placeholder with validation followed by one memmove. */
    (void) target;
    (void) capacity;
    (void) source;
    (void) source_size;
    return COPY_OK;
}

int main(void)
{
    const struct { char source[8]; size_t size; } cases[] = {
        {"", 1}, {"C17", 4}, {"ABCDE", 6}, {"ABC", 3}, {"C17", 0}
    };
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        char target[8] = "keep";
        CopyStatus status = copy_text(target, """ + str(capacity) + r""", cases[i].source, cases[i].size);
        if (printf("%d:%s\n", (int) status, target) < 0) {
            return EXIT_FAILURE;
        }
    }
    char target[8] = "keep";
    CopyStatus missing_target = copy_text(NULL, 0, "", 1);
    CopyStatus missing_source = copy_text(target, sizeof target, NULL, 0);
    if (printf("null-target=%d null-source=%d text=%s\n",
               (int) missing_target, (int) missing_source, target) < 0 || fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
""",
            "stdin": "",
            "expectedOutput": "".join(
                f"0:{text}\n" if len(text) < capacity else "3:keep\n"
                for text in ("", "C17", "ABCDE")
            ) + "2:keep\n2:keep\nnull-target=1 null-source=1 text=keep\n",
            "hints": (
                "strlen volaj až po úspešnom ohraničenom hľadaní nuly cez memchr. Limit 3 v prípade ABC nezahŕňa nulu uloženú za týmto rozsahom.",
                "Podmienka length >= capacity necháva miesto pre koncovú nulu. Pri chybe sa vráť bez zápisu do target.",
            ),
        }
    if topic == "stdlib-reference":
        values = _pick(((3, 1, 3, -2), (0, 5, -1, 5), (9, 7, -2, 0), (2, 2, 1, 3)), variant)
        return {
            "title": "Porovnávač bez pretečenia",
            "description": "Doplň compare_ints pre vzostupné poradie: záporný výsledok pre a < b, nula pre rovnosť a kladný pre a > b. Neodčítavaj priamo a - b. Pripravený main triedi, hľadá a kontroluje znamienka pri INT_MIN a INT_MAX. Tabuľku, qsort, bsearch ani výpisy nemeň. Porovnávač nemusí vracať presne -1 alebo 1; výpis normalizuje iba znamienko.",
            "starterSource": r"""#include <limits.h>
#include <stdio.h>
#include <stdlib.h>

static int compare_ints(const void *left, const void *right)
{
    int a = *(const int *) left;
    int b = *(const int *) right;
    /* Replace this placeholder with a comparison that cannot overflow. */
    (void) a;
    (void) b;
    return 0;
}

int main(void)
{
    int values[] = {""" + ", ".join(map(str, values)) + r"""};
    const size_t count = sizeof values / sizeof values[0];
    qsort(values, count, sizeof values[0], compare_ints);
    for (size_t i = 0; i < count; ++i) {
        if (printf("%d%s", values[i], i + 1 == count ? "\n" : " ") < 0) {
            return EXIT_FAILURE;
        }
    }
    int key = """ + str(values[0]) + r""";
    int found = bsearch(&key, values, count, sizeof values[0], compare_ints) != NULL;
    key = 99;
    int missing = bsearch(&key, values, count, sizeof values[0], compare_ints) == NULL;
    int low = INT_MIN;
    int high = INT_MAX;
    int forward = compare_ints(&low, &high);
    int reverse = compare_ints(&high, &low);
    int equal = compare_ints(&high, &high);
    if (printf("found=%d missing=%d edge=%d reverse=%d equal=%d\n", found, missing,
               (forward > 0) - (forward < 0), (reverse > 0) - (reverse < 0),
               (equal > 0) - (equal < 0)) < 0 || fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
""",
            "stdin": "",
            "expectedOutput": " ".join(map(str, sorted(values))) + "\nfound=1 missing=1 edge=-1 reverse=1 equal=0\n",
            "hints": (
                "Porovnania a > b a a < b dávajú hodnoty 0 alebo 1. Ich rozdiel sa do int vždy zmestí.",
                "Rovnocenné prvky musia dostať nulu. Pretypovanie už pretečeného a - b neopraví porušenie rozsahu.",
            ),
        }
    if topic == "stdio-reference":
        capacity = _pick((9, 8, 1, 0), variant)
        capacities = (capacity, 9, 8, 1, 0)
        return {
            "title": "Tri výsledky snprintf",
            "description": "Doplň format_result: záporný required znamená FORMAT_ERROR (1), nezáporný required >= capacity znamená FORMAT_TRUNCATED (2), inak FORMAT_OK (0). Pri nulovej kapacite sa text neuložil ani pri required == 0. Main skúša skutočné formátovanie aj samostatné záporné návraty; tie iba simulujú chybu pre klasifikátor. Main ani enum nemeň. Zápornú hodnotu skontroluj pred prevodom na neznamienkový typ.",
            "starterSource": r"""#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef enum { FORMAT_OK, FORMAT_ERROR, FORMAT_TRUNCATED } FormatStatus;

static FormatStatus format_result(int required, size_t capacity)
{
    /* Replace this placeholder with the three return-value checks. */
    (void) required;
    (void) capacity;
    return FORMAT_OK;
}

int main(void)
{
    const size_t capacities[] = {""" + ", ".join(map(str, capacities)) + r"""};
    for (size_t i = 0; i < sizeof capacities / sizeof capacities[0]; ++i) {
        char text[9] = "old";
        size_t capacity = capacities[i];
        int required = snprintf(capacity == 0 ? NULL : text, capacity, "value=%d", 42);
        if (required < 0) { return EXIT_FAILURE; }
        if (printf("%zu:%d:%d:[%s]\n", capacity, required,
                   (int) format_result(required, capacity), text) < 0) {
            return EXIT_FAILURE;
        }
    }
    if (printf("errors=%d,%d empty=%d,%d\n", (int) format_result(-1, 0),
               (int) format_result(-1, SIZE_MAX), (int) format_result(0, 0),
               (int) format_result(0, 1)) < 0 || fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
""",
            "stdin": "",
            "expectedOutput": "".join(
                f"{size}:8:{0 if size > 8 else 2}:[{'value=42'[:size - 1] if size else 'old'}]\n"
                for size in capacities
            ) + "errors=1,1 empty=2,0\n",
            "hints": (
                "Najprv sa vráť pri required < 0. Až potom porovnávaj nezápornú požadovanú dĺžku a kapacitu.",
                "Pre spoločný neznamienkový typ oboch hodnôt použi uintmax_t. Rovnosť už znamená, že chýba miesto pre koncovú nulu.",
            ),
        }
    if topic == "numeric-reference":
        first, category = _pick((("'7'", 1), (r"'\n'", 2), ("'a'", 0), ("0xFF", 0)), variant)
        return {
            "title": "Klasifikácia bajtu bez záporného argumentu",
            "description": "Doplň classify_char: číslica má výsledok 1, biely znak 2 a ostatné 0. Použi isdigit a isspace v počiatočnom C locale. Parameter char je uložený bajt, nie výsledok fgetc ani EOF: pred volaním ctype ho preveď na unsigned char a testuj nenulový výsledok. Main vrátane bajtov 00, FF a 80 nemeň. Porovnanie výstupu samo osebe nedokazuje dodržanie domény ctype; skontroluj aj argumenty vo svojom kóde.",
            "starterSource": r"""#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned int classify_char(char value)
{
    /* Replace this placeholder with unsigned-byte classification. */
    (void) value;
    return 0;
}

int main(void)
{
    const unsigned char values[] = {""" + first + r""", '0', '9', ' ', '\t', 'A', 0, 0xFF, 0x80};
    for (size_t i = 0; i < sizeof values / sizeof values[0]; ++i) {
        if (printf("%u\n", classify_char((char) values[i])) < 0) {
            return EXIT_FAILURE;
        }
    }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
""",
            "stdin": "",
            "expectedOutput": f"{category}\n1\n1\n2\n2\n0\n0\n0\n0\n",
            "hints": (
                "Ulož (unsigned char) value do pomocnej premennej. Obe klasifikačné funkcie musia dostať túto nezápornú hodnotu.",
                "isdigit ani isspace nemusia pri pravde vrátiť práve 1. Použi != 0 a až potom vráť dohodnutú kategóriu.",
            ),
        }
    if topic == "callbacks":
        limit = _pick((8, 3, 10, 6), variant)
        accepted = (3, 5, 9, 1)
        stop = next((index for index, value in enumerate(accepted) if value >= limit), len(accepted))
        return {
            "title": "Callback riadi zastavenie a mení svoj kontext",
            "description": "Doplň accept_below. NULL kontext znamená VISIT_ERROR. Inak ide o živý LimitState: pri value >= limit vráť VISIT_STOP bez zmeny, potom odmietni accepted == SIZE_MAX ako VISIT_ERROR. Až pri prijatí zvýš accepted, ulož last a vráť VISIT_CONTINUE. Pole, walk_values a main nemeň. Zastavujúci prvok sa nepočíta; skoršie prijaté hodnoty zostávajú v kontexte.",
            "starterSource": WALK_VALUES + r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct { int limit; size_t accepted; int last; } LimitState;

static VisitAction accept_below(int value, void *context)
{
    /* Replace this placeholder with context checks and one accepted value. */
    (void) value;
    (void) context;
    return VISIT_CONTINUE;
}

int main(void)
{
    const int values[] = {3, 5, 9, 1};
    LimitState state = {""" + str(limit) + r""", 0, 77};
    WalkStatus status = walk_values(values, sizeof values / sizeof values[0], accept_below, &state);
    if (printf("status=%d accepted=%zu last=%d\n", (int) status, state.accepted, state.last) < 0) { return EXIT_FAILURE; }
    WalkStatus missing = walk_values(values, 1, accept_below, NULL);
    WalkStatus empty = walk_values(NULL, 0, accept_below, NULL);
    WalkStatus no_callback = walk_values(values, 1, NULL, &state);
    LimitState full = {10, SIZE_MAX, 77};
    VisitAction overflow = accept_below(1, &full);
    if (printf("missing=%d empty=%d callback=%d full=%d unchanged=%d\n", (int) missing,
               (int) empty, (int) no_callback, (int) overflow,
               full.accepted == SIZE_MAX && full.last == 77) < 0) { return EXIT_FAILURE; }
    LimitState boundary = {state.limit, 0, 77};
    VisitAction equal = accept_below(boundary.limit, &boundary);
    VisitAction stop_full = accept_below(full.limit, &full);
    if (printf("equal=%d unchanged=%d full-stop=%d\n", (int) equal,
               boundary.accepted == 0 && boundary.last == 77, (int) stop_full) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
""",
            "stdin": "",
            "expectedOutput": f"status={int(stop < len(accepted))} accepted={stop} last={accepted[stop - 1] if stop else 77}\n"
                              "missing=3 empty=0 callback=2 full=2 unchanged=1\nequal=1 unchanged=1 full-stop=1\n",
            "hints": (
                "Po kontrole NULL priraď context do LimitState *state. Poradie kontroly limitu a kapacity počítadla patrí do kontraktu.",
                "Stav meníš iba vo vetve VISIT_CONTINUE. VISIT_STOP nie je príkaz na preskočenie prvku, ale na ukončenie celého prechodu.",
            ),
        }
    if topic == "portability":
        value = _pick((43981, 65535, 256, 0), variant)
        values = (value, 0, 255, 256, 65535, 65536)
        return {
            "title": "Ulož presne dohodnuté dva oktety",
            "description": "Doplň encode_u16be: NULL odmietni ako CODEC_ARGUMENT (1), kapacitu menšiu než 2 ako CODEC_SIZE (2), hodnotu nad 65535 ako CODEC_RANGE (3). Iba pri úspechu ulož horných osem bitov na index 0, dolných osem na index 1 a vráť CODEC_OK (0). Chyba nesmie zmeniť cieľ. Main ani enum nemeň. Požiadavka CHAR_BIT == 8 je výslovná; nekopíruj vnútorný obraz celého čísla.",
            "starterSource": r"""#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

_Static_assert(CHAR_BIT == 8, "This wire format requires 8-bit bytes");
typedef enum { CODEC_OK, CODEC_ARGUMENT, CODEC_SIZE, CODEC_RANGE } CodecStatus;

static CodecStatus encode_u16be(unsigned char *target, size_t capacity, uint_least32_t value)
{
    /* Replace this placeholder with validation and big-endian encoding. */
    (void) target;
    (void) capacity;
    (void) value;
    return CODEC_OK;
}

int main(void)
{
    const uint_least32_t values[] = {""" + ", ".join(f"UINT32_C({item})" for item in values) + r"""};
    for (size_t i = 0; i < sizeof values / sizeof values[0]; ++i) {
        unsigned char bytes[] = {0xAA, 0xBB};
        CodecStatus status = encode_u16be(bytes, sizeof bytes, values[i]);
        if (printf("%d:%02X %02X\n", (int) status, (unsigned int) bytes[0],
                   (unsigned int) bytes[1]) < 0) { return EXIT_FAILURE; }
    }
    for (size_t capacity = 0; capacity < 2; ++capacity) {
        unsigned char bytes[] = {0xAA, 0xBB};
        CodecStatus status = encode_u16be(bytes, capacity, capacity == 0 ? UINT32_C(65536) : 1);
        if (printf("short=%d:%02X %02X\n", (int) status, (unsigned int) bytes[0],
                   (unsigned int) bytes[1]) < 0) { return EXIT_FAILURE; }
    }
    if (printf("null=%d\n", (int) encode_u16be(NULL, 0, UINT32_C(65536))) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
""",
            "stdin": "",
            "expectedOutput": "".join(f"0:{item >> 8:02X} {item & 255:02X}\n" if item <= 65535 else "3:AA BB\n" for item in values)
                              + "short=2:AA BB\nshort=2:AA BB\nnull=1\n",
            "hints": (
                "Všetky tri kontroly patria pred prvý zápis. Nepretypúvaj hodnotu na úzky typ ešte pred kontrolou rozsahu.",
                "Horný oktet získaš posunom o 8 doprava, dolný maskou 255. Indexy určuje formát, nie poradie bajtov procesora.",
            ),
        }
    if topic == "producer-groups":
        count = _pick((3, 0, 1, 2), variant)
        return {
            "title": "Dokonči skupinu v správnom poradí",
            "description": "Doplň finish_group. Pri neúspešnom doterajšom výsledku uzavri frontu pred join. Pripoj každého z started producentov cez join_or_exit; chybu pracovníka zaznamenaj a uzavri frontu, ale pokračuj v pripájaní. Po producentoch frontu uzavri aj pri started == 0, pripoj konzumenta a zohľadni jeho výsledok. Žiadny mutex nedržíš a platné sú iba úspešne vytvorené identifikátory. Ostatný kód nemeň. Bezpečný štartovací kód skupinu zruší a vráti chybu. Samotný výpis nepreverí všetky poradia a zlyhania.",
            "starterSource": THREAD_JOIN + BOUNDED_QUEUE + GROUP_TYPES + GROUP_WORKERS + r"""
static int finish_group(Queue *queue, thrd_t *producers, size_t started,
                        thrd_t consumer, int result)
{
    /* Replace this cancellation-only placeholder with coordinated completion. */
    (void) result;
    queue_close(queue);
    for (size_t i = 0; i < started; ++i) {
        int worker_result;
        join_or_exit(producers[i], &worker_result);
    }
    int consumer_result;
    join_or_exit(consumer, &consumer_result);
    return EXIT_FAILURE;
}
""" + GROUP_RUN + GROUP_MAIN.replace("run_group(batches, 3, &summary)", f"run_group(batches, {count}, &summary)"),
            "stdin": "",
            "expectedOutput": f"accepted={count * 4} consumed={count * 4} total={(0, 10, 110, 1110)[count]}\n",
            "hints": (
                "Konzument musí odoberať položky aj počas čakania na producentov. Bežné uzavretie preto patrí až za ich slučku join.",
                "Každý join potvrdí dokončenie, ale návrat pracovníka treba vyhodnotiť zvlášť. Chyba jedného nesmie preskočiť zvyšné platné identifikátory.",
            ),
        }
    if topic == "deadlines":
        value = _pick((42, -7, 0, 123), variant)
        return {
            "title": "Rozhodni aj po timeoute podľa stavu",
            "description": "Doplň wait_for_item_until. Pri vstupe už držíš queue->mutex; pomocná funkcia ho sama nezamyká ani neodomyká. Kým je fronta otvorená a prázdna, volaj cnd_timedwait s nezmeneným deadline. Pri thrd_timedout vráť QUEUE_TIMEOUT iba ak stále nie je položka ani uzavretie; iné návraty kontroluj cez check_sync. Po slučke vráť QUEUE_ITEM pri count != 0, inak QUEUE_END. Dáta a deadline nemeň, ostatný kód ponechaj. Test výpisu sám neoveruje všetky prebudenia ani zachovanie pôvodného termínu.",
            "starterSource": QUEUE_SUPPORT + QUEUE_CLOSE + TIMED_QUEUE_TYPES + r"""
static QueueRead wait_for_item_until(Queue *queue, const struct timespec *deadline)
{
    /* Replace this placeholder with a loop and state checks after timeout. */
    (void) queue;
    (void) deadline;
    return QUEUE_TIMEOUT;
}
""" + TIMED_QUEUE_POP + QUEUE_PUSH + TIMED_QUEUE_MAIN.replace("queue_push(&queue, 42)", f"queue_push(&queue, {value})"),
            "stdin": "",
            "expectedOutput": f"timeout=1 unchanged=1 accepted=1\nitem=1 value={value}\nend=1 unchanged=1\n",
            "hints": (
                "Timeout nie je thrd_error. Skontroluj count a closed ešte pod opäť získaným mutexom.",
                "Nepoužívaj nové timespec_get v slučke. Dostupná položka má v tomto kontrakte prednosť aj na uzavretej fronte.",
            ),
        }
    if topic == "cancellation":
        stop_after = _pick((3, 1, 2, 4), variant)
        return {
            "title": "Producent rešpektuje odmietnutý push",
            "description": f"Doplň produce_until_closed pre platný ProducerJob. Posielaj hodnoty 1 až 12. Po úspešnom push zvýš accepted; pri odmietnutí nastav stopped=true a vráť EXIT_SUCCESS bez započítania položky. Ak vložíš všetkých 12, uzavri frontu a tiež vráť úspech. Konzument tu po {stop_after}. položke uzatvára prijímanie a dočíta zvyšok. Ostatné funkcie nemeň. Štartovacia funkcia frontu bezpečne uzavrie a vráti chybu, aby konzument nezostal čakať. Výpis kontroluje rovnosť počtov a rozsah, nie konkrétny rozvrh.",
            "starterSource": THREAD_JOIN + BOUNDED_QUEUE + COOPERATIVE_JOBS.replace("STOP_AFTER = 3", f"STOP_AFTER = {stop_after}") + r"""
static int produce_until_closed(void *context)
{
    /* Replace this placeholder with counted pushes and cooperative stopping. */
    (void) queue_push;
    ProducerJob *job = context;
    queue_close(job->queue);
    return EXIT_FAILURE;
}
""" + COOPERATIVE_MAIN,
            "stdin": "",
            "expectedOutput": "stopped=1 drained=1 bounded=1\n",
            "hints": (
                "queue_push vracia 0 iba pri uzavretej fronte. Tento očakávaný koniec nie je zlyhanie pracovníka.",
                "accepted zvyšuj až za vetvou odmietnutia. Nevypínaj konzumenta ani nemaž už prijaté položky.",
            ),
        }
    if topic == "conditions":
        value = _pick((42, -7, 0, 123), variant)
        return {
            "title": "Počkaj na splnený predikát",
            "description": "Doplň await_gate pre živú inicializovanú bránu. Zamkni mutex, vo while (!gate->ready) volaj cnd_wait s tým istým mutexom, potom načítaj value, odomkni a vráť hodnotu. Každý návrat synchronizačnej operácie kontroluj cez pripravený check_sync. Ostatné funkcie nemeň. Štartovacia funkcia bezpečne vracia nesprávnu hodnotu 77. Porovnanie výpisu neoverí všetky prebudenia; while je súčasťou požadovaného protokolu aj vtedy, keď by if náhodou prešlo.",
            "starterSource": THREAD_JOIN + GATE_SUPPORT + r"""
static int await_gate(Gate *gate)
{
    /* Replace this placeholder with a predicate loop under the mutex. */
    (void) gate;
    return 77;
}
""" + GATE_MAIN.replace("gate_open(&gate, 42)", f"gate_open(&gate, {value})"),
            "stdin": "",
            "expectedOutput": f"received={value}\n",
            "hints": (
                "cnd_wait odomkne a pri úspešnom návrate znova zamkne mutex. Nevkladaj vlastné odomknutie pred čakanie.",
                "Hodnotu skopíruj do lokálnej premennej ešte pod mutexom. Až potom odomkni a vráť ju.",
            ),
        }
    if topic == "queues":
        value = _pick((10, -9, 0, 123), variant)
        return {
            "title": "Uzavri frontu a zobuď obe skupiny",
            "description": "Doplň queue_close: zamkni mutex, nastav closed=true, zavolaj cnd_broadcast na not_empty aj not_full a odomkni. Všetky návraty skontroluj cez check_sync. Nemeň count, head ani items; opakované uzavretie má zachovať dáta. Fronta je živá a inicializovaná. Pripravený main a ostatné operácie nemeň. Štartovací kód ukončí proces chybou, aby neostal čakať na otvorenej prázdnej fronte. Jednovláknový výpis testuje dočítanie, nie doručenie prebudení; obidva broadcast sú povinnou časťou riešenia.",
            "starterSource": QUEUE_SUPPORT + r"""
static void queue_close(Queue *queue)
{
    /* Replace this placeholder with close and both broadcasts under the mutex. */
    (void) queue;
    _Exit(EXIT_FAILURE);
}
""" + QUEUE_OPERATIONS + QUEUE_DRAIN_MAIN.replace("queue_push(&queue, 10)", f"queue_push(&queue, {value})"),
            "stdin": "",
            "expectedOutput": f"rejected=1 first=1:{value} second=1:-2 end=0:77\n",
            "hints": (
                "Čakať môže producent na plnej aj konzument na prázdnej fronte. Pre uzavretie treba zobudiť všetkých z oboch skupín.",
                "Uzavretie nie je vyprázdnenie: existujúce položky a indexy nechaj bez zmeny. Join sem nepatrí.",
            ),
        }
    if topic == "threads":
        values = _pick(((3, -2, 9, 1), (-9, -3, -7, -4), (0, 0, 0, 0), (12, 4, 6, 3)), variant)
        return {
            "title": "Výsledok pracovníka v požičanom objekte",
            "description": "Doplň find_maximum. NULL kontext, NULL pole a nulový počet odmietni cez EXIT_FAILURE bez zápisu. Inak nájdi maximum od prvého prvku, zapíš job->maximum a vráť EXIT_SUCCESS. Job aj pole sú živé do úspešného join; pripravený main ich počas práce nemení a výsledok číta až po pripojení. run_job, vytváranie vlákien a výpisy nemeň. ok=1 znamená úspešného pracovníka, nie číselnú hodnotu thrd_success.",
            "starterSource": THREAD_JOIN + r"""
typedef struct { const int *values; size_t count; int maximum; } MaximumJob;

static int find_maximum(void *context)
{
    /* Replace this placeholder with validation and a worker-owned result. */
    (void) context;
    return EXIT_FAILURE;
}

static int run_job(MaximumJob *job)
{
    thrd_t thread;
    if (thrd_create(&thread, find_maximum, job) != thrd_success) { return -1; }
    int result = EXIT_FAILURE;
    join_or_exit(thread, &result);
    return result == EXIT_SUCCESS;
}

int main(void)
{
    const int values[] = {""" + ", ".join(map(str, values)) + r"""};
    const int negative[] = {-8, -2};
    const int zero[] = {0};
    MaximumJob jobs[] = {
        {values, 4, 77}, {negative, 2, 77}, {zero, 1, 77},
        {values, 0, 77}, {NULL, 1, 77}
    };
    for (size_t i = 0; i < sizeof jobs / sizeof jobs[0]; ++i) {
        int ok = run_job(&jobs[i]);
        if (ok < 0) { return EXIT_FAILURE; }
        if (printf("%d:%d\n", ok, jobs[i].maximum) < 0) { return EXIT_FAILURE; }
    }
    int missing = run_job(NULL);
    if (missing < 0 || printf("null=%d\n", missing == 0) < 0) { return EXIT_FAILURE; }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
""",
            "stdin": "",
            "expectedOutput": f"1:{max(values)}\n1:-2\n1:0\n0:77\n0:77\nnull=1\n",
            "hints": (
                "Z context vytvor MaximumJob * až po kontrole NULL. Prvý prvok čítaj až po kontrole poľa a počtu.",
                "Začiatok maxima na nule by pokazil záporné vstupy. Jediný výsledný zápis patrí až za úspešný prechod poľa.",
            ),
        }
    if topic == "atomics":
        value = _pick((42, -7, 0, 123), variant)
        return {
            "title": "Čítaj iba publikovanú správu",
            "description": "Doplň try_read pre jednorazovú schránku. NULL argument odmietni návratom 0. Potom načítaj ready cez atomic_load_explicit s memory_order_acquire; pri false vráť 0 bez čítania value a bez zmeny výsledku. Iba pri true skopíruj value a vráť 1. publish_once ani main nemeň. Tento jednovláknový test kontroluje stavy a výstup, nie všetky rozvrhy: správny výpis sám nedokazuje správne pamäťové poradie.",
            "starterSource": ATOMIC_SUPPORT + r"""
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct { atomic_bool ready; int value; } Mailbox;

static void publish_once(Mailbox *box, int value)
{
    box->value = value;
    atomic_store_explicit(&box->ready, true, memory_order_release);
}

static int try_read(Mailbox *box, int *result)
{
    /* Replace this placeholder with acquire-before-payload access. */
    (void) box;
    (void) result;
    return 0;
}

int main(void)
{
    const int values[] = {""" + str(value) + r""", -3, 0, 42};
    for (size_t i = 0; i < sizeof values / sizeof values[0]; ++i) {
        Mailbox box;
        atomic_init(&box.ready, false);
        box.value = 0;
        int result = 77;
        int before = try_read(&box, &result);
        if (printf("before=%d:%d\n", before, result) < 0) { return EXIT_FAILURE; }
        publish_once(&box, values[i]);
        int ready = try_read(&box, &result);
        if (printf("ready=%d:%d\n", ready, result) < 0) { return EXIT_FAILURE; }
        result = 77;
        int missing_box = try_read(NULL, &result);
        int missing_result = try_read(&box, NULL);
        if (printf("null=%d output=%d value=%d\n", missing_box, missing_result, result) < 0) { return EXIT_FAILURE; }
    }
    return fflush(stdout) == EOF ? EXIT_FAILURE : EXIT_SUCCESS;
}
""",
            "stdin": "",
            "expectedOutput": "".join(f"before=0:77\nready=1:{item}\nnull=0 output=0 value=77\n" for item in (value, -3, 0, 42)),
            "hints": (
                "Kontrola ukazovateľov predchádza načítaniu príznaku. Čítanie value smie byť až vo vetve úspešného acquire.",
                "Schránka má jediného producenta a po publikácii nemenný payload. Nepridávaj reset ready ani opakovaný zápis value.",
            ),
        }
    if topic == "testing":
        samples = _pick((
            ((), (0,), (-2, 0, 3), (4,)),
            ((), (-3,), (0, 0), (4, 0, 2)),
            ((0,), (-1, 0), (0, 2), (0, 0, 0)),
            ((), (-4, -1), (1, 2, 3), (0, 0, 4)),
        ), variant)
        rows = "\n".join(
            "        {{" + (", ".join(map(str, values)) or "0") + "}, "
            + f"{len(values)}, {sum(value > 0 for value in values)}" + "},"
            for values in samples
        )
        return {
            "title": "Test musí rozpoznať aj známu chybu",
            "description": "Doplň failed(actual, expected): pri rozdiele vráť 1, pri zhode 0. Pripravený main spočíta neúspešné prípady pre správne count_positive aj chybné count_faulty, ktoré započítava nuly. Funkcie výpočtu, tabuľku očakávaní a main nemeň. Nejde o počet chybných prvkov, ale o počet zlyhaných testovacích prípadov. Nepouži assert: porovnania majú fungovať aj s NDEBUG.",
            "starterSource": COUNT_POSITIVE + r"""
#include <stdio.h>
#include <stdlib.h>

static size_t count_faulty(const int values[], size_t count)
{
    size_t positive = 0;
    for (size_t i = 0; i < count; ++i) {
        if (values[i] >= 0) {
            ++positive;
        }
    }
    return positive;
}

static size_t failed(size_t actual, size_t expected)
{
    /* Replace this placeholder with an always-active comparison. */
    (void) actual;
    (void) expected;
    return 0;
}

int main(void)
{
    const struct {
        int values[4];
        size_t count;
        size_t expected;
    } cases[] = {
""" + rows + r"""
    };
    size_t good = 0;
    size_t faulty = 0;
    for (size_t i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        good += failed(count_positive(cases[i].values, cases[i].count), cases[i].expected);
        faulty += failed(count_faulty(cases[i].values, cases[i].count), cases[i].expected);
    }
    if (printf("good=%zu faulty=%zu\n", good, faulty) < 0 || fflush(stdout) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
""",
            "stdin": "",
            "expectedOutput": f"good=0 faulty={sum(0 in values for values in samples)}\n",
            "hints": (
                "Operátor != vytvorí 0 pri zhode a 1 pri rozdiele. Vráť výsledok porovnania, nie samotnú vypočítanú hodnotu.",
                "Zlyhanie známeho mutanta je tu žiadaná informácia. Tento program porovnáva dve implementácie, preto samotný počet faulty neznamená neúspech celého programu.",
            ),
        }
    return None


def tutorial_practice(language_code: str, topic: str, variant: Any = 0) -> dict[str, Any] | None:
    """Vytvorí verejný popis jedného variantu zadania."""
    normalized_variant = _variant(variant)
    if language_code != "c":
        return None
    exercise = _c_practice(topic, normalized_variant)
    if exercise is None:
        return None
    return {
        "id": f"{language_code}:{topic}:{normalized_variant}",
        "language": language_code,
        "topic": topic,
        "variant": normalized_variant,
        **exercise,
    }


def tutorial_practice_public(exercise: dict[str, Any]) -> dict[str, Any]:
    """Odstráni serverové očakávanie výstupu z odpovede pre čítačku."""
    return {key: value for key, value in exercise.items() if key != "expectedOutput"}


def evaluate_tutorial_practice(exercise: dict[str, Any], result: dict[str, Any], stdin: str) -> dict[str, str]:
    """Vyhodnotí jeden priebeh bez toho, aby výsledok predstieral úplné testovanie."""
    compile_result = result.get("compile") if isinstance(result.get("compile"), dict) else {}
    run_result = result.get("run") if isinstance(result.get("run"), dict) else {}
    if not result.get("compiled"):
        return {"status": "build_error", "message": "Najprv oprav preklad programu."}
    if not run_result or int(run_result.get("exitCode") or 0) != 0:
        return {"status": "runtime_error", "message": "Program sa neskončil úspešne."}
    expected_input = str(exercise.get("stdin") or "")
    if str(stdin or "") != expected_input:
        return {"status": "unchecked", "message": "Na automatické overenie použi pripravený vstup zadania."}
    actual = _normalized_output(run_result.get("stdout"))
    expected = _normalized_output(exercise.get("expectedOutput"))
    if actual == expected:
        return {"status": "passed", "message": "Tento variant je správne vyriešený."}
    if compile_result.get("timedOut") or run_result.get("timedOut"):
        return {"status": "timeout", "message": "Program prekročil časový limit."}
    return {"status": "output_mismatch", "message": "Výstup ešte nezodpovedá zadaniu."}


def _normalized_output(value: Any) -> str:
    return re.sub(r"\n+$", "", re.sub(r"[ \t]+\n", "\n", str(value or "").replace("\r\n", "\n")))
