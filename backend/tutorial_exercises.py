"""Deterministické, malé zadania pre učebnicu programovania.

Zadanie je odvodené iba z jazyka, témy a čísla variantu. Rovnaký variant teda
vždy vznikne rovnako a server môže skontrolovať výstup bez dôvery v klienta.
Prvé zadania sú vedome malé: slúžia na precvičenie jedného pojmu popri výklade,
nie ako náhrada za samostatný projekt vo Vývoji.
"""

from __future__ import annotations

import re
from typing import Any

from backend.tutorial_c_examples import COUNT_POSITIVE, LINE_READER


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
