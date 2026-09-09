"""Kurikulárna mapa učebnice programovania a vstavaných systémov.

Tento modul je obsahový kontrakt. Pred vytvorením lekcií musí mať každý jazyk
a každý firmvérový cieľ premyslené pokrytie od prvého programu po referenciu,
nástroje a typické chyby. Lekcie a generátory cvičení budú z tejto mapy čítať
poradie, predpoklady a študijné ciele.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


COMMON_LANGUAGE_MODULES: tuple[dict[str, Any], ...] = (
    {
        "id": "orientation",
        "title": "Orientácia a prvý beh",
        "subtopics": (
            "účel jazyka, verzia a hranice štandardu",
            "zdrojový súbor, kódovanie, komentáre a názvy",
            "preklad, interpretácia alebo virtuálny stroj",
            "spúšťanie, návratový kód, štandardný vstup a výstup",
            "čítanie diagnostiky, dokumentácie a príkladov",
        ),
    },
    {
        "id": "syntax-values",
        "title": "Syntax, hodnoty a typy",
        "subtopics": (
            "tokeny, identifikátory, literály, escape sekvencie a komentáre",
            "primitívne hodnoty, nulová hodnota a booleovská logika",
            "premenné, konštanty, rozsah mien a životnosť",
            "implicitné a explicitné konverzie, presnosť a pretečenie",
            "operátory, priorita, asociativita a vedľajšie účinky",
        ),
    },
    {
        "id": "control-functions",
        "title": "Riadenie toku a funkcie",
        "subtopics": (
            "vetvenie, porovnanie, pattern matching alebo ekvivalent",
            "cykly, iterácia, prerušenie a pokračovanie",
            "definícia, volanie, parametre, návratové hodnoty a rekurzia",
            "lokálny stav, uzávierky alebo lambda výrazy podľa jazyka",
            "vstupné podmienky, invarianty a malé kontrakty funkcií",
        ),
    },
    {
        "id": "data-text",
        "title": "Dáta, kolekcie a text",
        "subtopics": (
            "sekvencie, mapy, množiny a vlastné dátové štruktúry",
            "indexovanie, iterovanie a hranice",
            "reťazce, Unicode, formátovanie a regulárne výrazy",
            "mutovateľnosť, kopírovanie, zdieľanie a porovnávanie",
            "čítanie a zápis textových a binárnych dát",
        ),
    },
    {
        "id": "abstraction",
        "title": "Abstrakcie a organizácia programu",
        "subtopics": (
            "vlastné typy, objekty alebo algebraické dátové typy",
            "rozhrania, polymorfizmus, kompozícia a dedenie tam, kde existuje",
            "moduly, balíky, menné priestory a viditeľnosť",
            "verejné rozhranie, dokumentácia a kompatibilita",
            "čitateľný návrh, idiomy a rozumné hranice abstrakcie",
        ),
    },
    {
        "id": "errors-resources",
        "title": "Chyby, zdroje a bezpečný stav",
        "subtopics": (
            "návratové stavy, výsledkové typy, výnimky alebo panika",
            "validácia vstupu, hranice a spracovanie zlyhaní",
            "správa pamäte, súborov, spojení a ostatných zdrojov",
            "vlastníctvo, čistenie po chybe a zotavenie",
            "bezpečnostné dôsledky vstupu, formátovania a závislostí",
        ),
    },
    {
        "id": "projects-tooling",
        "title": "Projekt, nástroje a spolupráca",
        "subtopics": (
            "štruktúra viac-súborového projektu a závislosti",
            "správca balíkov, verzovanie a reprodukovateľný build",
            "formátovanie, statická analýza a varovania",
            "testy, debugger, profiler a zmenšovanie chyby",
            "Git, licencia, README a vydanie malého projektu",
        ),
    },
    {
        "id": "standard-library",
        "title": "Štandardná knižnica a praktické rozhrania",
        "subtopics": (
            "základné typy, kolekcie, text, čas a matematika",
            "súbory, cesty, procesy a prostredie",
            "serializácia, sieťové rozhrania a bezpečné parsovanie",
            "kontrakty API: vstup, výstup, chyby, vlastníctvo a zložitosť",
            "rozdiel medzi štandardom, implementáciou a externým balíkom",
        ),
    },
    {
        "id": "reference",
        "title": "Rýchla referencia a zaujímavosti",
        "subtopics": (
            "slovník syntaxe, kľúčových slov, operátorov a literálov",
            "prehľad štandardnej knižnice podľa úloh",
            "časté omyly, neintuitívne pravidlá a hraničné prípady",
            "história, návrhové kompromisy a vývoj verzií jazyka",
            "porovnania s príbuznými jazykmi bez miešania ich pravidiel",
        ),
    },
)


LANGUAGE_SPECIALISATIONS: dict[str, dict[str, Any]] = {
    "c": {
        "title": "C",
        "summary": "Systémový jazyk so silným dôrazom na pamäť, rozhrania a presné pravidlá štandardu.",
        "profile": "compiled-procedural",
        "modules": (
            ("translation", "Preprocesor, preklad a linkovanie", ("preprocesor a hlavičky", "prekladové jednotky", "linker, ABI a symboly", "include guardy, static a extern")),
            ("memory", "Adresy, polia a dynamická pamäť", ("ukazovatele a NULL", "polia a aritmetika ukazovateľov", "struct, union, enum a bitové polia", "malloc, calloc, realloc, free a vlastníctvo")),
            ("c-semantics", "Presnosť pravidiel C", ("const, volatile, restrict a kvalifikátory", "zarovnanie, sizeof a presné celočíselné typy", "nedefinované, nešpecifikované a implementačne závislé správanie", "variadické funkcie, callbacky a funkčné ukazovatele")),
            ("c-quality", "Spoľahlivosť C", ("varovania prekladača", "sanitizéry", "bezpečné formátovanie a parsovanie", "testovanie hraníc a audit pamäte")),
        ),
    },
    "cpp": {
        "title": "C++",
        "summary": "Moderný viacparadigmový jazyk: hodnotová sémantika, RAII, knižnica a generické programovanie.",
        "profile": "compiled-multiparadigm",
        "modules": (
            ("cpp-values", "Hodnoty, životnosť a RAII", ("inicializácia a uniform initialization", "lvalue, rvalue a move", "konštruktory, deštruktory a pravidlá nula/päť", "smart pointery a výnimková bezpečnosť")),
            ("cpp-library", "Štandardná knižnica ako základ", ("string, vector, array, map, unordered_map a variant", "iterátory, ranges a algoritmy", "chrono, filesystem, format a numerické nástroje", "zložitosť a invalidácia iterátorov")),
            ("cpp-types", "Triedy, polymorfizmus a šablóny", ("zapuzdrenie, dedenie a virtual", "operátory a konverzie", "templates, concepts a deduction", "constexpr, metaprogramovanie a generické rozhranie")),
            ("cpp-build", "Moderný projekt C++", ("štandardy C++ a prenosnosť", "CMake a závislosti", "testy, sanitizéry a debugger", "vlákna, atomics a model pamäte")),
        ),
    },
    "python": {
        "title": "Python",
        "summary": "Dynamický jazyk s bohatou štandardnou knižnicou, dôrazom na dátový model a čitateľnosť.",
        "profile": "interpreted-dynamic",
        "modules": (
            ("python-data-model", "Objekty a dátový model", ("identita, rovnosť a mutovateľnosť", "list, tuple, dict, set a comprehensions", "iterátory, generátory a yield", "dunder metódy a protokoly")),
            ("python-functions", "Funkcionálne a deklaratívne nástroje", ("argumenty, *args a **kwargs", "closures a decorators", "lambda, map, filter a itertools", "context managers a with")),
            ("python-projects", "Balíky, typy a prostredia", ("import systém a packages", "venv, pip a pyproject.toml", "type hints, generics a mypy", "pytest, logging a dokumentácia")),
            ("python-concurrency", "Súbežnosť a rozhrania", ("threading a multiprocessing", "asyncio, await a tasks", "dataclasses, pathlib, json a HTTP", "výkon, profiling a GIL")),
        ),
    },
    "javascript": {
        "title": "JavaScript",
        "summary": "ECMAScript a jeho runtime model: dynamické hodnoty, objekty, moduly a asynchrónnosť.",
        "profile": "dynamic-event-loop",
        "modules": (
            ("js-runtime", "Runtime a hodnoty JavaScriptu", ("let, const, var, scope a hoisting", "coercion, truthiness, equality a NaN", "this, closures a strict mode", "prototypy, property descriptors a classes")),
            ("js-async", "Event loop a asynchrónnosť", ("call stack, task a microtask queue", "Promise, async/await a error propagation", "iterátory, generátory a async iterators", "cancellation, timers a resource cleanup")),
            ("js-modules", "Moduly, Node a webové hranice", ("ES modules a dynamic import", "npm, package.json a lockfile", "browser Web APIs verzus Node APIs", "JSON, fetch, streams a bezpečný vstup")),
            ("js-quality", "Robustný JavaScript", ("testy, debugger a source maps", "linting a formátovanie", "XSS, prototypové znečistenie a závislosti", "výkon, memory leaks a profiling")),
        ),
    },
    "typescript": {
        "title": "TypeScript",
        "summary": "Statická kontrola typov nad JavaScriptom; kurz predpokladá pevné základy JavaScriptu.",
        "profile": "typed-javascript",
        "availability": "planned",
        "modules": (
            ("ts-types", "Typový systém", ("inferencia, union, intersection a literal types", "narrowing a type guards", "object, tuple, readonly a index signatures", "nullability a compiler options")),
            ("ts-generics", "Generiká a typové programovanie", ("generic functions, classes a constraints", "conditional, mapped a template literal types", "utility types a infer", "variance, structural compatibility a overloads")),
            ("ts-projects", "Projekt a interoperabilita", ("tsconfig a emit", "declaration files", "ES modules a JavaScript interop", "testy, linting a bezpečná migrácia z JavaScriptu")),
        ),
    },
    "php": {
        "title": "PHP",
        "summary": "Serverový jazyk s praktickou prácou s HTTP, textom, dátami a moderným objektovým systémom.",
        "profile": "dynamic-server",
        "modules": (
            ("php-values", "Typy a každodenná syntax", ("arrays ako usporiadané mapy", "type juggling a strict_types", "strings, encoding a regulárne výrazy", "superglobals, CLI a webový kontext")),
            ("php-oop", "Objekty a modularita", ("class, interface, abstract a visibility", "traits, enums a attributes", "namespaces, autoloading a Composer", "exceptions, generators a fibers")),
            ("php-web", "Bezpečný webový základ", ("HTTP vstup, sessions a cookies", "validácia, escaping a XSS", "databázové parametre a SQL injection", "testy, logging a deployment konfigurácia")),
        ),
    },
    "csharp": {
        "title": "C#",
        "summary": "Staticky typovaný jazyk .NET s moderným typovým systémom, LINQ a asynchrónnym programovaním.",
        "profile": "managed-typed",
        "modules": (
            ("csharp-types", "Typový systém .NET", ("value a reference types", "nullable reference types", "records, enums, structs a pattern matching", "generics a constraints")),
            ("csharp-objects", "Delegáty, udalosti a LINQ", ("classes, interfaces a virtual dispatch", "delegates, events a lambdas", "IEnumerable, LINQ a deferred execution", "attributes, reflection a expression trees")),
            ("csharp-runtime", "Úlohy, zdroje a .NET projekt", ("exceptions a using/IDisposable", "Task, async/await a cancellation", "SDK project, NuGet a build", "testy, debugger, profiler a interoperabilita")),
        ),
    },
    "java": {
        "title": "Java",
        "summary": "Jazyk JVM s explicitnými triedami, bohatou knižnicou, generikami a súbežnosťou.",
        "profile": "jvm-typed",
        "modules": (
            ("java-object-model", "Triedy a typy", ("primitívne a referenčné hodnoty", "class, interface, inheritance a composition", "records, enums, sealed types a pattern matching", "generics, variance a type erasure")),
            ("java-library", "Knižnica a funkcionálny štýl", ("collections, equals/hashCode a ordering", "lambdas, functional interfaces a streams", "time, IO/NIO, serialization a HTTP", "modules, packages a visibility")),
            ("java-runtime", "JVM, chyby a súbežnosť", ("exceptions a try-with-resources", "threads, executors, locks a synchronization", "virtual threads a structured concurrency podľa verzie", "Gradle/Maven, testy, debugger a garbage collector")),
        ),
    },
    "go": {
        "title": "Go",
        "summary": "Kompilovaný jazyk so silnou štandardnou výbavou, rozhraniami, modulmi a jednoduchou súbežnosťou.",
        "profile": "compiled-concurrent",
        "modules": (
            ("go-data", "Typy a idiomy Go", ("arrays, slices, maps a strings", "structs, methods, interfaces a embedding", "zero values, pointers a escape analysis", "defer, panic, recover a explicit errors")),
            ("go-project", "Balíky a nástroje", ("packages, modules a go.mod", "go fmt, vet, doc, build a test", "table-driven tests, coverage a fuzzing", "context, logging a konfigurácia")),
            ("go-concurrency", "Gorutiny a komunikácia", ("goroutines, channels a select", "sync primitives, atomics a race detector", "cancellation a deadlines s context", "memory model a návrh súbežných rozhraní")),
        ),
    },
    "rust": {
        "title": "Rust",
        "summary": "Systémový jazyk, v ktorom bezpečnosť pamäte a súbežnosti vyplýva z vlastníctva a typov.",
        "profile": "compiled-memory-safe",
        "modules": (
            ("rust-ownership", "Vlastníctvo, požičiavanie a životnosti", ("move, copy a borrowing", "references, slices a lifetimes", "interior mutability a smart pointers", "čo zaručuje compiler a kde začína unsafe")),
            ("rust-types", "Dátové modelovanie", ("structs, enums a match", "Option, Result a error propagation", "traits, generics, associated types a bounds", "patterns, macros a type conversions")),
            ("rust-projects", "Cargo a robustný program", ("crates, modules, visibility a workspaces", "collections, iterators a closures", "tests, docs, clippy, rustfmt a benchmarky", "threads, async/await, Send/Sync a FFI")),
        ),
    },
    "ruby": {
        "title": "Ruby",
        "summary": "Dynamický objektový jazyk s blokmi, modulmi, silnou prácou s textom a bohatou kultúrou idiomov.",
        "profile": "dynamic-object",
        "modules": (
            ("ruby-object-model", "Objekty, správy a bloky", ("všetko je objekt, self a method lookup", "classes, modules, mixins a inheritance", "blocks, proc, lambda a closures", "Enumerable, iterators a collections")),
            ("ruby-dynamic", "Dynamika a text", ("symbols, strings, ranges a regular expressions", "metaprogramming a define_method", "exceptions, ensure a resources", "IO, files, JSON a time")),
            ("ruby-project", "Gems a kvalita", ("RubyGems, Bundler a Gemfile", "Rake a projektová štruktúra", "testovanie a dokumentácia", "bezpečnosť vstupu a závislostí")),
        ),
    },
    "perl": {
        "title": "Perl",
        "summary": "Praktický jazyk na text, regulárne výrazy, automatizáciu a moduly CPAN.",
        "profile": "dynamic-text",
        "modules": (
            ("perl-data", "Sigily, kontext a dáta", ("scalars, arrays, hashes a slices", "lexikálny scope, strict a warnings", "scalar, list a void context", "references a vnorené štruktúry")),
            ("perl-text", "Textový nástroj", ("quoting a interpolation", "regulárne výrazy, match, substitution a capture", "filehandles, streams a Unicode", "špeciálne premenné a argumenty príkazového riadku")),
            ("perl-project", "Subrutiny, moduly a CPAN", ("subroutines, prototypes a closures", "packages, modules a symbol tables", "object orientation a Moo/Moose ako ekosystém", "prove, Test::More, bezpečnosť a údržba staršieho kódu")),
        ),
    },
    "bash": {
        "title": "Bash",
        "summary": "Shell na bezpečnú automatizáciu, prácu s procesmi, textovými tokmi a operačným systémom.",
        "profile": "shell",
        "modules": (
            ("bash-evaluation", "Ako shell skutočne vyhodnocuje príkaz", ("tokenizácia, quoting a escape", "parameter, command, arithmetic, brace, tilde a filename expansion", "word splitting a globbing", "poradie expanzií a jeho bezpečnostné dôsledky")),
            ("bash-programs", "Skripty a procesy", ("premenné, arrays, positional parameters a getopts", "functions, control structures a test expressions", "exit status, set -e/-u/-o pipefail a traps", "subshells, pipelines, jobs, signals a process substitution")),
            ("bash-io", "Súbory, presmerovania a prenosnosť", ("stdin, stdout, stderr a file descriptors", "redirections, here documents a here strings", "find, xargs, sed, awk a bezpečné názvy súborov", "POSIX sh verzus Bash, ShellCheck, testovanie a quoting vstupov")),
        ),
    },
    "asm": {
        "title": "Assembler x86-64",
        "summary": "Základy programovania procesora x86-64, binárneho rozhrania a práce pod operačným systémom.",
        "profile": "assembly-x86-64",
        "modules": (
            ("asm-machine", "Model stroja", ("binárne a hexadecimálne hodnoty, endianita", "registre, flags, program counter a režimy", "sekcie programu, symboly a formát objektu", "adresovanie pamäte a efektívne adresy")),
            ("asm-instructions", "Inštrukcie a riadenie toku", ("presuny, aritmetika, logika a posuny", "porovnania, podmienené skoky a cykly", "stack, call, ret a calling convention", "makrá assemblera a prepojenie s C")),
            ("asm-system", "Systémový kód a diagnostika", ("syscalls a ABI Linuxu", "linkovanie, relokácie a objdump", "GDB, registre, disassembly a watchpointy", "SIMD, floating point, bezpečnosť pamäte a hranice architektúry")),
        ),
    },
}


EMBEDDED_CORE_MODULES: tuple[dict[str, Any], ...] = (
    {"id": "embedded-foundation", "title": "Elektronika a doska", "subtopics": ("napájanie, úrovne napätia, reset a ochrana pinov", "datasheet, reference manual, errata a schéma dosky", "meranie multimetrom, osciloskopom a logickým analyzátorom", "bezpečná práca s externým hardvérom")},
    {"id": "embedded-build", "title": "Firmvér od zdroja po obraz", "subtopics": ("startup kód, linker script, vector table a memory map", "build profile, ELF, HEX, BIN a UF2", "clock configuration, reset a boot sequence", "konfigurácia čipu, fuse/option bytes a ochrana čítania")},
    {"id": "embedded-memory", "title": "Procesor, registre a pamäť", "subtopics": ("CPU registre, stack a calling convention", "Flash, SRAM, EEPROM, cache a memory-mapped registre", "volatile, atomicita, zarovnanie a memory barriers", "meranie využitia Flash/RAM a hranice stacku")},
    {"id": "embedded-gpio", "title": "Piny a digitálne periférie", "subtopics": ("GPIO input/output, pull-up/pull-down a debouncing", "pin multiplexing a periférne priradenie", "externé prerušenie a wake-up", "LED, tlačidlo a bezpečný prvý hardvérový experiment")},
    {"id": "embedded-time", "title": "Čas, časovače a PWM", "subtopics": ("clock tree, prescaler, compare a overflow", "periodické úlohy, capture a meranie", "PWM, duty cycle a riadenie výkonu", "watchdog, reset a low-power režimy")},
    {"id": "embedded-analog", "title": "Analógové periférie", "subtopics": ("ADC, referenčné napätie, sampling a kalibrácia", "DAC, comparator a filtre", "šum, impedance zdroja a prevod jednotiek", "bezpečné čítanie senzora a validácia výsledku")},
    {"id": "embedded-buses", "title": "Komunikácia", "subtopics": ("UART a sériový monitor", "SPI, I2C, CAN, USB a ich rozdielne zlyhania", "časovanie, framing, buffering a checksum", "ovládač periférie, protokol a test s reálnym zariadením")},
    {"id": "embedded-concurrency", "title": "Prerušenia, DMA a súbežnosť", "subtopics": ("priorita, latencia a vektor prerušenia", "kritické sekcie, volatile a race conditions", "DMA, ring buffer a producer/consumer", "RTOS alebo bare metal scheduling podľa cieľa")},
    {"id": "embedded-debug", "title": "Zápis, ladenie a pozorovanie", "subtopics": ("programátor, bootloader, SWD/JTAG/ICSP/UPDI", "breakpoint, step, registre, pamäť a peripheral view", "sériový log, trace a meranie signálu", "obmedzenia debug režimu, errata a opakovateľný postup obnovy")},
    {"id": "embedded-reliability", "title": "Spoľahlivý výrobok", "subtopics": ("chybové stavy, watchdog a brown-out", "power budget, sleep a životnosť batérie", "bootloader, aktualizácia, secure boot a ochrana firmvéru", "hardvérové testy, výrobný test a dokumentácia zapojenia")},
)


FIRMWARE_TARGET_SPECIALISATIONS: dict[str, dict[str, Any]] = {
    "avr-atmega328p": {"title": "AVR / ATmega328P", "architecture": "AVR 8-bit", "modules": (("avr-core", "AVR jadro a pamäť", ("pracovné registre, SREG a stack", "Flash, SRAM, EEPROM a boot section", "adresovacie režimy a AVR inštrukcie")), ("avr-tools", "AVR nástroje", ("avr-gcc, avr-libc a avrdude", "ISP, UART bootloader a fuses", "debugWIRE alebo UPDI podľa konkrétneho čipu")))},
    "pic16f18855": {"title": "Microchip PIC16", "architecture": "PIC 8-bit", "modules": (("pic16-core", "PIC16 architektúra", ("bankovaná pamäť, W register a hardware stack", "config words, program Flash, RAM a EEPROM", "PPS, CLC a periférne prerušenia")), ("pic16-tools", "MPLAB a ICSP", ("MPLAB X, XC8 a MCC", "ICSP, PICkit/ICD a konfigurácia", "limity in-circuit debug režimu")))},
    "dspic33ck": {"title": "Microchip dsPIC33", "architecture": "dsPIC 16-bit", "modules": (("dspic-core", "dsPIC a riadenie v reálnom čase", ("16-bit jadro, DSP engine a fixed-point", "PWM, ADC a motor-control periférie", "interrupt latency a deterministické slučky")), ("dspic-tools", "XC16 a programovanie", ("MPLAB X, XC16 a linker", "ICSP a MPLAB IPE", "debug a meranie časovania")))},
    "pic32mx": {"title": "Microchip PIC32MX", "architecture": "MIPS32", "modules": (("pic32-core", "PIC32 systém", ("MIPS32 jadro, cache a memory map", "interrupt controller a DMA", "Flash, boot a konfigurácia")), ("pic32-tools", "XC32 a MPLAB", ("MPLAB X, XC32 a Harmony", "ICSP/JTAG a MPLAB IPE", "periférie UART, SPI, I2C, ADC a timer")))},
    "samd21": {"title": "Microchip SAM D21", "architecture": "ARM Cortex-M0+", "modules": (("sam-core", "Cortex-M0+ a SAM", ("CMSIS, NVIC, vector table a SysTick", "clock system, GCLK a PM", "SERCOM, EIC, TC/TCC a ADC")), ("sam-tools", "SAM vývoj", ("ARM GNU, MPLAB X a Harmony", "SWD, J-Link alebo Atmel-ICE", "startup, linker script a periférne registre")))},
    "stm32f103": {"title": "STM32F103", "architecture": "ARM Cortex-M3", "modules": (("stm32-core", "STM32 a Cortex-M", ("CMSIS, NVIC, exception model a memory map", "RCC clock tree, GPIO, EXTI a timers", "ADC, DMA, USART, SPI a I2C")), ("stm32-tools", "Cube a SWD", ("STM32CubeMX, HAL, LL a kód generovaný nástrojom", "ST-Link, OpenOCD, GDB a SWD", "option bytes, flashovanie a debug konfigurácia")))},
    "esp32": {"title": "Espressif ESP32", "architecture": "Xtensa alebo RISC-V podľa čipu", "modules": (("esp-runtime", "ESP-IDF a systém", ("component model, CMake a menuconfig", "FreeRTOS tasks, queues, event loop a watchdog", "partitions, NVS, heap a logovanie")), ("esp-connectivity", "Sieť a zápis", ("GPIO, I2C, SPI, UART, ADC a PWM", "Wi-Fi, Bluetooth, HTTP a bezpečnosť poverení", "esptool, serial monitor, JTAG a OTA aktualizácia")))},
    "rp2040": {"title": "Raspberry Pi RP2040", "architecture": "ARM Cortex-M0+", "modules": (("rp2040-core", "RP2040 a Pico SDK", ("dual-core, IRQ a multicore synchronizácia", "PIO, DMA, timers a PWM", "GPIO, ADC, UART, SPI, I2C a USB")), ("rp2040-tools", "UF2, SWD a Pico projekt", ("CMake a Pico SDK", "BOOTSEL, UF2, picotool a USB serial", "Debug Probe, OpenOCD, GDB a SWD")))},
}


VISUALIZATION_POLICY: dict[str, tuple[str, ...] | str] = {
    "principle": "Dynamická vizualizácia patrí iba tam, kde objasní stav, ktorý nie je priamo viditeľný v zdrojovom kóde, alebo postupnosť udalostí v čase.",
    "requirements": (
        "Každý krok musí mať jasný vzťah ku konkrétnemu riadku kódu alebo údaju.",
        "Používateľ môže postup spustiť, pozastaviť, vykonať po krokoch, vrátiť späť a obnoviť.",
        "Rovnaké vysvetlenie musí mať textovú a tabuľkovú alternatívu bez pohybu.",
        "Vizualizácia sa nesmie spúšťať sama a musí rešpektovať preferenciu obmedzeného pohybu.",
        "Model musí pomenovať zjednodušenia; nesmie predstierať presné správanie runtime alebo hardvéru, ktoré nezobrazuje.",
    ),
    "notUsefulFor": (
        "samotný zoznam kľúčových slov, funkcií alebo parametrov API",
        "bežnú deklaráciu, ktorej význam sa dá vysvetliť krátkym príkladom",
        "dekoratívny pohyb bez novej informácie o stave alebo čase",
    ),
}


# Každý kandidát je zámer lekcie, nie automatický prvok rozhrania. Rozhranie ho
# zobrazí len pri danej téme a vždy spolu s neanimovaným ekvivalentom.
LANGUAGE_VISUALIZATION_CANDIDATES: dict[str, tuple[dict[str, str], ...]] = {
    "c": (
        {"id": "c-memory-lifetime", "moduleId": "memory", "kind": "memory-state", "title": "Adresa, pole a životnosť pamäte", "purpose": "Ukáže vzťah medzi ukazovateľom, poľom, stackom, heapom a volaním free."},
        {"id": "c-call-stack", "moduleId": "control-functions", "kind": "call-stack", "title": "Volanie funkcií a rekurzia", "purpose": "Krokovo ukáže parametre, lokálne premenné a návrat z vnorených volaní."},
    ),
    "cpp": (
        {"id": "cpp-raii-lifetime", "moduleId": "cpp-values", "kind": "resource-lifetime", "title": "RAII a presuny", "purpose": "Zobrazí konštrukciu, presun, vlastníctvo zdroja a deterministické volanie deštruktora."},
        {"id": "cpp-iterator-invalidation", "moduleId": "cpp-library", "kind": "collection-state", "title": "Zmena kontajnera a iterátory", "purpose": "Pomôže pochopiť, kedy operácia nad kontajnerom zneplatní iterátor alebo referenciu."},
    ),
    "python": (
        {"id": "python-object-references", "moduleId": "python-data-model", "kind": "object-reference", "title": "Objekty, mená a mutovateľnosť", "purpose": "Ukáže rozdiel medzi priradením mena, zdieľanou referenciou, kópiou a zmenou objektu."},
        {"id": "python-generator-flow", "moduleId": "python-data-model", "kind": "execution-flow", "title": "Generátor po krokoch", "purpose": "Ukáže body yield, pozastavenie funkcie a postupné vyžiadanie ďalšej hodnoty."},
    ),
    "javascript": (
        {"id": "js-event-loop", "moduleId": "js-async", "kind": "event-loop", "title": "Event loop, tasky a microtasky", "purpose": "Zobrazí call stack, frontu úloh a microtask queue v poradí, v akom sa vykonajú."},
        {"id": "js-scope-closures", "moduleId": "js-runtime", "kind": "scope-state", "title": "Scope a closure", "purpose": "Ukáže, ktoré mená sú po návrate funkcie stále zachytené uzávierkou."},
    ),
    "typescript": (
        {"id": "ts-narrowing", "moduleId": "ts-types", "kind": "type-state", "title": "Zužovanie typu", "purpose": "Krokovo ukáže, ako podmienka alebo type guard zmení bezpečne dostupné vlastnosti hodnoty."},
    ),
    "php": (
        {"id": "php-request-boundary", "moduleId": "php-web", "kind": "request-lifecycle", "title": "Cesta HTTP požiadavky", "purpose": "Ukáže hranicu medzi vstupom požiadavky, validáciou, databázovým parametrom a bezpečným výstupom."},
    ),
    "csharp": (
        {"id": "csharp-async-task", "moduleId": "csharp-runtime", "kind": "async-timeline", "title": "Task, await a zrušenie", "purpose": "Rozlíši čakanie na Task, pokračovanie metódy, chybu a zrušenie operácie."},
        {"id": "csharp-linq-deferred", "moduleId": "csharp-objects", "kind": "execution-flow", "title": "Odložené LINQ", "purpose": "Ukáže rozdiel medzi vytvorením dotazu a jeho vykonaním pri iterácii."},
    ),
    "java": (
        {"id": "java-thread-synchronization", "moduleId": "java-runtime", "kind": "concurrency-timeline", "title": "Vlákna a synchronizácia", "purpose": "Ukáže pretekanie, kritickú sekciu a poradie udalostí pri zdieľanom stave."},
        {"id": "java-stream-pipeline", "moduleId": "java-library", "kind": "data-pipeline", "title": "Stream pipeline", "purpose": "Zobrazí, ako hodnoty prechádzajú cez filter, map a terminálnu operáciu."},
    ),
    "go": (
        {"id": "go-channel-flow", "moduleId": "go-concurrency", "kind": "channel-timeline", "title": "Gorutiny a kanály", "purpose": "Ukáže blokovanie, odoslanie, prijatie, select a zrušenie pomocou contextu."},
    ),
    "rust": (
        {"id": "rust-ownership", "moduleId": "rust-ownership", "kind": "ownership-lifetime", "title": "Vlastníctvo a požičiavanie", "purpose": "Ukáže presun hodnoty, platnosť referencií a konflikt medzi mutovateľným a nemutovateľným požičaním."},
        {"id": "rust-result-flow", "moduleId": "rust-types", "kind": "execution-flow", "title": "Option, Result a operátor ?", "purpose": "Krokovo ukáže vetvenie úspešnej a chybovej cesty bez skrytých výnimiek."},
    ),
    "ruby": (
        {"id": "ruby-method-lookup", "moduleId": "ruby-object-model", "kind": "lookup-flow", "title": "Hľadanie metódy a mixiny", "purpose": "Ukáže poradie, v akom Ruby hľadá metódu cez triedu, moduly a predkov."},
    ),
    "perl": (
        {"id": "perl-context", "moduleId": "perl-data", "kind": "evaluation-state", "title": "Skalárny a zoznamový kontext", "purpose": "Ukáže, prečo ten istý výraz vracia inú hodnotu podľa miesta použitia."},
        {"id": "perl-regex", "moduleId": "perl-text", "kind": "pattern-state", "title": "Regulárny výraz po krokoch", "purpose": "Zobrazí postup matchovania, captures a substitúciu na krátkom kontrolovanom vstupe."},
    ),
    "bash": (
        {"id": "bash-expansion-order", "moduleId": "bash-evaluation", "kind": "command-transformation", "title": "Ako vznikne príkaz", "purpose": "Ukáže poradie expanzií, quotingu, word splittingu, globbingu a výsledné argumenty procesu."},
        {"id": "bash-pipeline-fds", "moduleId": "bash-io", "kind": "stream-flow", "title": "Pipelines a presmerovania", "purpose": "Zobrazí, kam tečú stdin, stdout, stderr a jednotlivé file descriptory."},
    ),
    "asm": (
        {"id": "asm-registers-flags", "moduleId": "asm-machine", "kind": "cpu-state", "title": "Registre, pamäť a príznaky", "purpose": "Po inštrukciách ukáže zmenu registrov, vybraných buniek pamäte a flagov."},
        {"id": "asm-call-stack", "moduleId": "asm-instructions", "kind": "call-stack", "title": "call, ret a ABI", "purpose": "Ukáže návratovú adresu, stack frame a odovzdanie argumentov medzi assemblerom a C."},
    ),
}


EMBEDDED_VISUALIZATION_CANDIDATES: tuple[dict[str, str], ...] = (
    {"id": "embedded-build-image", "moduleId": "embedded-build", "kind": "build-artifact-flow", "title": "Od zdrojového kódu po obraz firmvéru", "purpose": "Ukáže úlohu prekladu, linkovania a formátov ELF, HEX, BIN alebo UF2 pred zápisom do čipu."},
    {"id": "embedded-memory-map", "moduleId": "embedded-memory", "kind": "memory-map", "title": "Mapa pamäte a periférne registre", "purpose": "Ukáže hranice Flash, SRAM, stacku a memory-mapped registrov konkrétneho cieľa."},
    {"id": "embedded-gpio-signal", "moduleId": "embedded-gpio", "kind": "pin-state", "title": "Pin, pull-up a tlačidlo", "purpose": "Ukáže logickú úroveň pinu, plávajúci vstup, pull rezistor a odskakovanie kontaktu."},
    {"id": "embedded-timer-pwm", "moduleId": "embedded-time", "kind": "signal-timeline", "title": "Časovač a PWM", "purpose": "Zobrazí clock, prescaler, čítač, compare register a výsledný PWM priebeh."},
    {"id": "embedded-adc-sampling", "moduleId": "embedded-analog", "kind": "sampling-flow", "title": "Vzorkovanie ADC", "purpose": "Ukáže okamih vzorkovania, referenciu, kvantizáciu a prevod na fyzikálnu jednotku."},
    {"id": "embedded-bus-waveform", "moduleId": "embedded-buses", "kind": "bus-waveform", "title": "Rámec UART, SPI alebo I2C", "purpose": "Ukáže bity, hodiny, adresu, ACK a typické zlyhanie komunikácie na jednej zbernici."},
    {"id": "embedded-interrupt-dma", "moduleId": "embedded-concurrency", "kind": "event-timeline", "title": "Prerušenie, DMA a hlavná slučka", "purpose": "Ukáže prioritu udalostí, kritickú sekciu a presun dát bez blokovania CPU."},
    {"id": "embedded-debug-cycle", "moduleId": "embedded-debug", "kind": "program-debug-cycle", "title": "Zápis a ladenie čipu", "purpose": "Ukáže cestu obrazu firmvéru cez programátor po breakpoint, registre a opakovateľné pozorovanie chyby."},
)


FIRMWARE_TARGET_VISUALIZATION_CANDIDATES: dict[str, tuple[dict[str, str], ...]] = {
    "avr-atmega328p": ({"id": "avr-register-stack", "moduleId": "avr-core", "kind": "cpu-state", "title": "AVR registre, SREG a stack", "purpose": "Ukáže 8-bitové registre, príznaky a rámec volania na ATmega328P."},),
    "pic16f18855": ({"id": "pic16-banks-pps", "moduleId": "pic16-core", "kind": "peripheral-routing", "title": "Banky pamäte a PPS", "purpose": "Ukáže prepnutie pamäťovej banky a priradenie periférie ku konkrétnemu pinu."},),
    "dspic33ck": ({"id": "dspic-pwm-adc", "moduleId": "dspic-core", "kind": "signal-timeline", "title": "PWM, ADC a riadiaca slučka", "purpose": "Ukáže synchronizáciu vzorkovania ADC s PWM pri regulácii v reálnom čase."},),
    "pic32mx": ({"id": "pic32-interrupt-dma", "moduleId": "pic32-core", "kind": "event-timeline", "title": "PIC32 prerušenie a DMA", "purpose": "Ukáže cestu udalosti periférie cez interrupt controller a DMA do pamäte."},),
    "samd21": ({"id": "samd21-clock-tree", "moduleId": "sam-core", "kind": "clock-tree", "title": "SAM D21 clock tree", "purpose": "Ukáže zdroj hodinového signálu, GCLK a dôsledok voľby frekvencie pre periférie."},),
    "stm32f103": ({"id": "stm32f103-clock-dma", "moduleId": "stm32-core", "kind": "clock-tree", "title": "RCC, NVIC a DMA", "purpose": "Spojí clock tree STM32F103 s obsluhou prerušenia a presunom dát pomocou DMA."},),
    "esp32": ({"id": "esp32-freertos-events", "moduleId": "esp-runtime", "kind": "rtos-timeline", "title": "FreeRTOS tasky a event loop", "purpose": "Ukáže frontu udalostí, blokovanie taskov, watchdog a hranice zdieľaného stavu."},),
    "rp2040": ({"id": "rp2040-pio-dma", "moduleId": "rp2040-core", "kind": "state-machine-flow", "title": "PIO, DMA a dvojjadro", "purpose": "Ukáže, ako PIO state machine a DMA obslúžia signál bez neustáleho zásahu jadra CPU."},),
}


def _curriculum_visualizations(
    candidates: tuple[dict[str, str], ...], module_ids: set[str]
) -> list[dict[str, str]]:
    """Overí väzbu na osnovu a vráti nezdieľané kandidáty vizualizácií."""
    visualizations = [deepcopy(candidate) for candidate in candidates]
    candidate_ids = [candidate["id"] for candidate in visualizations]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("Vizualizačné kandidáty musia mať jedinečné identifikátory.")
    for candidate in visualizations:
        if candidate["moduleId"] not in module_ids:
            raise ValueError(f"Vizualizácia {candidate['id']!r} odkazuje na neznámy modul.")
        if not all(candidate.get(key) for key in ("kind", "title", "purpose")):
            raise ValueError(f"Vizualizácia {candidate['id']!r} nemá úplný popis.")
    return visualizations


def language_curriculum(code: str) -> dict[str, Any]:
    """Vráti úplnú osnovu jedného jazyka bez zdieľaných mutovateľných dát."""
    profile = LANGUAGE_SPECIALISATIONS.get(code)
    if not profile:
        raise KeyError(f"Chýba kurikulum pre jazyk {code!r}.")
    modules = [deepcopy(module) for module in COMMON_LANGUAGE_MODULES]
    modules.extend(
        {"id": module_id, "title": title, "subtopics": subtopics}
        for module_id, title, subtopics in profile["modules"]
    )
    visualizations = _curriculum_visualizations(
        LANGUAGE_VISUALIZATION_CANDIDATES[code], {module["id"] for module in modules}
    )
    return {
        "code": code,
        "title": profile["title"],
        "summary": profile["summary"],
        "profile": profile["profile"],
        "availability": profile.get("availability", "supported"),
        "modules": modules,
        "visualizationPolicy": deepcopy(VISUALIZATION_POLICY),
        "visualizations": visualizations,
    }


def firmware_curriculum(target_id: str) -> dict[str, Any]:
    """Vráti spoločný základ vstavaných systémov a prekrývanie konkrétneho cieľa."""
    profile = FIRMWARE_TARGET_SPECIALISATIONS.get(target_id)
    if not profile:
        raise KeyError(f"Chýba kurikulum pre firmvérový cieľ {target_id!r}.")
    modules = [deepcopy(module) for module in EMBEDDED_CORE_MODULES]
    modules.extend(
        {"id": module_id, "title": title, "subtopics": subtopics}
        for module_id, title, subtopics in profile["modules"]
    )
    visualizations = _curriculum_visualizations(
        EMBEDDED_VISUALIZATION_CANDIDATES + FIRMWARE_TARGET_VISUALIZATION_CANDIDATES[target_id],
        {module["id"] for module in modules},
    )
    return {
        "targetId": target_id,
        "title": profile["title"],
        "architecture": profile["architecture"],
        "modules": modules,
        "visualizationPolicy": deepcopy(VISUALIZATION_POLICY),
        "visualizations": visualizations,
    }


def missing_language_curricula(language_codes: set[str] | tuple[str, ...] | list[str]) -> set[str]:
    return {code for code in language_codes if code not in LANGUAGE_SPECIALISATIONS}


def missing_firmware_curricula(target_ids: set[str] | tuple[str, ...] | list[str]) -> set[str]:
    return {target_id for target_id in target_ids if target_id not in FIRMWARE_TARGET_SPECIALISATIONS}
