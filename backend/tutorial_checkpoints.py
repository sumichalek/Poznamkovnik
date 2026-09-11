"""Krátke kontrolné otázky nad konkrétnymi lekciami učebnice.

Správna voľba a spätná väzba zostávajú na serveri, kým používateľ neodpovie.
Otázky sú malé overenia princípu, nie hodnotený test ani náhrada praktického
cvičenia v skúšobni.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


TUTORIAL_CHECKPOINTS: dict[str, tuple[dict[str, Any], ...]] = {
    "c": (
        {
            "id": "c-main-entry",
            "prompt": "Čo v bežnom konzolovom programe znamená návratová hodnota 0 z main?",
            "options": (
                ("a", "Program nevypísal žiadny text."),
                ("b", "Program skončil úspešne a odovzdal túto informáciu prostrediu."),
                ("c", "Prekladač odstráni všetky lokálne premenné."),
            ),
            "correctOptionId": "b",
            "correctFeedback": "Správne. Návratový kód je dohoda programu s prostredím, nie výpis určený pre používateľa.",
            "incorrectFeedback": "Návratový kód oznamuje výsledok prostrediu. Hodnota 0 sa konvenčne používa pre úspešné skončenie.",
        },
        {
            "id": "c-value-conversion",
            "prompt": "Kedy je pri konverzii celočíselnej hodnoty potrebné najprv overiť rozsah?",
            "options": (
                ("a", "Vždy, keď sa môže cieľový typ zmestiť do zdrojového typu."),
                ("b", "Len pri konverzii z int na long."),
                ("c", "Keď by cieľový typ mohol danú hodnotu skrátiť, zmeniť znamienko alebo inak zmeniť jej význam."),
            ),
            "correctOptionId": "c",
            "correctFeedback": "Presne tak. Bezpečnosť konverzie závisí od konkrétnej hodnoty aj rozsahu oboch typov.",
            "incorrectFeedback": "Nejde o názov typu, ale o rozsah aktuálnej hodnoty a o to, či sa pri konverzii nestratí význam.",
        },
        {
            "id": "c-short-circuit",
            "prompt": "Prečo je podmienka pointer != NULL && pointer->count > 0 bezpečnejšia než opačné poradie?",
            "options": (
                ("a", "&& vyhodnocuje najprv ľavú časť a pri nepravde pravú už nečíta."),
                ("b", "Operátor && automaticky vytvorí objekt pre NULL ukazovateľ."),
                ("c", "Poradie častí podmienky v C nemá žiadny vplyv."),
            ),
            "correctOptionId": "a",
            "correctFeedback": "Áno. Skrátené vyhodnocovanie chráni dereferencovanie na pravej strane.",
            "incorrectFeedback": "&& vyhodnocuje zľava doprava a zastaví sa pri prvej nepravdivej časti. Preto musí byť kontrola ukazovateľa vľavo.",
        },
        {
            "id": "c-loop-invariant",
            "prompt": "Čo najlepšie opisuje invariant cyklu?",
            "options": (
                ("a", "Hodnotu, ktorú cyklus nesmie nikdy zmeniť v pamäti."),
                ("b", "Tvrdenie o stave programu, ktoré platí pred aj po každom priechode cyklom."),
                ("c", "Počet iterácií, ktorý musí byť vždy konštantný."),
            ),
            "correctOptionId": "b",
            "correctFeedback": "Správne. Invariant je pomôcka na návrh aj kontrolu správnosti cyklu.",
            "incorrectFeedback": "Invariant nemusí byť nemenná premenná ani pevný počet krokov. Je to vlastnosť stavu, ktorú cyklus zachováva.",
        },
        {
            "id": "c-pass-by-value",
            "prompt": "Ako funkcia v C zmení objekt, ktorý patrí volajúcej funkcii?",
            "options": (
                ("a", "Prijme ukazovateľ na objekt a po overení ho dereferencuje."),
                ("b", "Každý parameter sa v C automaticky odovzdáva referenciou."),
                ("c", "Zmení kópiu obyčajného parametra; volajúci to vždy uvidí."),
            ),
            "correctOptionId": "a",
            "correctFeedback": "Správne. Aj ukazovateľ sa odovzdáva hodnotou, ale táto hodnota označuje objekt volajúceho.",
            "incorrectFeedback": "C odovzdáva všetky parametre hodnotou. Na zmenu cudzieho objektu funkcia potrebuje dostať jeho adresu.",
        },
        {
            "id": "c-object-lifetime",
            "prompt": "Čo platí pre ukazovateľ vrátený na obyčajnú lokálnu premennú funkcie?",
            "options": (
                ("a", "Je platný až do ďalšieho volania tej istej funkcie."),
                ("b", "Po návrate funkcie už nesmie byť dereferencovaný, pretože objekt zanikol."),
                ("c", "Stane sa automaticky ukazovateľom na globálnu premennú."),
            ),
            "correctOptionId": "b",
            "correctFeedback": "Správne. Meno aj objekt s automatickou životnosťou patria do rámca daného volania.",
            "incorrectFeedback": "Lokálny objekt s automatickou životnosťou zaniká pri odchode z bloku funkcie. Ukazovateľ po ňom zostane neplatný.",
        },
        {
            "id": "c-array-bound",
            "prompt": "Pole s n prvkami má platné indexy v ktorom intervale?",
            "options": (
                ("a", "Od 0 po n - 1 vrátane."),
                ("b", "Od 1 po n vrátane."),
                ("c", "Od 0 po n vrátane."),
            ),
            "correctOptionId": "a",
            "correctFeedback": "Správne. Index n je už jeden krok za posledným prvkom a nesmie sa dereferencovať.",
            "incorrectFeedback": "Prvý prvok poľa má index 0. Pri n prvkoch je posledný platný index n - 1.",
        },
        {
            "id": "c-pointer-write",
            "prompt": "Čo mení príkaz *number = 12;, ak number ukazuje na platný int?",
            "options": (
                ("a", "Hodnotu samotného ukazovateľa number."),
                ("b", "Objekt typu int, na ktorý number ukazuje."),
                ("c", "Typ všetkých premenných pomenovaných number."),
            ),
            "correctOptionId": "b",
            "correctFeedback": "Áno. Dereferencovanie *number pristupuje k označenému objektu, nie k adrese uloženej v number.",
            "incorrectFeedback": "Hodnotu ukazovateľa by menilo number = ... . Zápis *number zapisuje do objektu na označenej adrese.",
        },
        {
            "id": "c-string-terminator",
            "prompt": "Koľko viditeľných znakov sa bezpečne zmestí do char text[8], ak má obsahovať C reťazec?",
            "options": (
                ("a", "8, pretože pole má osem buniek."),
                ("b", "7, pretože posledná bunka patrí znaku \\0."),
                ("c", "6, pretože dve bunky vždy rezervuje kompilátor."),
            ),
            "correctOptionId": "b",
            "correctFeedback": "Správne. C reťazec potrebuje za viditeľným textom ešte koncový nulový znak.",
            "incorrectFeedback": "Jedna bunka poľa musí niesť koncový nulový znak \\0. Preto do poľa veľkosti 8 patrí najviac 7 viditeľných znakov.",
        },
        {
            "id": "c-struct-enum",
            "prompt": "Kedy je vhodnejšie použiť enum než voľné celočíselné konštanty?",
            "options": (
                ("a", "Keď modeluješ malú pomenovanú množinu stavov, napríklad režim zariadenia."),
                ("b", "Keď potrebuješ dynamicky alokovať pamäť."),
                ("c", "Keď chceš uložiť text bez koncového nulového znaku."),
            ),
            "correctOptionId": "a",
            "correctFeedback": "Správne. enum dá stavom mená a zlepšuje čitateľnosť rozhraní.",
            "incorrectFeedback": "enum pomenúva malú množinu celočíselných stavov. Neslúži na alokáciu ani ukladanie textu.",
        },
        {
            "id": "c-bit-mask",
            "prompt": "Ktorý výraz zapne príznak READY bez zmeny ostatných bitov vo flags?",
            "options": (
                ("a", "flags &= READY;"),
                ("b", "flags |= READY;"),
                ("c", "flags = !READY;"),
            ),
            "correctOptionId": "b",
            "correctFeedback": "Správne. Bitové OR pridá bity masky READY a ostatné bity ponechá.",
            "incorrectFeedback": "Bitové OR s maskou zapína vybrané bity. &= by naopak ponechalo iba bity, ktoré sú už v maske.",
        },
        {
            "id": "c-realloc-temp",
            "prompt": "Prečo pri realloc s nenulovou požadovanou veľkosťou najprv uložíme výsledok do dočasného ukazovateľa?",
            "options": (
                ("a", "realloc vždy vynuluje pôvodný blok."),
                ("b", "Pri neúspechu môže vrátiť NULL, pričom pôvodný blok stále existuje."),
                ("c", "Dočasná premenná mení typ bloku na bezpečný."),
            ),
            "correctOptionId": "b",
            "correctFeedback": "Správne. Pri priamom priradení by sa mohla stratiť jediná adresa pôvodného platného bloku.",
            "incorrectFeedback": "Pri nenulovej požiadavke môže realloc zlyhať a vrátiť NULL. Pôvodná alokácia vtedy ostáva platná, preto jej adresu nesmieš prepísať bez kontroly.",
        },
        {
            "id": "c-atomic-increment",
            "prompt": "Dve vlákna zvyšujú spoločné atomic_uint počítadlo. Ktorý postup vykoná každé zvýšenie ako jednu nedeliteľnú operáciu?",
            "options": (
                ("a", "Najprv atomic_load, potom pripočítať 1 a nakoniec atomic_store."),
                ("b", "Nahradiť atomic_uint typom volatile unsigned int a použiť counter++."),
                ("c", "Použiť atomic_fetch_add(&counter, 1U)."),
            ),
            "correctOptionId": "c",
            "correctFeedback": "Správne. atomic_fetch_add spája načítanie a zvýšenie do jednej operácie a vracia predchádzajúcu hodnotu.",
            "incorrectFeedback": "Samostatné načítanie a uloženie môže prepísať zvýšenie druhého vlákna. volatile tento problém nerieši; potrebná je spojená atomická operácia.",
        },
        {
            "id": "c-macro-evaluation",
            "prompt": "Makro SQUARE(x) je definované ako ((x) * (x)). Čo platí o volaní SQUARE(next++)?",
            "options": (
                ("a", "Zátvorky zaručia jeden výpočet argumentu, rovnako ako pri funkcii."),
                ("b", "next sa zmení dvakrát bez potrebného usporiadania; výraz má nedefinované správanie."),
                ("c", "Preprocesor najprv vypočíta next++ a až potom vloží jeho číselný výsledok."),
            ),
            "correctOptionId": "b",
            "correctFeedback": "Správne. Rozvinutie obsahuje next++ dvakrát. Zátvorky riešia zoskupenie, nie počet vedľajších účinkov. Vhodná funkcia dostane hodnotu tohto argumentu iba raz.",
            "incorrectFeedback": "Preprocesor dosadzuje zápis, nie vypočítanú hodnotu. Vznikne ((next++) * (next++)); ďalšie zátvorky chybu neopravia. Použi funkciu alebo najprv samostatne získaj hodnotu.",
        },
        {
            "id": "c-declaration-definition",
            "prompt": "Čo rozlišuje deklaráciu funkcie v hlavičke od jej definície v zdrojovom súbore?",
            "options": (
                ("a", "Deklarácia opisuje rozhranie; definícia obsahuje telo funkcie."),
                ("b", "Deklarácia je vždy rýchlejšia pri behu programu."),
                ("c", "Definícia sa nesmie objaviť v zdrojovom súbore."),
            ),
            "correctOptionId": "a",
            "correctFeedback": "Správne. Hlavička umožní ostatným prekladovým jednotkám funkciu volať so správnym rozhraním.",
            "incorrectFeedback": "Deklarácia hovorí, ako sa funkcia používa. Definícia dodáva vykonateľné telo, ktoré linker spojí s volaniami.",
        },
        {
            "id": "c-input-boundary",
            "prompt": "Ktorý postup bezpečne oddeľuje textový vstup od logiky programu?",
            "options": (
                ("a", "Načítať riadok do obmedzeného poľa, overiť výsledok a až potom ho parsovať."),
                ("b", "Zapísať vstup priamo do ľubovoľného ukazovateľa."),
                ("c", "Vynechať kontrolu chýb, ak vstup pochádza od používateľa."),
            ),
            "correctOptionId": "a",
            "correctFeedback": "Správne. Hranica vstupu má mať obmedzenú veľkosť, kontrolu chyby a oddelené parsovanie.",
            "incorrectFeedback": "Vstup je nedôveryhodný. Najprv ho načítaj do známeho priestoru, over výsledok a až potom premeň na doménovú hodnotu.",
        },
        {
            "id": "c-error-status",
            "prompt": "Prečo by návratová hodnota funkcie nemala zamieňať chybu s bežným výsledkom?",
            "options": (
                ("a", "Pretože prekladač potom automaticky vypne varovania."),
                ("b", "Volajúci musí vedieť jednoznačne rozoznať úspešný výsledok od zlyhania."),
                ("c", "Chyby sa v C nesmú oznamovať žiadnym spôsobom."),
            ),
            "correctOptionId": "b",
            "correctFeedback": "Správne. Jasný kontrakt výsledku alebo stavu dá volajúcemu možnosť chybu spracovať.",
            "incorrectFeedback": "Ak jedna hodnota znamená zároveň výsledok aj chybu, volajúci nevie spoľahlivo rozhodnúť, čo sa stalo.",
        },
        {
            "id": "c-check-before-access",
            "prompt": "Program najprv načíta values[index] a až potom odmietne index >= count. Čo treba opraviť?",
            "options": (
                ("a", "Zapnúť optimalizáciu, aby prekladač dodatočne opravil poradie."),
                ("b", "Overiť platnosť indexu pred čítaním; neskoršie odmietnutie už neodstráni neplatný prístup."),
                ("c", "Nič, ak pri skúške program nespadol."),
            ),
            "correctOptionId": "b",
            "correctFeedback": "Správne. Najprv over nezápornosť a hranicu count, až potom čítaj prvok. Pri neplatnom prístupe už neskoršie if nepomôže.",
            "incorrectFeedback": "Kontrola musí predchádzať operácii, ktorú chráni. Úspešný beh ani optimalizácia nie sú dôkazom platného prístupu do poľa.",
        },
        {
            "id": "c-boundary-test",
            "prompt": "Ktorý test najlepšie dopĺňa bežný vstup pre funkciu, ktorá pracuje s poľom?",
            "options": (
                ("a", "Prázdne pole a hranice indexov, napríklad prvý a posledný platný prvok."),
                ("b", "Len ďalšie pole rovnakej veľkosti s inými náhodnými hodnotami."),
                ("c", "Test netreba, ak program prešiel prekladom bez varovania."),
            ),
            "correctOptionId": "a",
            "correctFeedback": "Správne. Hraničné prípady odhaľujú omyly v podmienkach a indexovaní, ktoré bežné dáta ľahko zakryjú.",
            "incorrectFeedback": "Bezvarovný preklad nie je dôkaz správnosti. Pri poli sú prázdny vstup a hranice indexov zvlášť dôležité.",
        },
        {
            "id": "c-copy-terminator-capacity",
            "prompt": "Text má tri bajty pred koncovou nulou. Čo musí platiť, aby sa celý zmestil do cieľa?",
            "options": (
                ("a", "Stačí kapacita 3; memmove pridá nulu za skopírované bajty."),
                ("b", "Kapacita musí byť aspoň 4 a koncová nula musí byť súčasťou kopírovaného rozsahu."),
                ("c", "Stačí použiť strncpy s limitom 3 a potom vždy volať strlen."),
            ),
            "correctOptionId": "b",
            "correctFeedback": "Správne. Tri bajty obsahu a jeden bajt ukončenia potrebujú štyri miesta. Bajtová funkcia nepridáva nič nad požadovaný počet.",
            "incorrectFeedback": "Kapacita zahŕňa koncovú nulu. Ani memmove, ani obmedzenie strncpy samo osebe nevytvorí miesto alebo nezaručí ukončenie.",
        },
        {
            "id": "c-comparator-overflow",
            "prompt": "Prečo je pri porovnávaní dvoch int v qsort vhodnejšie (a > b) - (a < b) než a - b?",
            "options": (
                ("a", "Pretože qsort vyžaduje vždy presne hodnoty -1, 0 a 1."),
                ("b", "Stačí znamienko výsledku a pri odčítaní samotných dát by mohol int pretiecť."),
                ("c", "Pretože odčítanie nikdy nevráti nulu pri rovnakých číslach."),
            ),
            "correctOptionId": "b",
            "correctFeedback": "Správne. Rozdiel dvoch pravdivostných hodnôt je malý a reprezentovateľný; rozdiel krajných dát nemusí byť.",
            "incorrectFeedback": "qsort potrebuje konzistentné záporné, nulové alebo kladné porovnanie. Konkrétna veľkosť výsledku nerozhoduje, ale znamienkové pretečenie by porušilo pravidlá C.",
        },
    ),
}


def tutorial_checkpoint(language_code: str, checkpoint_id: str) -> dict[str, Any] | None:
    for checkpoint in TUTORIAL_CHECKPOINTS.get(language_code, ()):
        if checkpoint["id"] == checkpoint_id:
            return deepcopy(checkpoint)
    return None


def tutorial_checkpoint_public(checkpoint: dict[str, Any] | None) -> dict[str, Any] | None:
    if not checkpoint:
        return None
    return {
        "id": checkpoint["id"],
        "prompt": checkpoint["prompt"],
        "options": [{"id": option_id, "text": text} for option_id, text in checkpoint["options"]],
    }


def evaluate_tutorial_checkpoint(checkpoint: dict[str, Any], option_id: str) -> dict[str, Any]:
    valid_option_ids = {item_id for item_id, _ in checkpoint["options"]}
    if option_id not in valid_option_ids:
        raise ValueError("Vybraná odpoveď nepatrí k tejto otázke.")
    is_correct = option_id == checkpoint["correctOptionId"]
    return {
        "checkpointId": checkpoint["id"],
        "optionId": option_id,
        "isCorrect": is_correct,
        "feedback": checkpoint["correctFeedback"] if is_correct else checkpoint["incorrectFeedback"],
    }
