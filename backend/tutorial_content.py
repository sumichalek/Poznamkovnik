"""Vstavaný, používateľovi nezávislý obsah prvej učebnice C."""

from backend.tutorial_c_examples import (
    ASSERT_MAXIMUM,
    ATOMIC_COUNTER,
    BINARY_ROUNDTRIP,
    BIT_MASKS,
    BOUNDARY_TESTS,
    CHECKED_ADD,
    CHECKED_DIVISION,
    CLASSIFY_BYTES,
    COMPARE_STRINGS,
    CONDITIONAL_BUILD,
    CONST_VIEWS,
    CONVERT_SIZES,
    COPY_TEXT_DEMO,
    DEBUG_POSITIVE,
    FILE_ROUNDTRIP,
    FORMATTED_OUTPUT,
    GROW_BUFFER,
    INTEGER_LIMITS,
    MACRO_EXPANDED,
    MACRO_EXPANSION,
    MACRO_PARENTHESES,
    MEASUREMENTS_HEADER,
    MEASUREMENTS_MAIN,
    MEASUREMENTS_SINGLE_FILE,
    MEASUREMENTS_SOURCE,
    MOVE_TEXT,
    PARSE_NUMBER,
    PARSE_POSITIVE,
    READ_LINES,
    RESTRICT_COPY,
    SAFE_INDEX,
    SINGLE_EVALUATION,
    SNPRINTF_MESSAGE,
    SORT_SEARCH,
    STRTOL_REFERENCE,
)

C_LANGUAGE = {
    "code": "c",
    "title": "C",
    "summary": "Praktická učebnica a referencia jazyka C so spustiteľnými príkladmi.",
}

C_PAGES = [
    {
        "key": "overview",
        "parent_key": "",
        "kind": "overview",
        "position": 0,
        "title": "C: učebnica a referencia",
        "summary": "Rýchla orientácia v obsahu, nástrojoch a hraniciach jazyka.",
        "content": {
            "lead": "C dáva priamu kontrolu nad dátami, pamäťou a rozhraním operačného systému. Odmenou za presnosť je rýchly a prenositeľný kód; cenou je zodpovednosť za detaily.",
            "sections": [
                {
                    "title": "Ako túto časť používať",
                    "paragraphs": [
                        "Kapitoly vysvetľujú súvislosti. Referencia na konci stromu slúži na rýchle pripomenutie konkrétnej funkcie alebo pravidla.",
                        "Spustiteľné príklady môžeš meniť bez obavy: tlačidlo Obnoviť vždy vráti pôvodný zápis. Vstup programu patrí do samostatného poľa skúšobne."
                    ],
                    "bullets": [
                        "Píš deklarácie tak, aby bolo vidieť vlastníkstvo pamäte a rozsah platnosti dát.",
                        "Kompiluj s varovaniami a opravuj ich skôr, než začneš hľadať chybu v behu programu.",
                        "Každý prístup cez ukazovateľ, index poľa a návratovú hodnotu knižnice ber ako miesto, ktoré treba vedome skontrolovať."
                    ]
                },
                {
                    "title": "Rozsah prvej verzie",
                    "paragraphs": [
                        "Príklady používajú štandard C17 a štandardnú knižnicu. Veci viazané na Linux alebo POSIX budú vždy označené zvlášť, aby sa nemiešali s prenositeľným C."
                    ],
                    "callout": "C nemá zabudovanú ochranu pred prístupom mimo poľa ani automatické uvoľňovanie pamäte. Správnosť je súčasťou návrhu, nie doplnok po dokončení programu."
                }
            ]
        }
    },
    {
        "key": "foundations",
        "parent_key": "",
        "kind": "chapter",
        "position": 10,
        "title": "Základy jazyka",
        "summary": "Zdrojový súbor, typy, výrazy a riadenie toku programu.",
        "content": {
            "lead": "Základy C sú krátke, ale presné: program pozostáva z deklarácií a funkcií, pričom vykonávanie začína vo funkcii main. Skôr než sa pustíš do pamäte a ukazovateľov, oplatí sa zvládnuť tok hodnoty od zdrojového súboru až po výsledok programu.",
            "sections": [
                {
                    "title": "Ako nad základmi premýšľať",
                    "paragraphs": [
                        "V C má aj malý zápis konkrétny význam: typ rozhoduje o tom, aký rozsah hodnoty môžeš uložiť, podmienka rozhoduje o ďalšom kroku a funkcia vymedzuje zodpovednosť časti programu. Nejde o izolované pravidlá syntaxe, ale o malý model toho, čo program smie urobiť.",
                        "Pri každej novej konštrukcii sa skús spýtať tri otázky: aké údaje prichádzajú dnu, za akých podmienok sa spracujú a čo presne ide von. Tento návyk sa neskôr prirodzene prenesie na polia, ukazovatele, chyby aj rozhrania medzi zdrojovými súbormi."
                    ],
                    "bullets": ["Stavba programu a kompilácia.", "Typy, rozsahy a konverzie.", "Podmienky, cykly a funkcie."]
                }
            ]
        }
    },
    {
        "key": "program",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 20,
        "title": "Prvý program a preklad",
        "summary": "main, hlavičkové súbory, návratová hodnota a základný príkaz prekladača.",
        "content": {
            "lead": "Zdrojový súbor je návod pre prekladateľ. Program, ktorý môže spustiť operačný systém, vznikne až po spracovaní hlavičiek, kontrole pravidiel jazyka a spojení potrebných častí.",
            "blocks": [
                {"type": "heading", "text": "Rozlíš tri okamihy"},
                {"type": "paragraph", "text": "Keď píšeš main.c, upravuješ zdrojový text. Pri preklade prekladateľ skontroluje jeho tvar a typy. Až spustený program číta vstup, vypisuje výsledok a vracia stav operačnému systému. Táto postupnosť ti pomôže hneď zaradiť chybu: je v zápise, v preklade alebo v správaní programu?"},
                {"type": "code", "language": "c", "title": "Najmenší samostatný program", "source": "#include <stdio.h>\n\nint main(void)\n{\n    puts(\"Ahoj, svet!\");\n    return 0;\n}"},
                {"type": "heading", "text": "Prečítaj ho zdola aj zhora"},
                {"type": "paragraph", "text": "main je vstupný bod, na ktorom sa prostredie s programom dohodlo. void v zátvorkách hovorí, že funkcia teraz neprijíma argumenty. return 0 znamená, že program skončil úspešne. puts vypíše text a pridá nový riadok, no aby prekladateľ poznal jej rozhranie, potrebujeme na začiatku deklaráciu z hlavičky stdio.h."},
                {"type": "paragraph", "text": "#include nie je príkaz, ktorý sa vykoná pri behu. Je to pokyn pre preprocesor pred prekladom. Preto hlavička zodpovedá na otázku, ako sa funkcia volá; jej vlastná implementácia môže byť v knižnici alebo v inom zdrojovom súbore."},
                {"type": "heading", "text": "Pracovný postup pri prvom behu"},
                {"type": "list", "items": ["Ulož zdroj ako main.c.", "Prelož ho s varovaniami: gcc -std=c17 -Wall -Wextra -Wpedantic main.c -o program.", "Prečítaj diagnostiku ešte pred spustením.", "Spusť výsledok: ./program a porovnaj výpis s tým, čo si očakával."]},
                {"type": "callout", "tone": "tip", "text": "Varovanie nie je nepodstatný dodatok. Často ukazuje na rozdiel medzi tým, čo si mal na mysli, a tým, čo je v zdrojovom texte naozaj napísané."},
                {"type": "heading", "text": "Prenes to do vlastného programu"},
                {"type": "paragraph", "text": "Pred ďalším spustením si vyber jednu vec, ktorú chceš pozorovať: výpis, návratový kód alebo diagnostiku. Tak sa z behu programu nestane náhodné kliknutie, ale malý overovací experiment."}
            ]
        }
    },
    {
        "key": "values",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 30,
        "title": "Typy, premenné a výrazy",
        "summary": "Celé čísla, desatinné čísla, const, rozsahy a bezpečné konverzie.",
        "content": {
            "lead": "Typ nie je ozdoba pri názve premennej. Určuje, aký druh údaja premenná predstavuje, aký rozsah hodnôt môže mať a ktoré operácie nad ňou dávajú zmysel.",
            "blocks": [
                {"type": "heading", "text": "Najprv pomenuj, čo hodnota vyjadruje"},
                {"type": "paragraph", "text": "Predstav si program, ktorý zaznamenáva merania. Počet vykonaných meraní je celé číslo, nameraná dĺžka môže mať desatinnú časť a značka jednotky je jeden znak. V pamäti sú to všetko údaje, no každá z týchto hodnôt opisuje niečo iné. Typ dá prekladateľovi aj čitateľovi programu jasne najavo, ako sa s hodnotou má pracovať."},
                {"type": "paragraph", "text": "Nezačínaj otázkou, aký typ zaberie najmenej bajtov. Najprv si polož tri otázky: Je hodnota celočíselná, približná, znaková alebo logická? Aký rozsah môže mať? Je jej presná šírka súčasťou dohody so súborom, sieťou alebo zariadením? Až potom vyber typ."},
                {"type": "heading", "text": "Základné skupiny typov v C"},
                {"type": "paragraph", "text": "Základné typy v C nie sú iba zoznam slov, ktoré sa treba naučiť naspamäť. Každá skupina opisuje iný druh hodnoty a vedie k iným bezpečným operáciám. Nasledujúci prehľad stačí na vedomý výber vo väčšine prvých programov."},
                {"type": "list", "items": ["Celočíselné typy char, short, int, long a long long ukladajú celé hodnoty. int je zvyčajná voľba pre bežné počty a výpočty; char sa často používa pre jeden znak, hoci je to stále celočíselný typ.", "Znamienkové a neznamienkové varianty signed a unsigned určujú, či typ potrebuje záporné hodnoty. unsigned nepoužívaj automaticky iba preto, že momentálne očakávaš kladné číslo; zmiešanie znamienok pri výpočte môže priniesť prekvapivý výsledok.", "Typy float, double a long double ukladajú približné desatinné hodnoty. Pre bežný výpočet je double obvykle najrozumnejšia voľba; float vyberaj až vtedy, keď máš konkrétny dôvod šetriť pamäť alebo to vyžaduje rozhranie.", "Logický typ bool zo stdbool.h vyjadruje otázku s odpoveďou true alebo false. Namiesto číselného príznaku tak názov aj typ hovoria, že ide o podmienku.", "void znamená neprítomnosť hodnoty. Funkcia s návratovým typom void vykoná činnosť, ale nevracia výsledok; s ukazovateľom void * sa stretneš neskôr pri všeobecných rozhraniach.", "size_t zo stddef.h je typ pre veľkosti objektov a indexy odvodené od ich veľkosti. Ak vyžaduje vonkajšie rozhranie presne danú šírku, použi typ ako int32_t alebo uint32_t zo stdint.h namiesto predpokladu, že int alebo long majú všade rovnakú veľkosť."]},
                {"type": "heading", "text": "Deklarácia spojí meno, typ a počiatočnú hodnotu"},
                {"type": "paragraph", "text": "Deklaráciou vytvoríš premennú a určíš jej typ. Ak už pri deklarácii poznáš hodnotu, inicializuj ju hneď. Program tak nezačne pracovať s neznámym obsahom pamäte a čitateľ hneď vidí zamýšľaný stav."},
                {"type": "code", "language": "c", "title": "Jeden program, viac druhov údajov", "source": "#include <stdbool.h>\n#include <stddef.h>\n#include <stdint.h>\n\nconst int measurement_count = 3;\ndouble average_length_m = 1.75;\nchar unit = 'm';\nbool is_complete = false;\nsize_t stored_values = 12;\nuint32_t device_id = 42u;"},
                {"type": "paragraph", "text": "measurement_count je bežný počet, preto má typ int. average_length_m je meraná veličina s možnou desatinnou časťou, preto má typ double. unit obsahuje práve jeden znak v apostrofoch. stored_values má typ size_t, pretože opisuje veľkosť kolekcie, a device_id má presne 32 bitov, lebo to vyžaduje rozhranie zariadenia."},
                {"type": "paragraph", "text": "const pri measurement_count hovorí, že cez toto meno už nepriradíš novú hodnotu. Nie je to náhrada za dobrý názov ani za kontrolu správnosti, ale pomáha zachytiť omyl skôr, než sa prejaví vo výsledku programu."},
                {"type": "heading", "text": "Celé a desatinné výpočty nie sú to isté"},
                {"type": "paragraph", "text": "Pri delení rozhodujú typy operandov. Ak sú oba celočíselné, C zlomkovú časť výsledku zahodí. Stačí, aby bol aspoň jeden operand typu double, a výsledok môže mať desatinnú časť. Tento rozdiel je dôležitejší než samotný zápis čísla v zdrojovom texte."},
                {"type": "code", "language": "c", "title": "Najprv vyber druh delenia", "source": "int completed = 7;\nint people = 2;\n\nint whole_share = completed / people;\ndouble exact_share = (double) completed / people;\n/* whole_share je 3, exact_share je 3.5 */"},
                {"type": "paragraph", "text": "double nedokáže presne vyjadriť každé desatinné číslo. Preto pri porovnávaní výsledkov merania často neporovnávame dve hodnoty priamo, ale sledujeme, či je ich rozdiel menší než zvolená tolerancia. Pre peniaze býva vhodnejšie ukladať najmenšiu jednotku ako celé číslo, napríklad počet centov."},
                {"type": "heading", "text": "Konverzia mení reprezentáciu, nie význam"},
                {"type": "paragraph", "text": "Konverzia je bezpečná iba vtedy, keď cieľový typ dokáže verne zachytiť konkrétnu hodnotu. Priradenie 3.9 do int vytvorí hodnotu 3. Prevod záporného čísla na unsigned typ môže vytvoriť veľké kladné číslo. Pretypovanie v zátvorkách iba vyjadruje, že prevod robíš zámerne; samo osebe údaje pred stratou nechráni."},
                {"type": "paragraph", "text": "Pred prevodom si preto over zdrojový rozsah, cieľový rozsah a význam hodnoty po prevode. Napríklad počet bajtov z veľkého súboru nepatrí bez kontroly do malého typu iba preto, že aktuálny testovací súbor bol krátky."},
                {"type": "heading", "text": "Od omylu k pravidlu"},
                {"type": "callout", "tone": "warning", "text": "Nezamieňaj otázku „prejde to prekladom?“ s otázkou „zachová sa význam hodnoty?“. Pred zúžením typu alebo prevodom znamienka najprv over rozsah. Ak šírka dát tvorí súčasť rozhrania, použi presný typ zo stdint.h a príslušný formát výpisu z inttypes.h."},
                {"type": "heading", "text": "Prenes to do vlastného programu"},
                {"type": "paragraph", "text": "Pri každej novej premennej si jednou vetou pomenuj jej význam, očakávaný rozsah a dôvod voľby typu. Potom zmeň jeden operand na double a porovnaj výsledok s celočíselným delením. Cieľom nie je zapamätať si zoznam typov, ale vedieť predvídať, čo program s hodnotou urobí."}
            ]
        }
    },
    {
        "key": "flow",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 40,
        "title": "Podmienky a cykly",
        "summary": "if, switch, for, while, do while a čitateľné vetvenie.",
        "content": {
            "lead": "Riadenie toku odpovedá na dve otázky: ktorú cestu má program vybrať a koľkokrát má krok zopakovať. Čitateľný zápis ukáže obe odpovede priamo v podmienke a v hranici cyklu.",
            "blocks": [
                {"type": "heading", "text": "Jedna podmienka, jedna otázka"},
                {"type": "paragraph", "text": "Predstav si meranie, pri ktorom chceš vypísať, či je hodnota záporná, nulová alebo kladná. Každá vetva má pomenovať jeden stav. Ak podmienka začne miešať kontrolu vstupu, práva aj výpočet, rozdeľ ju na menšie kroky s vlastnými názvami."},
                {"type": "code", "language": "c", "title": "Tri vzájomne sa vylučujúce stavy", "source": "if (value < 0) {\n    puts(\"záporné\");\n} else if (value == 0) {\n    puts(\"nula\");\n} else {\n    puts(\"kladné\");\n}"},
                {"type": "paragraph", "text": "C považuje nulu za nepravdu a každú nenulovú hodnotu za pravdu. Aj tak uprednostni porovnanie, ktoré čitateľovi povie význam otázky. value < 0 je zrozumiteľnejšie než iba value, ak naozaj testuješ znamienko."},
                {"type": "heading", "text": "Cykel potrebuje hranicu aj invariant"},
                {"type": "paragraph", "text": "for sa hodí, keď poznáš postup indexu alebo počet krokov. while použiješ, keď koniec závisí od stavu, ktorý sa počas behu mení. V oboch prípadoch si skús pomenovať invariant: tvrdenie o stave, ktoré platí pred aj po každom priechode."},
                {"type": "code", "language": "c", "title": "Súčet prvkov bez kroku mimo poľa", "source": "int total = 0;\n\nfor (size_t index = 0; index < count; ++index) {\n    total += values[index];\n}"},
                {"type": "paragraph", "text": "Pred prvým priechodom je total súčet nula prvkov. Po každom priechode je súčtom prvkov pred indexom. Podmienka index < count chráni hranicu poľa, pretože posledný platný index je count - 1."},
                {"type": "list", "items": ["Použi zložené zátvorky aj pri jedinom príkaze, ak tým lepšie vidno hranicu vetvy.", "Rozlišuj = pre priradenie a == pre porovnanie.", "V switch výslovne ošetri default a vedome rozhodni, kde má byť break."]},
                {"type": "heading", "text": "Prenes to do vlastného programu"},
                {"type": "paragraph", "text": "Pred napísaním cyklu doplň dve vety: čo sa zmení v jednom kroku a čo ho bezpečne ukončí. Ak ich nevieš povedať bez kódu, návrh ešte potrebuje zjednodušiť."}
            ]
        }
    },
    {
        "key": "operators",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 35,
        "title": "Operátory, priority a výrazy",
        "summary": "Porovnanie, logické spojky, priradenie a bezpečné zostavovanie podmienok.",
        "content": {
            "lead": "Výraz kombinuje hodnoty do výsledku. Dobrý výraz nežiada, aby si čitateľ pamätal tabuľku priorít; jeho zátvorky a poradie krokov ukážu úmysel samy.",
            "blocks": [
                {"type": "heading", "text": "Logika chráni ďalší krok"},
                {"type": "paragraph", "text": "Porovnávacie operátory vytvárajú pravdu alebo nepravdu, z ktorých &&, || a ! skladajú rozhodnutia. Poradie častí podmienky je dôležité, pretože && skončí pri prvej nepravdivej časti a || pri prvej pravdivej časti."},
                {"type": "code", "language": "c", "title": "Najprv over, potom použi", "source": "if (item != NULL && item->count > 0) {\n    process(item);\n}"},
                {"type": "paragraph", "text": "Ak item je NULL, ľavá časť je nepravdivá a C pravú časť vôbec nevyhodnotí. To je dôvod, prečo má kontrola ukazovateľa byť vľavo. Opačné poradie by sa pokúsilo prečítať item->count skôr, než by vedelo, či item označuje platný objekt."},
                {"type": "heading", "text": "Zátvorky vysvetľujú rozhodnutie"},
                {"type": "paragraph", "text": "Prekladateľ pozná prioritu násobenia, sčítania a porovnaní. Čitateľ však potrebuje rýchlo vidieť zámer. Zápis (width + padding) * height hneď ukáže, že najprv vznikne celková šírka; bez zátvoriek by výraz opisoval iný výpočet."},
                {"type": "code", "language": "c", "title": "Oddeľ vedľajší účinok od otázky", "source": "int read_count = read_value(&value);\n\nif (read_count > 0) {\n    use(value);\n}"},
                {"type": "paragraph", "text": "Takýto zápis sa dá ladiť aj vysvetliť po jednotlivých krokoch. Zápis if ((read_count = read_value(&value)) > 0) je platný, no spája priradenie s rozhodnutím a pri čítaní sa ľahko pomýli s ==."},
                {"type": "callout", "tone": "tip", "text": "Ternárny operátor si nechaj na krátky výber jednej hodnoty, napríklad maximum = left > right ? left : right. Pre viac krokov alebo zmenu stavu bude if a else čitateľnejšie."},
                {"type": "heading", "text": "Prenes to do vlastného programu"},
                {"type": "paragraph", "text": "Vyber jednu podmienku, ktorú už máš napísanú. Označ v nej kontrolu bezpečnosti, vlastné rozhodnutie a vedľajší účinok. Ak sú pomiešané, rozdeľ ich do samostatných riadkov."}
            ]
        }
    },
    {
        "key": "functions",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 50,
        "title": "Funkcie, rozsah a návratové hodnoty",
        "summary": "Parametre sa predávajú hodnotou, ukazovatele simulujú výstupné parametre.",
        "content": {
            "lead": "Funkcia je malá dohoda: prijme presne pomenovaný vstup, vykoná jednu súvisiacu úlohu a vráti výsledok alebo jasne zmení objekt, na ktorom má pracovať.",
            "blocks": [
                {"type": "heading", "text": "Najprv navrhni rozhranie"},
                {"type": "paragraph", "text": "Keď potrebuješ zistiť väčšiu z dvoch hodnôt, názov maximum, dva parametre int a návrat int vyjadria úlohu priamo. Volajúci nemusí vedieť, či vo vnútri používaš if alebo ternárny operátor; stačí mu dohoda o vstupe a výsledku."},
                {"type": "code", "language": "c", "title": "Funkcia, ktorá iba vracia hodnotu", "source": "static int maximum(int left, int right)\n{\n    return left > right ? left : right;\n}"},
                {"type": "paragraph", "text": "left a right sú pri volaní skopírované. Ak by si vo funkcii zmenil left, premenná volajúceho ostane nezmenená. Tento predvídateľný prenos hodnotou je základný mechanizmus C."},
                {"type": "heading", "text": "Ukazovateľ otvorí prístup k objektu"},
                {"type": "paragraph", "text": "Funkcia môže zmeniť objekt volajúceho iba vtedy, ak dostane jeho adresu. Aj samotná adresa sa odovzdáva hodnotou, ale cez dereferencovanie sa funkcia dostane k označenému objektu. Preto musí kontrakt povedať, či je ukazovateľ povinný, či smie byť NULL a čo sa po úspechu zmení."},
                {"type": "code", "language": "c", "title": "Výrez: zmena cez výstupný parameter", "source": "#include <stdbool.h>\n#include <stddef.h>\n\nstatic bool increment(int *value)\n{\n    if (value == NULL) {\n        return false;\n    }\n\n    *value += 1;\n    return true;\n}"},
                {"type": "paragraph", "text": "Návrat bool tu hovorí, či operácia uspela; skutočná hodnota sa zapisuje cez *value. Takéto rozdelenie je užitočné, keď výsledok môže byť akékoľvek celé číslo vrátane nuly a nulu nemožno použiť ako nejasný signál chyby."},
                {"type": "list", "items": ["Funkcia void nevracia hodnotu, ale stále môže mať jasný účinok.", "static pri funkcii obmedzí jej viditeľnosť na jeden zdrojový súbor.", "Nevracaj ukazovateľ na lokálnu premennú; po návrate funkcie jej objekt zanikol."]},
                {"type": "heading", "text": "Prenes to do vlastného programu"},
                {"type": "paragraph", "text": "Pri najbližšej funkcii si pred telom odpovedz: čo je platný vstup, aký výsledok dostane volajúci, ktoré údaje funkcia smie zmeniť a kto zodpovedá za prípadnú dynamickú pamäť. Až potom napíš prvý riadok tela."}
            ]
        }
    },
    {
        "key": "data",
        "parent_key": "",
        "kind": "chapter",
        "position": 60,
        "title": "Dáta a pamäť",
        "summary": "Polia, reťazce, ukazovatele, vlastné typy a dynamická pamäť.",
        "content": {"lead": "V C dáta a ich umiestnenie úzko súvisia. Táto kapitola vysvetľuje, ako ich navrhovať bez nejasného vlastníctva.", "sections": [{"title": "V tejto kapitole", "bullets": ["Polia a hranice indexov.", "Reťazce ukončené nulovým znakom.", "Ukazovatele, struct a dynamická pamäť."]}]}
    },
    {
        "key": "scope",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 55,
        "title": "Rozsah, životnosť a const",
        "summary": "Kde meno platí, ako dlho objekt žije a čo skutočne chráni const.",
        "content": {
            "lead": "Rozsah určuje, kde môžeš použiť meno premennej alebo funkcie. Životnosť hovorí, dokedy existuje samotný objekt. Tieto dve veci spolu súvisia, no odpovedajú na odlišné otázky.",
            "blocks": [
                {"type": "heading", "text": "Najprv odlíš meno od objektu"},
                {"type": "paragraph", "text": "Meno je označenie, ktoré používaš v zdrojovom texte. Objekt je miesto s hodnotou, na ktoré toto meno odkazuje. Rozsah odpovedá na otázku „môžem tu napísať toto meno?“. Životnosť odpovedá na otázku „existuje ešte objekt, ktorého adresu alebo hodnotu chcem použiť?“."},
                {"type": "paragraph", "text": "Pri bežnej lokálnej premennej sa tieto hranice často zhodujú: vznikne pri vstupe do bloku zložených zátvoriek a po jeho opustení zanikne. Keď však pracuješ s ukazovateľmi, rozdiel je rozhodujúci. Ukazovateľ môže mať stále uloženú adresu, hoci objekt na nej už dávno neexistuje."},
                {"type": "code", "language": "c", "title": "Jedno meno, dva rôzne bloky", "source": "int main(void)\n{\n    int result = 0;\n\n    if (result == 0) {\n        int message_count = 1;\n        result += message_count;\n    }\n\n    /* message_count tu už nie je v rozsahu. */\n    return result;\n}"},
                {"type": "paragraph", "text": "message_count je platný iba medzi vnútornými zloženými zátvorkami. Prekladateľ preto odmietne pokus použiť ho pod blokom. Takéto malé rozsahy sú užitočné: čitateľovi ukazujú, ktoré údaje patria iba k jednému kroku programu."},
                {"type": "heading", "text": "static mení životnosť, nie zmysel premennej"},
                {"type": "code", "language": "c", "title": "Stav, ktorý pretrvá medzi volaniami", "source": "static unsigned int next_ticket(void)\n{\n    static unsigned int last_ticket = 0U;\n\n    last_ticket += 1U;\n    return last_ticket;\n}"},
                {"type": "paragraph", "text": "last_ticket je viditeľný iba vo funkcii next_ticket, ale vytvorí sa raz a jeho hodnota zostane zachovaná do konca programu. Takýto stav používaj vtedy, keď funkcia naozaj vlastní vlastnú históriu. Ak ho potrebuje meniť viac častí programu, jasnejšie býva odovzdať stav ako parameter alebo ho uložiť do štruktúry."},
                {"type": "list", "items": ["Premenná deklarovaná v bloku nemá byť dostupná mimo tohto bloku.", "static pri lokálnej premennej zachováva objekt medzi volaniami funkcie.", "static pri definícii funkcie obmedzí jej viditeľnosť na daný zdrojový súbor.", "Globálne premenne vytvárajú vzdialené závislosti; používaj ich iba vtedy, keď je spoločný stav naozaj zámerom návrhu."]},
                {"type": "heading", "text": "const vyjadruje spôsob použitia"},
                {"type": "code", "language": "c", "title": "Funkcia, ktorá hodnoty iba číta", "source": "#include <stddef.h>\n\nstatic int sum(const int values[], size_t count)\n{\n    int total = 0;\n\n    for (size_t index = 0; index < count; ++index) {\n        total += values[index];\n    }\n    return total;\n}"},
                {"type": "paragraph", "text": "const int values[] hovorí, že funkcia nebude meniť prvky poľa cez parameter values. Volajúci ich môže vlastniť a meniť inde, ale táto konkrétna funkcia má iba čítací pohľad. Naopak int *const pointer chráni samotnú adresu uloženú v premennej pointer; const int *const pointer chráni aj adresu, aj hodnotu dostupnú cez ňu."},
                {"type": "callout", "tone": "warning", "text": "const nerieši vlastníctvo, platnosť ukazovateľa ani súbežný prístup. Vyjadruje, čo tento kus kódu smie meniť, a dáva prekladateľovi možnosť zachytiť časť omylov."},
                {"type": "heading", "text": "Prenes to do vlastného programu"},
                {"type": "paragraph", "text": "Pri najbližšej premennej si označ blok, v ktorom ju skutočne potrebuješ. Pri každom parametri ukazovateľa si potom napíš, či funkcia údaje číta, mení alebo preberá. Už tieto dve rozhodnutia výrazne zmenšia priestor pre neplatné mená a nejasné vedľajšie účinky."}
            ]
        }
    },
    {
        "key": "arrays",
        "parent_key": "data",
        "kind": "lesson",
        "position": 70,
        "title": "Polia a ukazovatele",
        "summary": "Súvislá pamäť, indexovanie, adresa objektu a NULL.",
        "content": {
            "lead": "Pole obsahuje prvky rovnakého typu uložené vedľa seba v pamäti. Prvý prvok má index 0, posledný platný index je vždy počet prvkov mínus jedna.",
            "blocks": [
                {"type": "heading", "text": "Pole má kapacitu, počet a platné indexy"},
                {"type": "paragraph", "text": "Ak má pole päť prvkov, jeho indexy sú 0, 1, 2, 3 a 4. Hodnota 5 už neoznačuje ďalší prvok, ale prvé miesto za poľom. Prístup mimo tejto hranice má v C nedefinované správanie: program nemusí spadnúť hneď, no výsledok už nemá žiadnu záruku."},
                {"type": "paragraph", "text": "Rozlišuj kapacitu, teda koľko prvkov sa do poľa zmestí, od počtu prvkov, ktoré v ňom práve považuješ za použité. Pri poli vytvorenom priamo v tom istom rozsahu môžeš jeho počet vypočítať pomocou sizeof. Pri dynamickom poli alebo parametri funkcie musíš počet niesť samostatne."},
                {"type": "code", "language": "c", "title": "Počet prvkov urči tam, kde pole naozaj existuje", "source": "#include <stddef.h>\n#include <stdio.h>\n\nint main(void)\n{\n    const int values[] = {3, 1, 4, 1, 5};\n    const size_t count = sizeof values / sizeof values[0];\n\n    for (size_t index = 0; index < count; ++index) {\n        printf(\"%d\\n\", values[index]);\n    }\n    return 0;\n}"},
                {"type": "paragraph", "text": "sizeof values dá veľkosť celého poľa v bajtoch a sizeof values[0] veľkosť jedného prvku. Ich podiel je preto počet prvkov. Podmienka index < count chráni oba okraje: pri prázdnom poli neprejde ani raz a pri poslednom prvku dovolí index count - 1, nie count."},
                {"type": "heading", "text": "Funkcia potrebuje prvý prvok aj počet"},
                {"type": "code", "language": "c", "title": "Kontrakt funkcie nad poľom", "source": "#include <stddef.h>\n\nstatic int sum(const int values[], size_t count)\n{\n    int total = 0;\n\n    for (size_t index = 0; index < count; ++index) {\n        total += values[index];\n    }\n    return total;\n}"},
                {"type": "paragraph", "text": "V zozname parametrov sa zápis const int values[] upraví na ukazovateľ na prvý prvok. Funkcia preto nepozná pôvodnú kapacitu poľa a sizeof values by tu meral iba veľkosť ukazovateľa. count je druhá polovica kontraktu: hovorí, koľko prvkov smie funkcia prečítať."},
                {"type": "paragraph", "text": "Takýto kontrakt musí povedať aj to, čo platí pri count rovnom nule. Bežné pravidlo znie: pri nule funkcia nečíta žiaden prvok; pri kladnom počte values označuje najmenej count platných prvkov. Keď to rozhranie vysloví, volajúci aj implementácia majú rovnaké hranice."},
                {"type": "heading", "text": "Čítaj cyklus ako dôkaz hranice"},
                {"type": "paragraph", "text": "Pred prvým priechodom cyklu je total súčtom nula prvkov. Po každom priechode je súčtom prvkov s indexom menším než index. Keď index dosiahne count, všetky platné prvky už boli spracované a žiaden neplatný nebol načítaný. Takéto tvrdenie sa nazýva invariant a pomáha odhaliť chybu ešte pred spustením."},
                {"type": "list", "items": ["Použi index < count, nie index <= count.", "sizeof pole používaj iba v rozsahu, kde je hodnota naozaj poľom, nie parametrom funkcie.", "const pri parametri poľa vyjadruje, že funkcia prvky iba číta.", "Pri práci s indexom z vonkajšieho vstupu najprv over, že nie je záporný a že je menší než count."]},
                {"type": "callout", "tone": "warning", "text": "Pole v C samo nenesie svoju dĺžku ani nekontroluje index. Každá bezpečná operácia nad poľom preto potrebuje viditeľný počet prvkov a podmienku, ktorá túto hranicu rešpektuje."},
                {"type": "heading", "text": "Prenes to do vlastného programu"},
                {"type": "paragraph", "text": "Vyber jeden cyklus nad poľom. Povedz si, čo označuje index pred prvým priechodom, čo po každom priechode a prečo sa nikdy nedostane na hodnotu count pri prístupe do poľa. Ak túto odpoveď nevieš vysloviť, doplň názov count alebo rozdeľ výpočet na kratšie kroky."}
            ]
        }
    },
    {
        "key": "strings",
        "parent_key": "data",
        "kind": "lesson",
        "position": 80,
        "title": "Reťazce",
        "summary": "char, nulový znak, bezpečný vstup a funkcie z string.h.",
        "content": {
            "lead": "C reťazec je pole znakov char ukončené znakom \\0. Dĺžka nie je uložená oddelene, preto funkcie z string.h prechádzajú pamäť, kým koncový nulový znak nenájdu.",
            "blocks": [
                {"type": "heading", "text": "Text potrebuje miesto aj pre neviditeľný koniec"},
                {"type": "paragraph", "text": "Zápis char name[32] vytvorí priestor pre 32 znakov, nie pre 32-písmenové meno. Ak má hodnota tvoriť reťazec, jeden prvok musí obsahovať koncový znak \\0. Do takého poľa sa preto zmestí najviac 31 viditeľných znakov a jeden neviditeľný ukončovač."},
                {"type": "paragraph", "text": "Funkcia strlen počíta znaky pred \\0, nie kapacitu poľa. Ak sa nulový znak v dostupnej pamäti nenachádza, strlen, printf s %s aj ďalšie textové funkcie pokračujú za hranicou poľa. Bezpečný program teda musí zaistiť, že každé pole používané ako reťazec má platný koniec."},
                {"type": "code", "language": "c", "title": "Literál, ukazovateľ a upraviteľné pole", "source": "const char *message = \"Ahoj\";\nchar name[32] = \"Ada\";\n\n/* message[0] = 'a';  -- textový literál sa nemá meniť */\nname[0] = 'a';          /* vlastné pole meniť môžeš */"},
                {"type": "paragraph", "text": "message ukazuje na textový literál, preto ho čítaj cez const char *. name je vlastné pole s kópiou znakov a môžeš meniť jeho prvky. Rozdiel nie je iba v zápise: pokus meniť literál má nedefinované správanie, hoci ukazovateľ môže vyzerať podobne ako pole."},
                {"type": "heading", "text": "Riadok najprv načítaj, potom ho spracuj"},
                {"type": "code", "language": "c", "title": "Bezpečný základ riadkového vstupu", "source": "#include <stdio.h>\n#include <string.h>\n\nchar name[32] = \"\";\n\nfputs(\"Meno: \", stdout);\nif (fgets(name, sizeof name, stdin) == NULL) {\n    fputs(\"Vstup sa nepodaril.\\n\", stderr);\n    return 1;\n}\n\nname[strcspn(name, \"\\n\")] = '\\0';"},
                {"type": "paragraph", "text": "fgets dostane kapacitu poľa, preto zapíše najviac veľkosť mínus jeden znak a vždy doplní \\0, ak sa vstup podarí. Ak sa znak nového riadku zmestil, strcspn nájde jeho pozíciu a nahradí ho koncom reťazca. Ak sa riadok nezmestil, strcspn nájde už existujúci \\0 a zápis ostane bezpečný, no zvyšok vstupu stále čaká v štandardnom vstupe."},
                {"type": "paragraph", "text": "To je dôležité pri ďalšom čítaní: príliš dlhý riadok neznamená, že sa celé meno podarilo načítať. Podľa potreby môžeš zvyšok riadka zahodiť alebo používateľovi oznámiť, že má zadať kratší text. Úspešný návrat fgets hovorí iba to, že sa načítala časť vstupu do pripraveného poľa."},
                {"type": "heading", "text": "Reťazce porovnávaj obsahom"},
                {"type": "code", "language": "c", "title": "Dve textové hodnoty", "source": "#include <string.h>\n\nconst char expected[] = \"C17\";\nconst char entered[] = \"C17\";\n\nif (strcmp(expected, entered) == 0) {\n    /* znaky sú rovnaké */\n}"},
                {"type": "paragraph", "text": "Operátor == pri ukazovateľoch porovnáva adresy, nie znaky v texte. strcmp vráti nulu, keď sú oba reťazce rovnaké. Pri kopírovaní a spájaní textov si vždy polož otázku, aká je kapacita cieľa; strcpy a strcat ju samy nekontrolujú."},
                {"type": "list", "items": ["strlen meria dĺžku platného reťazca, nie veľkosť poľa.", "fgets je vhodný základ pre riadkový vstup, pretože dostane kapacitu cieľového poľa.", "Textový literál neupravuj; pre vlastný meniteľný text použi pole char.", "Pri porovnaní obsahu používaj strcmp, nie ==."]},
                {"type": "callout", "tone": "warning", "text": "Funkcie strcpy, strcat a sprintf nepoznajú kapacitu cieľového poľa. Použi ich iba tam, kde už máš dokázané, že sa celý výsledok zmestí; v novom kóde častejšie vyhovuje fgets, snprintf alebo postup so samostatne sledovanou kapacitou."},
                {"type": "heading", "text": "Prenes to do vlastného programu"},
                {"type": "paragraph", "text": "Pri každom texte si dopíš tri veci: kapacitu poľa, najväčší povolený viditeľný počet znakov a okamih, v ktorom overíš výsledok vstupu alebo formátovania. Tým sa z reťazca nestane iba postupnosť znakov, ale údaj s jasnou hranicou."}
            ]
        }
    },
    {
        "key": "pointers",
        "parent_key": "data",
        "kind": "lesson",
        "position": 75,
        "title": "Ukazovatele a zmena objektov",
        "summary": "Adresy, dereferencovanie, výstupné parametre a platnosť ukazovateľa.",
        "content": {
            "lead": "Ukazovateľ uchováva adresu objektu. Sám objekt nemení, no operátor * dovolí pristúpiť k hodnote na danej adrese. Použi ho, keď funkcia potrebuje meniť objekt volajúceho alebo pracovať s blokom dát bez zbytočného kopírovania.",
            "blocks": [
                {"type": "heading", "text": "Adresa nie je hodnota, ale cesta k nej"},
                {"type": "paragraph", "text": "Operátor & vytvorí adresu existujúceho objektu. Keď ju uložíš do premennej typu int *, ukazovateľ opisuje, kde sa nachádza celé číslo. Operátor * v použití výrazu otvorí prístup k objektu na tejto adrese. Rovnaký znak má v deklarácii inú úlohu: int *value deklaruje ukazovateľ, zatiaľ čo *value vo výraze dereferencuje jeho cieľ."},
                {"type": "code", "language": "c", "title": "Zmena hodnoty volajúceho", "source": "#include <stdbool.h>\n#include <stddef.h>\n\nstatic bool increment(int *value)\n{\n    if (value == NULL) {\n        return false;\n    }\n\n    *value += 1;\n    return true;\n}\n\nint score = 7;\nincrement(&score);"},
                {"type": "paragraph", "text": "score je objekt typu int. &score odovzdá jeho adresu a parameter value túto adresu prijme. Zápis *value += 1 nemení ukazovateľ, ale int, na ktorý ukazuje. Návratová hodnota bool oddelí otázku, či operácia uspela, od samotnej hodnoty, ktorá sa menila."},
                {"type": "heading", "text": "Pred dereferencovaním polož štyri otázky"},
                {"type": "list", "items": ["Je ukazovateľ NULL alebo označuje konkrétny objekt?", "Existuje cieľový objekt ešte teraz, alebo už skončila jeho životnosť?", "Zodpovedá typ ukazovateľa typu objektu, na ktorý smeruje?", "Dovoľuje kontrakt funkcie objekt iba čítať, alebo ho smie aj meniť?"]},
                {"type": "paragraph", "text": "NULL znamená, že ukazovateľ nemá cieľ, ktorý by si mohol dereferencovať. Nie je to chyba sám o sebe; často predstavuje chýbajúci voliteľný objekt. Chyba vznikne až vtedy, keď sa program pokúsi čítať alebo zapisovať cez NULL bez predchádzajúcej kontroly alebo bez kontraktu, ktorý ho vylučuje."},
                {"type": "paragraph", "text": "Aj nenulová adresa môže byť neplatná. Adresa lokálnej premennej prestane byť použiteľná po návrate z funkcie, adresa uvoľnenej dynamickej pamäte po free a adresa prvku poľa po prístupe za jeho hranicu. Samotná číselná hodnota adresy nie je dôkaz, že objekt ešte žije."},
                {"type": "heading", "text": "Výstupný parameter má mať jasný kontrakt"},
                {"type": "code", "language": "c", "title": "Stav zvlášť, výsledok zvlášť", "source": "#include <stdbool.h>\n#include <stddef.h>\n\nstatic bool first_value(const int values[], size_t count, int *result)\n{\n    if (values == NULL || count == 0U || result == NULL) {\n        return false;\n    }\n\n    *result = values[0];\n    return true;\n}"},
                {"type": "paragraph", "text": "values je čítací vstup, count určuje jeho hranicu a result je výstup, ktorý funkcia mení až po overení všetkých podmienok. Volajúci preto vie, že pri návrate false nemá výsledok používať ako nový platný údaj. Takéto rozhranie je čitateľnejšie než skrytá globálna premenná alebo nejasná zvláštna návratová hodnota."},
                {"type": "heading", "text": "Posun ukazovateľa patrí iba do jeho poľa"},
                {"type": "paragraph", "text": "Pri poli môžeš ukazovateľ posúvať po prvkoch rovnakého typu; values + 1 označuje druhý prvok. Pravidlo platí iba v rámci konkrétneho poľa a presne o jedno miesto za jeho koncom. Dereferencovať smieš iba ukazovateľ na skutočný prvok, nikdy adresu tesne za poľom ani adresu z iného nesúvisiaceho objektu."},
                {"type": "callout", "tone": "warning", "text": "Ukazovateľ automaticky neznamená vlastníctvo. Pri každom parametri alebo návratovej hodnote má byť zrejmé, či funkcia objekt iba číta, mení, preberá zodpovednosť za jeho uvoľnenie alebo vracia novovytvorený objekt."},
                {"type": "heading", "text": "Prenes to do vlastného programu"},
                {"type": "paragraph", "text": "Vyber jednu funkciu, ktorá teraz používa ukazovateľ. Pred jej telo napíš vetu o platnom vstupe, o tom, ktoré objekty smie funkcia meniť, a o tom, čo platí po návrate false alebo po chybe. Až potom kontroluj jednotlivé adresy v kóde."}
            ]
        }
    },
    {
        "key": "types",
        "parent_key": "data",
        "kind": "lesson",
        "position": 90,
        "title": "struct, enum a typedef",
        "summary": "Vlastné dátové typy, pomenované stavy a zoskupenie súvisiacich hodnôt.",
        "content": {
            "lead": "struct spája hodnoty, ktoré spolu opisujú jeden pojem. enum vyjadruje malú pomenovanú množinu stavov. typedef skracuje opakovaný názov typu, no sám osebe nemení jeho pravidlá ani vlastníctvo dát.",
            "blocks": [
                {"type": "heading", "text": "Najprv nájdi jeden pojem, nie iba viac premenných"},
                {"type": "paragraph", "text": "Keď sa spolu objavujú identifikátor objednávky, počet položiek a jej stav, tri voľne položené premenné sa ľahko rozídu. struct ich spojí do jedného objektu s jedným názvom. Čitateľ tak vidí, že údaje patria k sebe a funkcia môže prijať alebo vrátiť celý pojem."},
                {"type": "code", "language": "c", "title": "Pomenovaný objekt a jeho stav", "source": "#include <stddef.h>\n\ntypedef enum {\n    ORDER_NEW,\n    ORDER_PAID,\n    ORDER_SENT\n} OrderState;\n\ntypedef struct {\n    int id;\n    size_t item_count;\n    OrderState state;\n} Order;\n\nOrder order = {.id = 42, .item_count = 3U, .state = ORDER_NEW};"},
                {"type": "paragraph", "text": "Menovaná inicializácia ukazuje, ktorá hodnota patrí ku ktorému členu, a zostane čitateľná aj po pridaní ďalšieho člena. order.state je prístup k členu hodnoty. Ak máš ukazovateľ Order *order_pointer, zápis order_pointer->state je skratka pre (*order_pointer).state."},
                {"type": "heading", "text": "enum pomenuje rozhodnutia programu"},
                {"type": "paragraph", "text": "Hodnoty enum sú v C celočíselné hodnoty s pomenovanými menami. ORDER_PAID povie viac než nezdokumentované číslo 1 a umožní prekladateľovi aj čitateľovi lepšie sledovať vetvy programu. enum sa hodí pre stav, režim, typ správy alebo inú malú uzavretú sadu možností."},
                {"type": "code", "language": "c", "title": "Každý stav má vlastnú vetvu", "source": "static bool can_send(OrderState state)\n{\n    switch (state) {\n    case ORDER_PAID:\n        return true;\n    case ORDER_NEW:\n    case ORDER_SENT:\n        return false;\n    }\n\n    return false;\n}"},
                {"type": "paragraph", "text": "switch robí možné stavy viditeľné na jednom mieste. Posledný return chráni funkciu aj pred hodnotou, ktorá sa do enum dostala z neovereného vstupu alebo chybným pretypovaním. Typ enum zlepšuje výraznosť programu, no sám nezaručí, že sa v pamäti nikdy neobjaví iné celé číslo."},
                {"type": "heading", "text": "Invariant drží štruktúru pohromade"},
                {"type": "paragraph", "text": "Dátový typ potrebuje pravidlá, ktoré musia platiť vždy. Pre Order môže byť invariant napríklad: item_count opisuje skutočný počet položiek a objednávku možno odoslať iba v stave ORDER_PAID. Pri zásobníku by zas platilo, že count nikdy neprekročí capacity a ukazovateľ na pamäť je buď NULL, alebo smeruje na platnú alokáciu."},
                {"type": "paragraph", "text": "Napíš invariant pred funkciami, ktoré štruktúru menia. Potom pri každej funkcii over dve veci: čo musí platiť pred volaním a čo bude platiť po úspešnom návrate. Tak sa návrh typu nestane iba zoznamom členov, ale malou zmluvou v programe."},
                {"type": "heading", "text": "typedef je meno navyše, nie nový druh bezpečnosti"},
                {"type": "paragraph", "text": "typedef struct { ... } Order vytvorí kratší názov Order namiesto zápisu struct Order. To môže zlepšiť čitateľnosť, najmä pri type používanom na viacerých miestach. typedef však nevytvorí nový nepriepustný typ: alias sa pri kontrolách správa rovnako ako pôvodný typ, preto stále záleží na dobrých názvoch a invariantoch."},
                {"type": "list", "items": ["Použi struct, keď hodnoty spolu tvoria jeden reálny alebo logický pojem.", "Použi enum, keď má program pracovať s malou pomenovanou množinou stavov.", "Člen hodnoty sprístupni bodkou, člen cez ukazovateľ šípkou ->.", "Inicializuj členy menovanou inicializáciou, keď tým zlepšíš čitateľnosť alebo odolnosť pri zmene poradia."]},
                {"type": "callout", "tone": "warning", "text": "Ukazovateľ uložený v štruktúre potrebuje rovnaký kontrakt ako ukazovateľ v parametri funkcie: kto ho vytvoril, kto ho uvoľní, či smie byť NULL a dokedy zostáva platný. struct tieto otázky neschováva ani nevyrieši automaticky."},
                {"type": "heading", "text": "Prenes to do vlastného programu"},
                {"type": "paragraph", "text": "Nájdi dve alebo tri premenné, ktoré spolu vždy cestujú funkciami. Skús ich pomenovať jedným typom struct a dopíš jednu vetu, ktorá musí o ich členoch platiť. Ak program rozlišuje viac než dve pomenované možnosti, nahraď voľné čísla enumom a prečítaj vetvy ako zoznam možných stavov."}
            ]
        }
    },
    {
        "key": "bits",
        "parent_key": "data",
        "kind": "lesson",
        "position": 85,
        "title": "Bity, masky a celočíselné hranice",
        "summary": "Bitové operátory, príznaky, posuny a presné celočíselné typy.",
        "content": {
            "lead": "Jedno celé číslo môže predstavovať počet, ale aj skupinu nezávislých príznakov. Pri bitovej maske nás nezaujíma súčet ako taký: každej bitovej pozícii priradíme vlastný význam a meníme ju bez zásahu do ostatných.",
            "blocks": [
                {"type": "heading", "text": "Od samostatných prepínačov k jednej maske"},
                {"type": "paragraph", "text": "Predstav si súbor s tromi oprávneniami: čítať, zapisovať a odosielať. Všetky môžu platiť súčasne, preto nejde o výber jediného stavu. Mohol by si použiť tri premenné bool. Maska je užitočná vtedy, keď knižnica, protokol alebo register zariadenia očakáva tieto stavy uložené v jednom čísle."},
                {"type": "paragraph", "text": "Bit nadobúda hodnotu 0 alebo 1. Pozície počítame sprava od nuly; ich váhy sú postupne 1, 2, 4, 8. Ak sú zapnuté bity 0 a 2, dostaneme hodnotu 1 + 4 = 5, zapísanú pomocou štyroch bitov ako 0101. Zobrazené štyri bity sú iba výrez: unsigned int môže mať viac bitov. V C17 nepoužívaj na binárny literál predponu 0b, ktorá nepatrí do tohto štandardu."},
                {"type": "heading", "text": "Čo robí každý bitový operátor"},
                {"type": "list", "items": [
                    "a & b ponechá na danej pozícii jednotku iba vtedy, keď ju majú oba operandy. Tak vyberieme bity, ktoré nás zaujímajú.",
                    "a | b nastaví jednotku, keď ju má aspoň jeden operand. Pridaním príznaku tak nestratíme tie, ktoré už boli zapnuté.",
                    "a ^ b nastaví jednotku, keď sa príslušné bity líšia. Jednotky v maske preto prepnú vybrané bity; nuly ostatné zachovajú.",
                    "~a obráti všetky bity operandu po celočíselnom povýšení. Na vypnutie vybraných príznakov používame flags &= ~mask, nie flags = ~mask.",
                    "a << n a a >> n posunú bity o n pozícií. Pri neznamienkovom operande sa uvoľnené pozície doplnia nulami; bity mimo rozsahu sa nezachovajú."
                ]},
                {"type": "heading", "text": "Sleduj masku po každej zmene"},
                {"type": "code", "language": "c", "title": "Nastavenie, vypnutie a prepnutie príznaku", "source": BIT_MASKS},
                {"type": "paragraph", "text": "read, write a send majú hodnoty 1, 2 a 4. Najprv spojíme čítanie s odosielaním: flags je 5, teda 0101. Po zapnutí zápisu je 7, teda 0111. Vypnutím odosielania dostaneme 3, teda 0011, a prepnutím zápisu nakoniec 1, teda 0001. Skús tieto štyri výsledky predpovedať ešte pred spustením."},
                {"type": "paragraph", "text": "Posledné dva výpisy odpovedajú na odlišné otázky. Výraz (flags & required) != 0U zisťuje, či platí aspoň jeden požadovaný príznak. Výraz (flags & required) == required zisťuje, či platia všetky. Preto sa vypíše any: 1, ale all: 0. Ak je required nulová maska, test všetkých príznakov vyjde pravdivý: nič sme nepožadovali."},
                {"type": "callout", "tone": "warning", "text": "Nezamieňaj & s && ani | s ||. Logické operátory odpovedajú na otázku pravda/nepravda a používajú skrátené vyhodnocovanie. Bitové operátory spracúvajú jednotlivé bity a túto ochranu neposkytujú. Test masky vždy uzavri do zátvoriek: (flags & mask) != 0U."},
                {"type": "heading", "text": "Posun potrebuje správny typ aj počet"},
                {"type": "paragraph", "text": "Zápis 1U << 3 vytvorí masku s hodnotou 8. Prípona U dáva jednotke typ unsigned int. Zápis 1 << 31 môže byť na bežnom 32-bitovom int nedefinovaný, aj keď výsledok neskôr priradíš do unsigned: rozhoduje typ výrazu pri výpočte, nie cieľ priradenia. Pre väčšie masky vyber zodpovedajúci neznamienkový typ a literál, napríklad 1ULL."},
                {"type": "paragraph", "text": "Počet posúvaných miest nesmie byť záporný ani dosiahnuť šírku povýšeného ľavého operandu. Pri znamienkových typoch pribúdajú ďalšie obmedzenia: v C17 je posun záporného čísla doľava nedefinovaný a výsledok jeho posunu doprava závisí od implementácie. Bitové masky preto navrhuj s neznamienkovými operandmi."},
                {"type": "paragraph", "text": "Pozor na malé typy: hodnota uint8_t sa na bežnej platforme pred operáciou povýši na int. Výsledok ~value tak nie je automaticky osembitový. Ak potrebuješ iba spodných osem bitov, vyber ich maskou 0xFFU a až potom ulož výsledok. Typy uint8_t či uint32_t zo stdint.h sú dostupné iba tam, kde implementácia podporuje presnú požadovanú šírku. Počet bitov v jednom bajte udáva CHAR_BIT z limits.h."},
                {"type": "heading", "text": "Rozsah over ešte pred výpočtom"},
                {"type": "paragraph", "text": "Znamienkové pretečenie nie je spoľahlivé pretočenie na zápornú hodnotu. Výraz INT_MAX + 1 má v C nedefinované správanie. Neznamienková aritmetika sa síce vykonáva modulo maximum plus jedna, ale ani jej definované pretočenie nie je vhodné pri počítaní veľkosti pamäte alebo ceny."},
                {"type": "code", "language": "c", "title": "Sčítanie, ktoré odmietne výsledok mimo rozsahu", "source": CHECKED_ADD},
                {"type": "paragraph", "text": "Pri kladnom right sa pýtame, či je left väčšie než ešte dostupný rozsah INT_MAX - right. Pri zápornom right kontrolujeme dolnú hranicu INT_MIN - right. Tieto odčítania sú vo svojich vetvách bezpečné. Až keď kontrola prejde, vypočítame súčet. Parameter result musí ukazovať na platný meniteľný int; pri neúspechu zostane jeho pôvodná hodnota zachovaná."},
                {"type": "heading", "text": "Vyskúšaj si hranice"},
                {"type": "paragraph", "text": "Pridaj štvrté oprávnenie s hodnotou 1U << 3 a over, že vypnutie zápisu ostatné príznaky nezmení. Potom pri checked_add porovnaj dvojice INT_MAX a 0, INT_MAX a 1, INT_MIN a -1. Vysvetli, prečo kontrola vykonaná až po sčítaní prichádza neskoro."}
            ]
        }
    },
    {
        "key": "memory",
        "parent_key": "data",
        "kind": "lesson",
        "position": 100,
        "title": "Dynamická pamäť",
        "summary": "malloc, calloc, realloc, free a vlastníctvo alokácie.",
        "content": {
            "lead": "Dynamická alokácia umožňuje získať pamäť počas behu programu a riadiť jej životnosť nezávisle od jedného volania funkcie. Získaný blok má svoju veľkosť a vlastníka: program musí vedieť, kam smie zapisovať a kto pamäť napokon uvoľní.",
            "blocks": [
                {"type": "heading", "text": "Kedy pevné pole nestačí"},
                {"type": "paragraph", "text": "Program zbiera merania, no ich konečný počet na začiatku nepozná. Pevné pole môže mať zbytočne veľkú rezervu alebo sa zaplniť príliš skoro. Dynamické pole si preto eviduje ukazovateľ na blok, počet platných hodnôt a kapacitu. Počet hovorí, koľko prvkov už obsahuje údaje; kapacita hovorí, koľko prvkov sa do bloku zmestí."},
                {"type": "paragraph", "text": "Musí platiť count <= capacity. Zapisovať smieme iba na index menší než capacity; čítať ako meranie iba prvok, ktorý sme už inicializovali. Alokácia nezisťuje, či používaš správny index. Ak vopred poznáš malú pevnú hornú hranicu a údaje nepotrebujú dlhšiu životnosť, obyčajné pole býva jednoduchšie."},
                {"type": "heading", "text": "Štyri základné funkcie zo stdlib.h"},
                {"type": "list", "items": [
                    "malloc(bytes) žiada jeden blok s daným počtom bajtov. Jeho obsah nie je inicializovaný; pred čítaním musíš uložiť hodnoty.",
                    "calloc(count, size) žiada miesto pre count prvkov danej veľkosti a vynuluje všetky bity. Pre pole int to znamená nulové hodnoty. Všeobecne však nulové bity nemusia predstavovať nulový ukazovateľ ani hodnotu 0.0 každého desatinného typu.",
                    "realloc(pointer, bytes) mení veľkosť alokovaného bloku. Zachová obsah po menšiu zo starej a novej veľkosti; pridaná časť nie je inicializovaná. Môže pritom premiestniť celý blok.",
                    "free(pointer) uvoľní platný dynamicky alokovaný blok. Odovzdaj jeho začiatok, nie adresu vnútorného prvku. free(NULL) je dovolené a nič neurobí."
                ]},
                {"type": "paragraph", "text": "Pri požiadavke na nenulovú veľkosť znamená návrat NULL, že sa pamäť nepodarilo získať. Over ho pred prvým zápisom. V C netreba návrat malloc pretypovať: void * sa prevedie na vhodný objektový ukazovateľ. Potrebnú deklaráciu funkcie však musíš mať z hlavičky stdlib.h."},
                {"type": "heading", "text": "Veľkosť bloku nie je počet prvkov"},
                {"type": "paragraph", "text": "Pole n celých čísel potrebuje n * sizeof *values bajtov. Zápis sizeof *values vychádza z typu prvku, takže zostane správny aj po zmene int na iný typ. Samotné násobenie ale môže pretiecť. Ak n pochádza zo vstupu alebo z výpočtu, ešte pred násobením over n <= SIZE_MAX / sizeof *values. SIZE_MAX zo stdint.h je najväčšia hodnota typu size_t."},
                {"type": "callout", "tone": "warning", "text": "Nulovú požiadavku rieš osobitne. Pravidlá alokácie veľkosti 0, najmä realloc(pointer, 0), nie sú vhodný základ prenositeľného rozhrania. V nasledujúcom príklade nulu odmietame; vyprázdnenie riešime explicitným free a nastavením vlastného stavu na NULL a 0."},
                {"type": "heading", "text": "Rast poľa bez straty pôvodných dát"},
                {"type": "code", "language": "c", "title": "Z troch meraní na päť", "source": GROW_BUFFER},
                {"type": "paragraph", "text": "Funkcia resize_values dostáva adresu ukazovateľa aj adresu kapacity, pretože po úspechu musí zmeniť obe premenné volajúceho. Zápis int **values je ukazovateľ na ukazovateľ; *values je samotná adresa bloku a sizeof **values je veľkosť jedného int. Oba výstupné parametre musia označovať platné premenné. Vlastník odovzdá buď NULL, alebo začiatok svojho stále platného alokovaného bloku."},
                {"type": "list", "items": [
                    "Na začiatku máme values == NULL, count == 0 a capacity == 0. Volanie realloc s NULL a kladnou veľkosťou sa správa ako malloc.",
                    "Po prvej úspešnej požiadavke je kapacita 3. Tri zápisy vytvoria merania 10, 20 a 30 a zvýšia count na 3.",
                    "Druhá požiadavka zmení kapacitu na 5. Staré tri merania zostávajú zachované, no dve nové miesta ešte nemajú hodnoty.",
                    "Až po zápise 40 a 50 je count rovné 5. Program vypíše count: 5, capacity: 5 a riadok 10 20 30 40 50.",
                    "Pri zlyhaní rastu stále vlastníme pôvodný blok, preto ho pred návratom z main uvoľníme."
                ]},
                {"type": "paragraph", "text": "Dočasný ukazovateľ chráni chybovú cestu. Keby sme napísali values = realloc(values, bytes) a alokácia zlyhala, prepísali by sme jedinú adresu pôvodného bloku hodnotou NULL. Funkcia v príklade preto mení ukazovateľ aj kapacitu až po úspechu; pri neúspechu zachová oboje. Pri zmenšení kapacity by volajúci musel upraviť aj počet platných prvkov. Náš main kapacitu iba zväčšuje."},
                {"type": "callout", "tone": "warning", "text": "Po úspešnom realloc používaj výhradne vrátený ukazovateľ. Staré kópie adresy aj ukazovatele na vnútorné prvky už nepoužívaj, ani keď blok zdanlivo zostal na rovnakej adrese. Potrebné pohľady vytvor znovu z nového ukazovateľa a platného indexu."},
                {"type": "heading", "text": "Vlastníctvo musí prežiť aj chybu"},
                {"type": "paragraph", "text": "Vlastník je tá časť programu, ktorá zodpovedá za uvoľnenie bloku. Ostatné funkcie si môžu adresu iba požičať, napríklad na výpis, a nesmú ju svojvoľne uvoľniť. Do zmluvy funkcie preto patrí, či pamäť vytvára, požičiava si ju alebo preberá jej vlastníctvo. Návrat z funkcie neuvoľní dynamický blok automaticky."},
                {"type": "list", "items": [
                    "Únik pamäte nastane, keď stratíš možnosť uvoľniť blok, ktorý už nepotrebuješ.",
                    "Dvojité free uvoľňuje ten istý blok opakovane a má nedefinované správanie.",
                    "Prístup po free používa objekt, ktorého životnosť sa skončila; obsah na adrese už nie je tvoj.",
                    "Nastavenie vlastného ukazovateľa na NULL po free uľahčí správu stavu, ale nezneplatní bezpečným spôsobom jeho kópie v iných premenných."
                ]},
                {"type": "heading", "text": "Over si životný cyklus"},
                {"type": "paragraph", "text": "V modeli životnosti pamäte sleduj zvlášť adresu a existenciu objektu. Potom v programe zmeň požadovanú kapacitu z 5 na 0. Funkcia má požiadavku odmietnuť a main musí pôvodný blok uvoľniť bez výpisu piatich meraní. Vysvetli aj to, prečo samotný správny číselný výstup ešte nedokazuje, že program pamäť uvoľnil."}
            ]
        }
    },
    {
        "key": "callbacks",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 52,
        "title": "Funkčné ukazovatele, callbacky a variadické funkcie",
        "summary": "Ako odovzdať správanie funkcii, kedy pridať kontext a kde má variadické rozhranie svoje hranice.",
        "content": {
            "lead": "Funkčný ukazovateľ je hodnota s adresou funkcie a presným typom jej rozhrania. Callback nie je zvláštny jazykový mechanizmus: je to funkcia, ktorú jedna časť programu odovzdá druhej spolu s jasným kontraktom.",
            "blocks": [
                {"type": "heading", "text": "Typ callbacku je súčasťou kontraktu"},
                {"type": "paragraph", "text": "Pomenovaný typedef skracuje zápis a dáva rozhraniu význam. Podpis musí presne vyjadriť parametre aj návratovú hodnotu; nekompatibilný pretypovaný ukazovateľ na funkciu nie je bezpečná náhrada."},
                {"type": "code", "language": "c", "title": "Odovzdanie jednej operácie", "source": "typedef int (*BinaryOperation)(int left, int right);\n\nstatic int apply(int left, int right, BinaryOperation operation)\n{\n    return operation(left, right);\n}\n\nstatic int maximum(int left, int right)\n{\n    return left > right ? left : right;\n}\n\nint result = apply(4, 9, maximum);"},
                {"type": "callout", "tone": "tip", "text": "Callback, ktorý potrebuje vlastný stav, zvyčajne dostane navyše ukazovateľ context. Kto ho vytvoril, kto ho uvoľní a či smie byť NULL, musí byť v kontrakte rozhrania."},
                {"type": "heading", "text": "Variadické argumenty"},
                {"type": "paragraph", "text": "Funkcia s ... nepozná počet ani typ ďalších argumentov. Preto potrebuje samostatné pravidlo, napríklad formátovací reťazec ako printf alebo presný počet argumentov. V implementácii používaj va_list, va_start, va_arg a va_end z stdarg.h."},
                {"type": "callout", "tone": "warning", "text": "Variadické rozhranie prichádza o časť typovej kontroly. Keď sa dá rovnaký problém vyjadriť poľom, štruktúrou alebo bežnou funkciou, je to spravidla čitateľnejšia a bezpečnejšia voľba."},
            ],
        },
    },
    {
        "key": "qualifiers",
        "parent_key": "data",
        "kind": "lesson",
        "position": 105,
        "title": "const, volatile, restrict a atomické operácie",
        "summary": "Kvalifikátory typu vyjadrujú zmluvu o zmene dát, vonkajších účinkoch, aliasoch a súbežnosti.",
        "content": {
            "lead": "Samotný typ int * ešte nepovie, či funkcia smie údaje meniť, či ich mení zariadenie alebo či s nimi pracuje viac vlákien. const, volatile, restrict a atomické typy riešia odlišné otázky. Porozumieť ich rozdielom je dôležitejšie než pridať ku každej premennej ďalšie slovo.",
            "blocks": [
                {"type": "heading", "text": "const: čo cez toto meno smieme zmeniť"},
                {"type": "paragraph", "text": "Funkcia, ktorá iba číta merania, môže dostať const int *values. Zápis oznamuje, že cez tento ukazovateľ nesmie meniť prvky. Nesľubuje však, že dáta nikto iný nikdy nezmení. Rozlišuj objekt skutočne definovaný ako const od pohľadu na meniteľný objekt cez ukazovateľ na const."},
                {"type": "list", "items": [
                    "const int limit = 10 vytvorí objekt, ktorý sa nesmie meniť. Pokus o jeho zmenu po odstránení const pretypovaním má nedefinované správanie.",
                    "const int *view dovolí zmeniť uloženú adresu, ale nedovolí zápis cez *view. Rovnaký význam má int const *view.",
                    "int *const fixed nedovolí priradiť inú adresu do fixed, ale dovoľuje meniť int, na ktorý ukazuje.",
                    "const int *const fixed_view nedovolí ani zmenu adresy, ani zápis do cieľa cez tento ukazovateľ."
                ]},
                {"type": "code", "language": "c", "title": "Jeden objekt, tri pohľady", "source": CONST_VIEWS},
                {"type": "paragraph", "text": "Zápis *fixed = 15 mení prvý prvok obyčajného poľa int, preto je dovolený. view vidí tú istú hodnotu 15: const z poľa nevytvorilo samostatnú kópiu. Potom ++view presunie pohľad na druhý prvok a výpis je 20. fixed_view naďalej ukazuje na prvý prvok s hodnotou 15. Jeho nemennosť sa týka prístupu cez tento ukazovateľ, nie všetkých ciest k pôvodnému poľu."},
                {"type": "callout", "tone": "warning", "text": "const nezaručuje životnosť objektu ani bezpečnosť medzi vláknami. Ukazovateľ na const môže zostať visieť po free rovnako ako iný ukazovateľ. Meniteľné pole z príkladu smieme upravovať jeho pôvodným prístupom; skutočne const objekt nesmieme meniť žiadnym prístupom."},
                {"type": "heading", "text": "volatile nie je zámok"},
                {"type": "paragraph", "text": "Pamäťovo mapovaný register zariadenia sa môže zmeniť bez priradenia v tvojom C kóde. Čítanie môže mať aj účinok na hardvér, napríklad potvrdenie udalosti. volatile označuje prístup, ktorý prekladač musí rešpektovať podľa pravidiel svojej implementácie, namiesto toho, aby s hodnotou zaobchádzal ako s obyčajnou nemennou medzihodnotou."},
                {"type": "paragraph", "text": "Adresy registrov, šírku prístupu aj prípadné pamäťové bariéry určuje konkrétny mikrokontrolér a jeho dokumentácia. Používaj hlavičky výrobcu; na bežnom počítači neskúšaj dereferencovať vymyslenú adresu registra. Pri obsluhe signálov v C sa za presne určených pravidiel používa volatile sig_atomic_t zo signal.h. Ani tento typ nie je všeobecným nástrojom na komunikáciu vlákien."},
                {"type": "callout", "tone": "warning", "text": "volatile nezaručuje nedeliteľnosť operácie ani synchronizáciu bežnej pamäte medzi vláknami. Výraz counter++ na volatile int nie je bezpečné spoločné počítadlo. Na register zariadenia zasa bez preverenia dokumentácie nepoužívaj atomické operácie určené pre bežnú pamäť."},
                {"type": "heading", "text": "restrict: sľub o prístupoch k pamäti"},
                {"type": "paragraph", "text": "Dva ukazovatele môžu označovať ten istý objekt; tomu sa hovorí aliasovanie. Prekladač musí pri optimalizácii zohľadniť, že zápis cez jeden môže zmeniť hodnotu čítanú cez druhý. restrict umožní rozhraniu vyjadriť silnejší sľub o prístupoch k meneným objektom počas daného vykonávania bloku. Nie je to automatická kontrola ani zákaz existencie všetkých kópií adresy."},
                {"type": "code", "language": "c", "title": "Kopírovanie neprekrývajúcich sa polí", "source": RESTRICT_COPY},
                {"type": "paragraph", "text": "Táto funkcia zapisuje cez target a číta cez source. Jej zmluva vyžaduje dve platné oblasti s aspoň count prvkami, ktoré sa neprekrývajú. Samostatné polia source a target v main podmienku spĺňajú a program vypíše 3 1 4. Volanie copy_values(values + 1, values, 2) by pri dostatočne veľkom poli stále porušovalo zmluvu prekrývaním; výsledok nie je spoľahlivý."},
                {"type": "paragraph", "text": "Ak prekrývanie potrebuješ, pre kopírovanie bajtov slúži memmove. Samotné odstránenie restrict neopraví smer kopírovania v každom ručne napísanom cykle. Tento kvalifikátor pridávaj až vtedy, keď vieš sľub rozhrania dodržať vo všetkých volaniach."},
                {"type": "heading", "text": "Atomická operácia je nedeliteľný krok"},
                {"type": "paragraph", "text": "Predstav si dve vlákna, ktoré práve dokončili po jednej úlohe. Ak obe prečítajú obyčajné počítadlo s hodnotou 0 a obe zapíšu 1, jedno zvýšenie sa stratí. V C je nesynchronizovaný konflikt prístupov k bežnému objektu, z ktorých aspoň jeden zapisuje, dátovým pretekom a má nedefinované správanie. Atomické typy a funkcie zo stdatomic.h poskytujú operácie určené na takúto spoluprácu."},
                {"type": "list", "items": [
                    "atomic_int alebo _Atomic int označuje atomický int; atomic_uint je neznamienková verzia. Objekt inicializuj predtým, než k nemu získajú prístup ďalšie vlákna.",
                    "atomic_load prečíta hodnotu a atomic_store uloží novú hodnotu. Každé volanie je samostatná atomická operácia.",
                    "atomic_fetch_add spája načítanie, zvýšenie a zápis do jednej operácie a vracia predchádzajúcu hodnotu. Rozdelenie na atomic_load a neskorší atomic_store by mohlo zvýšenia opäť strácať.",
                    "atomic_exchange vymení hodnotu a vráti pôvodnú. atomic_compare_exchange porovná hodnotu s očakávanou a podmienene ju zmení; používa sa v pokročilejších algoritmoch.",
                    "atomic_flag poskytuje základné operácie test-and-set a clear. Ani z týchto stavebných prvkov však bez správneho návrhu nevznikne bezpečný zámok."
                ]},
                {"type": "code", "language": "c", "title": "Predchádzajúca a nová hodnota počítadla", "source": ATOMIC_COUNTER},
                {"type": "paragraph", "text": "Program vypíše previous: 0 a current: 1. Beží zámerne v jednom vlákne, aby bolo vidieť návratovú hodnotu atomic_fetch_add; nepredstiera tým skúšku súbežného programu. Atómovosť navyše nemusí znamenať jednu strojovú inštrukciu ani vykonanie bez interného zámku. Podpora atomických typov je v C17 voliteľná; pri prenose na mikrokontrolér over prekladač aj dostupnú knižnicu."},
                {"type": "heading", "text": "Poradie pamäte a hranice záruky"},
                {"type": "paragraph", "text": "Použité funkcie bez prípony _explicit pracujú s poradím memory_order_seq_cst. Pri pokročilom návrhu existujú aj slabšie poradia: relaxed zaručuje atomickú operáciu, no samo nesprístupňuje okolité neatomické dáta inému vláknu. Zodpovedajúca dvojica release a acquire môže vytvoriť potrebný vzťah medzi zápisom dát a ich čítaním. Slabšie poradie nevyberaj iba podľa predstavy, že bude rýchlejšie."},
                {"type": "paragraph", "text": "Ani dve atomické premenné netvoria automaticky jednu transakciu. Ak musia zostať súčasne konzistentné viaceré hodnoty, napríklad počet a obsah frontu, často je vhodnejší mutex a jasné pravidlo jeho držania. Podrobné algoritmy vlákien a pamäťový model patria do samostatného pokračovania; tu je cieľom správne vybrať nástroj a nepliesť si jeho záruky."},
                {"type": "heading", "text": "Vyber nástroj podľa problému"},
                {"type": "paragraph", "text": "Čítanie poľa bez jeho úpravy vyjadri cez const. Prístup k hardvéru rieš podľa dokumentácie vrátane volatile. Neprekrývajúce sa oblasti môže rozhranie sľúbiť cez restrict. Spoločné počítadlo potrebuje atomickú operáciu; viac navzájom závislých zmien môže potrebovať zámok. Pri každej voľbe vysvetli aj to, čo vybraný nástroj nezaručuje."},
            ],
        },
    },
    {
        "key": "preprocessor",
        "parent_key": "tooling",
        "kind": "lesson",
        "position": 115,
        "title": "Preprocesor, makrá a podmienený preklad",
        "summary": "Textová fáza pred prekladom, include guardy, bezpečné makrá a hranica medzi konfiguráciou a kódom.",
        "content": {
            "lead": "Skôr než prekladač skontroluje typy a vytvorí strojový kód, preprocesor vloží hlavičky, rozvinie makrá a vyberie podmienene prekladané časti. Nie je to druhý program bežiaci popri tvojom programe: pripravuje text, ktorý sa ešte len bude prekladať.",
            "blocks": [
                {"type": "heading", "text": "Prečo sa zdroj najprv upravuje"},
                {"type": "paragraph", "text": "Predstav si program na meranie teploty. Potrebuje deklarácie knižničných funkcií, spoločné rozhranie snímača a možno aj diagnostické výpisy, ktoré vo výslednej verzii nechceš. Vkladanie deklarácií rieši #include, pomenované náhrady #define a výber konfigurácie #if. Aktuálnu nameranú teplotu však preprocesor nepozná; o nej rozhodne až bežný if počas behu."},
                {"type": "paragraph", "text": "Preprocesor pracuje s tokenmi, teda so základnými jednotkami zdrojového zápisu, napríklad s menami, číslami a operátormi. Nerozumie im ako typovaným premenným a funkciám. Direktíva začína znakom # na začiatku riadka, prípadne po medzerách. Za #include ani #define sa nepridáva bodkočiarka; pri makre by sa stala súčasťou náhrady."},
                {"type": "heading", "text": "Čo sa vloží cez include"},
                {"type": "paragraph", "text": "#include <stdio.h> sprístupní štandardné deklarácie pre vstup a výstup. #include \"merania.h\" používame pre vlastnú hlavičku projektu. Presný postup hľadania závisí od implementácie a jej nastavení; GCC pri úvodzovkách najprv hľadá pri súbore, ktorý hlavičku vkladá. Ďalšie projektové adresáre možno pridať prepínačom -I."},
                {"type": "paragraph", "text": "Vloženie hlavičky nie je volanie funkcie ani automatické pripojenie jej implementácie. Pri čítaní zdroja si predstav, že sa na miesto direktívy vložia deklarácie z hlavičky. Kde sa neskôr vezme strojový kód funkcie, rieši preklad a linkovanie v nasledujúcej lekcii."},
                {"type": "heading", "text": "Ochrana pred opakovaným vložením"},
                {"type": "code", "language": "c", "title": "Malá hlavička snimac.h", "source": "#ifndef POZNAMKOVNIK_SNIMAC_H\n#define POZNAMKOVNIK_SNIMAC_H\n\ntypedef struct {\n    double teplota;\n} Meranie;\n\n#endif"},
                {"type": "paragraph", "text": "Pri prvom vložení meno POZNAMKOVNIK_SNIMAC_H ešte nie je definované, preto #ifndef pustí obsah ďalej. #define meno zapamätá a pri ďalšom vložení sa obsah preskočí. Takáto ochrana sa nazýva include guard. Meno zvoľ jedinečné v projekte a nezačínaj ho podčiarkovníkom. #pragma once je rozšírená alternatíva prekladačov, nie súčasť prenositeľného C17."},
                {"type": "callout", "tone": "warning", "text": "Guard chráni pred opakovaným vložením v rámci jednej prekladovej jednotky. Nezabráni tomu, aby sa definícia globálneho objektu alebo bežnej funkcie z hlavičky vytvorila osobitne v dvoch .c súboroch. To je iný problém, ktorý môže odhaliť až linker."},
                {"type": "heading", "text": "Dva základné druhy makier"},
                {"type": "list", "items": [
                    "Objektové makro, napríklad #define SAMPLE_LIMIT 16, nahrádza meno postupnosťou tokenov. Nevytvára premennú ani vlastný typ.",
                    "Funkčné makro, napríklad #define SQUARE(value) ((value) * (value)), prijíma argumenty zápisu a dosadzuje ich do náhrady. Pri definícii nesmie byť medzera medzi menom makra a otváracou zátvorkou.",
                    "#undef SAMPLE_LIMIT ukončí platnosť definície makra od daného miesta. Makrá nemajú blokový rozsah ako lokálne premenné a názvami môžu ovplyvniť aj neskôr vložené hlavičky."
                ]},
                {"type": "paragraph", "text": "Makro si nevyberaj iba preto, že pomenúva konštantu. Pre typovanú hodnotu býva vhodné const a pre pomenované celočíselné možnosti enum. Makro je potrebné napríklad tam, kde jeho hodnotu musí vyhodnotiť samotný #if. Pozor: lokálne const int v C17 nie je automaticky celočíselným konštantným výrazom ako v niektorých iných jazykoch."},
                {"type": "heading", "text": "Zátvorky chránia argument aj celý výsledok"},
                {"type": "code", "language": "c", "title": "Rovnaký argument, rozdielna náhrada", "source": MACRO_PARENTHESES},
                {"type": "paragraph", "text": "BAD_SQUARE(2 + 3) nedostane najprv vypočítanú päťku. Do jeho náhrady sa dvakrát vloží zápis 2 + 3 a vznikne 2 + 3 * 2 + 3, teda 11. SQUARE uzavrie argumenty aj celý súčin do zátvoriek, preto dá 25. Vonkajšie zátvorky zachovajú zoskupenie aj pri výraze 100 / SQUARE(2 + 3), ktorého výsledok je 4."},
                {"type": "code", "language": "c", "title": "Samostatný vstup pre preprocesor: makra.c", "source": MACRO_EXPANSION},
                {"type": "code", "language": "sh", "title": "Iba rozvinutie makier pomocou GCC", "source": "gcc -std=c17 -E -P makra.c"},
                {"type": "code", "language": "c", "title": "Výstup preprocesora pre makra.c", "source": MACRO_EXPANDED},
                {"type": "paragraph", "text": "Prepínač -E zastaví GCC po predspracovaní a -P potlačí značky pôvodných riadkov, aby bol krátky výstup prehľadný. Tento zdroj zámerne neobsahuje main: sledujeme iba predspracovanie, nie spustiteľný program. Rozvinutie makra je dobrý prvý krok pri hľadaní chyby, ktorú v pôvodnom zápise nevidno."},
                {"type": "heading", "text": "Zátvorky nevyriešia vedľajšie účinky"},
                {"type": "paragraph", "text": "Ani lepšie zapísané SQUARE nie je bezpečné pre ľubovoľný argument. SQUARE(next++) by sa rozvinulo na ((next++) * (next++)): ten istý objekt by sa menil dvakrát bez potrebného usporiadania. V C17 má takýto výraz nedefinované správanie. Nehľadaj preň správny číselný výsledok; oprav spôsob odovzdania hodnoty."},
                {"type": "code", "language": "c", "title": "Funkcia vyhodnotí tento argument iba raz", "source": SINGLE_EVALUATION},
                {"type": "paragraph", "text": "square dostane hodnotu 3, premenná next sa zvýši na 4 a telo funkcie vráti 9. Použitie parametra value dvakrát už nemení next, pretože parameter je samostatná kópia hodnoty. inline nie je príkaz na povinné vloženie strojového kódu; o optimalizácii rozhoduje prekladač. Aj funkcia potrebuje platný rozsah vstupu, aby jej násobenie nepretieklo."},
                {"type": "heading", "text": "Podmienený preklad nie je bežná podmienka"},
                {"type": "code", "language": "c", "title": "Diagnostika podľa konfigurácie zostavenia", "source": CONDITIONAL_BUILD},
                {"type": "paragraph", "text": "Bez vlastného nastavenia má DEBUG_LOG hodnotu 0 a program vypíše iba average: 12.0 na stdout. Po zmene hodnoty na 1 pribudne diagnostika na stderr. V termináli možno rovnakú konfiguráciu odovzdať ako -DDEBUG_LOG=1 pri preklade. Hodnota 2 vyvolá cez #error zámernú chybu konfigurácie ešte pred vytvorením programu."},
                {"type": "list", "items": [
                    "#ifdef NAME zisťuje existenciu definície; #ifndef NAME jej neprítomnosť. Aj #define DEBUG_LOG 0 preto vyhovuje #ifdef DEBUG_LOG.",
                    "#if DEBUG_LOG testuje hodnotu. #elif pridá ďalšiu možnosť, #else zvyšnú vetvu a #endif celú skupinu uzavrie.",
                    "defined(NAME) možno použiť vo výraze #if. Nedefinované mená sa v takomto výraze nahradia nulou; -Wundef v GCC pomáha odhaliť preklepy.",
                    "#if nepozná hodnoty premenných, typy ani sizeof. Bežný if spracúva hodnoty za behu a nenahrádza výber platformovo odlišného zdrojového kódu."
                ]},
                {"type": "heading", "text": "Ďalšie zápisy, ktoré stretneš v knižniciach"},
                {"type": "paragraph", "text": "Operátor # pred parametrom makra vytvorí reťazcový literál z jeho zápisu; ## spojí susedné tokeny do jedného platného tokenu, napríklad časti mena. Pri týchto operátoroch sa argument nerozvinie vopred obvyklým spôsobom, preto sa používa aj dvojúrovňové makro. Variadické makrá používajú ... a __VA_ARGS__. Viacriadková definícia pokračuje spätnou lomkou tesne pred koncom riadka. Toto sú nástroje na tvorbu rozhraní a diagnostiky, nie náhrada bežných funkcií."},
                {"type": "paragraph", "text": "Makro s viacerými príkazmi sa často balí do do { ... } while (0), aby sa v podmienke správalo ako jeden príkaz. Stále však treba preveriť opakované argumenty aj kolízie pomocných mien. V diagnostike sa stretneme aj s __FILE__ a __LINE__; __STDC_VERSION__ označuje verziu štandardu. Podrobné generovanie kódu makrami je nadstavba, nie podmienka na zvládnutie tejto lekcie."},
                {"type": "heading", "text": "Skús predpovedať výsledok"},
                {"type": "paragraph", "text": "Najprv bez spustenia rozviň SQUARE(1 + 4) a vysvetli obe úrovne zátvoriek. Potom porovnaj #ifdef DEBUG_LOG s #if DEBUG_LOG pri hodnote 0. Nakoniec povedz, prečo sa zápis SQUARE(next++) neopraví pridaním ďalších zátvoriek okolo celého volania. Správna odpoveď musí hovoriť o počte zmien next, nie iba o poradí násobenia."},
            ],
        },
    },
    {
        "key": "portability",
        "parent_key": "tooling",
        "kind": "lesson",
        "position": 136,
        "title": "Prenositeľnosť a presné pravidlá C",
        "summary": "Rozdiel medzi definovaným, nešpecifikovaným a implementačne závislým správaním; ako písať kód, ktorý nie je náhodou závislý od jedného stroja.",
        "content": {
            "lead": "C dáva implementácii priestor pre odlišnosti architektúr a prekladačov. Prenositeľný program sa nespolieha na to, čo na jednom počítači vyšlo náhodou rovnako ako zamýšľané pravidlo.",
            "blocks": [
                {"type": "heading", "text": "Tri hranice správania"},
                {"type": "list", "items": ["Definované správanie opisuje štandard a program sa naň môže spoliehať.", "Implementačne závislé správanie má dovolené varianty, no implementácia ho má zdokumentovať, napríklad znamienkovosť char.", "Nešpecifikované správanie ponúka viac dovolených výsledkov bez povinnosti zvoliť stále ten istý.", "Nedefinované správanie ruší záruky štandardu, napríklad prístup mimo poľa alebo znamienkové pretečenie."]},
                {"type": "heading", "text": "Píš úmysel, nie predpoklad"},
                {"type": "paragraph", "text": "Na presnú šírku použi typy z stdint.h, na veľkosti size_t, na poradie bajtov explicitnú konverziu a na text kontroluj kódovanie aj kapacitu. Nikdy neodvodzuj rozloženie struct podľa očakávaného počtu bajtov bez pravidiel zarovnania a prenosového formátu."},
                {"type": "callout", "tone": "warning", "text": "-Wall a ďalšie varovania, sanitizéry a testovanie na viac než jednej platforme pomáhajú, ale nie sú dôkazom, že sa program vyhol všetkému nedefinovanému správaniu. Kontrakt a pravidlá jazyka majú prednosť."},
            ],
        },
    },
    {
        "key": "tooling",
        "parent_key": "",
        "kind": "chapter",
        "position": 110,
        "title": "Nástroje a spoľahlivosť",
        "summary": "Moduly, vstup/výstup, chyby a nedefinované správanie.",
        "content": {"lead": "Čitateľný C program sa nestavia iba syntaxou. Dôležitá je štruktúra zdrojov, kontrola chýb a systematické testovanie.", "sections": [{"title": "V tejto kapitole", "bullets": ["Hlavičkové a zdrojové súbory.", "Štandardný vstup a výstup.", "Varovania, sanitizéry a nedefinované správanie."]}]}
    },
    {
        "key": "build",
        "parent_key": "tooling",
        "kind": "lesson",
        "position": 120,
        "title": "Hlavičky, moduly a linkovanie",
        "summary": "Rozdelenie programu do .c a .h súborov bez duplicitných deklarácií.",
        "content": {
            "lead": "Pri rozdelení programu nestačí premiestniť polovicu riadkov do druhého súboru. Každý modul potrebuje zrozumiteľné rozhranie, vlastnú implementáciu a pravidlo, ako sa jeho strojový kód pripojí k ostatným. Hlavička a linker riešia dve odlišné časti tejto úlohy.",
            "blocks": [
                {"type": "heading", "text": "Začni rozdelením zodpovedností"},
                {"type": "paragraph", "text": "Program má zo zoznamu meraní zistiť minimum a maximum a potom ich vypísať. Výpočet nepotrebuje vedieť, či sa výsledok zobrazí na obrazovke alebo uloží do súboru. Preto ho oddelíme do modulu merania. main zostane zodpovedný za prípravu vstupu, rozhodnutie pri chybe a výpis výsledku."},
                {"type": "list", "items": [
                    "merania.h opisuje verejné typy a deklarácie, ktoré potrebuje používateľ modulu.",
                    "merania.c definuje funkciu a údaje modulu a obsahuje jeho súkromné pomocné funkcie.",
                    "main.c vloží hlavičku a používa jej rozhranie bez kopírovania implementácie."
                ]},
                {"type": "heading", "text": "Deklarácia oznamuje, definícia vytvára"},
                {"type": "paragraph", "text": "Deklarácia funkcie merania_rozsah oznamuje jej meno, návratový typ a typy parametrov. Definícia k tomu pridáva telo funkcie. Volajúci potrebuje deklaráciu ešte pred volaním, aby prekladač vedel skontrolovať argumenty; výsledný program potrebuje aj definíciu. Definícia je zároveň deklaráciou, ale samotný prototyp s bodkočiarkou telo nevytvorí."},
                {"type": "code", "language": "c", "title": "merania.h: verejné rozhranie", "source": MEASUREMENTS_HEADER},
                {"type": "paragraph", "text": "Hlavička sama vkladá stddef.h, pretože vo svojom rozhraní používa size_t. Používateľ nemusí hádať poradie ďalších include. Typ Rozsah spája dve súvisiace hodnoty; jeho definícia patrí do hlavičky, lebo volajúci vytvára objekt tohto typu. Guard zabráni opakovanej definícii typu v jednej prekladovej jednotke."},
                {"type": "paragraph", "text": "Zmluva merania_rozsah je nasledovná: values označuje aspoň count platných prvkov, result označuje meniteľný objekt Rozsah a pole musí byť neprázdne. Funkcia odmietne NULL, nulový počet aj nečíselné či nekonečné merania. Pri úspechu vráti 1 a zapíše výsledok; pri chybe vráti 0 a výsledný objekt nezmení. Pamäť si iba požičiava a nič z nej neuvoľňuje."},
                {"type": "heading", "text": "Implementácia pozná vlastnú hlavičku"},
                {"type": "code", "language": "c", "title": "merania.c: výpočet a súkromná kontrola", "source": MEASUREMENTS_SOURCE},
                {"type": "paragraph", "text": "merania.c vkladá svoju hlavičku ako prvú. Prekladač tak môže porovnať deklaráciu s definíciou v tom istom zdroji. Pomocná funkcia meranie_je_platne používa isfinite z math.h a nepripúšťa NaN ani nekonečno. Je označená static, preto jej meno má vnútornú väzbu: neposkytuje sa na volanie z inej prekladovej jednotky."},
                {"type": "paragraph", "text": "Rozsah začíname prvým meraním, nie nulou; inak by kladné alebo záporné údaje mohli viesť k nesprávnemu výsledku. Dočasný objekt range sa mení vo vnútri funkcie. Až po úspešnom prejdení všetkých prvkov sa celý zapíše cez result. Tak sa aj pri chybe uprostred poľa dodrží sľub, že pôvodný výstup zostane nedotknutý."},
                {"type": "heading", "text": "Volajúci sa spolieha na rozhranie"},
                {"type": "code", "language": "c", "title": "main.c: použitie modulu", "source": MEASUREMENTS_MAIN},
                {"type": "paragraph", "text": "Program vypíše version: 1 a potom minimum: 9.0, maximum: 14.0. Výpočet minima a maxima nie je súčasťou main; táto funkcia iba vytvorí pole, odovzdá jeho počet a skontroluje návratový stav. Zmena vnútorného algoritmu modulu nevyžaduje úpravu volajúceho, pokiaľ sa zachová rozhranie a jeho zmluva."},
                {"type": "heading", "text": "extern a static hovoria o väzbe mien"},
                {"type": "paragraph", "text": "extern const unsigned int merania_verzia v hlavičke deklaruje objekt, ktorého definícia je inde. Riadok const unsigned int merania_verzia = 1U v merania.c je jeho jediná definícia s inicializáciou. V C má takto definovaný objekt na úrovni súboru vonkajšiu väzbu aj napriek const. Tento príklad opisuje C, nie odlišné predvolené pravidlá C++."},
                {"type": "list", "items": [
                    "Bežné verejné funkcie deklaruj v hlavičke a definuj v jednom .c súbore. Slovo extern pri prototype funkcie sa zvyčajne vynecháva.",
                    "Pomocnú funkciu alebo objekt určený iba pre jeden .c súbor označ na úrovni súboru static. Rovnaké pomocné meno potom môže existovať aj v inom module nezávisle.",
                    "static pri lokálnej premennej funkcie rieši uchovanie hodnoty medzi volaniami. To nie je to isté použitie ako skrytie funkcie na úrovni súboru.",
                    "Do hlavičky nedávaj definíciu bežného globálneho objektu s inicializáciou. Ani extern s inicializáciou nie je iba deklarácia.",
                    "Definície typov, makrá a správne navrhnuté static inline pomocné funkcie sú bežné výnimky z jednoduchého pravidla, že implementácia patrí do .c."
                ]},
                {"type": "heading", "text": "Od troch súborov k jednému programu"},
                {"type": "paragraph", "text": "Každý .c súbor spolu s vloženými hlavičkami po predspracovaní tvorí samostatnú prekladovú jednotku. Prekladač z nej vytvorí objektový súbor. Linker spojí objektové súbory a potrebné knižnice, priradí použité mená k definíciám a vytvorí spustiteľný program. Hlavičku preto nepridávame ako ďalší .c súbor do príkazu."},
                {"type": "code", "language": "sh", "title": "Samostatný preklad a spojenie pomocou GCC", "source": "gcc -std=c17 -Wall -Wextra -Wpedantic -c main.c -o main.o\ngcc -std=c17 -Wall -Wextra -Wpedantic -c merania.c -o merania.o\ngcc main.o merania.o -o merania\n./merania"},
                {"type": "paragraph", "text": "Prepínač -c zastaví postup pred linkovaním. main.o preto môže existovať, aj keď ešte nemá pripojenú definíciu merania_rozsah. Rovnaký výsledný program možno vytvoriť jedným príkazom gcc -std=c17 -Wall -Wextra -Wpedantic main.c merania.c -o merania. Príkazy sú určené pre GCC a ./merania pre prostredie so shellom, napríklad Linux."},
                {"type": "paragraph", "text": "Pri zmene hlavičky treba znovu preložiť všetky zdroje, ktoré od nej závisia, nie iba jej vlastný modul. Nástroje ako Make alebo CMake tieto závislosti spravujú. Pri externých knižniciach je -I cesta k hlavičkám, -L cesta ku knižniciam a -l výber knižnice; pri statických knižniciach môže byť dôležité aj poradie za objektovými súbormi, ktoré ich používajú."},
                {"type": "heading", "text": "Zisti, v ktorej fáze nastala chyba"},
                {"type": "list", "items": [
                    "Chýbajúca merania.h: preprocesor nevie vložiť hlavičku. Over názov, relatívnu cestu a nastavenie adresárov hlavičiek.",
                    "Chýbajúci prototyp alebo nesúlad typov: prekladač nerozumie volaniu podľa platných deklarácií. Oprav hlavičku alebo jej vloženie, nie náhodné pretypovanie.",
                    "undefined reference: linker nenašiel potrebnú definíciu. V našom príklade nastane pri vynechaní merania.o zo spojenia.",
                    "multiple definition: do programu sa dostali viaceré definície toho istého verejného mena. Hľadaj implementáciu v hlavičke alebo opakovane pridaný objektový súbor.",
                    "Program sa spustí, ale vráti zlý výsledok: preklad a linkovanie prešli. Ďalej over vstupy, algoritmus a jeho hraničné prípady."
                ]},
                {"type": "paragraph", "text": "Skús vynechať merania.o z tretieho príkazu. main.c sa samostatne preloží, ale linker nemá odkiaľ získať výpočet ani verziu modulu. Ďalšie #include v main to neopraví: deklarácie už pozná. Náprava je pripojiť chýbajúci objektový súbor. Presné znenie hlásenia závisí od použitého linkera."},
                {"type": "callout", "tone": "warning", "text": "Nahradenie chýbajúceho objektového súboru zápisom #include \"merania.c\" zvyčajne iba pomieša zodpovednosti. Ak sa tento .c súbor zároveň preloží osobitne, môže vzniknúť viacnásobná definícia. V bežnom viacmodulovom projekte vkladaj hlavičku a implementáciu pridaj do zostavenia."},
                {"type": "heading", "text": "Prenes rozdelenie do vlastného projektu"},
                {"type": "paragraph", "text": "Jednosúborová verzia toho istého výpočtu je vhodná na skúšanie vstupných dát. Pri spojení zdrojových textov do jedného však zanikne hranica prekladových jednotiek. Takýto beh neoveruje väzby medzi samostatnými objektovými súbormi; na ich overenie treba zachovať trojsúborové rozdelenie a preložiť ho uvedenými príkazmi."},
                {"type": "paragraph", "text": "Porovnaj jedno meranie, rovnaké merania a iba záporné merania. Potom si vyber funkciu z vlastného programu a napíš jej prototyp, platné vstupy a správanie pri chybe. Rozhodni, čo má používateľ modulu poznať a čo má zostať za jeho rozhraním. Tak vzniká modul podľa zodpovednosti, nie iba podľa počtu riadkov."}
            ]
        }
    },
    {
        "key": "io",
        "parent_key": "tooling",
        "kind": "lesson",
        "position": 130,
        "title": "Vstup a výstup",
        "summary": "Prúdy, formátovaný výstup, celé riadky, koniec vstupu a bezpečná práca so súbormi.",
        "content": {
            "lead": "Predstav si program, ktorý prijíma merania a vytvára prehľad výsledkov. Výpočet môže byť správny, no program stále zlyhá, ak prijme iba polovicu čísla alebo si nevšimne chybu pri ukladaní. Vstup a výstup preto tvoria samostatnú časť riešenia s vlastnými pravidlami.",
            "blocks": [
                {"type": "heading", "text": "Tri prúdy, tri rôzne úlohy"},
                {"type": "paragraph", "text": "Prúd predstavuje postupnosť údajov, z ktorej čítame alebo do ktorej zapisujeme. V štandardnej knižnici ho zastupuje FILE *. Nemusíme pritom vedieť, či údaje pochádzajú z klávesnice, zo súboru alebo z iného programu. Hlavička stdio.h sprístupňuje funkcie aj tri vopred otvorené prúdy."},
                {"type": "list", "items": [
                    "stdin je štandardný vstup. Program z neho získava údaje; nie je zaručené, že pri ňom sedí človek.",
                    "stdout je štandardný výstup. Patria sem výsledky, ktoré môže ďalej spracovať iný program.",
                    "stderr je chybový výstup. Patria sem vysvetlenia zlyhaní, aby sa nemiešali s výslednými údajmi."
                ]},
                {"type": "paragraph", "text": "Ak program vypisuje iba čísla do súboru, správa „Chýba meranie“ by tento formát pokazila. Pošli ju preto na stderr a program ukonči neúspešným stavom. Naopak, výzva na zadanie vstupu je vhodná pri rozhovore s človekom, ale pri dávkovom spracovaní by znečisťovala výstup. Nasledujúce príklady preto výzvu nevypisujú."},
                {"type": "heading", "text": "Vyber funkciu podľa toho, čo prenášaš"},
                {"type": "list", "items": [
                    "fgetc a fputc čítajú alebo zapisujú jeden bajt. Návratovú hodnotu fgetc ulož do int, aby si odlíšil všetky hodnoty unsigned char od EOF.",
                    "fgets číta obmedzený úsek riadka. fputs zapisuje reťazec bez pridania nového riadka; puts zapisuje na stdout a nový riadok pridá.",
                    "printf zapisuje formátovaný text na stdout, fprintf do zvoleného prúdu a snprintf do poľa znakov s určenou kapacitou.",
                    "scanf a fscanf prevádzajú text z prúdu, sscanf z reťazca. Vrátia počet úspešne priradených položiek, prípadne EOF pri zlyhaní vstupu pred prvým prevodom. Tento počet nie je počet prečítaných znakov.",
                    "fread a fwrite prenášajú bloky dát a vracajú počet celých prenesených prvkov. Kratší prenos treba vyhodnotiť; surový zápis struct nie je automaticky prenositeľný formát súboru."
                ]},
                {"type": "heading", "text": "Formát nie je komentár, ale súčasť rozhrania"},
                {"type": "paragraph", "text": "Vo výraze printf(\"%d\", count) určuje %d, že ďalší argument má byť int. Funkcia z názvu premennej typ nezistí. Nesúlad formátu a argumentu môže vyvolať nedefinované správanie, nielen nesprávny vzhľad výpisu. Prekladač s varovaniami dokáže mnohé takéto omyly odhaliť."},
                {"type": "list", "items": [
                    "%d používa int, %u unsigned int, %ld long a %zu size_t.",
                    "%f používa pri výstupe double; argument typu float sa pri volaní prevedie na double. %.2f zobrazí dve číslice za desatinnou bodkou, nemení však uloženú hodnotu.",
                    "%c vypíše znak, %s nulou ukončený reťazec a %% samotné percento.",
                    "Pri scanf je rozdiel medzi %f a %lf podstatný: prvý očakáva float *, druhý double *. Pravidlá vstupu a výstupu nie sú totožné."
                ]},
                {"type": "code", "title": "Typy argumentov a kontrola výstupu", "language": "c", "source": FORMATTED_OUTPUT},
                {"type": "paragraph", "text": "Počet je celé číslo, veľkosť objektu má typ size_t a priemer vzniká desatinným delením. Veľkosť int nie je na všetkých platformách rovnaká, preto ju program zisťuje. Reťazec label je argumentom %s: jeho percento sa vypíše ako údaj a nevyhodnotí sa ako ďalší formát. Cudzí text nikdy nepouži priamo ako formát printf."},
                {"type": "paragraph", "text": "printf oznamuje chybu zápornou hodnotou. Úspešný zápis však môže údaje zatiaľ uložiť iba do vyrovnávacej pamäte knižnice. fflush(stdout) ich odovzdá ďalej a umožní zistiť aj chybu, ktorá sa prejaví až v tomto kroku. Nezaručuje fyzické uloženie na disk. Pri snprintf skontroluj záporný výsledok a potom aj to, či sa požadovaný počet znakov zmestil do kapacity vrátane koncového nulového znaku."},
                {"type": "heading", "text": "Prečítaný úsek ešte nemusí byť celý riadok"},
                {"type": "paragraph", "text": "Pre pole char line[8] môže fgets(line, sizeof line, stdin) načítať najviac sedem znakov a za ne pridať '\\0'. Ak sa zmestí aj '\\n', zostane v poli. Keď nový riadok chýba, existujú dve možnosti: riadok sa nezmestil, alebo vstup skončil bez posledného '\\n'. Samotné hľadanie '\\n' tieto situácie nerozlíši."},
                {"type": "paragraph", "text": "Úspešné fgets vracia adresu poľa. Pri NULL najprv odlíš chybu čítania cez ferror od konca vstupu; obsah poľa v chybovej vetve nespracúvaj. EOF nie je znak, ktorý musí byť uložený na konci súboru, ale osobitný výsledok čítacej funkcie. feof sa nastaví až po pokuse čítať za koncom, preto cyklus „kým nie je feof“ nevie vopred určiť, či ďalšie čítanie uspeje."},
                {"type": "paragraph", "text": "Naše rozhranie read_line bude mať jednoznačný výsledok: prijme iba celý riadok s najviac capacity - 1 bajtmi bez '\\n'. Dlhší riadok odmietne a dočíta jeho zvyšok. Inak by sa druhá polovica neplatného vstupu mohla pri ďalšom čítaní tváriť ako nový údaj. Na názorné sledovanie hranice použijeme fgetc; nie je to tvrdenie, že fgets je nevhodné."},
                {"type": "code", "title": "Celý riadok alebo pomenovaný dôvod odmietnutia", "language": "c", "source": READ_LINES},
                {"type": "list", "items": [
                    "LINE_OK znamená celý riadok. Aj prázdny riadok ukončený '\\n' je úspešne načítaný text.",
                    "LINE_END znamená koniec vstupu bez jediného znaku ďalšieho riadka. Posledný neprázdny riadok bez '\\n' sa ešte spracuje ako LINE_OK.",
                    "LINE_TOO_LONG znamená prekročenie kapacity. Pole sa vyprázdni a zvyšok riadka sa zahodí, aby nasledujúce čítanie začalo správne.",
                    "LINE_INVALID odmieta vložený nulový bajt. Inak by neskoršie reťazcové funkcie videli iba časť načítaných údajov.",
                    "LINE_ERROR znamená chybu čítania. Vtedy nepokračujeme, akoby išlo o obyčajný chybný údaj."
                ]},
                {"type": "paragraph", "text": "Premenná used rastie iba dovtedy, kým je miesto v poli. Cyklus však pokračuje až po koniec riadka. Príznak seen odlišuje koniec prúdu od posledného riadka bez '\\n'. Pole sa pri neúspechu vyprázdni podľa nášho kontraktu, čo je odlišné od kontraktu samotného fgets. Kapacita sa počíta v bajtoch; sedem bajtov UTF-8 nemusí znamenať sedem písmen."},
                {"type": "callout", "tone": "info", "text": "Skús riadky abc, 1234567, 12345678 a potom OK. Prvé dva sa zmestia, tretí sa odmietne a posledný sa musí načítať celý. Program spracuje ďalšie riadky, ale konečný stav zostane neúspešný, pretože aspoň jeden údaj odmietol."},
                {"type": "heading", "text": "Z textu na číslo až po kontrole riadka"},
                {"type": "paragraph", "text": "Načítanie „21“ ešte nevytvorilo int. Prevod cez strtol poskytne hodnotu typu long aj ukazovateľ na miesto, kde sa prevod zastavil. Overíme, či vzniklo číslo, či za ním nezostal nepovolený text a či sa zmestí do int. Úplnú implementáciu a poradie kontrol rozoberá nasledujúca kapitola Chybové kódy a kontrakty; skúšobný príklad Načítanie celého čísla tieto dve časti už spája."},
                {"type": "paragraph", "text": "Pri sscanf nestačí kontrola jednej priradenej položky na odmietnutie „21abc“: číselný začiatok mohol byť úspešne načítaný. Ani obmedzenie šírky číselného poľa samo osebe nezaručuje rozsah výsledku. Ak číselný prevod scanf nedokáže výsledok reprezentovať v cieľovom objekte, správanie je nedefinované. Pre neobmedzený číselný vstup preto v týchto príkladoch používame riadok a strtol."},
                {"type": "heading", "text": "Súbor má začiatok aj koniec životnosti"},
                {"type": "paragraph", "text": "fopen spojí prúd s pomenovaným súborom. Režim \"r\" číta existujúci súbor, \"w\" vytvorí súbor alebo vymaže doterajší obsah a \"a\" zapisuje na koniec. Znak + povoľuje čítanie aj zápis; b vyjadruje binárny režim. Pred prvou operáciou musíš overiť, či fopen nevrátil NULL."},
                {"type": "paragraph", "text": "Nasledujúci príklad používa tmpfile, aby pri skúšaní neprepisoval tvoje súbory. Zapíše krátky, vopred známy záznam, presunie sa na začiatok, záznam načíta a prúd uzavrie. Pri prechode zo zápisu na čítanie v aktualizačnom prúde treba dodržať pravidlá synchronizácie; tu údaje odošleme cez fflush a polohu zmeníme cez fseek."},
                {"type": "code", "title": "Zápis, návrat na začiatok a jedno uzavretie", "language": "c", "source": FILE_ROUNDTRIP},
                {"type": "paragraph", "text": "Premenná result začína neúspechom a zmení sa až po úspešnom načítaní. Každá chyba po otvorení vedie na cleanup, takže fclose prebehne práve raz. Aj jeho výsledok sa kontroluje: úspešné predchádzajúce volanie ešte nevylučuje chybu pri uzatváraní. Po fclose už prúd nepoužívaj ani ho znova nezatváraj, a to ani vtedy, keď fclose oznámilo chybu."},
                {"type": "paragraph", "text": "Tu sa zapisuje presne známy krátky riadok, preto sa zmestí do poľa s 32 prvkami. Pri čítaní ľubovoľného cudzieho súboru taký predpoklad neplatí: znovu treba kontrolovať celé riadky alebo navrhnúť blokové spracovanie. Surový obsah súboru nie je dôveryhodný iba preto, že je uložený na disku."},
                {"type": "heading", "text": "Over si porozumenie na hraniciach"},
                {"type": "paragraph", "text": "Pred spustením odhadni rozdiel medzi prázdnym vstupom, jedným prázdnym riadkom a číslom bez záverečného '\\n'. Potom skús číslo s medzerami, s pripojeným písmenom a riadok presahujúci kapacitu. Pri každom prípade povedz, či zlyhalo čítanie, formát textu alebo rozsah čísla. Toto rozlíšenie je dôležitejšie než zapamätanie jedného dlhého programu."}
            ]
        }
    },
    {
        "key": "safety",
        "parent_key": "tooling",
        "kind": "lesson",
        "position": 140,
        "title": "Chyby a nedefinované správanie",
        "summary": "Čo C sľubuje, čo nedefinuje a ako hľadať chyby systematicky.",
        "content": {
            "lead": "Nedefinované správanie znamená, že štandard jazyka už neurčuje výsledok. Program nemusí spadnúť; môže vypísať zdanlivo správny výsledok alebo sa správať inak po zmene optimalizácie.",
            "blocks": [
                {"type": "heading", "text": "Nie každá chyba znamená to isté"},
                {"type": "paragraph", "text": "Program má spočítať kladné merania. Podmienka value >= 0 namiesto value > 0 započíta aj nulu: je to logická chyba s dobre definovaným, ale nesprávnym výsledkom. Čítanie values[count] je iný problém. Porušuje pravidlá prístupu do poľa a jeho výsledok už nemožno odvodiť z pravidiel C. Oprava preto začína pomenovaním porušeného pravidla, nie hľadaním hodnoty, ktorá sa náhodou vypísala."},
                {"type": "list", "items": [
                    "Chyba syntaxe alebo obmedzenia jazyka vyžaduje diagnostiku prekladača; napríklad dve nezlučiteľné deklarácie tej istej funkcie v tom istom rozsahu. Diagnostika nemusí znamenať, že prekladač odmietne pokračovať.",
                    "Logická chyba porušuje zadanie. Prekladač nevie, či si chcel počítať kladné alebo nezáporné čísla.",
                    "Implementáciou definované správanie má zdokumentovanú voľbu, napríklad či má obyčajný char znamienko. Prenositeľný program nemá bezdôvodne predpokladať jednu voľbu.",
                    "Nešpecifikované správanie pripúšťa viac možností bez povinnosti dokumentovať zvolenú možnosť. Napríklad poradie vyhodnotenia nezávislých argumentov funkcie nie je určené zľava doprava.",
                    "Nedefinované správanie, skrátene UB, nemá záruky výsledku. Pád, úspešný návrat ani rovnaký výpis pri desiatich behoch nie sú jeho definíciou ani spoľahlivým testom."
                ]},
                {"type": "heading", "text": "Hranicu kontroluj pred prístupom"},
                {"type": "code", "title": "Chybný úryvok: kontrola prichádza neskoro", "language": "c", "source": "int value = values[index]; /* UB if index is outside the array. */\nif (index >= count) {\n    return 1;\n}\n"},
                {"type": "paragraph", "text": "Priradenie už načítalo prvok. Neskoršie if nemôže vziať tento prístup späť. Ani podmienka values[index] != 0 && index < count nepomôže, pretože ľavá strana sa vyhodnotí prvá. Správne poradie pri nezápornom indexe je index < count && values[index] != 0. Skrátené vyhodnocovanie && potom zabezpečí, že sa pravá strana pri neplatnom indexe nevykoná."},
                {"type": "paragraph", "text": "Pole so štyrmi prvkami má platné indexy 0, 1, 2 a 3. Adresu jeden prvok za koncom možno vytvoriť a použiť ako hranicu cyklu, ale nemožno z nej čítať prvok. Ešte vzdialenejší ukazovateľ nemožno všeobecne ani vytvoriť aritmetikou nad týmto poľom. Počet prvkov odovzdaný funkcii musí zodpovedať skutočnému dostupnému poľu; samotný parameter count nič nealokuje."},
                {"type": "code", "title": "Úplný vstup, rozsah indexu a až potom čítanie", "language": "c", "source": SAFE_INDEX},
                {"type": "paragraph", "text": "Prvé dve pomocné funkcie poznáš z kapitol o vstupe a kontraktoch. read_line odmietne neúplný či príliš dlhý riadok a parse_int overí celý číselný zápis aj rozsah int. V main sa najprv odmietne záporný index. uintmax_t zo stdint.h potom umožní porovnať nezáporné číslo s count bez zúženia na potenciálne menší size_t. Prevod na size_t pri indexovaní už nasleduje po dôkaze, že index je menší než count."},
                {"type": "list", "items": [
                    "Vstup 0 vyberie 10, vstup 3 vyberie 40. Sú to prvý a posledný platný prvok.",
                    "Vstupy -1 a 4 sa odmietnu bez čítania prvku. Rovnosť s count už znamená neplatný index.",
                    "Vstupy 2x, prázdny riadok, číslo mimo int a riadok nad 63 bajtov sa odmietnu ešte pri spracovaní vstupu.",
                    "Program zámerne prijíma index typu int. Pre skutočne veľké polia by rozhranie potrebovalo iný číselný rozsah aj zodpovedajúci parser."
                ]},
                {"type": "heading", "text": "Aritmetiku nemožno dodatočne ospravedlniť"},
                {"type": "paragraph", "text": "Pri znamienkovom int musí byť výsledok aritmetickej operácie reprezentovateľný. Výraz INT_MAX + 1 nemá zaručené pretočenie na INT_MIN. Kontrola výsledku po sčítaní je neskoro; kapitola o bitoch ukazuje checked_add s kontrolou pred sčítaním. Naproti tomu unsigned int používa modulárnu aritmetiku, ale aj definované pretočenie môže pokaziť výpočet veľkosti alokácie."},
                {"type": "paragraph", "text": "Celočíselné delenie má dve nebezpečné hranice: nulový deliteľ a nereprezentovateľný podiel. Na bežnom dvojkovom doplnku je INT_MIN / -1 mimo int. Rovnaký problém má aj INT_MIN % -1, hoci matematický zvyšok vyzerá ako nula. Pri platnom delení sa podiel skracuje smerom k nule: -7 / 2 je -3, nie -4."},
                {"type": "code", "title": "Delenie s kontrolou pred operáciou", "language": "c", "source": CHECKED_DIVISION},
                {"type": "paragraph", "text": "Kontroly vracajú DIVIDE_ARGUMENT=1, DIVIDE_ZERO=2 alebo DIVIDE_RANGE=3 ešte pred zápisom. Iba DIVIDE_OK=0 mení výsledok. Preto posledný riadok ukážky oznámi status=2 value=99. Podmienka numerator < -INT_MAX zachytí zápornú hodnotu bez kladného náprotivku aj bez predpokladu konkrétnej reprezentácie C17. Samotné -INT_MAX je reprezentovateľné; vypočítať najprv -numerator by pri krajnej hodnote mohlo vyvolať práve chybu, ktorej sa snažíme vyhnúť."},
                {"type": "heading", "text": "Poradie účinkov nie je priorita operátorov"},
                {"type": "code", "title": "Chybné dvojité zvýšenie a jednoznačná náhrada", "language": "c", "source": "/* Wrong in C17: unsequenced modifications of i. */\nprintf(\"%d %d\\n\", i++, i++);\n\n/* Instead, use separate full expressions. */\nint first = i;\n++i;\nint second = i;\n++i;\nprintf(\"%d %d\\n\", first, second);\n"},
                {"type": "paragraph", "text": "Zátvorky určujú zoskupenie, nie všeobecné poradie vedľajších účinkov. Dve nezoradené zmeny i v argumentoch printf sú v C17 UB, nie iba výber medzi dvoma poradiami výpisu. Náhrada predpokladá, že obe zvýšenia zostanú v rozsahu int; napríklad pri i=4 vypíše 4 5 a zanechá i=6. Samostatné príkazy spriehľadnia poradie, ale neodstránia potrebu kontrolovať rozsah."},
                {"type": "heading", "text": "Životnosť a knižničné kontrakty"},
                {"type": "paragraph", "text": "Po free už pôvodný objekt neexistuje. Nastavenie jednej premennej na NULL neopraví ostatné ukazovatele, ktoré naň odkazovali. Rovnako nemožno vrátiť adresu lokálneho poľa a používať ju po návrate funkcie. Oprava musí určiť vlastníka a životnosť objektu, napríklad nechať pole vytvoriť volajúcim alebo jasne odovzdať vlastníctvo dynamickej alokácie."},
                {"type": "list", "items": [
                    "Nenulový ukazovateľ ešte nemusí byť platný. Kontrola proti NULL nenahrádza znalosť životnosti, veľkosti a zarovnania objektu.",
                    "Nečítaj neinicializované lokálne hodnoty. Inicializácia je súčasť prípravy stavu, nie kozmetická úprava varovaní.",
                    "printf potrebuje správny typ argumentu pre formát; pre size_t je určené %zu. Preklad bez varovania nie je univerzálnym overením knižničných kontraktov.",
                    "memcpy nesmie kopírovať prekrývajúce sa oblasti; pre platné prekrývajúce sa oblasti je určené memmove. Zmena funkcie však neopraví príliš malý cieľ.",
                    "Nedefinovaný nie je ľubovoľný nepríjemný výsledok. Neúspešné fopen s návratom NULL je bežná definovaná chybová cesta."
                ]},
                {"type": "callout", "tone": "warning", "text": "Chybné úryvky slúžia na rozbor, nie ako programy s očakávaným výstupom. UB neopravíš tým, že vypneš optimalizáciu alebo že sanitizér pri jednom behu nič neoznámil. Najprv oprav porušený predpoklad a potom doplň testy hraníc."},
                {"type": "heading", "text": "Od chyby k overiteľnej oprave"},
                {"type": "paragraph", "text": "Zapíš konkrétny vstup a požadovaný výsledok. Zmenši program bez odstránenia príčiny. Nájdeš kontrolu až za operáciou, nesprávnu hranicu alebo objekt po skončení životnosti? Presuň kontrolu pred operáciu a výstup meň až po úspechu. Nakoniec over najbližší platný aj neplatný prípad: pri neprázdnom poli index count - 1 a count, pri delení nulu aj krajné hodnoty z limits.h. Prázdny rozsah over osobitne bez odčítania od nulového count. Nasledujúca kapitola ukáže, ako z takýchto prípadov zostaviť opakovateľný test."}
            ]
        }
    },
    {
        "key": "errors",
        "parent_key": "tooling",
        "kind": "lesson",
        "position": 135,
        "title": "Chybové kódy a kontrakty",
        "summary": "Návratové hodnoty, errno, výstupné parametre a čitateľné hlásenie zlyhania.",
        "content": {
            "lead": "Predstav si nastavenie počtu meraní. Používateľ zadá „24“, prázdny text alebo príliš veľké číslo. Funkcia musí oznámiť, čo sa stalo, a zároveň nepokaziť doterajšie platné nastavenie. Práve tieto sľuby tvoria jej kontrakt.",
            "blocks": [
                {"type": "heading", "text": "Čo má volajúci vedieť ešte pred volaním"},
                {"type": "paragraph", "text": "Kontrakt je dohoda medzi funkciou a kódom, ktorý ju používa. Určuje platné vstupy, výsledok pri úspechu a stav programu pri neúspechu. Nie je to opis každého riadka implementácie. Volajúci potrebuje vedieť, na čo sa môže spoľahnúť bez skúmania jej vnútra."},
                {"type": "list", "items": [
                    "Predpoklady: odkazuje text na platný reťazec ukončený nulou? Je výstupný objekt zapisovateľný? Aké hodnoty funkcia prijíma?",
                    "Úspech: aký stav sa vráti a aká hodnota sa zapíše do výstupného objektu?",
                    "Neúspech: ktoré dôvody sa rozlišujú a zostane pôvodná hodnota zachovaná?",
                    "Vlastníctvo: kto otvoril súbor alebo pridelil pamäť a kto ich má uvoľniť?",
                    "Vedľajšie účinky: číta funkcia prúd, zapisuje správy alebo mení ďalšie objekty?"
                ]},
                {"type": "paragraph", "text": "Kontrola ukazovateľa proti NULL neoverí, či ľubovoľná nenulová adresa naozaj patrí platnému objektu. Túto zodpovednosť má volajúci. Podobne const char * znamená, že cez tento parameter nebudeme meniť text; nesľubuje jeho platnú životnosť ani správny obsah."},
                {"type": "heading", "text": "Ako môže funkcia oznámiť zlyhanie"},
                {"type": "list", "items": [
                    "Vyhradená hodnota: fopen vracia pri chybe NULL. Je to vhodné, pretože NULL nie je úspešne otvorený prúd.",
                    "Číselný návratový kód: fclose vracia pri úspechu 0 a pri chybe EOF. Konvenciu treba poznať; nemožno ju automaticky preniesť na inú funkciu.",
                    "Stav oddelený od dát: náš prevod vráti ParseStatus a číslo zapíše cez int *. Nula tak zostáva platným výsledkom parse_int, nie skrytým označením chyby.",
                    "Výsledok so stavom v jednej štruktúre: ďalšia možnosť pre vlastné rozhranie, najmä ak vracia viac údajov. Význam neplatného výsledku musí byť stále jasný."
                ]},
                {"type": "paragraph", "text": "bool stačí, keď volajúci potrebuje iba rozhodnutie áno alebo nie. Ak však pri chybe vie urobiť rôzne kroky, pomenovaný enum mu dá viac informácií. Nejde o množstvo chybových kódov, ale o rozlíšenia, ktoré vie ďalšia časť programu zmysluplne využiť."},
                {"type": "heading", "text": "Navrhnime presné pravidlá prevodu"},
                {"type": "paragraph", "text": "parse_int prijíma desiatkové celé číslo s voliteľným znamienkom a okolitými bielymi znakmi. Text „  +24  “ je platný, „24 kusov“ nie. Prázdny text ani samotné medzery neobsahujú číslo. Až keď vyhovuje zápis aj rozsah, funkcia zmení výstupný objekt."},
                {"type": "list", "items": [
                    "PARSE_ARGUMENT oznamuje NULL namiesto požadovaného vstupu alebo výstupného ukazovateľa.",
                    "PARSE_INVALID oznamuje chýbajúce číslo alebo neprípustný zvyšok textu.",
                    "PARSE_RANGE znamená správny číselný zápis, ktorého hodnota sa nezmestí do int.",
                    "PARSE_OK znamená platný výsledok zapísaný cez result.",
                    "parse_positive pridáva pravidlo aplikácie: hodnota musí byť väčšia než nula. Nulu a záporné hodnoty v rozsahu int odmietne stavom PARSE_INVALID."
                ]},
                {"type": "code", "title": "Prevod, kontrola kladnosti a zachovanie pôvodnej hodnoty", "language": "c", "source": PARSE_POSITIVE},
                {"type": "heading", "text": "Prejdi prevod krok za krokom"},
                {"type": "paragraph", "text": "strtol číta číselný začiatok textu, vracia long a cez end ukazuje, kde sa zastavilo. Základ 10 znamená desiatkovú sústavu; preto napríklad 012 nečítame ako osmičkové číslo. Samotná vrátená nula nestačí na rozhodnutie: môže pochádzať zo správneho „0“, ale aj zo vstupu bez čísla."},
                {"type": "paragraph", "text": "Najprv preto kontrolujeme end == text. Pri prázdnom texte a samotných medzerách táto rovnosť znamená, že nevzniklo číslo. Až potom preskočíme povolené biele znaky za ním. Keby sme poradie obrátili, ukazovateľ by sa pri medzerách posunul a kontrola neprítomného čísla by mohla zlyhať."},
                {"type": "paragraph", "text": "Ak po preskočení bielych znakov zostalo písmeno alebo iný znak, odmietneme celý vstup. Pri isspace prevádzame znak na unsigned char, pretože záporná hodnota obyčajného char, ktorá nie je EOF, nie je platným argumentom tejto funkcie. Až po kontrole textu overíme rozsah a vykonáme priradenie do int."},
                {"type": "paragraph", "text": "Toto poradie určuje aj prednosť chýb. Obrovské číslo s pripojeným písmenom má u nás PARSE_INVALID, pretože chybný zápis má prednosť pred rozsahom. Číselný zápis bez takého zvyšku môže dostať PARSE_RANGE. Iná aplikácia môže mať inú dohodu, ale nesmie ju meniť náhodne podľa vetvy programu."},
                {"type": "heading", "text": "errno je doplnková informácia ku konkrétnemu volaniu"},
                {"type": "paragraph", "text": "Pred strtol nastavíme errno na nulu a hneď po volaní si jeho hodnotu odložíme. ERANGE signalizuje, že výsledok presiahol rozsah long. Potom osobitne porovnáme hodnotu s INT_MIN a INT_MAX: na platforme so širším long môže prevod do long uspieť, hoci následné uloženie do int už nie."},
                {"type": "paragraph", "text": "Úspešné volanie nemusí vymazať starú hodnotu errno. Zároveň nie každá knižničná funkcia používa errno rovnakým spôsobom. Najprv si všimni jej návratový výsledok a dokumentovaný kontrakt; až podľa neho interpretuj errno. Odloženie do conversion_errno chráni informáciu pred tým, aby ju zmenilo ďalšie volanie."},
                {"type": "paragraph", "text": "perror vypíše na stderr správu odvodenú od aktuálneho errno. Nie je to univerzálny prekladač vlastného enumu. Pri PARSE_INVALID vieme oznámiť zrozumiteľnú chybu sami. Pri chybách stdio navyše nemiešaj prenositeľné záruky ISO C s dodatočnými zárukami POSIX; to, že konkrétny systém poskytuje errno, ešte nie je pravidlo pre každú platformu C."},
                {"type": "heading", "text": "Zmenu vykonaj až po všetkých kontrolách"},
                {"type": "paragraph", "text": "parse_positive používa pomocnú premennú candidate. Keby najprv zapísala výsledok parse_int priamo do objektu volajúceho a až potom zistila, že hodnota nie je kladná, pri chybe by už bolo nastavenie prepísané. Pomocná premenná umožní pripraviť výsledok, overiť ho a až potom vykonať jediný zápis."},
                {"type": "paragraph", "text": "V ukážke začína value pred každým pokusom hodnotou 77. Pri „24“ sa zmení na 24; pri prázdnom texte, medzerách, „12x“, nule a zápornom čísle zostane 77. Dlhý číselný zápis ukazuje chybu rozsahu na bežných platformách s najviac 64-bitovým long. Presné hranice konkrétnej implementácie určujú makrá z limits.h."},
                {"type": "callout", "tone": "info", "text": "Program ukážky sa môže skončiť úspešne, aj keď jeho tabuľka obsahuje odmietnuté vstupy: jeho úlohou je ich klasifikovať a ukázať zachovanie hodnoty. Program, ktorého úlohou je prijať jeden platný údaj, pri odmietnutí vráti EXIT_FAILURE. Stav vnútornej funkcie a stav celého procesu sú dve rôzne úrovne."},
                {"type": "heading", "text": "Chybová cesta nesmie zabudnúť na zdroje"},
                {"type": "paragraph", "text": "Pri reťazci otvorenie súboru, pridelenie pamäte a spracovanie môže zlyhať každý krok. Uvoľňuj iba zdroje, ktoré už vznikli, a každý práve raz. Pri viacerých krokoch je spoločné miesto cleanup často čitateľnejšie než opakovanie rovnakého upratovania v každej vetve. Predchádzajúca kapitola to ukazuje na tmpfile a fclose."},
                {"type": "paragraph", "text": "Ak zlyhá spracovanie a potom aj uzavretie, nestrácaj pôvodnú príčinu. Program môže oznámiť obe udalosti, no výsledok musí zostať neúspešný. Ani zachovanie jednej premennej pri chybe nezaručí vrátenie všetkých účinkov: už zapísané bajty alebo odoslanú správu nemožno všeobecne vziať späť. Kontrakt má preto pomenovať aj hranice svojho sľubu."},
                {"type": "heading", "text": "Vyskúšaj rozhodnutie, nie iba šťastnú cestu"},
                {"type": "paragraph", "text": "Pred spustením tabuľky ku každému vstupu priraď stav a konečnú hodnotu value. Potom navrhni podobné rozhranie pre počet pokusov od 1 do 5: čo bude chyba zápisu, čo chyba rozsahu a čo porušenie pravidla aplikácie? V cvičení doplníš kontroly jednoduchej funkcie tak, aby pri chybe zachovala pôvodný údaj."}
            ]
        }
    },
    {
        "key": "testing",
        "parent_key": "tooling",
        "kind": "lesson",
        "position": 145,
        "title": "Testovanie a ladenie",
        "summary": "Malé testy, assert, varovania, sanitizéry a postup pri hľadaní chyby.",
        "content": {
            "lead": "Spoľahlivosť nevznikne jedným veľkým testom na konci. V C sa oplatí oddeliť čistý výpočet od vstupu a výstupu, aby si mohol malé funkcie kontrolovať priamo.",
            "blocks": [
                {"type": "heading", "text": "Najprv sľub funkcie, potom test"},
                {"type": "paragraph", "text": "count_positive má vrátiť počet hodnôt väčších než nula medzi prvými count prvkami. Nula sa nepočíta. Volajúci zaručuje čitateľné pole s aspoň count prvkami; pri count=0 sa nečíta nič a možno odovzdať aj NULL. Funkcia nevykonáva vstup ani výstup, preto ju možno skúšať priamo, bez simulácie terminálu."},
                {"type": "paragraph", "text": "Test pozostáva z prípravy dát, jedného volania a porovnania so samostatne určeným očakávaním. Očakávanie nepočítaj rovnakým algoritmom ako výsledok: skopírovaná chyba by potvrdila samu seba. Pri poli {-2, 0, 3} vieme ručne povedať, že výsledok má byť 1."},
                {"type": "list", "items": [
                    "Prázdny rozsah overí, že funkcia vráti nulu bez načítania prvku.",
                    "Jeden záporný, nulový a kladný prvok odlíšia jednotlivé vetvy podmienky.",
                    "Kladný prvok iba na začiatku alebo iba na konci odhalí vynechanú hranicu cyklu.",
                    "Zmiešané pole s nulami rozlíši > od >= a preverí opakované zvyšovanie počítadla.",
                    "Neplatné vstupy testuj podľa kontraktu. Funkciu bez sľubu kontroly NULL nevolaj s NULL a kladným count a neočakávaj bezpečnú chybu. Pre kontrolované rozhranie by si musel navrhnúť stav zlyhania."
                ]},
                {"type": "heading", "text": "assert: krátke tvrdenie s dôležitou podmienkou"},
                {"type": "code", "title": "Štyri tvrdenia, alebo výslovné odmietnutie vypnutých testov", "language": "c", "source": ASSERT_MAXIMUM},
                {"type": "paragraph", "text": "Aktívny assert pri nepravdivom výraze vypíše diagnostiku a ukončí program cez abort. Ďalšie tvrdenia už neprebehnú. Ak je pri vložení assert.h definované NDEBUG, výraz assert sa vôbec nevyhodnocuje. Platí to aj pre -DNDEBUG=0: rozhoduje existencia makra, nie jeho číselná hodnota. Ukážka preto pri vypnutí testov vracia neúspech a nikdy netvrdí, že prešli."},
                {"type": "callout", "tone": "warning", "text": "Potrebné operácie nedávaj dovnútra assert. Pri assert(read_value(&value)) sa s NDEBUG neuskutoční ani čítanie. Operáciu vykonaj osobitne, jej chybu spracuj bežným if a assert si nechaj na interné tvrdenie. Rovnako ním nenahrádzaj kontrolu cudzieho vstupu alebo neúspešného malloc."},
                {"type": "heading", "text": "Tabuľka testov, ktorá zostane aktívna"},
                {"type": "code", "title": "Sedem pomenovaných prípadov a návratový stav", "language": "c", "source": BOUNDARY_TESTS},
                {"type": "paragraph", "text": "Každý riadok tabuľky nesie názov, dáta, počet spracovaných prvkov a očakávanie. Pole values má vždy päť miest; empty znamená nulový spracovaný rozsah, nie neprenositeľné pole dĺžky nula. Pri rozdiele pribudne zlyhanie a vypíše sa názov, očakávanie aj skutočnosť. Súhrn tests=7 failures=0 znamená, že prešlo týchto sedem prípadov, nie dôkaz správnosti pre každý vstup."},
                {"type": "paragraph", "text": "Porovnania cez if fungujú aj s NDEBUG a program pri zlyhaní vracia EXIT_FAILURE. To je dôležité pre automatizáciu: samotné slovo FAIL vo výstupe s úspešným návratom by bežný testovací skript nemusel považovať za chybu. Názvy prípadov navyše umožnia pochopiť zlyhanie bez hádania, ktorý riadok tabuľky sa práve vykonal."},
                {"type": "paragraph", "text": "Over aj kvalitu testov. Dočasne zmeň > 0 na >= 0: prípady zero, first, last a mixed musia zlyhať, spolu štyri. Potom obnov správnu podmienku. Takto vložená známa chyba sa nazýva mutant. Testy, ktoré ju nerozlíšia od správneho programu, majú medzeru. Cvičenie na konci kapitoly precvičuje práve kontrolu správneho a zámerne chybného výpočtu."},
                {"type": "heading", "text": "Varovania a sanitizéry odpovedajú na iné otázky"},
                {"type": "paragraph", "text": "Varovania kontrolujú podozrivý zdroj počas prekladu, napríklad nesúlad formátu a argumentu. Sanitizéry pridávajú kontroly vykonaných operácií počas behu. UBSan vie odhaliť napríklad znamienkové pretečenie; AddressSanitizer, skrátene ASan, pomáha pri viacerých chybách pamäte. Ani jeden nepozná zadanie count_positive, preto od nich nečakaj hlásenie na >= namiesto >."},
                {"type": "code", "title": "Samostatné príkazy v lokálnom termináli s GCC", "language": "sh", "source": "gcc -std=c17 -Wall -Wextra -Wpedantic -Wconversion -Wshadow -Wformat=2 -g3 -O0 main.c -o program\n./program\n\ngcc -std=c17 -Wall -Wextra -g3 -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer main.c -o program-sanitized\n./program-sanitized\n"},
                {"type": "paragraph", "text": "Druhý preklad potrebuje dostupné knižnice sanitizérov. ASan na 64-bitových platformách mapuje veľký virtuálny adresný priestor, čo nie je to isté ako spotreba fyzickej pamäte. Preto tento príkaz nie je prísľubom behu v pamäťovo obmedzenom sandboxe. Vo Vývoji profil Ladenie pri C používa UBSan, nie ASan; profil Vydanie tieto kontroly nepridáva. Kontroly behu nastanú až pri vedomom spustení programu, nie počas písania."},
                {"type": "paragraph", "text": "Pri UBSan môže byť povolené pokračovanie po diagnostike, takže úspešný návrat procesu nevylučuje nájdenú chybu. Lokálny príkaz vyššie používa -fno-sanitize-recover=all, aby prvé zachytené porušenie skončilo neúspešne. Čítaj preto aj stderr. Tichý sanitizér znamená iba to, že pri vykonaných operáciách jeho zapnuté kontroly nič nezachytili."},
                {"type": "heading", "text": "Ladenie konkrétnej logickej chyby"},
                {"type": "code", "title": "Zámerne chybný program: nula sa počíta ako kladná", "language": "c", "source": DEBUG_POSITIVE},
                {"type": "paragraph", "text": "Tento program má definované správanie: vypíše expected=1 actual=2 a vráti neúspech. Nečíta mimo poľa. Taký príklad sa hodí na prvé krokovanie, pretože vieme odlíšiť chybný výsledok od nepredvídateľného UB. Prelož ho ako main.c prvým príkazom s -g3 -O0 a spusti gdb ./program. Diagnostické symboly priradia inštrukcie k zdroju; bez optimalizácie sa stav sleduje jednoduchšie."},
                {"type": "code", "title": "Príkazy v GDB po otvorení programu", "language": "text", "source": "break count_positive\nrun\nprint count\nprint values[0]@3\nbacktrace\nlist count_positive\n"},
                {"type": "paragraph", "text": "Breakpoint zastaví vstup do count_positive. count má byť 3 a výraz values[0]@3 v GDB zobrazí tri prvky {-2, 0, 3}; znak @ je syntax debuggera, nie operátor C. Backtrace ukáže count_positive volané z main. Na riadku inicializácie ešte nemusí byť positive nastavené: debugger zvyčajne ukazuje príkaz, ktorý sa len chystá vykonať."},
                {"type": "paragraph", "text": "Príkazom next prejdi inicializáciu a potom cyklus. Pri každom if sleduj print i, print values[i] a print positive. Kým i=0, záporné číslo počítadlo nezvýši. Pri i=1 má values[i] hodnotu 0, no podmienka >= 0 dovolí ++positive. To je prvý rozdiel oproti kontraktu. Výrazy values[i] vyhodnocuj iba vnútri platného rozsahu, nie po skončení cyklu s i=count."},
                {"type": "list", "items": [
                    "next prejde na ďalší zdrojový krok bez vstupu do volanej funkcie. Jeden zdrojový riadok nemusí zodpovedať jednej strojovej inštrukcii.",
                    "step môže vstúpiť do volanej funkcie. Na call-site count_positive v main tak môžeš pozorovať prechod do výpočtu.",
                    "finish dokončí aktuálnu funkciu a vráti sa k volajúcemu; pri tomto programe uvidíš chybný návrat 2.",
                    "continue pokračuje po ďalší breakpoint alebo koniec programu. backtrace ukazuje zásobník aktuálnych volaní, nie históriu všetkých predošlých volaní."
                ]},
                {"type": "heading", "text": "Oprava má zostať chránená regresným testom"},
                {"type": "paragraph", "text": "Zmeň jedinú chybnú podmienku na > 0, ukonči GDB, prelož znova a zopakuj beh. Očakávanie sa nemení: teraz má byť actual=1. Prípad s nulou zachovaj v tabuľke, aby sa rovnaká chyba neskôr nevrátila. Over aj pôvodné ostatné prípady, pretože oprava jedného vstupu môže pokaziť iný."},
                {"type": "callout", "tone": "info", "text": "Keď sa zlyhanie nedá zopakovať, odlož presný vstup, verziu zdroja, príkaz prekladu, návratový stav a obe výstupné vetvy stdout a stderr. Pri náhodných testoch aj počiatočné semeno. Menší reprodukovateľný príklad zvyčajne pomôže viac než množstvo výpisov bez jasnej otázky."}
            ]
        }
    },
    {
        "key": "reference",
        "parent_key": "",
        "kind": "chapter",
        "position": 150,
        "title": "Rýchla referencia",
        "summary": "Najpoužívanejšie časti štandardnej knižnice a praktické pripomenutia.",
        "content": {"lead": "Referencia nepreberá celý štandard C, ale zhŕňa veci, ku ktorým sa pri bežnej práci oplatí vracať.", "sections": [{"title": "Princíp", "paragraphs": ["Pred použitím funkcie si over jej vstupy, výstup, návratovú hodnotu a kto vlastní výsledné dáta. Príklad v kapitole nenahrádza kontrakt funkcie."]}]}
    },
    {
        "key": "stdio-reference",
        "parent_key": "reference",
        "kind": "reference",
        "position": 160,
        "title": "stdio.h: printf, fgets a FILE",
        "summary": "Formáty a návratové hodnoty, snprintf, celé riadky, binárne dáta a životnosť prúdu.",
        "content": {
            "lead": "stdio.h je rozhranie k štandardnému vstupu, výstupu a súborom.",
            "blocks": [
                {"type": "heading", "text": "Rýchla orientácia v návratových hodnotách"},
                {"type": "list", "items": [
                    "printf a fprintf vracajú pri úspechu počet vypísaných znakov; záporný výsledok znamená chybu. fprintf navyše prijíma cieľový FILE *.",
                    "snprintf zapisuje do poľa s danou kapacitou a vracia požadovanú dĺžku bez koncovej nuly, aj keď sa výstup celý nezmestil. Záporný výsledok znamená chybu formátovania.",
                    "fgets vracia cieľový ukazovateľ alebo NULL. fgetc vracia znak cez int alebo EOF. Pri neúspešnom čítaní odlišuj koniec od chyby cez ferror.",
                    "fread a fwrite vracajú počet celých prenesených prvkov, nie všeobecne počet bajtov. Ak je veľkosť prvku 1, ide zároveň o počet bajtov.",
                    "fopen a tmpfile vracajú FILE * alebo NULL. fclose a fflush vracajú pri úspechu 0, pri chybe EOF; fseek vracia pri úspechu 0, inak nenulovú hodnotu."
                ]},
                {"type": "heading", "text": "Formát je typový kontrakt, nie ozdoba výpisu"},
                {"type": "list", "items": [
                    "%d očakáva int, %u unsigned int, %ld long a %zu size_t. Počet bajtov zo sizeof teda nevypisuj automaticky cez %d.",
                    "%f pri printf očakáva double; float sa pri volaní s premenlivým počtom argumentov povýši na double. Pre long double je určené %Lf.",
                    "%c pracuje s argumentom typu int po celočíselných povýšeniach. %s potrebuje platný reťazec, nie ľubovoľné pole alebo NULL.",
                    "%p očakáva void *. Pri ukazovateli na objekt použi napríklad printf(\"%p\", (void *) pointer); presný zápis adresy závisí od implementácie.",
                    "Šírka či presnosť cez hviezdičku prijíma int. Pri %.*s preto nemožno bez kontroly podať size_t alebo ho naslepo zúžiť na int.",
                    "%% vypíše doslovné percento. Cudzí text patrí do argumentu, napríklad printf(\"%s\", text), nie na miesto formátu."
                ]},
                {"type": "paragraph", "text": "Počet a typy argumentov musia zodpovedať formátu aj pri sprintf či snprintf. Nesprávny formát neopraví menšia kapacita cieľa. Prekladač pri známych formátoch pomôže varovaniami, ale formát vytvorený až počas behu nemusí vedieť overiť. Šírka ako %8s je minimálna šírka zobrazenia, nie ochrana pred dlhým reťazcom. Presnosť %.8s obmedzuje počet vypísaných bajtov, nie celkovú veľkosť výsledku s ďalším textom."},
                {"type": "paragraph", "text": "Pri scanf je kontrakt odlišný: odovzdávaš adresy objektov. %f tam potrebuje float * a %lf double *; pre printf sa float aj tak povýši na double. Počet úspešných priradení ešte nemusí znamenať prijatie celého vstupu. Číselný prevod scanf s nereprezentovateľným výsledkom môže viesť k UB, preto pre neobmedzený číselný vstup naďalej používame celý riadok a kontrolovaný parser z predchádzajúcich kapitol."},
                {"type": "heading", "text": "snprintf má tri výsledky"},
                {"type": "code", "title": "Presná kapacita, skrátenie a nulová kapacita", "language": "c", "source": SNPRINTF_MESSAGE},
                {"type": "paragraph", "text": "Text value=42 má osem bajtov a potrebuje deviate miesto pre koncovú nulu. FORMAT_OK=0 znamená celý uložený text, FORMAT_ERROR=1 záporný návrat a FORMAT_TRUNCATED=2 nedostatok miesta. Pri kapacite 9 vznikne celý text, pri 8 iba value=4 a pri 1 prázdny reťazec. Vo všetkých týchto prípadoch snprintf vracia požadovanú dĺžku 8, nie skutočne uložený počet."},
                {"type": "paragraph", "text": "Najprv sa overuje záporný výsledok. Až potom sa nezáporná požadovaná dĺžka porovnáva s kapacitou cez uintmax_t, aby sa nezúžila ani na platforme s menším size_t než int. Rovnosť už znamená nedostatok miesta pre nulu. Na bežnej platforme so širším size_t uvidíš aj zápis (size_t) required >= capacity; jeho prenositeľnosť však závisí od rozsahu prevodu."},
                {"type": "paragraph", "text": "Pri kapacite 0 sa nezapisuje nič a cieľ môže byť NULL. Posledný riadok preto ukáže pôvodné old v našom nedotknutom poli a zároveň požadovanú dĺžku 8. Také volanie je otázkou na veľkosť, nie úspešným vytvorením reťazca. Pred neskoršou alokáciou required + 1 najprv skontroluj nezápornosť a to, že celý súčet vojde do size_t."},
                {"type": "callout", "tone": "warning", "text": "Skrátenie cez snprintf už mohlo zmeniť cieľ. Nie je to rovnaký kontrakt ako copy_text, ktoré pri odmietnutí nezapisuje nič. Po zápornom výsledku nepovažuj obsah za platný dokončený reťazec. Prekrývanie cieľa s textovým argumentom, napríklad snprintf(text, capacity, \"%s!\", text), nie je podporovaná náhrada memmove."},
                {"type": "paragraph", "text": "Kapacita sa počíta v bajtoch. Skrátený UTF-8 text sa môže skončiť uprostred znaku, aj keď má správnu nulovú termináciu. Ak aplikácia potrebuje celé používateľské znaky, musí navrhnúť samostatné pravidlo skrátenia. Samotný snprintf rieši hranicu objektu, nie jazykové hranice textu."},
                {"type": "heading", "text": "fgets: časť riadka nie je celý údaj"},
                {"type": "paragraph", "text": "Pre platný prúd a cieľ s count miestami, kde count je aspoň 2, načíta fgets najviac count - 1 znakov a pri úspechu pridá nulu. Ak sa do tejto hranice zmestí nový riadok, zostane v poli. Chýbajúci nový riadok môže znamenať dlhší vstup, ale aj posledný riadok ukončený EOF. Pri NULL obsah bez ďalšieho nespracúvaj; skontroluj príčinu čítania."},
                {"type": "paragraph", "text": "fgets prijíma limit typu int. Pri veľkom dynamickom poli preto neposielaj jeho size_t kapacitu cez neoverený prevod. Navyše môže načítať vložený nulový bajt, po ktorom strlen už nevidí zvyšok údajov. Keď kontrakt vyžaduje iba úplné textové riadky bez vloženej nuly, treba tieto pravidlá overiť osobitne."},
                {"type": "code", "title": "Opakovanie overeného čítania celých riadkov", "language": "c", "source": READ_LINES},
                {"type": "paragraph", "text": "Toto je rovnaký read_line z kapitoly o vstupe, nie nová verzia. Pri poli na osem bajtov prijme sedem bajtov obsahu; dlhší riadok odmietne a spotrebuje jeho zvyšok. Prázdny riadok je platný text, prázdny vstup je LINE_END. Program skúša abc a 1234567, pričom posledný riadok nemusí mať záverečné '\\n'. Chybové vetvy poznáš z pôvodnej kapitoly."},
                {"type": "heading", "text": "FILE: otvorenie, poloha a jedno uzavretie"},
                {"type": "paragraph", "text": "Režim fopen \"r\" číta existujúci súbor, \"w\" vytvorí alebo vymaže obsah a \"a\" pridáva na koniec. Znak + povoľuje oba smery, b žiada binárny režim. Otvorenie vždy môže zlyhať. Po úspešnom otvorení musí vlastník zabezpečiť uzavretie na každej návratovej ceste; po fclose sa FILE * už nepoužíva ani pri hlásenej chybe uzavretia."},
                {"type": "paragraph", "text": "Pri aktualizačnom prúde nemožno ľubovoľne striedať čítanie a zápis. Pri prechode zo zápisu na čítanie pomôže fflush alebo operácia polohovania; opačný prechod vyžaduje polohovanie, okrem prípadu, keď čítanie narazilo na EOF. Ukážka používa explicitný fflush a fseek. rewind nemá návratový stav, preto tu pre kontrolované zlyhanie používame fseek."},
                {"type": "heading", "text": "Binárny prenos zachová aj vloženú nulu"},
                {"type": "code", "title": "Štyri bajty cez dočasný súbor", "language": "c", "source": BINARY_ROUNDTRIP},
                {"type": "paragraph", "text": "tmpfile vytvorí dočasný binárny aktualizačný prúd bez prepisovania používateľských súborov. fwrite a fread majú veľkosť prvku 1, preto porovnávame ich návrat priamo s počtom bajtov. Výpis 41 00 FF 0A ukáže aj nulu, pri ktorej by sa výpis cez %s skončil. Porovnanie cez memcmp nastáva až po úspešnom načítaní celého požadovaného rozsahu."},
                {"type": "paragraph", "text": "Kratší fread s prvkami veľkosti 1 môže znamenať koniec alebo chybu; ferror tieto situácie rozlíši. Pri väčších prvkoch môže zostať aj neúplný prvok, ktorého hodnotu nemožno používať ako hotový údaj. Nečítaj neinicializovaný zvyšok poľa a nezamieňaj počet dokončených prvkov s kapacitou objektu. Táto ukážka očakáva presne štyri bajty, nie ľubovoľne dlhý prúd."},
                {"type": "paragraph", "text": "Surový zápis struct alebo celého čísla cez fwrite nevytvára sám osebe prenositeľný súborový formát. Treba dohodnúť šírky, bajtové poradie a kódovanie; výplňové bajty štruktúry nie sú jej logickými dátami. Naša ukážka preto prenáša explicitné bajtové hodnoty, nie obraz vnútorného objektu."},
                {"type": "heading", "text": "Výstup môže zlyhať aj neskôr"},
                {"type": "paragraph", "text": "Úspešný printf alebo fwrite môže údaje iba uložiť do knižničného vyrovnávacieho priestoru. Preto sa kontrolujú aj fflush a fclose. fflush nezaručuje fyzickú trvácnosť dát na disku a fflush(stdin) nie je v ISO C prenositeľné čistenie vstupu. Ak už zlyhal zápis a potom aj uzavretie, výsledok zostáva neúspešný a pôvodná príčina sa nemá stratiť."},
                {"type": "callout", "tone": "info", "text": "Pri formátovaní vyskúšaj kapacitu presne s nulou, o bajt menšiu, 1 a 0. Pri súbore over neúspešné otvorenie, krátky prenos a chybu uzavretia bez druhého fclose. Testovať treba návrat aj stav dát, nie iba pekný výpis šťastnej cesty."}
            ]
        }
    },
    {
        "key": "stdlib-reference",
        "parent_key": "reference",
        "kind": "reference",
        "position": 170,
        "title": "stdlib.h: malloc, free a strtol",
        "summary": "Vlastníctvo pamäte, kontrolované prevody, triedenie, hľadanie a návratové kódy.",
        "content": {
            "lead": "stdlib.h obsahuje základné nástroje pre dynamickú pamäť, konverzie a riadenie programu.",
            "blocks": [
                {"type": "heading", "text": "Rýchly výber podľa úlohy"},
                {"type": "list", "items": [
                    "malloc(size): nový blok s neurčeným obsahom. Pred čítaním ho inicializuj; pri neúspechu dostaneš NULL.",
                    "calloc(count, size): priestor pre count prvkov, každý so size bajtmi, nastavený na nulové bity. Nie je to všeobecná inicializácia ľubovoľného typu na jeho jazykovú nulovú hodnotu.",
                    "realloc(pointer, size): zmena veľkosti vlastneného bloku; úspech nahrádza pôvodný objekt, neúspech pri nenulovej veľkosti ho zachová.",
                    "free(pointer): koniec vlastníctva bloku. free(NULL) nič neurobí; ostatné argumenty musia spĺňať pravidlá alokátora.",
                    "strtol(text, &end, base): prevod číselného začiatku textu na long s kontrolovateľným koncom a rozsahom.",
                    "qsort(base, count, size, compare): triedenie poľa na mieste. bsearch(key, base, count, size, compare): hľadanie v poli usporiadanom podľa zodpovedajúceho porovnávača."
                ]},
                {"type": "heading", "text": "Alokácia: veľkosť, vlastník a obsah"},
                {"type": "paragraph", "text": "Výraz count * sizeof *values vyjadruje požadovanú veľkosť poľa. Ešte pred násobením však pri nenulovej veľkosti prvku over count <= SIZE_MAX / sizeof *values. Inak by sa neznamienkový súčin mohol pretočiť na malý blok a následný zápis by prekročil jeho hranicu. Pre nulu si urč samostatnú vetvu: napríklad prázdne pole reprezentované NULL a počtom 0, bez volania alokátora."},
                {"type": "paragraph", "text": "V C sa void * z malloc automaticky prevedie na ukazovateľ na objekt. Dôležitá je hlavička stdlib.h, správna veľkosť a kontrola NULL, nie pretypovanie výsledku. Alokovaná pamäť musí zostať dostupná cez vlastníka až po free. Funkcia free neprijíma adresu lokálneho poľa, reťazcového literálu ani ukazovateľ posunutý doprostred bloku."},
                {"type": "paragraph", "text": "calloc nastavuje bity, nie konštruktory objektov. Pre pole int tým dostaneš nuly, no všetky nulové bity nemusia predstavovať nulový ukazovateľ alebo desatinnú nulu na každej implementácii. Podobne memset(pointer, 0, bytes) nie je všeobecnou náhradou správnej inicializácie ľubovoľnej štruktúry."},
                {"type": "heading", "text": "realloc: dve rôzne návratové cesty"},
                {"type": "code", "title": "Rovnaký overený rast poľa ako v kapitole o pamäti", "language": "c", "source": GROW_BUFFER},
                {"type": "paragraph", "text": "Pomocná funkcia prijíma adresy premenných vlastníka; tie musia byť platné. Pôvodné *values je NULL alebo živý blok alokátora. Dočasný ukazovateľ temporary zachová pôvodný pri neúspechu. Až po úspechu sa zmení vlastník aj kapacita. Nové prvky po zväčšení nemajú určený obsah, preto ich main pred čítaním doplní. Počet platných prvkov a kapacita sú dve odlišné hodnoty."},
                {"type": "list", "items": [
                    "Pri úspechu sa zachová obsah po menšiu z pôvodnej a novej veľkosti. Pamäť sa mohla presunúť.",
                    "Po úspešnom realloc už nepoužívaj pôvodné ukazovatele do bloku, ani ich neporovnávaj s novým vlastníkom. Potrebnú pozíciu si uchovaj ako index a nový pohľad vytvor z nového bloku.",
                    "Pri neúspechu s nenulovou veľkosťou starý blok stále patrí volajúcemu a musí sa napokon uvoľniť. Priame priradenie values = realloc(values, bytes) by mohlo stratiť jeho jedinú adresu.",
                    "Ukážka odmieta requested=0. realloc(pointer, 0) má v C17 osobitné implementačne závislé správanie; prázdny stav rieš výslovným free a nastavením vlastníka na NULL.",
                    "Pri zmenšení musí volajúci upraviť aj počet platných prvkov, aby nepresahoval novú kapacitu. resize_values samo upravuje iba kapacitu."
                ]},
                {"type": "callout", "tone": "warning", "text": "Po free nastav vlastnícku premennú na NULL, ak bude ďalej existovať, ale nepovažuj to za opravu všetkých ostatných odkazov na blok. Zánik objektu sa týka aj jeho aliasov. Zlyhanie alokácie testuj riadeným testovacím alokátorom, nie pokusom vyčerpať pamäť počítača."},
                {"type": "heading", "text": "strtol: výsledok ešte nie je overený vstup"},
                {"type": "paragraph", "text": "strtol vracia long, nie int. Pri platnom základe preskočí počiatočné biele znaky, prijme voliteľné znamienko a číta číselný začiatok. Základ 10 znamená desiatkový zápis; základ 0 môže podľa predpony voliť osmičkový alebo šestnástkový zápis. Ak rozhranie žiada bežné desiatkové číslo, použi 10 a nenechávaj predponu meniť jeho význam."},
                {"type": "list", "items": [
                    "Pred volaním nastav errno=0 a hneď po ňom zachyť jeho hodnotu. Úspešné volanie nemusí vymazať predchádzajúcu chybu.",
                    "end == text znamená, že nevzniklo číslo. Samotný návrat 0 to neprezradí, pretože nula môže byť platným údajom.",
                    "Cez end skontroluj zvyšok textu. Pri „42x“ mohol byť úspešne prečítaný číselný začiatok, hoci celý vstup nie je platné číslo.",
                    "ERANGE znamená problém rozsahu long; pred prevodom na int osobitne over INT_MIN a INT_MAX.",
                    "Povoľovanie koncových medzier je pravidlo nášho parsera, nie automatická kontrola strtol. Pracuj iba s platným ukončeným reťazcom."
                ]},
                {"type": "code", "title": "Ten istý parser, šesť odlišných vstupov", "language": "c", "source": STRTOL_REFERENCE},
                {"type": "paragraph", "text": "parse_int z kapitoly Chybové kódy a kontrakty sa používa bez novej implementácie. PARSE_OK=0 zapíše výsledok, PARSE_ARGUMENT=1 odmietne NULL, PARSE_INVALID=2 chybný zápis a PARSE_RANGE=3 rozsah. Pri chybe zostáva 77. Posledný vstup vznikne pridaním desiatkovej nuly za zápis INT_MAX: prekročí rozsah int danej implementácie bez toho, aby samotný program vykonal pretekajúce násobenie."},
                {"type": "paragraph", "text": "atoi neposkytuje porovnateľné hlásenie rozsahu a konca prevodu. Rovnako zmena na strtoul sama osebe nezakáže záporný zápis: táto funkcia prijíma voliteľné znamienko. Pri nezáporných počtoch preto skontroluj pravidlá zápisu aj rozsah cieľového typu. Parser čísla stále nenahrádza predchádzajúce načítanie celého riadka."},
                {"type": "heading", "text": "qsort a bsearch: porovnanie je súčasť kontraktu"},
                {"type": "code", "title": "Triedenie a vyhľadávanie bez pretekajúceho odčítania", "language": "c", "source": SORT_SEARCH},
                {"type": "paragraph", "text": "Porovnávač dostáva ukazovatele na dva prvky a vracia zápornú hodnotu, nulu alebo kladnú hodnotu. Výraz (a > b) - (a < b) vytvorí -1, 0 alebo 1 bez odčítania samotných dát. Oproti tomu return a - b môže pretiecť napríklad pri INT_MIN a kladnom b. Porovnávač musí dávať konzistentné poradie a počas porovnávania nemení prvky."},
                {"type": "paragraph", "text": "qsort mení poradie v zapisovateľnom poli a nevracia stav úspechu. Názov nezaručuje konkrétny triediaci algoritmus ani zachovanie pôvodného poradia rovnocenných prvkov. bsearch potrebuje pole usporiadané podľa rovnakého poradia; pri nájdení vracia ukazovateľ do tohto poľa, inak NULL. Pri viacerých rovnocenných prvkoch nie je zaručený prvý z nich."},
                {"type": "paragraph", "text": "V ukážke vznikne -3 0 2 7 7, kľúč 7 sa nájde a 9 chýba. Výsledok hľadania nevlastní nový blok a nevolá sa naň free. Zanikne s poľom; po ďalšom triedení či presune bloku už nemusí označovať pôvodne hľadaný údaj. Veľkosť prvku je sizeof values[0], počet je count, nie počet bajtov celého poľa."},
                {"type": "heading", "text": "Ukončenie a ďalšie hranice"},
                {"type": "list", "items": [
                    "EXIT_SUCCESS alebo návrat 0 z main oznamuje úspech, EXIT_FAILURE neúspech. Konkrétna číselná hodnota EXIT_FAILURE nie je prenositeľnou konštantou 1.",
                    "exit zabezpečuje normálne ukončenie vrátane registrovaných funkcií a spracovania otvorených prúdov; abort je abnormálne ukončenie a rovnaké upratanie nezaručuje.",
                    "abs nie je kontrolovaný prevod na kladnú hodnotu. Ak absolútna hodnota nie je reprezentovateľná ako int, výsledok je nedefinovaný.",
                    "rand je generátor pseudonáhodných čísel, nie zdroj kryptografických tajomstiev. Výraz rand() % n navyše vyžaduje nenulové n a môže vytvárať nerovnomerné rozdelenie."
                ]},
                {"type": "callout", "tone": "info", "text": "Pred použitím funkcie si povedz: kto vlastní objekt, koľko prvkov existuje, čo znamená návrat a čo zostane pri chybe? V cvičení doplníš porovnávač a preveríš aj krajné hodnoty int, aby správne poradie nestálo na náhodnom pretočení odčítania."}
            ]
        }
    },
    {
        "key": "string-reference",
        "parent_key": "reference",
        "kind": "reference",
        "position": 165,
        "title": "string.h: dĺžka, porovnanie a kopírovanie",
        "summary": "Dĺžka a kapacita, úplná zhoda a prefix, kontrolované kopírovanie a prekrývanie oblastí.",
        "content": {
            "lead": "Funkcie z string.h pracujú s poľami. Časť z nich očakáva reťazec ukončený nulovým znakom, časť pracuje s ľubovoľnými bajtami a vždy potrebuje presnú dĺžku.",
            "blocks": [
                {"type": "heading", "text": "Reťazec a rozsah bajtov nie sú to isté"},
                {"type": "list", "items": [
                    "strlen, strcmp, strcpy a strcat pracujú s reťazcami ukončenými nulovým znakom. Nezistia, akú veľkosť objektu im volajúci skutočne odovzdal.",
                    "memchr, memcmp, memcpy, memmove a memset pracujú s počtom bajtov. Vložená nula pre ne neznamená koniec dát.",
                    "Kapacita je počet dostupných miest v objekte. Dĺžka textu je počet bajtov pred prvou nulou, bez samotnej nuly.",
                    "Prázdny reťazec potrebuje jeden bajt s hodnotou 0. Nulová kapacita nie je miesto ani pre prázdny reťazec."
                ]},
                {"type": "paragraph", "text": "strlen vracia size_t. Nepočíta Unicode znaky, viditeľné písmená ani šírku na obrazovke: v UTF-8 môže jedno písmeno zaberať viac bajtov. sizeof poľa pozná jeho kapacitu v mieste, kde je objekt poľom; sizeof parametra char * alebo char text[] vo funkcii zistí veľkosť ukazovateľa, nie odovzdaného poľa. Kapacitu preto odovzdaj osobitne."},
                {"type": "heading", "text": "strcmp a strncmp: zhoda alebo iba prefix"},
                {"type": "code", "title": "Rovnaký začiatok ešte nie je rovnaký text", "language": "c", "source": COMPARE_STRINGS},
                {"type": "paragraph", "text": "Pole text má kapacitu 8 a dĺžku 3. strcmp(text, \"C17\") vráti nulu, ale porovnanie celého textu s \"C17 notes\" je záporné. strncmp s limitom 3 vidí iba spoločný začiatok, preto hlási zhodu. Program normalizuje výsledok porovnania na -1, 0 alebo 1; samotné strcmp tieto konkrétne hodnoty nesľubuje."},
                {"type": "paragraph", "text": "strcmp a strncmp porovnávajú podľa hodnôt unsigned char, nie podľa pravidiel slovenského abecedného radenia. Pre úplnú rovnosť platných reťazcov použi strcmp(...) == 0. Limit v strncmp neoveruje celkovú platnosť dlhšieho textu; obe oblasti musia byť čitateľné až po rozhodujúce porovnanie, skoršiu koncovú nulu alebo stanovený limit."},
                {"type": "heading", "text": "Kopírovanie musí pomenovať chybovú cestu"},
                {"type": "paragraph", "text": "strcpy kopíruje aj koncovú nulu, ale nepozná veľkosť cieľa. strcat navyše najprv hľadá koniec existujúceho cieľového reťazca. Obe potrebujú dostatočnú kapacitu a neprekrývajúce sa oblasti. Rozhodni sa vopred, či dlhý text odmietneš, skrátiš alebo preň vytvoríš väčší blok. Nasledujúce rozhranie odmieta a pri chybe necháva celý cieľ nezmenený."},
                {"type": "code", "title": "Kontrola ukončenia a kapacity pred jediným zápisom", "language": "c", "source": COPY_TEXT_DEMO},
                {"type": "paragraph", "text": "Kapacitu cieľa aj rozsah zdroja poskytuje volajúci. source_size musí opisovať skutočne čitateľnú oblasť; číslo samo z ľubovoľnej adresy platný objekt nevytvorí. memchr ohraničene vyhľadá nulový bajt. Až keď ho nájde, je bezpečné zavolať strlen. Sú to dva priechody, ale jasne oddeľujú overenie ukončenia od merania dĺžky."},
                {"type": "paragraph", "text": "Porovnanie length >= capacity odmietne prípad, keď by chýbalo miesto pre koncovú nulu. Nepočíta length + 1 skôr, než je potrebné. Keďže sa nula našla vo vnútri source_size, následné length + 1 sa zmestí aj do size_t. Jediný zápis cez memmove nastane až po všetkých kontrolách a zahŕňa nulu. Preto môže rozhranie povoliť aj prekrývanie zdroja a cieľa."},
                {"type": "list", "items": [
                    "COPY_OK=0 znamená úplný skopírovaný reťazec. Kapacita 4 presne stačí na \"C17\" vrátane nuly.",
                    "COPY_ARGUMENT=1 odmieta NULL namiesto zdroja alebo cieľa, aj pri nulovej kapacite. Nenulové adresy musia spĺňať kontrakt dostupných oblastí.",
                    "COPY_UNTERMINATED=2 znamená, že v poskytnutom zdrojovom rozsahu nie je nula. Pole {'C', '1', '7'} nie je reťazec.",
                    "COPY_SPACE=3 znamená, že platný reťazec nemá v cieli dosť miesta. Žiadna jeho skrátená časť sa nezapíše.",
                    "Poradie chýb je zámerné: NULL, potom ukončenie zdroja, potom kapacita cieľa. Pri dvoch porušeniach rozhranie nevracia náhodne prvé podľa priebehu kopírovania."
                ]},
                {"type": "callout", "tone": "warning", "text": "strncpy nie je automaticky bezpečnejšie strcpy. Pri zdroji dlhom aspoň n nemusí zapísať koncovú nulu; pri kratšom doplní nuly až do n zapísaných bajtov. Aj tak potrebuje cieľ s miestom pre n bajtov a nepovoľuje prekrytie. strncat má zase limit počtu pridávaných znakov, nie celkovú kapacitu cieľa."},
                {"type": "heading", "text": "memcpy verzus memmove: dva smery prekrytia"},
                {"type": "code", "title": "Vloženie predpony a následné odstránenie", "language": "c", "source": MOVE_TEXT},
                {"type": "paragraph", "text": "Prvý memmove posunie existujúci text doprava o dva bajty vrátane jeho nuly. memcpy potom doplní predponu z iného, neprekrývajúceho sa poľa. Druhý memmove odstráni predponu posunom doľava. Výstup je najprv > ABCDE a potom ABCDE. Obyčajný cyklus kopírujúci zľava doprava by pri prvom posune prepísal údaje, ktoré ešte len potrebuje čítať."},
                {"type": "paragraph", "text": "memmove sa správa, akoby údaje najprv odložilo bokom; implementácia nemusí skutočne vytvárať pomocné pole. Nie je to kontrola kapacity. Obe oblasti musia pokrývať presne požadovaný počet bajtov. Nula sa tu prenesie vďaka +1, nie preto, že ju funkcia sama pridáva."},
                {"type": "paragraph", "text": "Pri pridaní predpony sa priestor kontroluje odčítaním od známej kapacity, až po overení, že sa zmestí samotná predpona s nulou. Všeobecné length + prefix_length + 1 by pri neoverených veľkých hodnotách mohlo pretiecť. Na opačnom konci ukážky je existencia vloženej predpony známy predpoklad; pri cudzom vstupe by sa jej dĺžka a obsah museli najprv overiť."},
                {"type": "heading", "text": "Hľadanie a porovnávanie bajtov"},
                {"type": "list", "items": [
                    "memchr(data, value, count) hľadá prvý zodpovedajúci bajt v rozsahu; výsledok je ukazovateľ dovnútra pôvodného objektu alebo NULL. Nevlastní nový blok.",
                    "strchr(text, ch) hľadá v platnom reťazci; môže nájsť aj jeho koncovú nulu. strstr hľadá podreťazec. Návratový ukazovateľ stráca platnosť so zdrojovým objektom.",
                    "memcmp(left, right, count) porovná presne dané rozsahy ako unsigned char a používa sa znamienko výsledku. Nepovažuj ho za všeobecné porovnanie hodnôt struct: výplňové bajty nemusia byť zhodné.",
                    "memset(target, byte, count) opakuje jeden bajt. memset poľa int hodnotou 1 nevytvorí všeobecne pole celých čísel 1.",
                    "Nulový počet bajtov všeobecne neoprávňuje poslať NULL do funkcií string.h. Ak tvoje vlastné rozhranie povoľuje prázdny rozsah s NULL, vybav ho bez takého volania."
                ]},
                {"type": "heading", "text": "Čo nie je súčasťou sľubu C17"},
                {"type": "paragraph", "text": "strnlen, strdup či strlcpy môžu byť užitočné rozšírenia prostredia, ale nepatria medzi povinné funkcie ISO C17. Dostupnosť jednej z nich na počítači neznamená dostupnosť na mikrokontroléri. Ani voliteľné rozhrania s príponou _s nie sú univerzálne dostupné. V tejto referencii preto príklady stoja na základných funkciách C17 a vlastnom výslovnom kontrakte."},
                {"type": "paragraph", "text": "strtok mení odovzdaný text a uchováva stav medzi volaniami. Neposielaj mu reťazcový literál a neber ho ako hotový parser CSV: opakované oddeľovače nepredstavujú zachované prázdne polia a úvodzovky nemajú zvláštny význam. Výber knižničnej funkcie musí zodpovedať formátu, nie iba podobnému názvu operácie."},
                {"type": "callout", "tone": "info", "text": "Pri kopírovaní over prázdny text, presné zaplnenie, chýbajúcu nulu, nulovú kapacitu a oba smery prekrytia. Pri odmietnutí skontroluj aj pôvodný obsah cieľa, nielen návratový kód. Také testy odlišujú skutočný kontrakt od programu, ktorý iba nespadol."}
            ]
        }
    },
    {
        "key": "numeric-reference",
        "parent_key": "reference",
        "kind": "reference",
        "position": 175,
        "title": "Čísla, limity a znaky",
        "summary": "limits.h, stdint.h, ctype.h a bezpečné spracovanie znakov.",
        "content": {
            "lead": "Základné celočíselné typy majú implementáciou závislú šírku. Ak potrebuješ presný rozsah alebo prácu s jednotlivými znakmi vstupu, siahni po príslušných štandardných hlavičkách.",
            "blocks": [
                {"type": "heading", "text": "Vyber hlavičku podľa otázky"},
                {"type": "list", "items": [
                    "limits.h: CHAR_BIT a rozsahy základných celočíselných typov, napríklad CHAR_MIN, CHAR_MAX, INT_MIN a INT_MAX.",
                    "stddef.h: size_t pre veľkosti objektov a ptrdiff_t pre reprezentovateľný rozdiel ukazovateľov do toho istého poľa.",
                    "stdint.h: celočíselné rodiny s určenými požiadavkami na šírku, intmax_t/uintmax_t a limity vrátane SIZE_MAX.",
                    "inttypes.h: makrá formátov pre tieto celočíselné rodiny. Formát vyber podľa typu, nie podľa odhadu jeho typedef.",
                    "ctype.h: klasifikácia a zmena veľkosti jednotlivých bajtových znakov. Nie je to knižnica na spracovanie celých Unicode znakov.",
                    "float.h: rozsah a presnosť typov s pohyblivou rádovou čiarkou. Ich pravidlá sa nesmú zamieňať s celočíselnými limitmi."
                ]},
                {"type": "heading", "text": "Koľko bitov a aký rozsah naozaj máš"},
                {"type": "code", "title": "Hranice implementácie a formáty inttypes.h", "language": "c", "source": INTEGER_LIMITS},
                {"type": "paragraph", "text": "sizeof počíta bajty jazyka C a sizeof(char) je vždy 1. CHAR_BIT určuje, koľko bitov má taký bajt; nemusí ich byť osem. Súčin sizeof(int) a CHAR_BIT vyjadruje veľkosť uloženia, nie automaticky počet hodnotových bitov: reprezentácia môže obsahovať aj výplň. Skutočný rozsah int preto čítaj z INT_MIN a INT_MAX."},
                {"type": "paragraph", "text": "Číselné hranice vo výpise sa môžu líšiť medzi počítačom a mikrokontrolérom. CHAR_MIN môže byť záporné alebo nula podľa obyčajného char. Hodnoty measurement=123456 a count=9000000000 sa však zmestia do zvolených najmenej širokých typov a ich výpis používa zodpovedajúce makrá, nie predpoklad, že 64-bitový typ je vždy unsigned long."},
                {"type": "heading", "text": "Presná šírka, najmenej široký typ a konštanta"},
                {"type": "list", "items": [
                    "int32_t a uint64_t vyžadujú presne danú šírku bez výplňových bitov; presné typy sú dostupné len vtedy, keď ich implementácia vie poskytnúť.",
                    "int_least32_t a uint_least64_t garantujú aspoň potrebnú šírku, nie presný počet bajtov. Sú vhodné, keď potrebuješ rozsah a nie konkrétny obraz pamäte.",
                    "int_fast32_t vyberá implementácia s ohľadom na efektívnu prácu pri aspoň danej šírke. Názov nie je univerzálny výkonnostný sľub pre každý algoritmus.",
                    "INT32_C a UINT64_C vytvárajú konštanty pre zodpovedajúce least rodiny po povýšení. Samotný veľký číselný literál bez vhodnej prípony nemusí mať očakávaný typ.",
                    "PRIdLEAST32 a PRIuLEAST64 sa spoja s okolitými literálmi formátu pri preklade. Pre presné typy použi zodpovedajúce PRId32 či PRIu64, ak sú tieto typy dostupné."
                ]},
                {"type": "heading", "text": "Pretypovanie nie je kontrola rozsahu"},
                {"type": "paragraph", "text": "size_t je neznamienkový. Prevod -1 na size_t je definovaný a vytvorí SIZE_MAX, ale to z neplatného počtu nevytvorí použiteľnú kapacitu. Pri prevode veľkého neznamienkového čísla do int mimo rozsahu je v C17 výsledok implementačne definovaný alebo vznikne implementačne definovaný signál. Prevod môže teda byť chybným rozhodnutím aj bez bežného aritmetického pretečenia."},
                {"type": "code", "title": "Dva smery prevodu so zachovaním výsledku pri chybe", "language": "c", "source": CONVERT_SIZES},
                {"type": "paragraph", "text": "int_to_size najprv odmietne NULL, potom zápornú hodnotu a prípadné prekročenie SIZE_MAX. Aj nezáporný int môže byť na inej implementácii širší než size_t. size_to_int zase porovná s INT_MAX pred zápisom. uintmax_t dokáže reprezentovať hodnoty každého neznamienkového celočíselného typu, takže kontroly nestrácajú vysoké bity zúžením."},
                {"type": "paragraph", "text": "CONVERT_OK=0 znamená zapísaný výsledok, CONVERT_ARGUMENT=1 chýbajúci výstupný ukazovateľ a CONVERT_RANGE=2 neprípustnú hodnotu. V prvom riadku zostane pri -1 pôvodných 77. Nula aj 12 sú platné. Posledný prípad so SIZE_MAX závisí od konkrétnych limitov: na bežnom 64-bitovom počítači sa do int nezmestí, no výklad nepredpokladá rovnaký pomer typov na každom zariadení."},
                {"type": "callout", "tone": "warning", "text": "Najprv over rozsah pôvodnej hodnoty, až potom ju preveď. Kontrola už zúženého výsledku nemá informáciu o zahodených bitoch. Pri zmiešanom signed/unsigned porovnaní sa navyše môže záporná hodnota implicitne zmeniť na veľké neznamienkové číslo; vetvu pre záporné čísla preto rieš osobitne."},
                {"type": "heading", "text": "ctype.h má presnú doménu argumentov"},
                {"type": "paragraph", "text": "isdigit, isspace, toupper a príbuzné funkcie prijímajú EOF alebo hodnotu reprezentovateľnú ako unsigned char. Záporný obyčajný char, ktorý nie je EOF, je mimo kontraktu. Pre znak uložený v char preto použi isdigit((unsigned char) character). Samotné rozšírenie na int zápornú hodnotu neopraví."},
                {"type": "paragraph", "text": "Klasifikačné funkcie vracajú nulu alebo nenulovú hodnotu, nie nevyhnutne 1. Na rozhodnutie použi if (isdigit(byte)); pre výpis 0/1 použi isdigit(byte) != 0. toupper zase vracia prevedený znak alebo pôvodnú hodnotu, ak sa nič nemení; nie je to booleovský test."},
                {"type": "code", "title": "Bajty zo vstupu bez zámeny s EOF", "language": "c", "source": CLASSIFY_BYTES},
                {"type": "paragraph", "text": "fgetc sa najprv uloží do int a overí proti EOF. Až potom z neho vytvoríme bajt. Na bežnom osembitovom systéme by predčasné uloženie do signed char mohlo zmeniť bajt FF na -1 a zameniť ho s EOF; pri unsigned char by sa zase skutočné EOF mohlo stratiť. Cyklus sa skončí na výsledku čítania a následne ferror rozlíši chybu od obyčajného konca."},
                {"type": "paragraph", "text": "Skúšobný vstup a0 Z s novým riadkom ukáže číslicu, medzeru aj ukončenie riadka. Hodnoty sú vypísané šestnástkovo, aby boli viditeľné aj riadiace bajty. V ASCII prostredí sa a zmení z 61 na 41, číslica 0 je 30 a medzera 20. Číselné kódy písmen však nie sú všeobecnou zárukou jazyka C."},
                {"type": "heading", "text": "Locale, UTF-8 a biele znaky"},
                {"type": "paragraph", "text": "Program začína v locale C, kým ho sám nezmení cez setlocale. Klasifikácia písmen a niektorých ďalších znakov môže závisieť od locale; isspace v locale C rozpoznáva medzeru, '\\f', '\\n', '\\r', '\\t' a '\\v'. Ak protokol povoľuje iba doslovnú medzeru, širší test isspace by menil jeho pravidlá."},
                {"type": "paragraph", "text": "Prechod cez bajty UTF-8 a volanie toupper na každý z nich nevykoná správnu Unicode zmenu veľkosti písmen. Tá môže vyžadovať dekódovanie, viac znakov alebo jazykový kontext. Tento príklad vedome učí bajtové rozhranie, nie spracovanie ľubovoľného prirodzeného jazyka."},
                {"type": "heading", "text": "Pripomenutie limitov desatinných typov"},
                {"type": "paragraph", "text": "FLT_MAX a DBL_MAX opisujú najväčšiu konečnú kladnú hodnotu príslušného typu. FLT_MIN nie je najzápornejšie číslo, ale najmenšia kladná normalizovaná hodnota float. FLT_EPSILON opisuje rozostup pri hodnote 1, nie univerzálnu toleranciu pre všetky porovnania. Toleranciu a prijateľné zaokrúhlenie musí určiť význam výpočtu."},
                {"type": "callout", "tone": "info", "text": "Pri prenositeľnosti overuj pravidlá, nie naučený výpis jednej platformy. Skús rovnaký program so znamienkovým aj neznamienkovým char, EOF hneď na začiatku, vloženú nulu a bajt FF. Pri prevodoch otestuj obe hranice a potvrď, že odmietnutie nezmenilo výstupný objekt."}
            ]
        }
    }
]


# Krátke, konkrétne ciele robia z kapitol učebný sled. Zostávajú oddelené od
# samotného výkladu, aby sa dali rovnako použiť v čítačke, pri opakovaní aj v
# budúcom generátore cvičení.
C_LEARNING_GOALS = {
    "program": ("Vysvetliť úlohu main a hlavičkového súboru.", "Preložiť malý program s užitočnými varovaniami."),
    "values": ("Vybrať primeraný základný typ.", "Rozpoznať konverziu, pri ktorej sa môže stratiť hodnota."),
    "operators": ("Čítať podmienku bez spoliehania sa na náhodnú prioritu operátorov.", "Použiť zátvorky na vyjadrenie zámeru."),
    "flow": ("Zvoliť if, switch, for alebo while podľa povahy rozhodnutia.", "Pomenovať invariant jednoduchého cyklu."),
    "functions": ("Navrhnúť jasné vstupy a návratovú hodnotu funkcie.", "Rozlíšiť návrat hodnoty a zmenu cez ukazovateľ."),
    "callbacks": ("Prečítať a použiť presne typovaný ukazovateľ na funkciu.", "Pomenovať stav a vlastníctvo, ktoré callback dostáva cez context."),
    "scope": ("Rozlíšiť rozsah mena od životnosti objektu.", "Vysvetliť, čo const chráni a čo nie."),
    "arrays": ("Vypočítať platné indexy poľa.", "Odovzdať do funkcie pole aj jeho veľkosť."),
    "pointers": ("Prečítať význam operátorov & a * v konkrétnom výraze.", "Rozpoznať neplatný alebo NULL ukazovateľ pred dereferencovaním."),
    "strings": ("Rezervovať miesto aj pre koncový nulový znak.", "Bezpečne načítať jeden riadok textu."),
    "types": ("Navrhnúť struct s jasnými invariantmi.", "Použiť enum pre pomenovaný stav."),
    "bits": ("Nastaviť, vypnúť a prepnúť príznak bez zmeny ostatných bitov.", "Rozlíšiť test aspoň jedného a všetkých požadovaných príznakov.", "Overiť rozsah pred sčítaním a rozpoznať neplatný posun."),
    "memory": ("Rozlíšiť počet platných prvkov, kapacitu a veľkosť bloku v bajtoch.", "Zachovať pôvodný blok pri neúspešnom realloc.", "Určiť vlastníka a uvoľniť pamäť aj na chybovej ceste."),
    "qualifiers": ("Rozlíšiť nemenný objekt od pohľadu cez ukazovateľ na const.", "Vysvetliť podmienku neprekrývania pri kopírovaní s restrict.", "Odôvodniť, prečo volatile ani oddelené atomic_load a atomic_store nenahradia atomické zvýšenie."),
    "preprocessor": ("Rozvinúť jednoduché makro a vysvetliť účinok zátvoriek.", "Rozlíšiť existenciu makra od jeho hodnoty pri podmienenom preklade.", "Rozpoznať opakované vyhodnotenie argumentu a nahradiť ho vhodnou funkciou."),
    "portability": ("Rozlíšiť definované, implementačne závislé, nešpecifikované a nedefinované správanie.", "Vybrať prenositeľný typ alebo rozhranie namiesto predpokladu o jednej platforme."),
    "build": ("Rozdeliť výpočet na hlavičku, implementáciu a volajúci program.", "Vysvetliť rozdiel medzi deklaráciou, definíciou a väzbou mena.", "Odlíšiť chybu prekladu od chýbajúcej alebo viacnásobnej definície pri linkovaní."),
    "io": ("Skontrolovať chybu pri textovom vstupe a výstupe.", "Oddeliť parsovanie textu od logiky programu."),
    "safety": ("Odlíšiť logickú chybu od nedefinovaného správania.", "Overiť hranicu poľa a rozsah operácie pred jej vykonaním.", "Rozpoznať porušenú životnosť objektu a nezoradené vedľajšie účinky."),
    "errors": ("Navrhnúť návratový stav, ktorý nezamieňa chybu s hodnotou.", "Uvoľniť zdroje aj na chybovej ceste."),
    "testing": ("Zostaviť pomenované hraničné a regresné testy s návratovým stavom.", "Vysvetliť rozdiel medzi assert, kontrolou vstupu a NDEBUG.", "Overiť testy známou chybou a nájsť prvú odchýlku krokovaním v GDB."),
    "string-reference": ("Vybrať reťazcovú alebo bajtovú funkciu podľa dostupného rozsahu.", "Overiť ukončenie, kapacitu a prekrytie pred kopírovaním."),
    "stdlib-reference": ("Zachovať vlastníctvo a údaje pri chybe alokácie alebo prevodu.", "Navrhnúť konzistentný porovnávač bez pretekajúceho odčítania."),
    "stdio-reference": ("Odlíšiť chybu formátovania od skrátenia a skontrolovať miesto pre nulu.", "Správne vyhodnotiť počet prenesených prvkov a uzavrieť prúd aj pri chybe."),
    "numeric-reference": ("Zvoliť typ a formát podľa skutočných limitov implementácie.", "Overiť rozsah pred prevodom a dodržať doménu ctype.h bez straty EOF."),
}


# Tento rámec je úmyselne oddelený od faktického výkladu. Každá lekcia sa tak
# začína problémom, nadväznosťou a jadrom pojmu, potom smeruje k vlastnej práci.
C_TEACHING_FRAMES = {
    "program": {"context": "Potrebuješ spoľahlivo dostať krátky zdrojový súbor až k spustiteľnému programu a vedieť rozlíšiť chybu prekladu od výsledku behu.", "priorKnowledge": ("Dokážeš čítať krátky textový súbor.",), "keyIdea": "Zdroj, hlavičky, preklad a spustenie sú nadväzujúce kroky; main je dohodnutý vstupný bod programu.", "transfer": "Pri najbližšom programe najprv pomenuj, čo patrí do hlavičky, čo do main a akú informáciu má návratový kód odovzdať prostrediu."},
    "values": {"context": "Program musí odlíšiť počet, meranú veličinu, znak a údaj s presne daným formátom, aj keď všetko napokon leží v pamäti.", "priorKnowledge": ("Rozlíšiš celé číslo, desatinnú hodnotu a jeden znak.",), "keyIdea": "Typ je kontrakt medzi významom hodnoty, jej rozsahom a povolenými operáciami.", "transfer": "Pri vlastnom kóde pomenuj význam každej premennej a pri každej konverzii si over, či sa nestratí informácia."},
    "operators": {"context": "Pri rozhodovaní programu potrebuješ čítať podmienku rovnako presne, ako ju prekladateľ vyhodnotí.", "priorKnowledge": ("Vieš porovnať dve číselné hodnoty.",), "keyIdea": "Zátvorky a krátke medzivýsledky vyjadrujú zámer lepšie než spoliehanie sa na pamäť priorít.", "transfer": "Rozdeľ jednu dlhú podmienku vo vlastnom programe na pomenované otázky a skontroluj poradie pri && a ||."},
    "flow": {"context": "Programy musia rozhodovať podľa vstupu a opakovať krok bez toho, aby prekročili hranice dát alebo sa zasekli.", "priorKnowledge": ("Vieš porovnať hodnoty a priradiť výsledok do premennej.",), "keyIdea": "Podmienka vyberá cestu; invariant pomáha udržať správny stav v každom kroku cyklu.", "transfer": "Pri ďalšom cykle vyslov jednou vetou, čo už platí pred aktuálnym indexom a pri akej podmienke cyklus skončí."},
    "functions": {"context": "Väčší program rozdelíš na malé kroky, len ak každá funkcia jasne povie, čo potrebuje a čo po nej zostáva.", "priorKnowledge": ("Vieš vytvoriť premennú a podmienku.",), "keyIdea": "Funkcia dostáva parametre hodnotou; ukazovateľ dá prístup k objektu, nie výnimku z tohto pravidla.", "transfer": "Pri najbližšej funkcii napíš pred jej telom vetu o platnom vstupe, návratovej hodnote a vlastníctve prípadných ukazovateľov."},
    "scope": {"context": "Chyby s premennými často nevzniknú v riadku, kde sú vytvorené, ale keď sa program pokúsi použiť ich po zániku alebo mimo ich rozsahu.", "priorKnowledge": ("Poznáš funkcie a lokálne premenné.",), "keyIdea": "Rozsah hovorí, kde platí meno; životnosť hovorí, dokedy existuje objekt.", "transfer": "Pri každom ukazovateli si pomenuj objekt, na ktorý ukazuje, a okamih, v ktorom tento objekt zanikne."},
    "callbacks": {"context": "Niekedy chceš odovzdať časti programu nielen dáta, ale aj konkrétnu operáciu, ktorú majú vykonať.", "priorKnowledge": ("Vieš čítať deklaráciu funkcie.", "Poznáš základný význam ukazovateľa."), "keyIdea": "Callback je presne typovaný ukazovateľ na funkciu spolu s kontraktom vstupu, výstupu a prípadného kontextu.", "transfer": "Pri návrhu callbacku si zvlášť zapíš, kto vytvorí a kto uvoľní stav odovzdaný cez context."},
    "arrays": {"context": "Pri práci so zoznamom hodnôt potrebuješ bezpečne prejsť každý prvok bez prístupu o krok vedľa.", "priorKnowledge": ("Poznáš celočíselné premenné a cyklus for.",), "keyIdea": "Pole je súvislý blok rovnakých prvkov a jeho platné indexy sú od nuly po počet mínus jedna.", "transfer": "Pri každom cykle nad poľom si over, odkiaľ prichádza jeho veľkosť a či index nikdy nedosiahne count."},
    "pointers": {"context": "Funkcia niekedy potrebuje pracovať s tým istým objektom ako volajúci program, nie iba s jeho kópiou.", "priorKnowledge": ("Rozumieš premenným, funkciám a rozsahu platnosti.",), "keyIdea": "Ukazovateľ nesie adresu; dereferencovanie pristupuje k objektu na tejto adrese iba vtedy, keď je objekt platný.", "transfer": "Pred dereferencovaním si skontroluj, či ukazovateľ smie byť NULL a či jeho cieľ ešte žije."},
    "strings": {"context": "Text v C nie je samostatný typ, ale dohoda o poli znakov ukončenom nulovým znakom.", "priorKnowledge": ("Poznáš pole a znak typu char.",), "keyIdea": "Kapacita reťazca zahŕňa aj koncový znak \\0, preto musí vstup rešpektovať veľkosť cieľového poľa.", "transfer": "Pri každom načítaní textu vypočítaj, koľko viditeľných znakov sa zmestí, a over výsledok čítania."},
    "types": {"context": "Keď skupina hodnôt opisuje jednu vec, samostatné premenné rýchlo stratia spoločný význam.", "priorKnowledge": ("Poznáš základné typy a prístup k premenným.",), "keyIdea": "struct zhromažďuje údaje jedného konceptu a enum dáva pomenované hranice množine stavov.", "transfer": "Pri vlastnom type si napíš invariant, ktorý musí platiť pre jeho členy aj po zmene programu."},
    "bits": {"context": "Niektoré rozhrania ukladajú viac nezávislých stavov do jednotlivých bitov jedného čísla.", "priorKnowledge": ("Vieš pracovať s neznamienkovým celým číslom.",), "keyIdea": "Bitová maska pomenúva konkrétne bity; operácie &, |, ^ a ~ menia alebo čítajú práve tieto príznaky.", "transfer": "Pri každej maske si pomenuj význam jedného bitu a over, že posun ani konverzia nemenia jeho zamýšľanú šírku."},
    "memory": {"context": "Keď počet meraní nepoznáš vopred, potrebuješ meniť kapacitu poľa bez straty jeho doterajšieho obsahu.", "priorKnowledge": ("Poznáš polia, ukazovatele a životnosť objektu.", "Vieš meniť premennú volajúceho cez odovzdanú adresu."), "keyIdea": "Vlastník udržiava počet a kapacitu v súlade a uvoľní svoj blok aj pri chybe.", "transfer": "Pri každej alokácii pomenuj stav pred volaním, po úspechu aj po neúspechu a skontroluj všetky návratové cesty."},
    "qualifiers": {"context": "Rozhranie potrebuje povedať nielen typ dát, ale aj to, ktoré zmeny sú povolené a kto môže k objektu pristupovať.", "priorKnowledge": ("Poznáš ukazovatele, základné typy a životnosť objektov.",), "keyIdea": "Nemennosť prístupu, prístup k hardvéru, aliasovanie a súbežnosť sú odlišné problémy s odlišnými zárukami.", "transfer": "Pri každom kvalifikátore vysvetli, aký problém rieši, čo vyžaduje od volajúceho a čo naopak nezaručuje."},
    "preprocessor": {"context": "Pred samotným prekladom C sa zdrojový text mení podľa include a makier, čo môže pomôcť, ale aj skryť chybu.", "priorKnowledge": ("Vieš, čo robí hlavičkový súbor a funkcia.",), "keyIdea": "Preprocesor pracuje s textom pred typovou kontrolou; makro nie je funkcia a môže vyhodnotiť argument viac než raz.", "transfer": "Pri každom makre si skontroluj zátvorky, vedľajšie účinky argumentov a či by pomenovaná funkcia nebola jasnejšia."},
    "portability": {"context": "Kód môže dnes fungovať na jednom počítači a zajtra zlyhať inde, ak vychádza z nezdokumentovaného predpokladu.", "priorKnowledge": ("Poznáš typy, rozsahy a základný preklad.",), "keyIdea": "Prenositeľný C kód sa opiera o definované pravidlá a explicitné rozhrania, nie o náhodné vlastnosti jednej platformy.", "transfer": "Pri každej závislosti od veľkosti, bajtového poradia alebo typu char si vyhľadaj, čo sľubuje štandard a čo iba konkrétna platforma."},
    "build": {"context": "Viacsúborový projekt potrebuje oddeliť verejné rozhranie od implementácie a spojiť svoje časti do jedného programu.", "priorKnowledge": ("Vieš preložiť jeden zdrojový súbor a odovzdať pole funkcii.",), "keyIdea": "Deklarácia umožní skontrolovať volanie; definícia poskytne implementáciu a linker pripojí potrebné objektové súbory.", "transfer": "Pri pridávaní funkcie rozhodni, či je verejná, a skontroluj jej deklaráciu, definíciu aj zaradenie do zostavenia."},
    "io": {"context": "Vstup a výstup sú hranica medzi tvojím programom a nepredvídateľným vonkajším svetom.", "priorKnowledge": ("Poznáš reťazce, hodnoty a návratový stav funkcie.",), "keyIdea": "Najprv čítaj do známeho priestoru, potom over výsledok a až potom prevádzaj text na doménovú hodnotu.", "transfer": "Pri každom vstupe oddel načítanie, validáciu a vlastnú logiku do viditeľných krokov."},
    "safety": {"context": "Program môže vypísať správne číslo a pritom už porušiť pravidlá jazyka pri prístupe do pamäte.", "priorKnowledge": ("Poznáš polia, ukazovatele, životnosť objektov a chybové kontrakty.",), "keyIdea": "Bezpečnostná kontrola musí predchádzať neplatnej operácii; zdanlivý úspech ani neskoršia podmienka jej následky neodstránia.", "transfer": "Pri vlastnom indexovaní alebo delení nájdi posledný platný a prvý neplatný vstup a over poradie kontrol."},
    "errors": {"context": "Volajúci program musí vedieť, či dostal výsledok alebo iba náznak, že niečo zlyhalo.", "priorKnowledge": ("Vieš navrhnúť jednoduchú funkciu.",), "keyIdea": "Dobrý chybový kontrakt oddeľuje stav zlyhania od bežných dát a zachováva zdroje v platnom stave.", "transfer": "Pri funkcii s chybou si napíš, čo platí o výstupe a zdrojoch po každej návratovej ceste."},
    "testing": {"context": "Počítanie kladných hodnôt môže prejsť prekladom aj sanitizérom a predsa nesprávne započítať nulu.", "priorKnowledge": ("Vieš preložiť program, oddeliť funkciu a pomenovať jej kontrakt.", "Rozlišuješ logickú chybu a nedefinované správanie."), "keyIdea": "Test porovná výsledok s nezávislým očakávaním; debugger hľadá prvú odchýlku a regresný prípad chráni opravu.", "transfer": "Doplň hraničný test k vlastnej funkcii a zámernou malou chybou over, že test naozaj zlyhá."},
}

C_EXERCISE_TOPICS = {
    "program": "program",
    "values": "values",
    "operators": "operators",
    "flow": "flow",
    "functions": "functions",
    "scope": "scope",
    "arrays": "arrays",
    "pointers": "pointers",
    "strings": "strings",
    "types": "types",
    "bits": "bits",
    "memory": "memory",
    "preprocessor": "preprocessor",
    "build": "build",
    "io": "io",
    "errors": "errors",
    "safety": "safety",
    "testing": "testing",
    "string-reference": "string-reference",
    "stdlib-reference": "stdlib-reference",
    "stdio-reference": "stdio-reference",
    "numeric-reference": "numeric-reference",
}


# Nie každá kapitola potrebuje pohyblivý model. Tieto väzby zámerne ostávajú
# krátke: používame ich iba tam, kde zdrojový text sám neukáže stav v čase.
C_VISUALIZATION_IDS = {
    "functions": ("c-call-stack",),
    "arrays": ("c-memory-lifetime",),
    "pointers": ("c-memory-lifetime",),
    "memory": ("c-memory-lifetime",),
}


C_CHECKPOINT_IDS = {
    "program": "c-main-entry",
    "values": "c-value-conversion",
    "operators": "c-short-circuit",
    "flow": "c-loop-invariant",
    "functions": "c-pass-by-value",
    "scope": "c-object-lifetime",
    "arrays": "c-array-bound",
    "pointers": "c-pointer-write",
    "strings": "c-string-terminator",
    "types": "c-struct-enum",
    "bits": "c-bit-mask",
    "memory": "c-realloc-temp",
    "qualifiers": "c-atomic-increment",
    "preprocessor": "c-macro-evaluation",
    "build": "c-declaration-definition",
    "io": "c-input-boundary",
    "errors": "c-error-status",
    "safety": "c-check-before-access",
    "testing": "c-boundary-test",
    "string-reference": "c-copy-terminator-capacity",
    "stdlib-reference": "c-comparator-overflow",
    "stdio-reference": "c-snprintf-required",
    "numeric-reference": "c-ctype-input-domain",
}

C_EXAMPLES = [
    {
        "key": "macro-parentheses", "page_key": "preprocessor", "position": 20,
        "title": "Makro a zoskupenie výrazu",
        "description": "Porovnaj náhradu bez zátvoriek, so zátvorkami a ako súčasť väčšieho výrazu.",
        "source": MACRO_PARENTHESES, "stdin": "",
    },
    {
        "key": "macro-single-evaluation", "page_key": "preprocessor", "position": 30,
        "title": "Jedno zvýšenie argumentu",
        "description": "Funkcia dostane hodnotu argumentu iba raz; jej ďalšie použitie už pôvodnú premennú nemení.",
        "source": SINGLE_EVALUATION, "stdin": "",
    },
    {
        "key": "conditional-diagnostics", "page_key": "preprocessor", "position": 40,
        "title": "Zapnutá a vypnutá diagnostika",
        "description": "Porovnaj DEBUG_LOG s hodnotou 0 a 1; hodnota 2 predstavuje chybu konfigurácie.",
        "source": CONDITIONAL_BUILD, "stdin": "",
    },
    {
        "key": "measurements-single-file", "page_key": "build", "position": 20,
        "title": "Výpočet rozsahu v jednom súbore",
        "description": "Rovnaký algoritmus ako v trojsúborovom príklade; tento variant overuje výpočet, nie oddelené linkovanie.",
        "source": MEASUREMENTS_SINGLE_FILE, "stdin": "",
    },
    {
        "key": "mask-operations", "page_key": "bits", "position": 20,
        "title": "Zmeny masky krok za krokom",
        "description": "Porovnaj zapnutie, vypnutie a prepnutie bitu aj test jedného či všetkých príznakov.",
        "source": BIT_MASKS, "stdin": "",
    },
    {
        "key": "checked-add", "page_key": "bits", "position": 30,
        "title": "Sčítanie s kontrolou rozsahu",
        "description": "Over bežný súčet a odmietnutie pretečenia ešte pred jeho výpočtom.",
        "source": CHECKED_ADD, "stdin": "",
    },
    {
        "key": "grow-buffer", "page_key": "memory", "position": 20,
        "title": "Bezpečné zväčšenie poľa",
        "description": "Zachovaj tri merania, pridaj ďalšie dve a sleduj vlastníctvo pri zlyhaní realloc.",
        "source": GROW_BUFFER, "stdin": "",
    },
    {
        "key": "const-views", "page_key": "qualifiers", "position": 20,
        "title": "Nemenná adresa a pohľad na const",
        "description": "Tri ukazovatele ukazujú na rovnaké pole, ale povoľujú odlišné operácie.",
        "source": CONST_VIEWS, "stdin": "",
    },
    {
        "key": "restrict-copy", "page_key": "qualifiers", "position": 30,
        "title": "Kopírovanie s jasnou zmluvou",
        "description": "Zdrojová a cieľová oblasť sa neprekrývajú, ako vyžaduje toto rozhranie s restrict.",
        "source": RESTRICT_COPY, "stdin": "",
    },
    {
        "key": "atomic-counter", "page_key": "qualifiers", "position": 40,
        "title": "Atomické zvýšenie počítadla",
        "description": "Ukážka v jednom vlákne vysvetľuje pôvodnú a novú hodnotu pri atomic_fetch_add.",
        "source": ATOMIC_COUNTER, "stdin": "",
    },
    {
        "key": "hello",
        "page_key": "program",
        "position": 10,
        "title": "Výpis pozdravu",
        "description": "Najmenší kompletný program s návratovou hodnotou.",
        "source": "#include <stdio.h>\n\nint main(void)\n{\n    printf(\"Ahoj z C!\\n\");\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "integer-division",
        "page_key": "values",
        "position": 10,
        "title": "Celočíselné a desatinné delenie",
        "description": "Zmeň hodnoty a porovnaj výsledok delenia int a double.",
        "source": "#include <stdio.h>\n\nint main(void)\n{\n    int count = 7;\n    int groups = 2;\n\n    printf(\"int: %d\\n\", count / groups);\n    printf(\"double: %.2f\\n\", (double) count / groups);\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "grade",
        "page_key": "flow",
        "position": 10,
        "title": "Hodnotenie bodov",
        "description": "Program načíta celé číslo zo vstupu a vyberie zodpovedajúcu vetvu.",
        "source": "#include <stdio.h>\n\nint main(void)\n{\n    int points = 0;\n\n    printf(\"Body: \");\n    if (scanf(\"%d\", &points) != 1) {\n        fprintf(stderr, \"Očakávam celé číslo.\\n\");\n        return 1;\n    }\n\n    if (points >= 90) {\n        puts(\"výborne\");\n    } else if (points >= 50) {\n        puts(\"splnené\");\n    } else {\n        puts(\"skús znova\");\n    }\n\n    return 0;\n}\n",
        "stdin": "72\n",
    },
    {
        "key": "maximum",
        "page_key": "functions",
        "position": 10,
        "title": "Funkcia s návratovou hodnotou",
        "description": "Oddelenie výpočtu od vstupu a výstupu.",
        "source": "#include <stdio.h>\n\nint maximum(int left, int right)\n{\n    return left > right ? left : right;\n}\n\nint main(void)\n{\n    printf(\"%d\\n\", maximum(12, 9));\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "array-sum",
        "page_key": "arrays",
        "position": 10,
        "title": "Súčet prvkov poľa",
        "description": "Funkcia dostane ukazovateľ na prvý prvok a jeho počet.",
        "source": "#include <stddef.h>\n#include <stdio.h>\n\nint sum(const int values[], size_t count)\n{\n    int result = 0;\n\n    for (size_t index = 0; index < count; ++index) {\n        result += values[index];\n    }\n    return result;\n}\n\nint main(void)\n{\n    int values[] = {3, 1, 4, 1, 5};\n    size_t count = sizeof values / sizeof values[0];\n\n    printf(\"Súčet: %d\\n\", sum(values, count));\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "person",
        "page_key": "types",
        "position": 10,
        "title": "Štruktúra a pomenovaný stav",
        "description": "Jedna štruktúra nesie súvisiace údaje o osobe.",
        "source": "#include <stdio.h>\n\ntypedef enum {\n    beginner,\n    advanced\n} Level;\n\ntypedef struct {\n    const char *name;\n    Level level;\n} Person;\n\nint main(void)\n{\n    Person person = {.name = \"Mária\", .level = advanced};\n    const char *label = person.level == advanced ? \"pokročilý\" : \"začiatočník\";\n\n    printf(\"%s: %s\\n\", person.name, label);\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "average",
        "page_key": "memory",
        "position": 10,
        "title": "Alokácia a uvoľnenie poľa",
        "description": "calloc pripraví miesto pre hodnoty, free ho na konci uvoľní.",
        "source": "#include <stdio.h>\n#include <stdlib.h>\n\nint main(void)\n{\n    size_t count = 4;\n    int *values = calloc(count, sizeof *values);\n\n    if (values == NULL) {\n        fputs(\"Nedostatok pamäte.\\n\", stderr);\n        return 1;\n    }\n\n    for (size_t index = 0; index < count; ++index) {\n        values[index] = (int) (index + 1) * 10;\n    }\n\n    printf(\"Posledná hodnota: %d\\n\", values[count - 1]);\n    free(values);\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "operators-short-circuit",
        "page_key": "operators",
        "position": 10,
        "title": "Skrátené vyhodnocovanie",
        "description": "Druhá časť podmienky sa vykoná iba vtedy, keď je menovateľ nenulový.",
        "source": "#include <stdio.h>\n\nint main(void)\n{\n    const int dividend = 12;\n    const int denominator = 4;\n\n    if (denominator != 0 && dividend / denominator > 2) {\n        puts(\"Podmienka platí.\");\n    } else {\n        puts(\"Podmienka neplatí.\");\n    }\n\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "static-counter",
        "page_key": "scope",
        "position": 10,
        "title": "Lokálna statická hodnota",
        "description": "Počítadlo si uchová stav medzi jednotlivými volaniami funkcie.",
        "source": "#include <stdio.h>\n\nstatic unsigned int next_call(void)\n{\n    static unsigned int count = 0U;\n\n    count += 1U;\n    return count;\n}\n\nint main(void)\n{\n    printf(\"Volanie %u\\n\", next_call());\n    printf(\"Volanie %u\\n\", next_call());\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "swap-pointers",
        "page_key": "pointers",
        "position": 10,
        "title": "Výmena dvoch hodnôt",
        "description": "Funkcia dostane adresy premenných a zmení objekty volajúceho.",
        "source": "#include <stddef.h>\n#include <stdio.h>\n\nstatic void swap(int *left, int *right)\n{\n    if (left == NULL || right == NULL) {\n        return;\n    }\n\n    int temporary = *left;\n    *left = *right;\n    *right = temporary;\n}\n\nint main(void)\n{\n    int first = 3;\n    int second = 8;\n\n    swap(&first, &second);\n    printf(\"%d, %d\\n\", first, second);\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "feature-flags",
        "page_key": "bits",
        "position": 10,
        "title": "Príznaky v jednej hodnote",
        "description": "Bitová maska uloží viac nezávislých stavov do unsigned int.",
        "source": "#include <stdio.h>\n\nenum {\n    FEATURE_READ = 1U << 0,\n    FEATURE_WRITE = 1U << 1,\n    FEATURE_EXPORT = 1U << 2\n};\n\nint main(void)\n{\n    unsigned int flags = 0U;\n\n    flags |= FEATURE_READ;\n    flags |= FEATURE_EXPORT;\n\n    printf(\"Čítanie: %s\\n\", (flags & FEATURE_READ) != 0U ? \"áno\" : \"nie\");\n    printf(\"Zápis: %s\\n\", (flags & FEATURE_WRITE) != 0U ? \"áno\" : \"nie\");\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "trim-newline",
        "page_key": "strings",
        "position": 10,
        "title": "Riadkový vstup bez nového riadku",
        "description": "fgets načíta text a strcspn nájde znak nového riadku, ak sa zmestil.",
        "source": "#include <stdio.h>\n#include <string.h>\n\nint main(void)\n{\n    char name[32] = \"\";\n\n    fputs(\"Meno: \", stdout);\n    if (fgets(name, sizeof name, stdin) == NULL) {\n        fputs(\"Vstup sa nepodaril.\\n\", stderr);\n        return 1;\n    }\n\n    name[strcspn(name, \"\\n\")] = '\\0';\n    printf(\"Ahoj, %s!\\n\", name);\n    return 0;\n}\n",
        "stdin": "Ada\n",
    },
    {
        "key": "module-static-helper",
        "page_key": "build",
        "position": 10,
        "title": "Pomocná funkcia modulu",
        "description": "static vyjadruje, že pomocná funkcia nie je súčasťou verejného rozhrania.",
        "source": "#include <stdio.h>\n\nstatic int clamp(int value, int minimum, int maximum)\n{\n    if (value < minimum) {\n        return minimum;\n    }\n    if (value > maximum) {\n        return maximum;\n    }\n    return value;\n}\n\nint main(void)\n{\n    printf(\"%d\\n\", clamp(14, 0, 10));\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "parse-number",
        "page_key": "io",
        "position": 10,
        "title": "Načítanie celého čísla",
        "description": "Celý riadok, platný zápis a rozsah int sa overia oddelene. Skús aj medzery, 21abc a prázdny vstup.",
        "source": PARSE_NUMBER,
        "stdin": "21\n",
    },
    {
        "key": "formatted-output",
        "page_key": "io",
        "position": 20,
        "title": "Formáty a vyrovnávacia pamäť",
        "description": "Typ argumentu určuje formát; printf aj záverečné fflush môžu oznámiť chybu.",
        "source": FORMATTED_OUTPUT,
        "stdin": "",
    },
    {
        "key": "whole-lines",
        "page_key": "io",
        "position": 30,
        "title": "Hranica riadka a ďalší vstup",
        "description": "Najviac sedem bajtov na riadok. Dlhší riadok sa odmietne celý, ďalší sa spracuje.",
        "source": READ_LINES,
        "stdin": "abc\n1234567\nOK",
    },
    {
        "key": "file-roundtrip",
        "page_key": "io",
        "position": 40,
        "title": "Súbor od otvorenia po uzavretie",
        "description": "Dočasný súbor bez prepisovania vlastných dát; kontrola zápisu, čítania a uzavretia.",
        "source": FILE_ROUNDTRIP,
        "stdin": "",
    },
    {
        "key": "safe-index",
        "page_key": "safety",
        "position": 10,
        "title": "Kontrola indexu poľa",
        "description": "Index sa overí ešte pred pretypovaním na size_t a prístupom do poľa.",
        "source": SAFE_INDEX,
        "stdin": "2\n",
    },
    {
        "key": "checked-division", "page_key": "safety", "position": 20,
        "title": "Delenie až po kontrole",
        "description": "Nulový deliteľ a nereprezentovateľný podiel sa odmietnu pred operáciou; výsledok pri chybe zostane nezmenený.",
        "source": CHECKED_DIVISION, "stdin": "",
    },
    {
        "key": "parse-positive",
        "page_key": "errors",
        "position": 10,
        "title": "Stav a výstupný parameter",
        "description": "Tabuľka platných aj chybných vstupov ukáže stav a zachovanie pôvodnej hodnoty pri odmietnutí.",
        "source": PARSE_POSITIVE,
        "stdin": "",
    },
    {
        "key": "assert-maximum",
        "page_key": "testing",
        "position": 10,
        "title": "Malé testy cez assert",
        "description": "Štyri tvrdenia pre maximum; pri NDEBUG program výslovne oznámi, že testy neprebehli.",
        "source": ASSERT_MAXIMUM,
        "stdin": "",
    },
    {
        "key": "boundary-positive", "page_key": "testing", "position": 20,
        "title": "Tabuľka hraničných testov",
        "description": "Sedem pomenovaných prípadov, počet zlyhaní a neúspešný návrat pri chybe; kontroly zostávajú aktívne aj s NDEBUG.",
        "source": BOUNDARY_TESTS, "stdin": "",
    },
    {
        "key": "debug-positive", "page_key": "testing", "position": 30,
        "title": "Nájdi chybu krokovaním",
        "description": "Zámerná logická chyba: nula sa počíta ako kladná. Výstup expected=1 actual=2 a neúspešný návrat sú podkladom na opravu.",
        "source": DEBUG_POSITIVE, "stdin": "",
    },
    {
        "key": "snprintf-message",
        "page_key": "stdio-reference",
        "position": 10,
        "title": "Formátovanie s kapacitou",
        "description": "Kapacity 9, 8, 1 a 0 ukážu rozdiel medzi požadovanou dĺžkou a skutočným obsahom cieľa.",
        "source": SNPRINTF_MESSAGE,
        "stdin": "",
    },
    {
        "key": "stdio-lines-reference", "page_key": "stdio-reference", "position": 20,
        "title": "Celý riadok v referencii",
        "description": "Spoločný overený read_line: sedem bajtov obsahu, koncová nula a odlíšenie konca od odmietnutia.",
        "source": READ_LINES, "stdin": "abc\n1234567",
    },
    {
        "key": "binary-roundtrip-reference", "page_key": "stdio-reference", "position": 30,
        "title": "Binárny súbor vrátane nulového bajtu",
        "description": "fwrite a fread s prvkami veľkosti 1, kontrola krátkeho prenosu a jediné fclose na každej ceste.",
        "source": BINARY_ROUNDTRIP, "stdin": "",
    },
    {
        "key": "strtol-reference",
        "page_key": "stdlib-reference",
        "position": 10,
        "title": "Prevod textu na číslo",
        "description": "Šesť prípadov pre spoločný parse_int: číslo, nula, medzery, chybný zvyšok, prázdny text a prekročenie int.",
        "source": STRTOL_REFERENCE,
        "stdin": "",
    },
    {
        "key": "stdlib-resize-reference", "page_key": "stdlib-reference", "position": 20,
        "title": "Vlastník po zmene kapacity",
        "description": "Overený príklad z kapitoly Dynamická pamäť: dočasný ukazovateľ a zachovanie starého bloku pri neúspechu.",
        "source": GROW_BUFFER, "stdin": "",
    },
    {
        "key": "sort-search-reference", "page_key": "stdlib-reference", "position": 30,
        "title": "Usporiadaj a vyhľadaj",
        "description": "qsort a bsearch používajú rovnaké poradie; porovnávač neodčítava hodnoty, ktoré môžu pretiecť.",
        "source": SORT_SEARCH, "stdin": "",
    },
    {
        "key": "compare-strings",
        "page_key": "string-reference",
        "position": 10,
        "title": "Porovnanie textov",
        "description": "Dĺžka verzus kapacita a zhoda prefixu verzus úplná zhoda; výsledok strcmp sa vyhodnocuje podľa znamienka.",
        "source": COMPARE_STRINGS,
        "stdin": "",
    },
    {
        "key": "copy-text-reference", "page_key": "string-reference", "position": 20,
        "title": "Celý text alebo nezmenený cieľ",
        "description": "Ohraničené overenie koncovej nuly, kontrola kapacity a jediný zápis cez memmove až pri úspechu.",
        "source": COPY_TEXT_DEMO, "stdin": "",
    },
    {
        "key": "move-text-reference", "page_key": "string-reference", "position": 30,
        "title": "Prekrývajúce sa oblasti v oboch smeroch",
        "description": "Pridanie a odstránenie predpony s memmove; koncová nula je súčasťou kopírovaného rozsahu.",
        "source": MOVE_TEXT, "stdin": "",
    },
    {
        "key": "classify-character",
        "page_key": "numeric-reference",
        "position": 10,
        "title": "Bezpečná práca so znakom",
        "description": "fgetc zostáva int až po kontrolu EOF; klasifikácia vracia 0/1 a výpis ukáže aj riadiace bajty.",
        "source": CLASSIFY_BYTES,
        "stdin": "a0 Z\n",
    },
    {
        "key": "integer-limits-reference", "page_key": "numeric-reference", "position": 20,
        "title": "Hranice typov na tejto platforme",
        "description": "CHAR_BIT, rozsahy int a char, SIZE_MAX a výpis najmenej širokých typov cez makrá inttypes.h.",
        "source": INTEGER_LIMITS, "stdin": "",
    },
    {
        "key": "convert-sizes-reference", "page_key": "numeric-reference", "position": 30,
        "title": "Prevod veľkosti až po kontrole",
        "description": "Oba smery medzi int a size_t odmietnu neprípustný rozsah bez prepísania pôvodného výsledku.",
        "source": CONVERT_SIZES, "stdin": "",
    },
    {
        "key": "callback-operation",
        "page_key": "callbacks",
        "position": 10,
        "title": "Odovzdanie operácie callbackom",
        "description": "Funkcia apply prijme presne typovanú operáciu a zavolá ju s dvoma hodnotami.",
        "source": "#include <stdio.h>\n\ntypedef int (*BinaryOperation)(int left, int right);\n\nstatic int apply(int left, int right, BinaryOperation operation)\n{\n    return operation(left, right);\n}\n\nstatic int maximum(int left, int right)\n{\n    return left > right ? left : right;\n}\n\nint main(void)\n{\n    printf(\"%d\\n\", apply(4, 9, maximum));\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "const-view",
        "page_key": "qualifiers",
        "position": 10,
        "title": "Funkcia s nemenným pohľadom na pole",
        "description": "const v parametri vyjadruje, že funkcia hodnoty iba číta.",
        "source": "#include <stddef.h>\n#include <stdio.h>\n\nstatic int sum(const int values[], size_t count)\n{\n    int result = 0;\n\n    for (size_t index = 0; index < count; ++index) {\n        result += values[index];\n    }\n    return result;\n}\n\nint main(void)\n{\n    int values[] = {3, 1, 4};\n\n    printf(\"%d\\n\", sum(values, sizeof values / sizeof values[0]));\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "macro-and-inline",
        "page_key": "preprocessor",
        "position": 10,
        "title": "Makro a inline funkcia",
        "description": "Oba zápisy počítajú druhú mocninu; inline funkcia pritom dostáva jeden vyhodnotený argument.",
        "source": "#include <stdio.h>\n\n#define SQUARE(value) ((value) * (value))\n\nstatic inline int square_int(int value)\n{\n    return value * value;\n}\n\nint main(void)\n{\n    int value = 5;\n\n    printf(\"makro: %d\\n\", SQUARE(value));\n    printf(\"funkcia: %d\\n\", square_int(value));\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "exact-width-id",
        "page_key": "portability",
        "position": 10,
        "title": "Presný celočíselný typ",
        "description": "uint32_t a formát PRIu32 vyjadrujú očakávanú šírku aj bezpečný výpis hodnoty.",
        "source": "#include <inttypes.h>\n#include <stdint.h>\n#include <stdio.h>\n\nint main(void)\n{\n    uint32_t identifier = UINT32_C(4000000000);\n\n    printf(\"%\" PRIu32 \"\\n\", identifier);\n    return 0;\n}\n",
        "stdin": "",
    },
]


# Python je druhá vstavaná učebnica. Struktúra je úmyselne rovnaká ako pri C:
# databáza ju môže bezpečne synchronizovať pre každého používateľa bez toho,
# aby obsah lekcií bol závislý od záznamov konkrétneho používateľa.
PYTHON_LANGUAGE = {
    "code": "python",
    "title": "Python",
    "summary": "Praktická učebnica Pythonu: čitateľný kód, dátový model, balíky a asynchrónne programovanie.",
}

PYTHON_PAGES = [
    {
        "key": "overview",
        "parent_key": "",
        "kind": "overview",
        "position": 0,
        "title": "Python: učebnica a referencia",
        "summary": "Orientácia v kurze, verziách Pythonu a v tom, ako pracovať s príkladmi.",
        "content": {
            "lead": "Python stavia na čitateľnosti, dobrej štandardnej knižnici a jasných dátových modeloch. Rýchlo sa v ňom začína, no pevné základy rozhodujú aj pri väčších programoch.",
            "sections": [
                {"title": "Ako kurz používať", "paragraphs": ["Lekcie dávajú poradie a súvislosti, ukážky môžeš bez obáv upravovať a spúšťať v skúšobni.", "Pri každom novom type alebo rozhraní najprv zisti, či objekt meníš, vytváraš nový, alebo iba čítaš jeho hodnotu."], "bullets": ["Príklady predpokladajú aktuálny Python 3.", "Odsadenie je syntax, nie iba vzhľad.", "Dokumentácia a malé experimenty sú bežná súčasť práce v Pythone."]},
                {"title": "Hranice kurzu", "paragraphs": ["Štandardná knižnica je oddelená od externých balíkov. Keď príklad vyžaduje inštaláciu, bude to označené; najprv sa uč na veciach, ktoré fungujú v čistom prostredí."], "callout": "Nevykonávaj automaticky kód skopírovaný z internetu. Najmä práca so súbormi, procesmi, sieťou a deserializáciou má mať jasný účel a hranice vstupu."},
            ],
        },
    },
    {
        "key": "foundations",
        "parent_key": "",
        "kind": "chapter",
        "position": 10,
        "title": "Základy a riadenie toku",
        "summary": "Prvý program, hodnoty, podmienky, cykly a funkcie.",
        "content": {"lead": "Pythonový program je textový súbor vykonaný interpreterom. Premenné dostávajú typ z priradenej hodnoty, no názvy a kontrakty funkcií majú byť stále presné.", "sections": [{"title": "V tejto kapitole", "bullets": ["Výpis, vstup a čitateľné názvy.", "Čísla, text, None a pravdivosť hodnôt.", "Vetvy, iterovanie a malé funkcie."]}]},
    },
    {
        "key": "program",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 20,
        "title": "Prvý program, spustenie a odsadenie",
        "summary": "print, vstupný bod skriptu, návratový kód a bloky riadené odsadením.",
        "content": {"lead": "Python číta zdroj zhora nadol. Blok po if, for, def alebo class začína dvojbodkou a jeho hranicu určuje konzistentné odsadenie.", "sections": [{"title": "Spustenie", "paragraphs": ["Súbor main.py spustíš príkazom python3 main.py. Funkcia print premení hodnoty na text a zapíše ich na štandardný výstup.", "Podmienka if __name__ == '__main__': rozlíši priamo spustený skript od modulu importovaného iným súborom."], "bullets": ["Používaj štyri medzery, nie miešanie tabulátorov a medzier.", "Komentár začína znakom #.", "Funkcia sys.exit(kod) oznámi prostrediu výsledok, ak ho skript potrebuje." ]}, {"title": "Chyby odsadenia", "paragraphs": ["Nesprávne odsadenie nezmení iba vzhľad: interpreter ho odmietne alebo vykoná inú vetvu, než si zamýšľal."], "callout": "Neskúšaj opraviť IndentationError náhodným dopĺňaním medzier. Najprv si nájdi začiatok bloku a zarovnaj všetky jeho príkazy."}]},
    },
    {
        "key": "values",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 30,
        "title": "Hodnoty, mená a porovnanie",
        "summary": "int, float, bool, str, None, priradenie, rovnosť a identita.",
        "content": {"lead": "Premenná v Pythone je meno viazané na objekt. Priradenie obyčajne nekopíruje objekt; vytvorí alebo zmení väzbu mena.", "sections": [{"title": "Hodnoty", "paragraphs": ["int má ľubovoľnú presnosť, float je binárne desatinné číslo s obmedzenou presnosťou, str je nemenná Unicode postupnosť a None vyjadruje neprítomnosť hodnoty.", "Operátor == porovnáva hodnoty. Operátor is porovnáva identitu objektov a v bežnom kóde patrí predovšetkým ku kontrolám is None a is not None."], "bullets": ["0, prázdny text, prázdne kolekcie a None sú v podmienke nepravdivé.", "bool je samostatný typ s hodnotami True a False.", "Pri peniazoch a presných desatinných výpočtoch zváž decimal.Decimal."]}, {"title": "Konverzie", "paragraphs": ["int(text), float(text) a str(hodnota) môžu zlyhať alebo zmeniť význam hodnoty. Konverziu vstupu vždy oddeľ od vlastnej logiky a ošetri ValueError."], "callout": "Nedôveruj pravdivosti textu. bool('False') je True, pretože neprázdny reťazec je pravdivý."}]},
    },
    {
        "key": "flow",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 40,
        "title": "Podmienky, cykly a comprehensions",
        "summary": "if, match, for, while, enumerate, break, continue a deklaratívne skladanie kolekcií.",
        "content": {"lead": "Python najčastejšie iteruje priamo cez hodnoty, nie cez číselné indexy. Čitateľný for cyklus obyčajne lepšie vyjadruje zámer než ručne spravovaný while.", "sections": [{"title": "Vetvy a iterovanie", "paragraphs": ["if, elif a else vyberajú jednu cestu. match je vhodný, keď rozoberáš tvar alebo pomenované možnosti hodnoty.", "for item in collection prechádza prvky. enumerate(collection, start=1) pridá poradové číslo a zip spája viaceré rovnako dlhé iterovateľné hodnoty."], "bullets": ["break ukončí najbližší cyklus, continue preskočí jeho zvyšok.", "else pri cykle sa vykoná iba vtedy, keď cyklus neskončil cez break.", "range(stop) končí pred stop; range(start, stop, step) má tiež vylúčenú hornú hranicu."]}, {"title": "Comprehensions", "paragraphs": ["List, set a dict comprehension sú stručné pre jednoduchú transformáciu alebo filter. Ak sa výraz natiahne do viacerých rozhodnutí, obyčajný cyklus je zrozumiteľnejší."], "callout": "Nemeň kolekciu, po ktorej práve iteruješ. Ak potrebuješ filtrovať, vytvor novú kolekciu alebo iteruj cez kópiu."}]},
    },
    {
        "key": "functions",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 50,
        "title": "Funkcie, parametre a rozsah mien",
        "summary": "def, návratová hodnota, pozičné a menované argumenty, *args, **kwargs a lokálny rozsah.",
        "content": {"lead": "Funkcia má vykonávať jeden súvisiaci krok a mať zrozumiteľný kontrakt. Argumenty sú väzby na objekty; funkcia môže meniť mutovateľný objekt, ktorý dostala.", "sections": [{"title": "Rozhranie", "paragraphs": ["Parametre môžu byť pozičné, menované, s predvolenou hodnotou alebo výhradne menované. *args zozbiera ďalšie pozičné argumenty do tuple a **kwargs ďalšie menované do dict.", "return vráti výsledok. Bez return, alebo pri return bez hodnoty, funkcia vráti None."], "bullets": ["Predvolenú hodnotu vytvor funkciou alebo None, ak by bola mutovateľná.", "Lokálne priradenie vytvára lokálne meno; global a nonlocal používaj iba pri jasnom dôvode.", "Docstring opisuje účel, parametre, výsledok a podmienky použitia." ]}, {"title": "Mutovateľný predvolený argument", "paragraphs": ["Zápis def add(item, items=[]): zdieľa jeden zoznam medzi volaniami. Bezpečný tvar je items=None a vytvorenie nového zoznamu vo vnútri funkcie."], "callout": "Typový zápis pomáha čitateľovi aj nástrojom, ale nepresadzuje ho samotný interpreter. Kontrakt funkcie musí stále overovať hranice vstupu."}]},
    },
    {
        "key": "data",
        "parent_key": "",
        "kind": "chapter",
        "position": 60,
        "title": "Dáta, text a objekty",
        "summary": "Kolekcie, mutovateľnosť, reťazce, vlastné typy a protokoly Pythonu.",
        "content": {"lead": "Väčšina Pythonu je práca s objektmi a ich protokolmi. Rozlišovanie medzi mutovateľným a nemenným objektom chráni pred nečakaným zdieľaním stavu.", "sections": [{"title": "V tejto kapitole", "bullets": ["list, tuple, dict a set.", "Unicode text, formátovanie a regulárne výrazy.", "triedy, dataclasses, iterátory a generátory."]}]},
    },
    {
        "key": "collections",
        "parent_key": "data",
        "kind": "lesson",
        "position": 70,
        "title": "list, tuple, dict a set",
        "summary": "Výber kolekcie podľa vlastníctva, poradia, jedinečnosti a spôsobu vyhľadávania.",
        "content": {"lead": "list je meniteľná usporiadaná postupnosť, tuple je nemenná postupnosť, dict mapuje kľúče na hodnoty a set uchováva jedinečné prvky bez sľubu poradia.", "sections": [{"title": "Správny nástroj", "paragraphs": ["Do dict zapisuj podľa stabilného kľúča a chýbajúci kľúč rieš cez in, get alebo vhodnú predvolenú hodnotu. set je užitočný na odstraňovanie duplicít a rýchle otázky členstva.", "Rozbaľovanie umožní zápis first, *middle, last = values, no počet výsledných hodnôt musí zodpovedať tvaru vstupu."], "bullets": ["list.append pridá jeden prvok, list.extend iterovateľné prvky.", "dict.items vracia dvojice kľúč, hodnota.", "sorted vytvorí novú postupnosť; list.sort mení pôvodný zoznam."]}, {"title": "Kopírovanie", "paragraphs": ["list(values), values.copy() a dict.copy() sú plytké kópie. Vnorené meniteľné objekty sa ďalej zdieľajú; pre hlbokú kópiu najprv zvažuj, či návrh nevie zdieľanie odstrániť."], "callout": "Nespoliehaj sa na náhodné poradie setu ako na časť rozhrania. Keď je poradie výstupu dôležité, explicitne ho usporiadaj."}]},
    },
    {
        "key": "text",
        "parent_key": "data",
        "kind": "lesson",
        "position": 80,
        "title": "Text, Unicode a formátovanie",
        "summary": "str, f-string, delenie a spájanie textu, encoding, regulárne výrazy a bezpečné parsovanie.",
        "content": {"lead": "str v Pythone obsahuje Unicode znaky. Pri súboroch a sieti sa z neho stávajú bytes až pri jasne zvolenom kódovaní, často UTF-8.", "sections": [{"title": "Formátovanie", "paragraphs": ["f-string je čitateľný pre bežné formátovanie: f'{name}: {score:.2f}'. Na spájanie mnohých krátkych častí použij ''.join(parts), nie opakované + v cykle.", "Metódy split, strip, partition a replace riešia mnoho úloh bez regulárnych výrazov."], "bullets": ["len(text) počíta kódové body, nie vždy používateľom vnímané znaky.", "bytes a str sa nemiešajú bez explicitného encode alebo decode.", "Pri open(..., encoding='utf-8') je kódovanie viditeľné v rozhraní."]}, {"title": "Regulárne výrazy", "paragraphs": ["Modul re je vhodný pre rozpoznanie tvaru textu. Pre validáciu používaj celý zápis cez fullmatch a obmedzuj vstup skôr, než výraz pustíš na nedôveryhodné dáta."], "callout": "Regulárny výraz nie je univerzálny parser. Vnorené formáty, JSON, CSV alebo adresy URL čítaj špecializovanou knižnicou."}]},
    },
    {
        "key": "objects",
        "parent_key": "data",
        "kind": "lesson",
        "position": 90,
        "title": "Triedy, dataclasses a dátový model",
        "summary": "Atribúty, metódy, __init__, dataclass, vlastnosti a porovnanie objektov.",
        "content": {"lead": "Trieda je vhodná vtedy, keď dáta a operácie nad nimi vytvárajú jeden stabilný pojem. Pre jednoduché dátové nosiče znižuje dataclass množstvo opakovaného kódu.", "sections": [{"title": "Návrh typu", "paragraphs": ["__init__ vytvorí platný objekt a metódy udržiavajú jeho invarianty. self je prvý parameter metódy a označuje konkrétny objekt.", "@dataclass môže automaticky vytvoriť __init__, __repr__ a porovnanie. default_factory vytvorí samostatnú meniteľnú predvolenú hodnotu pre každý objekt."], "bullets": ["Atribút triedy je zdieľaný, atribút self patrí jednému objektu.", "@property patrí k rozhraniu, nie k skrývaniu triviálnych atribútov.", "Kompozícia býva jednoduchšia než dedenie, ak nepotrebuješ skutočný vzťah 'je typom'."]}, {"title": "Rovnosť a hash", "paragraphs": ["Objekt použitý ako kľúč dict alebo prvok setu musí mať stabilný hash. Meniteľné dátové objekty preto zvyčajne nie sú hashovateľné."], "callout": "Nevytváraj triedu iba preto, aby mala pár statických funkcií. Modulové funkcie a jednoduché dátové typy sú často priamočiarejšie."}]},
    },
    {
        "key": "iteration",
        "parent_key": "data",
        "kind": "lesson",
        "position": 100,
        "title": "Iterátory, generátory a context managers",
        "summary": "Iterator protocol, yield, lazy spracovanie a bezpečné uvoľňovanie zdrojov cez with.",
        "content": {"lead": "Iterátor vydáva hodnoty postupne. Generátor s yield ich vytvára len vtedy, keď ich príjemca žiada, takže spracuje aj veľký tok bez načítania celého do pamäte.", "sections": [{"title": "Lazy postupnosť", "paragraphs": ["Generator expression (transform(value) for value in values) je lenivý. Keď ho prejdeš raz, nemusí byť možné ho prejsť znova; ak potrebuješ opakovanie, ulož výsledok alebo vytvor nový generátor.", "iter(obj) získa iterátor a next(iterator) vyžiada hodnotu; koniec signalizuje StopIteration, ktorú for spracuje za teba."], "bullets": ["yield pozastaví funkciu a pri ďalšom kroku pokračuje.", "itertools ponúka bezpečné nástroje na skladanie iterácií.", "Pre veľký súbor iteruj priamo cez riadky súborového objektu."]}, {"title": "with", "paragraphs": ["with open(path, encoding='utf-8') as file: zaistí, že sa súbor zatvorí aj pri chybe. Rovnaký princíp platí pre zámky, transakcie a vlastné context managery."], "callout": "Neodkladaj zatvorenie súboru na garbage collector. Zdroj má byť uzavretý v tom istom mieste, kde je jeho životnosť zrejmá."}]},
    },
    {
        "key": "projects",
        "parent_key": "",
        "kind": "chapter",
        "position": 110,
        "title": "Projekt, balíky a spoľahlivosť",
        "summary": "Moduly, prostredia, chyby, testy, typy, vstup a asynchrónne rozhrania.",
        "content": {"lead": "Dobrý Pythonový projekt má malé moduly, jasné závislosti a opakovateľné prostredie. Rovnako dôležité je vedieť, ako sa program správa pri neplatnom vstupe a zlyhaní zdroja.", "sections": [{"title": "V tejto kapitole", "bullets": ["import, package, venv a pyproject.toml.", "Výnimky, súbory, cesty a serializácia.", "Testy, typové anotácie, logging a asyncio."]}]},
    },
    {
        "key": "modules",
        "parent_key": "projects",
        "kind": "lesson",
        "position": 120,
        "title": "Moduly, balíky a virtuálne prostredie",
        "summary": "import, verejné rozhranie modulu, package, venv, pip a pyproject.toml.",
        "content": {"lead": "Modul je súbor Pythonu, balík je pomenovaný priestor modulov. Import spustí kód modulu pri prvom načítaní, preto majú vedľajšie účinky pri importe zostať minimálne.", "sections": [{"title": "Rozhranie projektu", "paragraphs": ["Importuj konkrétne mená alebo moduly explicitne: import statistics alebo from package.module import function. Cyklus importov je signál, že zodpovednosti modulov treba rozdeliť inak.", "Vytvor venv pre každý projekt a závislosti zapisuj do pyproject.toml; verzie nenechávaj iba v pamäti alebo v globálnej inštalácii."], "bullets": ["python3 -m venv .venv vytvorí prostredie.", "python3 -m pip ... zaručí, že pip patrí k zvolenému interpreteru.", "__all__ je pomocná dohoda o verejných menách, nie bezpečnostná hranica."]}, {"title": "Spustiteľný modul", "paragraphs": ["python3 -m package.module spúšťa modul v kontexte balíka a predchádza problémom s relatívnymi importmi."], "callout": "Nenazývaj vlastný súbor json.py, typing.py alebo random.py. Zatienil by štandardný modul a chyba sa môže prejaviť až na inom počítači."}]},
    },
    {
        "key": "errors_io",
        "parent_key": "projects",
        "kind": "lesson",
        "position": 130,
        "title": "Výnimky, súbory, cesty a JSON",
        "summary": "try/except/else/finally, pathlib, with, validácia vstupu a bezpečná serializácia.",
        "content": {"lead": "Výnimka znamená, že normálny postup nemožno dokončiť. Zachytávaj iba chyby, ktoré vieš na danej hranici zmysluplne spracovať alebo obohatiť o kontext.", "sections": [{"title": "Hranica chyby", "paragraphs": ["try obsahuje malý rizikový krok, except konkrétny typ chyby, else úspešnú cestu a finally nevyhnutné upratanie. Nezachytávaj holé Exception, ak nemáš naozaj poslednú hranicu aplikácie.", "pathlib.Path zjednocuje cesty a with open(...) drží otvorený súbor iba počas potrebného bloku."], "bullets": ["ValueError často znamená zlý tvar vstupu.", "OSError pokrýva chyby pri práci so systémovým zdrojom.", "json.load a json.dumps pracujú s jednoduchými typmi; obsah stále validuj podľa vlastného modelu."]}, {"title": "Bezpečná deserializácia", "paragraphs": ["pickle nenačítavaj z nedôveryhodného zdroja: jeho obsah môže pri čítaní vykonať kód. JSON je bezpečnejší formát dát, ale neznamená automaticky platné dáta pre tvoju aplikáciu."], "callout": "Chyba má niesť použiteľný kontext, nie tajné údaje. Do používateľského výpisu nepatria heslá, tokeny ani úplné interné cesty."}]},
    },
    {
        "key": "quality",
        "parent_key": "projects",
        "kind": "lesson",
        "position": 140,
        "title": "Testy, typy, logging a ladenie",
        "summary": "unittest alebo pytest, typové anotácie, assert, logging, debugger a meranie výkonu.",
        "content": {"lead": "Test overuje pozorovateľný kontrakt, nie vnútornú implementáciu. Typové anotácie a formátovanie znižujú počet omylov skôr, než program spustíš.", "sections": [{"title": "Malá kvalitná slučka", "paragraphs": ["Napíš funkciu s čistým vstupom a výstupom, otestuj bežný aj hraničný prípad, spusti formátovač a statickú kontrolu a až potom ju pripoj k súboru alebo sieti.", "assert patrí do testov a interných invariantov, nie na validáciu externého vstupu; môže byť vypnutý režimom -O."], "bullets": ["unittest je v štandardnej knižnici, pytest je bežný externý nástroj.", "typing označí zmluvu, mypy alebo pyright ju vedia kontrolovať.", "logging má úrovne; print nepatrí do dlhodobej diagnostiky služby."]}, {"title": "Ladenie a výkon", "paragraphs": ["Reprodukuj najmenší príklad, prečítaj traceback od konca a skontroluj typy a hodnoty na hranici zlyhania. Až meranie cez timeit alebo profiler rozhodne, či je konkrétna optimalizácia potrebná."], "callout": "Neopravuj výkon naslepo. Najprv pomenuj vstup, očakávanú zložitosť a miesto, ktoré meranie skutočne označilo."}]},
    },
    {
        "key": "async",
        "parent_key": "projects",
        "kind": "lesson",
        "position": 150,
        "title": "asyncio, úlohy a rušenie",
        "summary": "Coroutine, await, Task, súbežné I/O, timeouts a korektné ukončenie práce.",
        "content": {"lead": "asyncio je vhodné pre množstvo čakajúcich I/O operácií. Nie je to náhrada za procesy pri výpočtovo náročnej práci; dlhý výpočet bez await blokuje event loop.", "sections": [{"title": "Model vykonávania", "paragraphs": ["async def vytvorí coroutine. await odovzdá riadenie loopu, kým výsledok nie je pripravený. asyncio.create_task spustí samostatnú úlohu, ktorú však treba neskôr počkať alebo zrušiť.", "Použi timeout a premysli rušenie: CancelledError má prejsť cez cleanup, nie byť potichu prehltnutý."], "bullets": ["awaitaj všetky vytvorené tasks.", "Pre blokujúcu funkciu použi vhodný executor alebo ju presuň mimo event loop.", "Súbežnosť nemení potrebu validovať vstup a uzatvárať zdroje."]}, {"title": "Hranice rozhrania", "paragraphs": ["Asynchrónna funkcia má jasne dokumentovať, ktoré výnimky vyhadzuje, kedy možno jej prácu zrušiť a kto vlastní otvorené spojenie alebo stream."], "callout": "Nespúšťaj nový event loop v knižničnej funkcii. Knižnica má vracať coroutine; rozhodnutie o asyncio.run patrí vstupnému bodu aplikácie."}]},
    },
]

PYTHON_LEARNING_GOALS = {
    "program": ("Spustiť skript Pythonu a rozpoznať hranice bloku podľa odsadenia.", "Oddeliť importovateľný kód od vstupného bodu skriptu."),
    "values": ("Rozlíšiť porovnanie hodnoty od identity objektu.", "Bezpečne premeniť a overiť hodnotu pochádzajúcu z textu."),
    "flow": ("Zvoliť iterovanie cez hodnoty, enumerate alebo range podľa úlohy.", "Použiť comprehension len tam, kde zostáva čitateľná."),
    "functions": ("Navrhnúť funkciu s malým, overiteľným kontraktom.", "Vyhnúť sa zdieľanému mutovateľnému predvolenému argumentu."),
    "collections": ("Vybrať kolekciu podľa poradia, jedinečnosti a vyhľadávania.", "Rozpoznať plytkú kópiu a zdieľaný vnorený stav."),
    "text": ("Pracovať s textom a bytes s explicitným kódovaním.", "Vybrať jednoduché textové operácie pred zbytočným regulárnym výrazom."),
    "objects": ("Navrhnúť malý dátový typ s jasnými invariantmi.", "Použiť dataclass a default_factory bez zdieľania mutovateľných hodnôt."),
    "iteration": ("Vysvetliť rozdiel medzi iterovateľnou hodnotou, iterátorom a generátorom.", "Použiť with na jasnú životnosť súboru alebo iného zdroja."),
    "modules": ("Rozdeliť projekt na moduly s malým verejným rozhraním.", "Vytvoriť izolované virtuálne prostredie a pomenovať závislosti."),
    "errors_io": ("Zachytiť konkrétnu chybu na správnej hranici programu.", "Čítať textové dáta cez pathlib, with a explicitné kódovanie."),
    "quality": ("Napísať hraničný test pre čistú funkciu.", "Vysvetliť, čo prinesú typové anotácie, logging a profiler."),
    "async": ("Použiť await a Task bez blokovania event loopu.", "Navrhnúť timeout a bezpečné rušenie asynchrónnej práce."),
}

PYTHON_VISUALIZATION_IDS = {
    "values": ("python-object-references",),
    "iteration": ("python-generator-flow",),
}

PYTHON_EXAMPLES = [
    {"key": "first-program", "page_key": "program", "position": 10, "title": "Pozdrav ako spustiteľný skript", "description": "Funkcia main drží prácu pokope a blok __main__ ju spúšťa iba pri priamom štarte súboru.", "source": "def main() -> None:\n    name = 'Ada'\n    print(f'Ahoj, {name}!')\n\n\nif __name__ == '__main__':\n    main()\n", "stdin": "", "standard": "python3"},
    {"key": "safe-number", "page_key": "values", "position": 10, "title": "Overenie čísla z textu", "description": "Konverzia vstupu je samostatná funkcia, ktorá rozlíši neplatný tvar od platného čísla.", "source": "def parse_count(text: str) -> int | None:\n    try:\n        value = int(text)\n    except ValueError:\n        return None\n    return value if value >= 0 else None\n\n\nprint(parse_count('12'))\nprint(parse_count('nie'))\n", "stdin": "", "standard": "python3"},
    {"key": "scores", "page_key": "flow", "position": 10, "title": "Čítanie dvojíc cez enumerate", "description": "enumerate pridá poradové číslo bez ručného počítadla.", "source": "scores = [7, 10, 8]\n\nfor place, score in enumerate(scores, start=1):\n    print(f'{place}. miesto: {score}')\n", "stdin": "", "standard": "python3"},
    {"key": "default-argument", "page_key": "functions", "position": 10, "title": "Bezpečný predvolený zoznam", "description": "None odlíši chýbajúci argument od nového prázdneho zoznamu pre konkrétne volanie.", "source": "def append_name(name: str, names: list[str] | None = None) -> list[str]:\n    result = [] if names is None else names\n    result.append(name)\n    return result\n\n\nprint(append_name('Ada'))\nprint(append_name('Linus'))\n", "stdin": "", "standard": "python3"},
    {"key": "word-count", "page_key": "collections", "position": 10, "title": "Frekvencia slov v dict", "description": "get poskytne bezpečnú predvolenú hodnotu, keď kľúč ešte neexistuje.", "source": "words = ['modul', 'test', 'modul', 'typ']\ncounts: dict[str, int] = {}\n\nfor word in words:\n    counts[word] = counts.get(word, 0) + 1\n\nfor word in sorted(counts):\n    print(f'{word}: {counts[word]}')\n", "stdin": "", "standard": "python3"},
    {"key": "person", "page_key": "objects", "position": 10, "title": "Dátový objekt bez zdieľaného zoznamu", "description": "default_factory pripraví pre každú osobu vlastný zoznam značiek.", "source": "from dataclasses import dataclass, field\n\n\n@dataclass\nclass Person:\n    name: str\n    tags: list[str] = field(default_factory=list)\n\n\nada = Person('Ada')\nada.tags.append('matematika')\nprint(ada)\n", "stdin": "", "standard": "python3"},
    {"key": "json-file", "page_key": "errors_io", "position": 10, "title": "JSON s overením tvaru", "description": "JSON je najprv všeobecná hodnota; až potom sa overí konkrétny model aplikácie.", "source": "import json\n\nraw = '{\\\"name\\\": \\\"Ada\\\", \\\"score\\\": 12}'\ndata = json.loads(raw)\n\nif not isinstance(data, dict) or not isinstance(data.get('name'), str):\n    raise ValueError('Očakávam objekt s textovým menom.')\n\nprint(data['name'])\n", "stdin": "", "standard": "python3"},
    {"key": "async-tasks", "page_key": "async", "position": 10, "title": "Dve čakajúce úlohy", "description": "Gather čaká na obe korutiny a výsledky zachová v poradí argumentov.", "source": "import asyncio\n\n\nasync def label(name: str, delay: float) -> str:\n    await asyncio.sleep(delay)\n    return name\n\n\nasync def main() -> None:\n    first, second = await asyncio.gather(label('prvá', 0.01), label('druhá', 0.01))\n    print(first, second)\n\n\nasyncio.run(main())\n", "stdin": "", "standard": "python3"},
]


JAVASCRIPT_LANGUAGE = {
    "code": "javascript",
    "title": "JavaScript",
    "summary": "Praktická učebnica ECMAScriptu: hodnoty, objekty, moduly, event loop a bezpečné rozhrania.",
}

JAVASCRIPT_PAGES = [
    {
        "key": "overview",
        "parent_key": "",
        "kind": "overview",
        "position": 0,
        "title": "JavaScript: učebnica a referencia",
        "summary": "Moderný JavaScript pre Node aj prehliadač, s jasným rozlíšením ich rozhraní.",
        "content": {"lead": "JavaScript je jazyk ECMAScriptu, ktorý potrebuje runtime: napríklad prehliadač alebo Node.js. Základ jazyka je spoločný, no súbory, DOM a sieťové rozhrania patria konkrétnemu prostrediu.", "sections": [{"title": "Ako kurz používať", "paragraphs": ["Príklady bežia v Node.js, preto nepredpokladajú DOM ani objekt window. Pri každom API si kontroluj, či patrí do štandardu ECMAScriptu, webových API alebo Node.", "Dynamický typový systém neznamená, že kontrakty netreba. Vstupy overuj pri hraniciach a vnútri programu udržiavaj jednoduché, čitateľné tvary dát."], "bullets": ["Používaj moderný ECMAScript a let alebo const namiesto var.", "Moduly, nie globálne premenné, sú základnou jednotkou organizácie.", "Asynchrónnosť vysvetľuj cez event loop, nie len cez slovo await."]}, {"title": "Bezpečná práca", "paragraphs": ["Nedôveryhodný text nepatrí priamo do HTML, príkazu shellu ani dynamicky vytváraného kódu. Správne API na výstup je bezpečnejšie než ručné skladanie reťazca."], "callout": "eval, Function a vkladanie neovereného textu cez innerHTML nie sú pohodlné skratky. Menia dáta na vykonateľný alebo interpretovaný obsah."}]},
    },
    {
        "key": "foundations",
        "parent_key": "",
        "kind": "chapter",
        "position": 10,
        "title": "Hodnoty, mená a funkcie",
        "summary": "Spustenie programu, typy, scope, riadenie toku, funkcie a closures.",
        "content": {"lead": "JavaScript má málo primitívnych typov, no mnoho presných pravidiel okolo konverzií, identity a rozsahu premenných. Táto kapitola buduje návyky, ktoré predídu väčšine nenápadných chýb.", "sections": [{"title": "V tejto kapitole", "bullets": ["let, const, scope a temporal dead zone.", "Čísla, text, null, undefined, rovnosť a pravdivosť.", "Funkcie, callbacky, closures a riadenie toku."]}]},
    },
    {
        "key": "program",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 20,
        "title": "Prvý program a režim runtime",
        "summary": "Node.js, console, návratový kód, strict mode a odlišnosť od prehliadača.",
        "content": {"lead": "Súbor main.js v tomto prostredí kontroluje a spúšťa Node.js. console.log zapisuje diagnostický výstup; program môže nastaviť process.exitCode bez okamžitého ukončenia procesu.", "sections": [{"title": "Runtime nie je jazyk", "paragraphs": ["ECMAScript definuje syntax a základné objekty. Node pridáva process, súbory a moduly, prehliadač pridáva document, DOM a webové API.", "Moderné moduly sú implicitne strict. V staršom skripte môžeš explicitne zapísať 'use strict'; aby sa vyhli tichým globálnym menám a niektorým historickým pravidlám."], "bullets": ["Spustenie: node main.js.", "console.error patrí k diagnostike, nie k bežnému dátovému formátu programu.", "process.exitCode = 1 oznámi chybu až po dokončení event loopu."]}, {"title": "Čitateľný začiatok", "paragraphs": ["Názov súboru a funkcie majú vyjadriť ich úlohu. Logiku vstupného bodu drž krátku a presuň ju do testovateľných funkcií."], "callout": "Nekopíruj kód určený pre prehliadač do Node bez overenia API. Referencia na document v Node nie je chyba JavaScriptu, ale zvoleného runtime."}]},
    },
    {
        "key": "values",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 30,
        "title": "Hodnoty, konverzie a porovnanie",
        "summary": "number, bigint, string, boolean, symbol, undefined, null, NaN, === a Object.is.",
        "content": {"lead": "JavaScript rozlišuje primitívne hodnoty a objekty. number pokrýva celé aj desatinné čísla v IEEE 754, preto nie všetky desatinné zlomky reprezentuje presne.", "sections": [{"title": "Rovnosť", "paragraphs": ["Používaj === a !==: neprevádzajú typy pred porovnaním. Operátory == a != majú historické pravidlá implicitnej konverzie, ktoré zbytočne zhoršujú čitateľnosť.", "NaN nie je rovné ani samo sebe; Number.isNaN(value) je presná kontrola. Object.is má špecifické použitie, napríklad rozlíši -0 a 0."], "bullets": ["typeof null je historicky 'object'; null preto kontroluj priamo.", "Number.isFinite overí konečné číslo bez konverzie textu.", "BigInt a number nemiešaj v aritmetike bez vedomého prevodu."]}, {"title": "Pravdivosť", "paragraphs": ["false, 0, -0, 0n, prázdny text, null, undefined a NaN sú nepravdivé. Ak však rozlišuješ neprítomnosť hodnoty od nuly alebo prázdneho textu, použi explicitnú podmienku alebo ?? namiesto ||."], "callout": "Zápis input || default nahradí aj platnú nulu. Operátor input ?? default nahrádza iba null a undefined."}]},
    },
    {
        "key": "scope",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 40,
        "title": "let, const, scope a closures",
        "summary": "Blokový rozsah, hoisting, nemenná väzba a funkcia, ktorá si nesie okolité mená.",
        "content": {"lead": "let a const majú blokový rozsah. const chráni väzbu mena, nie vnútro objektu: obsah const array možno stále meniť, pokiaľ ho nezmrazíš alebo nenavrhneš nemenný tok dát.", "sections": [{"title": "Rozsah a hoisting", "paragraphs": ["Deklarácia je v bloku známa od svojho miesta až po koniec bloku. Pred deklaráciou sa nachádza temporal dead zone, preto sa na let a const nedá bezpečne odkazovať skôr.", "var má funkčný rozsah a historické hoisting správanie. V novom kóde ho nepotrebuješ."], "bullets": ["Preferuj const, keď meno nebudeš znovu priraďovať.", "let použi pre meniteľný lokálny stav.", "Globálny stav skrýva závislosti; odovzdaj ho radšej ako parameter alebo vytvor modul."]}, {"title": "Closure", "paragraphs": ["Funkcia si pamätá lexikálne okolité mená aj po návrate vonkajšej funkcie. Je to užitočné pre malé továrne funkcií, no veľké zachytené objekty môžu zbytočne držať pamäť."], "callout": "V cykle používaj let pre premennú iterácie. Callback potom zachytí hodnotu konkrétneho kroku, nie jednu zdieľanú väzbu z var."}]},
    },
    {
        "key": "functions",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 50,
        "title": "Funkcie, callbacky a this",
        "summary": "Parametre, rest, destructuring, callback, arrow function a pravidlá this.",
        "content": {"lead": "Funkcie sú hodnoty: môžeš ich uložiť, odovzdať a vrátiť. Kontrakt funkcie má hovoriť, ktoré hodnoty prijíma, čo vracia a či mení objekt, ktorý dostala.", "sections": [{"title": "Parametre", "paragraphs": ["Predvolené parametre, rest parameter ...items a destructuring znižujú opakovanie, keď zostávajú čitateľné. Argument, ktorý funkcia nedostane, má hodnotu undefined.", "Callback má mať presne popísané argumenty, návrat a okamih volania. Keď môže byť asynchrónny, Promise je zvyčajne jasnejší kontrakt než vlastný callbackový protokol."], "bullets": ["Funkcia declaration sa hoistuje, function expression nie rovnakým spôsobom.", "Arrow function nemá vlastné this ani arguments.", "Pre nejasný this použij explicitný parameter alebo metódu volaj cez objekt."]}, {"title": "Metódy a this", "paragraphs": ["Hodnota this závisí od spôsobu volania obyčajnej funkcie. Arrow function ju lexikálne preberá z okolitého kódu, preto nie je univerzálnou náhradou metódy objektu."], "callout": "Nestrácaj this odovzdaním metódy ako holého callbacku. Buď ju zabaľ do funkcie, alebo vedome použi bind."}]},
    },
    {
        "key": "data",
        "parent_key": "",
        "kind": "chapter",
        "position": 60,
        "title": "Kolekcie, objekty a text",
        "summary": "Array, Map, Set, obyčajné objekty, prototypy, triedy a formáty dát.",
        "content": {"lead": "Objekt v JavaScripte je súbor vlastností s prototypom. Pre konkrétnu úlohu vyber dátový tvar podľa poradia, kľúčov, identity a potreby transformácie, nie len podľa zvyku.", "sections": [{"title": "V tejto kapitole", "bullets": ["Array a jeho transformačné metódy.", "Object, Map, Set a bezpečná práca s kľúčmi.", "Prototypy, class, JSON a text."]}]},
    },
    {
        "key": "collections",
        "parent_key": "data",
        "kind": "lesson",
        "position": 70,
        "title": "Array, Map, Set a Object",
        "summary": "Poradie, transformácia, vlastné kľúče, jedinečné hodnoty a bezpečný prístup k vlastnostiam.",
        "content": {"lead": "Array je usporiadaná kolekcia, Map mapuje ľubovoľné kľúče na hodnoty a Set drží jedinečné hodnoty. Obyčajný objekt je vhodný pre pomenovaný záznam, nie automaticky pre každú mapu.", "sections": [{"title": "Transformácie", "paragraphs": ["map vytvorí rovnaký počet transformovaných hodnôt, filter vyberie podmnožinu a reduce skladá hodnoty do jedného výsledku. Pri reduce vždy zadaj počiatočnú hodnotu, ak má byť prázdna kolekcia platným vstupom.", "for...of iteruje hodnoty iterovateľnej kolekcie. for...in prechádza mená vlastností vrátane dedičných a nepatrí na polia."], "bullets": ["Array.isArray(value) bezpečne rozlíši pole.", "Object.hasOwn(object, key) overí vlastnú vlastnosť.", "Map.get môže vrátiť undefined aj pre existujúci kľúč; pri potrebe rozlíšenia použi has."]}, {"title": "Mutácia", "paragraphs": ["sort mení pôvodné pole a bez porovnávacej funkcie triedi ako text. Nové nemenné pole vytvoria napríklad toSorted, map, filter alebo spread [...values]."], "callout": "Objekt s nedôveryhodnými kľúčmi nevytváraj cez obyčajné priradenie bez premyslenia prototypu. Pre dátovú mapu často pomôže Map alebo Object.create(null)."}]},
    },
    {
        "key": "objects",
        "parent_key": "data",
        "kind": "lesson",
        "position": 80,
        "title": "Prototypy, triedy a vlastnosti",
        "summary": "Delegácia cez prototyp, class syntax, private fields, getters, setters a kompozícia.",
        "content": {"lead": "class je pohodlná syntax nad prototypmi. Dedenie rieš iba pri skutočnom vzťahu typu; kompozícia malých objektov sa často mení jednoduchšie a menej prekvapuje.", "sections": [{"title": "Dátový objekt", "paragraphs": ["Konztruktor vytvorí platný objekt, metódy chránia jeho invarianty a private field #name skryje implementačný detail pred bežným prístupom zvonka.", "Getter a setter majú mať zmysluplnú prácu, napríklad validáciu. Triviálny getter pre každý atribút nezvyšuje zapuzdrenie."], "bullets": ["Metóda na prototype sa zdieľa medzi inštanciami.", "Vlastnosť vytvorená v konštruktore patrí konkrétnej inštancii.", "Object.freeze je plytký a nie je náhradou návrhu nemenných dát."]}, {"title": "Rovnosť objektov", "paragraphs": ["Dva oddelene vytvorené objekty s rovnakými vlastnosťami nie sú ===. Pri potrebe hodnotového porovnania ho navrhni explicitne podľa domény."], "callout": "Nekopíruj objekt cez JSON stringify/parse ako všeobecné riešenie. Stratí undefined, prototypy, dátumy, Map, Set a môže zlyhať na cyklických údajoch."}]},
    },
    {
        "key": "text_data",
        "parent_key": "data",
        "kind": "lesson",
        "position": 90,
        "title": "Text, Unicode a JSON",
        "summary": "Template literals, String metódy, code points, JSON.parse, JSON.stringify a validácia dát.",
        "content": {"lead": "JavaScriptový string je postupnosť UTF-16 kódových jednotiek. Dĺžka textu a počet používateľom vnímaných znakov nemusia byť rovnaké, najmä pri emoji alebo kombinovaných znakoch.", "sections": [{"title": "Textové operácie", "paragraphs": ["Template literal s backtickmi je vhodný na čitateľné formátovanie. Pri skladaní zoznamu častí použij array a join, nie opakované priraďovanie v dlhom cykle.", "Intl poskytuje lokalizačné formátovanie čísel, času a porovnávania textu; nerieš ho ručným skladaním podľa jedného jazyka."], "bullets": ["Text je nemenný; metódy vracajú nový text.", "for...of nad stringom pracuje lepšie s code points než indexovanie.", "RegExp používaj až vtedy, keď bežné metódy textu nestačia."]}, {"title": "JSON", "paragraphs": ["JSON.parse zmení text na všeobecnú hodnotu. Po načítaní vždy over, že má očakávaný tvar a typy; JSON sám nepozná tvoj doménový model."], "callout": "Nikdy nenahrádzaj JSON.parse výrazom eval. JSON je dátový formát, nie JavaScriptový zdrojový kód."}]},
    },
    {
        "key": "modules",
        "parent_key": "",
        "kind": "chapter",
        "position": 100,
        "title": "Moduly, asynchrónnosť a rozhrania",
        "summary": "ES moduly, Node, webové API, Promise, event loop, testy a bezpečnosť.",
        "content": {"lead": "Praktický JavaScript má explicitné moduly, malé hranice zodpovednosti a vedome navrhnuté asynchrónne operácie. Táto kapitola prepája jazyk s runtime bez miešania ich pravidiel.", "sections": [{"title": "V tejto kapitole", "bullets": ["import, export, package.json a závislosti.", "Promise, microtasks, tasks, async/await a rušenie.", "Node a webové API, testy, XSS a výkon."]}]},
    },
    {
        "key": "es_modules",
        "parent_key": "modules",
        "kind": "lesson",
        "position": 110,
        "title": "ES moduly, Node a balíky",
        "summary": "export, import, package.json, lockfile, závislosti a rozdiel medzi ESM a CommonJS.",
        "content": {"lead": "ES modul deklaruje svoje závislosti cez import a verejné mená cez export. To dá runtime aj nástrojom možnosť kontrolovať graf závislostí bez globálneho priestoru mien.", "sections": [{"title": "Projektová hranica", "paragraphs": ["package.json opisuje projekt, skripty a závislosti. Lockfile uchováva konkrétny vyriešený strom závislostí, aby build nebol náhodne iný na inom počítači.", "Node podporuje ESM aj historický CommonJS. Nemiešaj ich bez jasného dôvodu; konkrétny režim nastav explicitne a drž sa ho v projekte."], "bullets": ["Preferuj pomenované exporty pre stabilné malé rozhrania.", "Cyklus importov často znamená zle rozdelenú zodpovednosť.", "Závislosť aktualizuj spolu s testami a bezpečnostným prehľadom."]}, {"title": "Vedľajšie účinky", "paragraphs": ["Importovaný modul môže vykonať kód, preto inicializáciu servera alebo prístup k prostrediu neschovávaj do náhodného importu. Funkcia main alebo jasný štartovací modul dáva programu viditeľný vstupný bod."], "callout": "Názov vlastného súboru node_modules.js alebo modul s globálnymi side effectmi môže zakryť chyby v resolveri. Udržuj importy deterministické a jednoduché."}]},
    },
    {
        "key": "async",
        "parent_key": "modules",
        "kind": "lesson",
        "position": 120,
        "title": "Event loop, Promise a async/await",
        "summary": "Call stack, microtask queue, task queue, Promise reťazce, paralelnosť a AbortSignal.",
        "content": {"lead": "JavaScript vykonáva bežný kód v jednom call stacku. Po jeho vyprázdnení runtime spracuje microtasks, napríklad reakcie Promise, a potom ďalšie tasks, napríklad timer alebo I/O udalosť.", "sections": [{"title": "Promise ako kontrakt", "paragraphs": ["Promise má stav pending, fulfilled alebo rejected. Každú asynchrónnu vetvu buď awaitni, vráť jej Promise, alebo ju vedome spracuj; potlačené rejection sú zdrojom neviditeľných chýb.", "await zjednoduší zápis, ale nemení paralelné operácie na sériové automaticky. Nezávislé promises najprv spusti a potom ich čakaj cez Promise.all."], "bullets": ["Promise.all zlyhá pri prvom rejection.", "Promise.allSettled dá výsledok každého kroku.", "timeout a rušenie modeluj cez AbortSignal, nie iba ignorovaním výsledku."]}, {"title": "Blokovanie", "paragraphs": ["Dlhý výpočet bez prerušenia blokuje event loop a prestane reagovať na I/O. Pri CPU úlohách zváž worker, samostatný proces alebo rozdelenie práce na malé kroky."], "callout": "async funkcia vždy vracia Promise. Zlyhanie vyhodené v async funkcii sa zmení na rejected Promise, preto ho zachyť tam, kde má program rozhodnúť o obnove alebo ukončení."}]},
    },
    {
        "key": "runtime_apis",
        "parent_key": "modules",
        "kind": "lesson",
        "position": 130,
        "title": "Webové a Node rozhrania",
        "summary": "fetch, DOM, Node fs, process, streams, vstup a bezpečné hranice runtime.",
        "content": {"lead": "Prehliadač a Node zdieľajú JavaScript, nie rovnaké API. Kód, ktorý pracuje s DOM, patrí do prehliadača; kód, ktorý číta lokálny súbor cez fs, patrí do Node alebo iného serverového runtime.", "sections": [{"title": "Vstup a výstup", "paragraphs": ["V Node čítaj text cez explicitný encoding a validuj ho pred použitím. Stream spracuj postupne, keď vstup môže byť veľký, namiesto načítania všetkého do pamäte.", "fetch je asynchrónny v oboch moderných prostrediach, ale úspešné splnenie Promise neznamená HTTP 2xx. Over response.ok a obsah odpovede."], "bullets": ["DOM text zapisuj cez textContent, ak nepotrebuješ HTML.", "Cesty skladaj API runtime, nie ručným lepením oddeľovačov.", "Nepúšťaj vstup do shellu ani do dynamického importu bez návrhu povolených možností."]}, {"title": "Hranice údajov", "paragraphs": ["Dáta od siete, formulára, súboru alebo environment premennej majú prejsť validáciou presne raz na hranici. Vnútorné funkcie potom môžu pracovať s už overeným modelom."], "callout": "CORS je pravidlo prehliadača, nie prístupová kontrola servera. Oprávnenie musí server vynucovať nezávisle od hlavičiek klienta."}]},
    },
    {
        "key": "quality",
        "parent_key": "modules",
        "kind": "lesson",
        "position": 140,
        "title": "Testy, ladenie, bezpečnosť a výkon",
        "summary": "node:test, assert, debugger, linting, XSS, závislosti, memory leaks a profilovanie.",
        "content": {"lead": "Kvalita JavaScriptu vzniká z malých testovateľných funkcií, explicitných hraníc dát a nástrojov, ktoré odhalia problém skôr než produkčný používateľ.", "sections": [{"title": "Overenie správania", "paragraphs": ["Testuj verejný kontrakt: bežný vstup, hranice, chyby a asynchrónne zlyhanie. Node má node:test a assert; zvyšok projektu môže použiť vybraný test runner, ale nerozmnožuj nástroje bez prínosu.", "Debugger, source maps a profiler používaj podľa skutočného merania. Neoptimalizuj hot path, ktorý ešte nikto nezmeral."], "bullets": ["Linting zachytí nejasné a nebezpečné tvary skôr než runtime.", "Závislosti pravidelne aktualizuj a minimalizuj ich počet.", "Odober event listenery, timery a referencie, keď skončí životnosť komponentu."]}, {"title": "Bezpečnostný model", "paragraphs": ["Pred vložením do HTML používaj bezpečné DOM API alebo kontextovo správne escaping. Prístupové údaje, tokeny a tajomstvá nepatria do klientského bundle ani do chybovej odpovede."], "callout": "Bezpečnostná kontrola iba v používateľskom rozhraní nie je kontrola. Server musí autorizovať každú citlivú operáciu."}]},
    },
]

JAVASCRIPT_LEARNING_GOALS = {
    "program": ("Rozlíšiť ECMAScript od API konkrétneho runtime.", "Navrhnúť krátky a jasný vstupný bod programu."),
    "values": ("Použiť presné porovnanie a rozlíšiť nullish hodnotu od inej nepravdivej hodnoty.", "Vysvetliť hranice typu number a význam NaN."),
    "scope": ("Vybrať const alebo let podľa meniteľnosti väzby.", "Vysvetliť closure a vyhnúť sa zdieľanej väzbe z var v cykle."),
    "functions": ("Navrhnúť callback s jasným kontraktom.", "Predísť strate this pri odovzdaní metódy."),
    "collections": ("Vybrať Array, Map, Set alebo Object podľa úlohy.", "Rozlíšiť transformáciu od mutácie pôvodnej kolekcie."),
    "objects": ("Vysvetliť delegáciu cez prototyp a class syntax.", "Navrhnúť objekt s malým verejným rozhraním a invariantmi."),
    "text_data": ("Pracovať s textom bez chybných predpokladov o Unicode dĺžke.", "Validovať tvar dát po JSON.parse."),
    "es_modules": ("Rozdeliť projekt na moduly s explicitným verejným rozhraním.", "Vysvetliť úlohu package.json a lockfile pri opakovateľnom builde."),
    "async": ("Vysvetliť poradie call stacku, microtasks a tasks.", "Spustiť nezávislé asynchrónne operácie paralelne a ošetriť ich zlyhanie."),
    "runtime_apis": ("Rozlíšiť webové a Node API pred použitím.", "Overiť nedôveryhodné dáta na hranici runtime."),
    "quality": ("Napísať test pre bežný aj chybový priebeh funkcie.", "Pomenovať hlavné riziká XSS, závislostí a neodstránených zdrojov."),
}

JAVASCRIPT_VISUALIZATION_IDS = {
    "scope": ("js-scope-closures",),
    "async": ("js-event-loop",),
}

JAVASCRIPT_EXAMPLES = [
    {"key": "first-program", "page_key": "program", "position": 10, "title": "Jasný vstupný bod Node programu", "description": "Funkcia main oddelí logiku od štartu skriptu a návratový kód sa nastaví bez predčasného ukončenia.", "source": "function main() {\n  const name = 'Ada';\n  console.log(`Ahoj, ${name}!`);\n}\n\nmain();\n", "stdin": "", "standard": "javascript"},
    {"key": "nullish-default", "page_key": "values", "position": 10, "title": "Nula nie je chýbajúca hodnota", "description": "Operátor ?? zachová platnú nulu a nahradí iba null alebo undefined.", "source": "const suppliedLimit = 0;\nconst limit = suppliedLimit ?? 10;\n\nconsole.log(limit);\n", "stdin": "", "standard": "javascript"},
    {"key": "counter-closure", "page_key": "scope", "position": 10, "title": "Počítadlo cez closure", "description": "Vnútorná funkcia si pamätá vlastný lokálny stav bez globálnej premennej.", "source": "function createCounter() {\n  let value = 0;\n  return () => {\n    value += 1;\n    return value;\n  };\n}\n\nconst next = createCounter();\nconsole.log(next(), next());\n", "stdin": "", "standard": "javascript"},
    {"key": "group-scores", "page_key": "collections", "position": 10, "title": "Súčet podľa pomenovaného kľúča", "description": "Map drží dáta podľa kľúča bez miešania s vlastnosťami obyčajného objektu.", "source": "const scores = [['Ada', 4], ['Linus', 3], ['Ada', 5]];\nconst totals = new Map();\n\nfor (const [name, score] of scores) {\n  totals.set(name, (totals.get(name) ?? 0) + score);\n}\n\nfor (const [name, total] of totals) {\n  console.log(`${name}: ${total}`);\n}\n", "stdin": "", "standard": "javascript"},
    {"key": "temperature", "page_key": "objects", "position": 10, "title": "Trieda s overovaním invariantov", "description": "Setter chráni stav objektu pred nečíselnou hodnotou.", "source": "class Temperature {\n  #celsius;\n\n  constructor(celsius) {\n    this.celsius = celsius;\n  }\n\n  set celsius(value) {\n    if (!Number.isFinite(value)) throw new TypeError('Očakávam konečné číslo.');\n    this.#celsius = value;\n  }\n\n  get fahrenheit() {\n    return this.#celsius * 9 / 5 + 32;\n  }\n}\n\nconsole.log(new Temperature(20).fahrenheit);\n", "stdin": "", "standard": "javascript"},
    {"key": "safe-json", "page_key": "text_data", "position": 10, "title": "JSON s kontrolou tvaru", "description": "Po parse sa overí, že program dostal objekt s textovým menom.", "source": "const value = JSON.parse('{\\\"name\\\":\\\"Ada\\\",\\\"score\\\":12}');\n\nif (value === null || typeof value !== 'object' || typeof value.name !== 'string') {\n  throw new TypeError('Neplatný záznam.');\n}\n\nconsole.log(value.name);\n", "stdin": "", "standard": "javascript"},
    {"key": "parallel-promises", "page_key": "async", "position": 10, "title": "Dve nezávislé asynchrónne úlohy", "description": "Obe promises sa spustia pred await, takže sa na ne čaká paralelne.", "source": "function later(value) {\n  return new Promise((resolve) => setTimeout(() => resolve(value), 10));\n}\n\nasync function main() {\n  const first = later('prvá');\n  const second = later('druhá');\n  console.log((await Promise.all([first, second])).join(', '));\n}\n\nvoid main();\n", "stdin": "", "standard": "javascript"},
    {"key": "node-test", "page_key": "quality", "position": 10, "title": "Malý test cez node:test", "description": "Čistá funkcia sa overí pre bežný aj hraničný vstup.", "source": "const assert = require('node:assert/strict');\n\nfunction maximum(left, right) {\n  return left > right ? left : right;\n}\n\nassert.equal(maximum(2, 3), 3);\nassert.equal(maximum(-2, -2), -2);\nconsole.log('Testy prešli.');\n", "stdin": "", "standard": "javascript"},
]


CPP_LANGUAGE = {
    "code": "cpp",
    "title": "C++",
    "summary": "Praktická učebnica moderného C++: hodnotová sémantika, RAII, štandardná knižnica a bezpečné abstrahovanie.",
}

CPP_PAGES = [
    {
        "key": "overview",
        "parent_key": "",
        "kind": "overview",
        "position": 0,
        "title": "C++: učebnica a referencia",
        "summary": "Moderné C++ od prvého programu po RAII, kontajnery, šablóny, build a súbežnosť.",
        "content": {"lead": "C++ je viacparadigmový systémový jazyk. Dobré moderné C++ stavia na hodnotách, jasnom vlastníctve a štandardnej knižnici; ručná správa pamäte je výnimka, nie východiskový bod.", "sections": [{"title": "Ako kurz používať", "paragraphs": ["Príklady používajú C++20. Každý objekt má životnosť a každý zdroj má vlastníka; tieto dve otázky vyrieš pred optimalizáciou alebo dedičnosťou.", "C++ zdieľa časť syntaxe s C, ale nie je to rozšírené C. Kontajnery, RAII, preťaženie, výnimky a šablóny majú vlastné pravidlá."], "bullets": ["Uprednostni std::vector, std::string a algoritmy pred vlastným poľom a ručným cyklom.", "Uprednostni hodnotu, referenciu alebo smart pointer podľa významu vlastníctva.", "Kompiluj s varovaniami, sanitizérmi a konkrétnym štandardom jazyka."]}, {"title": "Hranice a bezpečnosť", "paragraphs": ["C++ dokáže pracovať blízko hardvéru, no to neznamená, že každý program má používať ukazovú aritmetiku alebo new. Bezpečnejšie abstrakcie sú spravidla aj zrozumiteľnejšie."], "callout": "Nedrž si surový ukazovateľ len preto, že objekt niekde existuje. Musí byť jasné, či iba pozoruje, alebo aj vlastní životnosť cieľa."}]},
    },
    {
        "key": "foundations",
        "parent_key": "",
        "kind": "chapter",
        "position": 10,
        "title": "Hodnoty, funkcie a životnosť",
        "summary": "Inicializácia, typy, funkcie, hodnotová sémantika, referencie a RAII.",
        "content": {"lead": "C++ stojí na objektoch s presne definovanou životnosťou. Konštruktor vytvorí platný stav, deštruktor uvoľní vlastnený zdroj a hodnota sa môže bezpečne kopírovať alebo presúvať podľa svojho typu.", "sections": [{"title": "V tejto kapitole", "bullets": ["Uniform initialization, auto, const a konverzie.", "Funkcie, referencie, návrat hodnotou a preťažovanie.", "RAII, move, smart pointery a výnimková bezpečnosť."]}]},
    },
    {
        "key": "program",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 20,
        "title": "Prvý program a kompilácia C++20",
        "summary": "main, iostream, namespace std, návratová hodnota a varovania prekladača.",
        "content": {"lead": "Program začína vo funkcii main. Hlavička iostream deklaruje std::cout; názov z priestoru std kvalifikuj explicitne, aby sa rozhranie zdroja dalo čítať bez skrytých mien.", "sections": [{"title": "Preklad", "paragraphs": ["Pre lokálnu kontrolu používaj g++ -std=c++20 -Wall -Wextra -Wpedantic main.cpp -o program. Návrat 0 z main znamená úspech; keď ho na konci main vynecháš, C++ ho doplní.", "Hlavička opisuje deklarácie a zdrojový súbor ich definuje. Linker potom spojí prekladové jednotky do jedného programu."], "bullets": ["#include <iostream> sprístupní streamy pre vstup a výstup.", "std::cout << value << '\\n'; zapíše hodnotu a nový riadok.", "using namespace std; v hlavičke nepoužívaj, pretože znečistí priestor každého používateľa hlavičky."]}, {"title": "Diagnostika", "paragraphs": ["Varovanie prekladača nie je dekorácia. Často upozorní na zúženie hodnoty, nepoužitý parameter alebo chybnú vetvu skôr, než vznikne runtime chyba."], "callout": "Kompilácia bez chyby nie je dôkaz správnosti. Hranice kolekcií, životnosť referencií a návratové stavy knižníc stále testuj."}]},
    },
    {
        "key": "values",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 30,
        "title": "Inicializácia, typy a const",
        "summary": "Brace initialization, auto, constexpr, pretečenie, konverzie a čitateľné deklarácie.",
        "content": {"lead": "Inicializácia v zložených zátvorkách zmenšuje priestor pre nechcené zúženie hodnoty. Typ má vyjadrovať rozsah a význam dát, nie len to, aby sa dnešný príklad náhodou preložil.", "sections": [{"title": "Hodnoty", "paragraphs": ["int count{0};, double ratio{0.5}; a std::string name{'A'}; vyjadrujú vytvorenie objektu s hodnotou. auto použi, keď je typ zjavný z pravej strany alebo by opakovanie zhoršilo čitateľnosť.", "const chráni objekt cez konkrétne meno alebo referenciu. constexpr označuje hodnotu alebo funkciu, ktorú možno vyhodnotiť pri preklade, ak sú vstupy známe."], "bullets": ["size_t patrí k veľkostiam a indexom kontajnerov.", "std::int32_t alebo std::uint64_t používaj, keď záleží na presnej šírke.", "static_cast pomenúva vedomú konverziu; sám však nepreverí rozsah."]}, {"title": "Zúženie", "paragraphs": ["Inicializácia int value{3.5}; je odmietnutá, pretože stráca časť hodnoty. Takáto chyba je presne dôvod, prečo uprednostniť brace initialization."], "callout": "Nezamieňaj const s nemennosťou celej dátovej štruktúry alebo s thread safety. Vyjadruje len to, čo možno meniť cez konkrétne rozhranie."}]},
    },
    {
        "key": "functions",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 40,
        "title": "Funkcie, referencie a návrat hodnotou",
        "summary": "Parametre hodnotou, const reference, výstupné parametre, overload a pravidlá života referencie.",
        "content": {"lead": "Malý objekt odovzdaj hodnotou. Väčší objekt, ktorý funkcia iba číta, odovzdaj cez const T&. Keď funkcia vytvára nový výsledok, bežne ho vráť hodnotou; compiler a move sémantika sa postarajú o efektívny prenos.", "sections": [{"title": "Rozhranie", "paragraphs": ["T& vyjadruje, že funkcia môže zmeniť existujúci objekt volajúceho. const T& vyjadruje pozorovanie bez zmeny. T* použi, keď môže existovať neprítomný cieľ alebo keď rozhranie prirodzene pracuje s adresou.", "Overload dovolí viaceré funkcie s rovnakým názvom, ale rozdielnymi parametrami. Nepridávaj overload, ktorý núti čitateľa hádať, ktorá konverzia zvíťazí."], "bullets": ["Nevracaj referenciu na lokálny objekt funkcie.", "std::optional alebo výsledkový typ lepšie vyjadrí možnú neprítomnosť než magická hodnota.", "Parametre s jasným vstupom a návratom sa testujú ľahšie než mnoho výstupných referencií."]}, {"title": "Hodnotová sémantika", "paragraphs": ["Vlastný typ má ideálne fungovať ako bežná hodnota: kopírovanie vytvorí nezávislú hodnotu, presun bezpečne odovzdá zdroj a po opustení rozsahu sa všetko uprace samo."], "callout": "Nesnaž sa optimalizovať návrat hodnotou na surovú referenciu. Najprv správne vyjadri vlastníctvo; RVO a move často odstránia zbytočné kopírovanie."}]},
    },
    {
        "key": "raii",
        "parent_key": "foundations",
        "kind": "lesson",
        "position": 50,
        "title": "RAII, move a smart pointery",
        "summary": "Životnosť zdroja viazaná na objekt, unique_ptr, shared_ptr, weak_ptr a základná výnimková bezpečnosť.",
        "content": {"lead": "RAII znamená, že objekt získa zdroj v konštruktore a uvoľní ho v deštruktore. Pri návrate z funkcie alebo výnimke C++ automaticky zničí lokálne objekty v opačnom poradí ich vzniku.", "sections": [{"title": "Vlastníctvo", "paragraphs": ["std::unique_ptr<T> má jedného vlastníka a presúva sa cez std::move. std::shared_ptr<T> používaj len vtedy, keď zdieľané vlastníctvo naozaj modeluje doménu; weak_ptr rozbije cyklus zdieľaných odkazov.", "Surový T* alebo T& často iba pozoruje objekt, ktorý vlastní niekto iný. Dokumentuj alebo typom vyjadri, kto zodpovedá za jeho životnosť."], "bullets": ["make_unique vytvorí unique_ptr bez samostatného new v kóde volajúceho.", "std::vector, std::string, lock_guard a file stream sú tiež RAII objekty.", "Po presune je zdrojový objekt platný, ale jeho konkrétny obsah neurčený kontraktom typu."]}, {"title": "Výnimková bezpečnosť", "paragraphs": ["Základná záruka ponechá objekty platné aj pri chybe, silná záruka navyše nenechá viditeľnú čiastočnú zmenu. RAII zaisťuje upratanie aj vtedy, keď sa vykonávanie nedostane na posledný riadok funkcie."], "callout": "Nekombinuj ručné new a delete s výnimkami. Pri predčasnom návrate alebo výnimke sa delete ľahko vynechá; vlastniaci objekt túto povinnosť nesie bezpečne."}]},
    },
    {
        "key": "library",
        "parent_key": "",
        "kind": "chapter",
        "position": 60,
        "title": "Štandardná knižnica a dáta",
        "summary": "Kontajnery, algoritmy, iterátory, ranges, text, čas, variant a chyby.",
        "content": {"lead": "Štandardná knižnica dáva modernému C++ bezpečné stavebné prvky. Začni vhodným kontajnerom a algoritmom; vlastný cyklus alebo ručný linked list majú prísť až pri konkrétnom dôvode.", "sections": [{"title": "V tejto kapitole", "bullets": ["vector, array, string, map, unordered_map, set, optional a variant.", "Algoritmy, iterátory, views a ich zložitosť.", "Invalidácia iterátorov, text, chrono a filesystem."]}]},
    },
    {
        "key": "containers",
        "parent_key": "library",
        "kind": "lesson",
        "position": 70,
        "title": "Kontajnery a dátové modely",
        "summary": "vector, array, string, map, unordered_map, set, optional, variant a voľba dátového typu.",
        "content": {"lead": "std::vector je predvolená voľba pre súvislú postupnosť s meniteľnou veľkosťou. std::array je pre pevnú veľkosť známej pri preklade a std::map alebo std::unordered_map mapujú kľúče na hodnoty s rozdielnymi zárukami poradia a zložitosti.", "sections": [{"title": "Výber typu", "paragraphs": ["std::string drží vlastnený text; std::string_view iba pohľad, ktorého cieľ musí ostať živý. std::span je podobný nevlastniaci pohľad na súvislé prvky.", "std::optional<T> vyjadruje výsledok, ktorý môže chýbať. std::variant drží jednu z explicitne pomenovaných možností namiesto voľnej kombinácie príznakov a ukazovateľov."], "bullets": ["reserve môže znížiť počet realokácií vectoru, ak poznáš približný počet prvkov.", "at kontroluje hranice a pri chybe vyhodí výnimku; operator[] ich nekontroluje.", "unordered_map vyžaduje hash a nerobí sľub poradia iterácie."]}, {"title": "Pohľady", "paragraphs": ["Pohľad je ľahký, no nevlastní dáta. Nevracaj string_view alebo span na lokálny string alebo vector, lebo cieľ po návrate zanikne."], "callout": "Nesiahaj po raw poli iba preto, že je 'rýchle'. vector má súvislú pamäť, pozná veľkosť a rieši životnosť bez ručného free."}]},
    },
    {
        "key": "algorithms",
        "parent_key": "library",
        "kind": "lesson",
        "position": 80,
        "title": "Algoritmy, iterátory a ranges",
        "summary": "find, sort, transform, accumulate, predikáty, lambda, views a zložitosť operácií.",
        "content": {"lead": "Algoritmus v std::algorithm hovorí, čo chceš vykonať, iterátory alebo range hovoria, nad čím. To často lepšie odhalí chybu hraníc aj zámer transformácie než ručne počítaný index.", "sections": [{"title": "Práca s rozsahom", "paragraphs": ["std::find, std::sort, std::count_if a std::transform pracujú nad polootvoreným intervalom [begin, end). Koniec nie je prvok a nesmie sa dereferencovať.", "Lambda má explicitný zoznam zachytených mien. Zachyť hodnotou, keď callback môže žiť dlhšie než okolitý rozsah; zachytenie referenciou môže po návrate vytvoriť visiacu referenciu."], "bullets": ["std::ranges skracuje zápis a znižuje počet párov begin/end.", "std::accumulate má počiatočnú hodnotu, ktorá určuje typ súčtu.", "Zložitosť je súčasťou kontraktu: sort je O(n log n), hľadanie vo vectori O(n)."]}, {"title": "Lazy views", "paragraphs": ["Views často nevytvárajú novú kolekciu hneď. Ich zdroj musí existovať, kým view používaš; materializuj výsledok do vectoru, keď potrebuješ samostatné vlastníctvo."], "callout": "Nevytváraj iterator a potom neupravuj kontajner bez kontroly jeho pravidiel invalidácie. Niektoré operácie vectoru presunú všetky prvky do nového bloku."}]},
    },
    {
        "key": "iterators",
        "parent_key": "library",
        "kind": "lesson",
        "position": 90,
        "title": "Invalidácia iterátorov a referencií",
        "summary": "Kedy zmena kontajnera zneplatní iterator, pointer alebo referenciu a ako navrhovať stabilný prístup.",
        "content": {"lead": "Iterator, pointer alebo referencia do kontajnera sú platné iba tak dlho, ako to sľubuje konkrétny kontajner a operácia. Najčastejší omyl je uložiť odkaz do vectoru a potom ho rozšíriť bez rezervovanej kapacity.", "sections": [{"title": "Vector", "paragraphs": ["Operácia, ktorá vyvolá realokáciu vectoru, zneplatní všetky iterátory, pointery a referencie na jeho prvky. Vloženie alebo vymazanie v strede môže zneplatniť prvky od miesta zmeny ďalej.", "reserve vie zabrániť realokácii iba do danej kapacity; nie je to večná záruka."], "bullets": ["Po erase použi iterator vrátený samotným erase.", "Nedrž referenciu na prvok, ak zároveň voláš push_back bez jasnej kapacity.", "Pre stabilnú identitu zváž vlastníctvo objektov mimo meniteľného kontajnera alebo iný dátový model."]}, {"title": "Čítaj kontrakt", "paragraphs": ["Pravidlá sa medzi vector, deque, list, map a unordered_map líšia. Neprenášaj intuície z jedného kontajnera na druhý bez overenia dokumentácie."], "callout": "Visiaci iterator sa nemusí prejaviť hneď. Program môže zdanlivo fungovať a zlyhať až po zmene kapacity alebo na inom prekladači."}]},
    },
    {
        "key": "types",
        "parent_key": "",
        "kind": "chapter",
        "position": 100,
        "title": "Vlastné typy a generické rozhrania",
        "summary": "Triedy, kompozícia, polymorfizmus, šablóny, concepts a constexpr.",
        "content": {"lead": "C++ dáva silné nástroje na vlastné abstrakcie. Použi ich až po pomenovaní invariantov, vlastníctva a malého verejného rozhrania; trieda alebo template nie sú automaticky lepší návrh.", "sections": [{"title": "V tejto kapitole", "bullets": ["Trieda, class invariant, special member functions a kompozícia.", "Dynamický polymorfizmus, virtual a životnosť cez základnú triedu.", "Templates, concepts, constexpr a chyby pri inštanciácii."]}]},
    },
    {
        "key": "classes",
        "parent_key": "types",
        "kind": "lesson",
        "position": 110,
        "title": "Triedy, invariants a polymorfizmus",
        "summary": "Zapuzdrenie, konštruktor, pravidlo nula/päť, virtual, override, kompozícia a dedenie.",
        "content": {"lead": "Dobrý typ nedovolí vznik neplatného stavu cez svoje verejné rozhranie. Ak trieda priamo nevlastní zdroj, často nepotrebuje vlastný deštruktor, kopírovanie ani presun: to je pravidlo nula.", "sections": [{"title": "Návrh triedy", "paragraphs": ["Daj dáta private, ale nevytváraj mechanické get/set pre každé pole. Verejná metóda má vyjadrovať doménovú operáciu a chrániť invariant.", "Kompozícia znamená, že objekt má iný objekt. Dedenie znamená, že odvodený objekt naozaj je substituovateľným druhom základného typu."], "bullets": ["Ak mažeš cez pointer na polymorfnú základnú triedu, jej deštruktor musí byť virtual.", "override nech je pri každej predefinovanej virtuálnej metóde.", "Preferuj std::unique_ptr<Base> pre vlastnený polymorfný objekt."]}, {"title": "Pravidlo nula", "paragraphs": ["Keď vlastnenie riešia členy ako vector, string a unique_ptr, compiler vie bezpečne vytvoriť vhodné special member functions. Ručne ich píš iba pri priamom vlastníctve neštandardného zdroja."], "callout": "Dedenie kvôli opätovnému použitiu implementácie bez vzťahu typu vedie ku krehkému kódu. Najprv skús vložiť spolupracujúci objekt ako člen."}]},
    },
    {
        "key": "templates",
        "parent_key": "types",
        "kind": "lesson",
        "position": 120,
        "title": "Šablóny, concepts a constexpr",
        "summary": "Generické funkcie a typy, dedukcia, constraints, compile-time výpočet a čitateľné chybové správy.",
        "content": {"lead": "Template vyjadruje algoritmus alebo typ nad rodinou vhodných typov. Generické rozhranie má opisovať potrebné operácie, nie náhodne predpokladať konkrétnu implementáciu kontajnera.", "sections": [{"title": "Generický kontrakt", "paragraphs": ["Template parameter sa dedukuje z argumentu. Concepts a requires obmedzia platné typy skôr a dajú používateľovi lepšiu diagnostiku než chyba hlboko v tele šablóny.", "constexpr funkcia môže vypočítať výsledok pri preklade, ale môže bežať aj za behu. consteval vyžaduje prekladový čas a patrí len tam, kde ho naozaj potrebuješ."], "bullets": ["Šablóny s definíciou viditeľnou v hlavičke sa inštanciujú v mieste použitia.", "auto a decltype pomáhajú dedukcii, no príliš zložitý typový trik skrýva návrh.", "std::span a ranges často znížia potrebu vlastnej generickej kontajnerovej vrstvy."]}, {"title": "Hranice abstrakcie", "paragraphs": ["Template nepatrí na každý jeden typ. Keď poznáš jediný konkrétny dátový model, obyčajná funkcia s jasným typom bude čitateľnejšia a ľahšie sa kompiluje."], "callout": "Metaprogramovanie nie je cieľ. Použi compile-time techniku iba vtedy, keď zlepší rozhranie, bezpečnosť alebo odstráni skutočný runtime náklad."}]},
    },
    {
        "key": "projects",
        "parent_key": "",
        "kind": "chapter",
        "position": 130,
        "title": "Projekt, nástroje a súbežnosť",
        "summary": "CMake, závislosti, testy, sanitizéry, debugger, vlákna, atomics a model pamäte.",
        "content": {"lead": "Spoľahlivý C++ projekt má reprodukovateľný build, jasne určený štandard, automatické testy a nástroje na hľadanie chýb pamäte. Súbežnosť pridaj až vtedy, keď má samostatný problém na riešenie.", "sections": [{"title": "V tejto kapitole", "bullets": ["CMake targets, verejné hlavičky a závislosti.", "Testy, sanitizéry, debugger, profiler a analýza varovaní.", "Vlákna, mutex, lock_guard, atomics a model pamäte."]}]},
    },
    {
        "key": "build_quality",
        "parent_key": "projects",
        "kind": "lesson",
        "position": 140,
        "title": "CMake, testy a sanitizéry",
        "summary": "Targets, závislosti, Debug/Release, unit testy, AddressSanitizer, UBSan a debugger.",
        "content": {"lead": "CMake opisuje targets a ich závislosti, nie sériu globálnych príznakov. Každá knižnica alebo program má dostať vlastné include cesty, štandard a linkované knižnice cez svoj target.", "sections": [{"title": "Opakovateľný build", "paragraphs": ["Nastav CMAKE_CXX_STANDARD alebo target_compile_features priamo v projekte. Debug a Release sú rozdielne build konfigurácie; testuj aj s optimalizáciou, ale chyby najprv hľadaj v čitateľnom Debug builde.", "Unit test má malý vstup, pozorovateľný výsledok a hraničný prípad. Test nepokrýva všetko, ale drží kontrakt pri budúcej úprave."], "bullets": ["AddressSanitizer hľadá mnohé chyby prístupu do pamäte.", "UndefinedBehaviorSanitizer odhalí časť nedefinovaného správania.", "Debugger ukáže skutočný stack a hodnoty; profiler najprv zmeria, potom optimalizuje."]}, {"title": "Závislosti", "paragraphs": ["Externú knižnicu dávaj do reprodukovateľného dependency workflowu. Verzia, licencia, bezpečnostné aktualizácie a verejné rozhranie sú súčasťou návrhu projektu."], "callout": "Sanitizér nie je dôkaz bezpečnosti. Je to citlivý testovací nástroj, ktorý musíš kombinovať s návrhom, testami a varovaniami."}]},
    },
    {
        "key": "concurrency",
        "parent_key": "projects",
        "kind": "lesson",
        "position": 150,
        "title": "Vlákna, zámky a atomické operácie",
        "summary": "thread, jthread, mutex, lock_guard, condition variable, atomic, data race a rušenie práce.",
        "content": {"lead": "Dve vlákna môžu bežať v ľubovoľnom poradí. Ak súčasne pristupujú k tej istej meniteľnej hodnote bez synchronizácie, vzniká data race a program má nedefinované správanie.", "sections": [{"title": "Zdieľaný stav", "paragraphs": ["std::mutex chráni kritickú sekciu a std::lock_guard uvoľní zámok aj pri výnimke. std::jthread rieši spojenie vlákna pri zničení objektu a ponúka stop_token pre kooperatívne rušenie.", "std::atomic patrí k jednoduchým nezávislým hodnotám a presným synchronizačným protokolom. Nenahrádza automaticky návrh vlastníctva alebo veľký zložený stav."], "bullets": ["Najprv preferuj komunikáciu správami alebo oddelené vlastníctvo pred zdieľaním.", "Viac zámkov vyžaduje jednotné poradie, inak hrozí deadlock.", "condition_variable vždy čaká s predikátom, aby odolala falošnému zobudeniu."]}, {"title": "Model pamäte", "paragraphs": ["Sekvenčná konzistencia je dobrý východiskový bod na učenie. Slabšie memory ordery pridávaj až po prečítaní kontraktu konkrétneho algoritmu a po meraní."], "callout": "Vlákno nikdy nenechaj bežať za životnosťou objektov, na ktoré odkazuje. Korektné ukončenie a vlastníctvo sú dôležitejšie než samotné spustenie thread."}]},
    },
]

CPP_LEARNING_GOALS = {
    "program": ("Preložiť malý program ako C++20 s užitočnými varovaniami.", "Rozlíšiť prekladovú jednotku, hlavičku a linkovanie."),
    "values": ("Použiť inicializáciu, ktorá neprehliadne zúženie hodnoty.", "Rozlíšiť const a constexpr v konkrétnom rozhraní."),
    "functions": ("Vybrať odovzdanie hodnotou, const referenciou alebo meniteľnou referenciou.", "Navrhnúť návrat hodnotou bez visiacej referencie."),
    "raii": ("Určiť vlastníka zdroja a jeho životnosť cez RAII objekt.", "Rozlíšiť unique_ptr, shared_ptr a nevlastniaci pohľad."),
    "containers": ("Vybrať kontajner alebo hodnotový typ podľa významu dát.", "Rozpoznať, kedy pohľad nevlastní dáta a môže ostať visieť."),
    "algorithms": ("Použiť štandardný algoritmus nad platným rozsahom.", "Rozlíšiť okamžitú kolekciu od lazy view a jej zdroja."),
    "iterators": ("Predpovedať invalidáciu iterátora pri zmene vectoru.", "Navrhnúť úpravu kontajnera bez použitia visiacej referencie."),
    "classes": ("Navrhnúť triedu s malým rozhraním a platným invariantom.", "Vybrať kompozíciu alebo polymorfizmus podľa vzťahu typov."),
    "templates": ("Vyjadriť požiadavku generického rozhrania cez concept alebo jasný typ.", "Rozlíšiť constexpr výpočet od bežného runtime výpočtu."),
    "build_quality": ("Vysvetliť, prečo target-based CMake zlepšuje reprodukovateľnosť buildu.", "Zvoliť test, varovania a sanitizér pre konkrétne riziko."),
    "concurrency": ("Rozpoznať data race a chrániť zdieľaný stav.", "Navrhnúť ukončenie vlákna bez prežitia vlastnených objektov."),
}

CPP_VISUALIZATION_IDS = {
    "raii": ("cpp-raii-lifetime",),
    "iterators": ("cpp-iterator-invalidation",),
}

CPP_EXAMPLES = [
    {"key": "first-program", "page_key": "program", "position": 10, "title": "Pozdrav v C++20", "description": "Štandardný výstup patrí do namespace std a nový riadok ukončí riadok bez zbytočného flush.", "source": "#include <iostream>\n\nint main()\n{\n    std::cout << \"Ahoj, svet!\\n\";\n}\n", "stdin": "", "standard": "cpp20"},
    {"key": "checked-initialization", "page_key": "values", "position": 10, "title": "Hodnota s jasným typom", "description": "auto odvodí zjavný typ a const vyjadruje, že ho cez dané meno nemeníme.", "source": "#include <iostream>\n#include <vector>\n\nint main()\n{\n    const std::vector<int> values{2, 3, 5};\n    const auto count = values.size();\n\n    std::cout << count << '\\n';\n}\n", "stdin": "", "standard": "cpp20"},
    {"key": "return-value", "page_key": "functions", "position": 10, "title": "Návrat vlastnenej hodnoty", "description": "Funkcia vytvorí vector lokálne a bezpečne ho vráti hodnotou.", "source": "#include <iostream>\n#include <vector>\n\nstd::vector<int> squares(int count)\n{\n    std::vector<int> result;\n    result.reserve(static_cast<std::size_t>(count));\n    for (int value{1}; value <= count; ++value) {\n        result.push_back(value * value);\n    }\n    return result;\n}\n\nint main()\n{\n    for (const int value : squares(4)) {\n        std::cout << value << ' ';\n    }\n    std::cout << '\\n';\n}\n", "stdin": "", "standard": "cpp20"},
    {"key": "unique-owner", "page_key": "raii", "position": 10, "title": "Jediný vlastník dynamického objektu", "description": "unique_ptr uvoľní objekt automaticky pri odchode z main.", "source": "#include <iostream>\n#include <memory>\n\nint main()\n{\n    auto value = std::make_unique<int>(42);\n    std::cout << *value << '\\n';\n}\n", "stdin": "", "standard": "cpp20"},
    {"key": "sort-values", "page_key": "algorithms", "position": 10, "title": "Triedenie štandardným algoritmom", "description": "std::sort vyjadruje operáciu nad celým rozsahom vectoru.", "source": "#include <algorithm>\n#include <iostream>\n#include <vector>\n\nint main()\n{\n    std::vector<int> values{8, 3, 5, 1};\n    std::sort(values.begin(), values.end());\n\n    for (const int value : values) {\n        std::cout << value << ' ';\n    }\n    std::cout << '\\n';\n}\n", "stdin": "", "standard": "cpp20"},
    {"key": "optional-lookup", "page_key": "containers", "position": 10, "title": "Možný výsledok cez optional", "description": "optional odlíši nájdenú hodnotu od neprítomnosti bez magického čísla.", "source": "#include <iostream>\n#include <optional>\n#include <vector>\n\nstd::optional<int> first_even(const std::vector<int>& values)\n{\n    for (const int value : values) {\n        if (value % 2 == 0) {\n            return value;\n        }\n    }\n    return std::nullopt;\n}\n\nint main()\n{\n    if (const auto value = first_even({3, 7, 8}); value) {\n        std::cout << *value << '\\n';\n    }\n}\n", "stdin": "", "standard": "cpp20"},
    {"key": "bounded-score", "page_key": "classes", "position": 10, "title": "Trieda, ktorá drží invariant", "description": "Konštruktor odmietne skóre mimo povoleného rozsahu.", "source": "#include <iostream>\n#include <stdexcept>\n\nclass Score {\npublic:\n    explicit Score(int value)\n    {\n        if (value < 0 || value > 100) {\n            throw std::out_of_range(\"Skóre musí byť od 0 po 100.\");\n        }\n        value_ = value;\n    }\n\n    int value() const { return value_; }\n\nprivate:\n    int value_{};\n};\n\nint main()\n{\n    std::cout << Score{86}.value() << '\\n';\n}\n", "stdin": "", "standard": "cpp20"},
    {"key": "template-maximum", "page_key": "templates", "position": 10, "title": "Jednoduchá generická funkcia", "description": "Template pracuje s hodnotami, ktoré sa dajú porovnať operátorom > a vracia samostatnú výslednú hodnotu.", "source": "#include <iostream>\n\ntemplate <typename T>\nT maximum(T left, T right)\n{\n    return left > right ? left : right;\n}\n\nint main()\n{\n    std::cout << maximum(4, 9) << '\\n';\n}\n", "stdin": "", "standard": "cpp20"},
]


CSHARP_LANGUAGE = {
    "code": "csharp",
    "title": "C#",
    "summary": "Praktická učebnica moderného C#: typy, .NET knižnica, LINQ, zdroje, Tasky a projektové nástroje.",
}

CSHARP_PAGES = [
    {
        "key": "overview", "parent_key": "", "kind": "overview", "position": 0,
        "title": "C#: učebnica a referencia", "summary": "Moderný C# a .NET od prvého programu po typový systém, LINQ a asynchrónne rozhrania.",
        "content": {"lead": "C# je staticky typovaný jazyk platformy .NET. Typy, nullable anotácie a malý verejný kontrakt nie sú byrokracia: dávajú kompilátoru aj čitateľovi možnosť zachytiť omyl pred spustením.", "sections": [{"title": "Ako kurz používať", "paragraphs": ["Príklady používajú moderný C# s top-level statements, records a async/await. Najprv rozlíš, či hodnota patrí do value alebo reference typu, a potom rozhodni, kto vlastní zdroj alebo zrušenie práce."], "bullets": ["Kompilátorové varovania ber ako návrhovú spätnú väzbu.", "Nullability zapínaj a rieš pri hranici vstupu.", "Preferuj štandardnú knižnicu pred vlastnými pomocníkmi bez jasného dôvodu."]}, {"title": "Hranice runtime", "paragraphs": [".NET poskytuje runtime, knižnicu, SDK a nástroje. Jazyk C# nie je to isté ako konkrétny webový framework alebo databázový driver; ich API sa uč až po pevných základoch."], "callout": "Výnimku neignoruj iba preto, že program pokračuje. Rozhodni, ktorá vrstva chybu spracuje, obohatí o kontext alebo korektne ukončí operáciu."}]},
    },
    {
        "key": "foundations", "parent_key": "", "kind": "chapter", "position": 10,
        "title": "Hodnoty, mená a riadenie toku", "summary": "Program, typy, nullability, pattern matching, vetvy a funkcie.",
        "content": {"lead": "C# rozlišuje hodnotové a referenčné typy, no každé priradenie má presný význam. Jazykový typ nie je náhradou validácie, ale je silná prvá obranná línia.", "sections": [{"title": "V tejto kapitole", "bullets": ["Top-level program, namespace a build.", "Value/reference types a nullable reference types.", "Výrazy, pattern matching a malé metódy."]}]},
    },
    {
        "key": "program", "parent_key": "foundations", "kind": "lesson", "position": 20,
        "title": "Prvý program a projekt .NET", "summary": "Top-level statements, Console, dotnet new, dotnet run a návratový kód.",
        "content": {"lead": "Moderný malý projekt môže začať priamo príkazmi na najvyššej úrovni súboru Program.cs. SDK z nich vytvorí vstupný bod; pri väčšom programe je stále dôležité držať štartovací kód krátky.", "sections": [{"title": "Spustenie", "paragraphs": ["dotnet new console vytvorí konzolový projekt a dotnet run ho zostaví aj spustí. Súbor .csproj opisuje target framework, balíky a vlastnosti buildu.", "Console.WriteLine vypíše diagnostický alebo používateľský text. Ak program potrebuje návratový kód, explicitne ho nastav cez Environment.ExitCode namiesto náhodného ukončenia uprostred práce."], "bullets": ["using sprístupní mená z namespace.", "Implicitné global usings sú pohodlné, no verejné API stále dokumentuj presnými typmi.", "Build musí byť opakovateľný z čistého checkoutu."]}, {"title": "Kompilátor", "paragraphs": ["Kompilátor kontroluje typy, dostupnosť členov a časť nullability. Chyba prekladu znamená, že kontrakt zdroja nie je splnený; varovanie môže byť rovnako dôležité."], "callout": "Nerob z varovaní trvalé pozadie. Prečítaj ich, oprav príčinu alebo výnimočne potlač konkrétne pravidlo spolu so zdôvodnením."}]},
    },
    {
        "key": "values", "parent_key": "foundations", "kind": "lesson", "position": 30,
        "title": "Typy, nullability a pattern matching", "summary": "Value/reference types, string, nullable, enum, var, is a switch expression.",
        "content": {"lead": "int, double, bool, enum a struct sú hodnotové typy; class, array, string a delegate sú referenčné typy. Prenos a uloženie hodnoty preto nie je to isté ako prenos premennej s odkazom na objekt.", "sections": [{"title": "Null ako súčasť kontraktu", "paragraphs": ["Zapnuté nullable reference types odlíšia string od string?. Metóda, ktorá môže nič nenájsť, má to vyjadriť v návratovom type alebo výsledkovom modeli, nie nečakaným null dereferencovaním.", "Operátory ?. a ?? riešia konkrétnu neprítomnosť. Nenahrádzajú validáciu povinného vstupu ani nepremeňujú chybu na tiché predvolené správanie."], "bullets": ["var odvodí známy statický typ; nevytvára dynamický typ.", "is string name súčasne overí typ a sprístupní bezpečné meno.", "switch expression je čitateľný pre uzavretý počet prípadov."]}, {"title": "Konverzie", "paragraphs": ["Nezúžuj hodnotu potichu. Pri texte používaj TryParse, aby neplatný vstup mal normálnu vetvu; výnimka patrí k neočakávanému zlyhaniu, nie k bežnému formuláru."], "callout": "Operátor ! iba utlmí upozornenie analyzéra. Nie je to kontrola, že hodnota skutočne nie je null."}]},
    },
    {
        "key": "flow", "parent_key": "foundations", "kind": "lesson", "position": 40,
        "title": "Vetvy, cykly a malé metódy", "summary": "if, switch, foreach, for, while, return, argumenty a výstupné hodnoty.",
        "content": {"lead": "Metóda má mať malý pozorovateľný kontrakt: aké hodnoty prijíma, čo vracia a za akých podmienok zlyhá. Krátke guard clauses často znížia vnorenie lepšie než dlhý reťazec else.", "sections": [{"title": "Riadenie toku", "paragraphs": ["foreach prechádza prvky IEnumerable bez ručného indexu. for vyber, keď je index súčasťou úlohy, a while keď podmienka prirodzene riadi pokračovanie.", "switch a pattern matching pomôžu, keď rozhoduješ podľa tvaru dát. Prípady majú byť úplné alebo vedome ošetriť nepodporovanú hodnotu."], "bullets": ["return ukončí metódu s výsledkom.", "out a ref používaj len pri jasnej potrebe; návratový objekt je často čitateľnejší.", "ArgumentNullException.ThrowIfNull vyjadruje hranicu povinného parametra."]}, {"title": "Čisté funkcie", "paragraphs": ["Čistá metóda s explicitným vstupom a výsledkom sa testuje jednoduchšie než metóda, ktorá číta globálny stav, konzolu a súbor naraz."], "callout": "Nevraciaj magické číslo pre chybu, ak sa môže pliesť s platnou hodnotou. Použi jasný výsledkový typ, Try-pattern alebo výnimku podľa kontraktu."}]},
    },
    {
        "key": "types", "parent_key": "", "kind": "chapter", "position": 50,
        "title": "Objekty, rozhrania a kolekcie", "summary": "Triedy, records, structy, rozhrania, generiká, delegáty a LINQ.",
        "content": {"lead": "Typový systém C# vie zachytiť veľa návrhových chýb, ak verejné rozhrania pomenúvajú skutočný význam dát. Uprednostni kompozíciu a malé rozhranie pred dedičnosťou iba kvôli zdieľaniu kódu.", "sections": [{"title": "V tejto kapitole", "bullets": ["class, record, struct, enum a invarianty.", "interface, generiká a delegáty.", "IEnumerable, LINQ a odložené vykonanie."]}]},
    },
    {
        "key": "records", "parent_key": "types", "kind": "lesson", "position": 60,
        "title": "Triedy, records, structy a enumy", "summary": "Zapuzdrenie, hodnotová rovnosť, nemennosť a výber dátového tvaru.",
        "content": {"lead": "class je vhodná pre objekt s identitou a meniteľným stavom. record vyjadruje dátovú hodnotu s porovnaním podľa obsahu; struct používaj pre malé, prirodzene hodnotové dáta, nie ako únikovú cestu pred návrhom.", "sections": [{"title": "Invariant typu", "paragraphs": ["Konstruktor alebo factory vytvorí platný stav a verejné metódy ho držia. Nesprístupňuj meniteľnú kolekciu tak, aby volajúci vedel obísť pravidlá objektu.", "readonly a init pomáhajú vyjadriť, kedy sa môže hodnota zmeniť. Nemenný objekt znižuje počet vzájomne závislých stavov."], "bullets": ["enum je pomenovaná uzavretá množina stavov.", "record s referenčnou kolekciou nekopíruje jej vnútro automaticky.", "Value equality je výhoda iba vtedy, keď zodpovedá významu domény."]}, {"title": "Návrh rozhrania", "paragraphs": ["Verejná vlastnosť nemá byť automatický setter na všetko. Ak zmena znamená operáciu domény, pomenuj ju metódou, ktorá vie overiť invariant."], "callout": "Dedičnosť nepridávaj iba pre opakovanie implementácie. Ak objekt nie je skutočným druhom rodičovského typu, preferuj kompozíciu."}]},
    },
    {
        "key": "interfaces", "parent_key": "types", "kind": "lesson", "position": 70,
        "title": "Rozhrania, generiká a polymorfizmus", "summary": "interface, implementácia, constraints, covariance a kompozícia.",
        "content": {"lead": "Rozhranie vyjadruje schopnosť alebo kontrakt bez viazania na jednu implementáciu. Generiká zachovajú informáciu o type tam, kde by object a cast skryli chybu až do runtime.", "sections": [{"title": "Malý kontrakt", "paragraphs": ["IRepository<T> alebo IComparer<T> má byť taký malý, aby klient naozaj potreboval každého jeho člena. Závislosť na rozhraní uľahčí testovanie, ale falošné vrstvy bez zmeny zodpovednosti iba komplikujú čítanie.", "Constraint where T : ... hovorí, ktoré operácie generická metóda potrebuje. Je to presnejšie než neskorý cast alebo odraz."], "bullets": ["Implementácia môže pridať vlastné členy, rozhranie opisuje spoločné minimum.", "Kompozícia vloží spolupracujúci objekt ako závislosť.", "Virtual dispatch používaj, keď je dedenie skutočnou súčasťou modelu."]}, {"title": "Delegáty a udalosti", "paragraphs": ["Delegate opisuje volateľný tvar. event chráni vlastníka udalosti: iné objekty sa môžu prihlásiť alebo odhlásiť, no nemôžu ju samy vyvolať."], "callout": "Predplatné udalosti môže držať referenciu na poslucháča. Pri dlhšie žijúcom vydavateľovi vždy premysli odhlásenie."}]},
    },
    {
        "key": "delegates", "parent_key": "types", "kind": "lesson", "position": 75,
        "title": "Delegáty, udalosti a lambdy", "summary": "Action, Func, vlastný delegate, event, prihlásenie, odhlásenie a uzávierky lambdy.",
        "content": {"lead": "Delegát je hodnota, ktorú možno zavolať cez dohodnutý tvar parametrov a výsledku. Lambda vytvorí takú hodnotu stručne; event z nej robí riadený oznamovací kanál vlastnený jedným objektom.", "sections": [{"title": "Dohoda o volaní", "paragraphs": ["Action<T> reprezentuje operáciu bez výsledku a Func<T, TResult> operáciu s výsledkom. Vlastný delegate vytvor iba vtedy, keď jeho názov pridá význam, ktorý všeobecný tvar Action alebo Func nevyjadrí.", "Lambda môže zachytiť okolité mená. Zachytený meniteľný stav je stále zdieľaný stav, preto ho neukrývaj do callbacku bez dohody o životnosti a vlákne."], "bullets": ["event povoľuje odberateľovi += a -=.", "Vydavateľ vyvolá udalosť iba vo vlastnej triede.", "Callback má dokumentovať okamih volania, chyby a vlastníctvo predplatného."]}, {"title": "Životnosť subscription", "paragraphs": ["Dlhšie žijúci publisher drží delegáta, ktorý často drží odberateľa. Ak sa odberateľ skončí skôr, odhlásenie alebo krátko žijúci subscription objekt zabráni memory leaku a neočakávanému volaniu."], "callout": "Udalosť nie je fronta ani transakcia. Ak potrebuješ garantované spracovanie, poradie alebo spätný tlak, navrhni explicitný kanál správ."}]},
    },
    {
        "key": "linq", "parent_key": "types", "kind": "lesson", "position": 80,
        "title": "Kolekcie, LINQ a odložené vykonanie", "summary": "List, Dictionary, IEnumerable, Select, Where, aggregate operácie a materializácia.",
        "content": {"lead": "LINQ vyjadruje transformáciu, filter a skladanie dát deklaratívne. Mnohé operátory však vytvoria iba dopyt; zdroj sa číta až pri iterácii alebo pri ToList, Count či inej terminálnej operácii.", "sections": [{"title": "Kedy sa dopyt vykoná", "paragraphs": ["IEnumerable môže hodnoty vydávať postupne. Ak po vytvorení dopytu zmeníš zdroj, neskoršia iterácia môže vidieť inú množinu dát; pre stabilný snapshot materializuj výsledok vedome.", "Where a Select sú lazy, ToList vytvorí konkrétny zoznam. Single a First majú rozdielne podmienky zlyhania, preto si vyber podľa dátového kontraktu."], "bullets": ["Dictionary mapuje jedinečný kľúč na hodnotu.", "OrderBy neznamená, že pôvodný List zmenil poradie.", "Pri veľkom toku nenačítaj všetko cez ToList bez potreby."]}, {"title": "Zložitosť a chyby", "paragraphs": ["Čitateľný LINQ dopyt nie je automaticky lacný. Meraj počet iterácií, materializácie a vstupov z databázy alebo siete; hranicu medzi query providerom a pamäťou maj viditeľnú."], "callout": "Nenapájaj nedôveryhodný text priamo do dynamicky skladaného dotazu. LINQ ani ORM samy nenahrádzajú validáciu a parametre na hranici databázy."}]},
    },
    {
        "key": "runtime", "parent_key": "", "kind": "chapter", "position": 90,
        "title": "Zdroje, Tasky a kvalitný projekt", "summary": "Výnimky, IDisposable, using, async/await, rušenie, NuGet, testy a ladenie.",
        "content": {"lead": "Garbage collector spravuje pamäť, nie všetky zdroje. Súbor, socket, databázové spojenie alebo subscription môžu vyžadovať presné ukončenie, ktoré vyjadríš cez IDisposable, using alebo jasný lifecycle.", "sections": [{"title": "V tejto kapitole", "bullets": ["Výnimky a bezpečné upratanie zdrojov.", "Task, await, CancellationToken a časové limity.", "SDK projekt, NuGet, testy, logging, debugger a profiler."]}]},
    },
    {
        "key": "resources", "parent_key": "runtime", "kind": "lesson", "position": 100,
        "title": "Výnimky, using a vlastníctvo zdrojov", "summary": "try/catch/finally, IDisposable, using declaration, cleanup a kontext chyby.",
        "content": {"lead": "using zabezpečí Dispose aj pri výnimke. Použi ho pri zdroji, ktorého životnosť tvoja metóda vlastní; ak zdroj vlastní volajúci, metóda ho nemá potichu zatvoriť.", "sections": [{"title": "Hranica chyby", "paragraphs": ["Zachyť konkrétnu výnimku tam, kde vieš obnoviť prácu alebo pridať doménový kontext. Stack trace zachovaj cez throw; a nie cez throw ex;, ktorý začne sledovanie odznova.", "finally patrí k nevyhnutnému uprataniu, keď using nie je vhodný. Log nesmie obsahovať tokeny, heslá ani kompletný citlivý vstup."], "bullets": ["ArgumentException znamená chybu kontraktu volajúceho.", "InvalidOperationException označuje nevhodný stav operácie.", "Dispose nie je náhradou za validáciu vstupu."]}, {"title": "Vlastníctvo", "paragraphs": ["Metóda, ktorá nový IDisposable vytvorí a vráti, má jasne zdokumentovať, kto ho dispose-ne. Rozhranie Stream alebo DbConnection samo nevysvetlí, či zdieľanie a zatvorenie očakáva volajúci."], "callout": "Garbage collector nepozná okamih, v ktorom musí byť súbor odomknutý alebo spojenie vrátené do poolu. Na to slúži deterministické Dispose."}]},
    },
    {
        "key": "async", "parent_key": "runtime", "kind": "lesson", "position": 110,
        "title": "Task, async/await a rušenie", "summary": "Task, await, paralelné I/O, chyby, CancellationToken a timeout.",
        "content": {"lead": "async metóda vracia Task alebo Task<T>. await neblokuje volajúce vlákno počas čakania na asynchrónnu operáciu, no nevytvorí paralelizmus sám od seba.", "sections": [{"title": "Životnosť Tasku", "paragraphs": ["Nezávislé operácie môžeš spustiť a potom čakať cez Task.WhenAll. Každý vytvorený Task musí mať vlastníka, ktorý spracuje úspech, výnimku alebo zrušenie; opustený Task schová chybu mimo normálnej cesty programu.", "CancellationToken je žiadosť o kooperatívne zrušenie. Odovzdaj ho až k I/O alebo dlhému výpočtu a rozlišuj OperationCanceledException od bežnej chyby."], "bullets": ["async void patrí takmer výlučne obsluhovaču udalosti.", "Timeout je politika volajúceho, nie dôvod zahodiť cleanup.", "CPU úlohu nepremaľuj na async; použi vhodný paralelný alebo procesový návrh."]}, {"title": "Zdieľaný stav", "paragraphs": ["Asynchrónne čakanie nevylučuje súbežný prístup k objektu. Drž stav lokálny, používaj bezpečné kolekcie alebo jasné synchronizačné pravidlo."], "callout": "Nedávaj .Result alebo .Wait do asynchrónnej cesty iba preto, aby sa kód javil synchronne. Môže blokovať vlákno a v niektorých prostrediach vytvoriť deadlock."}]},
    },
    {
        "key": "projects", "parent_key": "runtime", "kind": "lesson", "position": 120,
        "title": "SDK projekt, NuGet a konfigurácia", "summary": "csproj, target framework, PackageReference, appsettings, tajomstvá a publikovanie.",
        "content": {"lead": "Projektový súbor je súčasťou zdroja. Určuje target framework, balíky, analyzéry a build vlastnosti, preto musí byť čitateľný a verzovaný spolu s kódom.", "sections": [{"title": "Závislosti", "paragraphs": ["NuGet balík pridávaj s jasným dôvodom, licenciou a verziou. Aktualizácia závislosti má prejsť testami; netreba ju miešať s náhodnými funkčnými zmenami.", "Konfigurácia od prostredia nepatrí napevno do zdroja. Tajomstvá neukladaj do appsettings commitnutého do repozitára ani do klientského výstupu."], "bullets": ["dotnet restore pripraví balíky.", "dotnet build oddelí zostavenie od spustenia.", "Target framework vyber podľa skutočne podporovaného prostredia."]}, {"title": "Verejné API", "paragraphs": ["Zmena typu, nullability alebo výnimky verejnej metódy je zmena kontraktu. Verzionovanie a migráciu plánuj skôr, než sa z interného projektu stane knižnica pre iné tímy."], "callout": "Konfiguračný súbor nie je bezpečnostná hranica. Produkčný proces musí obmedziť prístup k tajomstvám nezávisle od toho, čo vidí aplikácia."}]},
    },
    {
        "key": "quality", "parent_key": "runtime", "kind": "lesson", "position": 130,
        "title": "Testy, analyzéry, debugger a výkon", "summary": "Unit testy, nullable varovania, analyzéry, structured logging, profiler a meranie.",
        "content": {"lead": "Testy chránia pozorovateľný kontrakt, analyzéry hľadajú podozrivé tvary a profiler ukáže skutočné miesto nákladov. Spolu vytvárajú krátku spätnú väzbu bez hádania.", "sections": [{"title": "Overenie", "paragraphs": ["Unit test pripraví malý vstup, overí výsledok a pomenuje hranicu, ktorú chráni. Testuj bežnú cestu, okraj a chybu; test implementačného detailu iba vtedy, keď je sám kontraktom.", "TreatWarningsAsErrors môže byť vhodný pre vlastný kód, ak tím varovania postupne rieši. Formátovanie, analyzéry a testy majú bežať reprodukovateľne v CI."], "bullets": ["Debugger pomáha pochopiť konkrétny priebeh.", "Structured logging nesie pomenované údaje, nie poskladaný text bez kontextu.", "Profiler používaj až po meraní reálneho scenára."]}, {"title": "Bezpečnosť", "paragraphs": ["Validuj vstup na hranici, používaj parametre databázových dotazov a výstup escapuj podľa konkrétneho kontextu HTML, URL alebo JSON. Typový systém pomáha, ale neoprávňuje nedôverovať sieti menej."], "callout": "Výnimková správa pre používateľa nemá byť výpisom interného stack trace. Detail patrí do chráneného logu s korelačným údajom."}]},
    },
]

CSHARP_LEARNING_GOALS = {
    "program": ("Vytvoriť a spustiť minimálny SDK projekt .NET.", "Rozlíšiť zdrojový súbor, projektový súbor a runtime."),
    "values": ("Rozlíšiť hodnotový a referenčný typ pri priradení.", "Vyjadriť a bezpečne spracovať možnosť null."),
    "flow": ("Navrhnúť malú metódu s overiteľným kontraktom.", "Vybrať foreach, for alebo pattern matching podľa úlohy."),
    "records": ("Vybrať class, record, struct alebo enum podľa významu dát.", "Chrániť invariant typu cez malé verejné rozhranie."),
    "interfaces": ("Navrhnúť malé rozhranie bez zbytočných členov.", "Použiť generický typ namiesto object a neskorého castu."),
    "delegates": ("Rozlíšiť callback, delegate a event podľa vlastníctva volania.", "Navrhnúť odhlásenie z udalosti podľa životnosti odberateľa."),
    "linq": ("Rozlíšiť lazy LINQ dopyt od materializovaného výsledku.", "Vybrať kolekciu podľa kľúča, poradia a zložitosti prístupu."),
    "resources": ("Určiť, kto vlastní IDisposable zdroj a kde sa dispose-ne.", "Zachytiť konkrétnu výnimku na správnej hranici."),
    "async": ("Spracovať Task vrátane chyby a zrušenia.", "Navrhnúť timeout a CancellationToken pre I/O operáciu."),
    "projects": ("Vysvetliť úlohu csproj, target frameworku a NuGetu.", "Oddeliť konfiguráciu a tajomstvá od zdrojového kódu."),
    "quality": ("Napísať test pre bežný aj hraničný priebeh metódy.", "Použiť analyzér, debugger alebo profiler podľa typu problému."),
}

CSHARP_VISUALIZATION_IDS = {
    "linq": ("csharp-linq-deferred",),
    "async": ("csharp-async-task",),
}

CSHARP_EXAMPLES = [
    {"key": "first-program", "page_key": "program", "position": 10, "title": "Pozdrav z top-level programu", "description": "Top-level statement je čitateľný vstupný bod malého konzolového projektu.", "source": "using System;\n\nConsole.WriteLine(\"Ahoj, svet!\");\n", "stdin": "", "standard": "csharp"},
    {"key": "nullable-pattern", "page_key": "values", "position": 10, "title": "Text len ak má obsah", "description": "Pattern súčasne vylúči null a prázdny text.", "source": "using System;\n\nstring? suppliedName = \"Ada\";\n\nif (suppliedName is { Length: > 0 } name)\n{\n    Console.WriteLine(name);\n}\n", "stdin": "", "standard": "csharp"},
    {"key": "clamp-score", "page_key": "flow", "position": 10, "title": "Metóda s jasným rozsahom", "description": "Math.Clamp drží výsledok v zadaných medziach.", "source": "using System;\n\nstatic int ClampScore(int value) => Math.Clamp(value, 0, 100);\n\nConsole.WriteLine(ClampScore(142));\n", "stdin": "", "standard": "csharp"},
    {"key": "score-record", "page_key": "records", "position": 10, "title": "Dátová hodnota cez record", "description": "Record vyjadruje hodnotu, ktorú porovnávame podľa jej obsahu.", "source": "using System;\n\nvar score = new Score(\"Ada\", 86);\nConsole.WriteLine($\"{score.Name}: {score.Value}\");\n\npublic sealed record Score(string Name, int Value);\n", "stdin": "", "standard": "csharp"},
    {"key": "generic-box", "page_key": "interfaces", "position": 10, "title": "Generický kontajner bez castu", "description": "Typový parameter uchová informáciu o hodnote až po jej prečítanie.", "source": "using System;\n\nConsole.WriteLine(new Box<int>(42).Value);\n\npublic sealed class Box<T>(T value)\n{\n    public T Value { get; } = value;\n}\n", "stdin": "", "standard": "csharp"},
    {"key": "event-notice", "page_key": "delegates", "position": 10, "title": "Udalosť s riadeným vyvolaním", "description": "Odberateľ sa prihlási cez event, no udalosť vyvolá iba jej vlastník.", "source": "using System;\n\nvar announcer = new Announcer();\nannouncer.Message += message => Console.WriteLine(message);\nannouncer.Publish(\"hotovo\");\n\npublic sealed class Announcer\n{\n    public event Action<string>? Message;\n\n    public void Publish(string message) => Message?.Invoke(message);\n}\n", "stdin": "", "standard": "csharp"},
    {"key": "linq-scores", "page_key": "linq", "position": 10, "title": "Filter a transformácia cez LINQ", "description": "Dopyt sa materializuje až pri ToArray.", "source": "using System;\nusing System.Linq;\n\nint[] scores = [4, 7, 10, 3];\nvar passing = scores.Where(score => score >= 5).Select(score => score * 10).ToArray();\n\nConsole.WriteLine(string.Join(\", \", passing));\n", "stdin": "", "standard": "csharp"},
    {"key": "using-reader", "page_key": "resources", "position": 10, "title": "Zdroj s deterministickým Dispose", "description": "using declaration zavrie StringReader pri opustení bloku.", "source": "using System;\nusing System.IO;\n\nusing var reader = new StringReader(\"prvý riadok\");\nConsole.WriteLine(reader.ReadLine());\n", "stdin": "", "standard": "csharp"},
    {"key": "await-task", "page_key": "async", "position": 10, "title": "Čakanie bez blokovania", "description": "Top-level await počká na Task a až potom vypíše výsledok.", "source": "using System;\nusing System.Threading.Tasks;\n\nawait Task.Delay(10);\nConsole.WriteLine(\"hotovo\");\n", "stdin": "", "standard": "csharp"},
]


RUBY_LANGUAGE = {
    "code": "ruby",
    "title": "Ruby",
    "summary": "Praktická učebnica Ruby: objekty, bloky, kolekcie, moduly, výnimky a projektová disciplína.",
}

RUBY_PAGES = [
    {"key": "overview", "parent_key": "", "kind": "overview", "position": 0, "title": "Ruby: učebnica a referencia", "summary": "Moderné Ruby od čitateľného skriptu po objektový model, mixiny a Bundler.", "content": {"lead": "Ruby je dynamický objektový jazyk: takmer všetko je objekt a metóda je vždy hľadaná podľa konkrétneho prijímača. Jeho stručnosť je silná, len keď nezakryje tok dát, vedľajšie účinky alebo hranice vstupu.", "sections": [{"title": "Ako kurz používať", "paragraphs": ["Príklady používajú aktuálny Ruby a štandardnú knižnicu. Pri každej metóde si všímaj, či vracia novú hodnotu, mení prijímač alebo môže vyhodiť výnimku."], "bullets": ["Odsadenie je dohoda o čitateľnosti, blok uzatvára end.", "Bez ! metóda zvyčajne nemení prijímač; výnimky existujú, preto čítaj dokumentáciu.", "Blok má vlastný účel a nemá skrývať neobmedzenú prácu."]}, {"title": "Bezpečná práca", "paragraphs": ["Vstup zo súboru, HTTP alebo environmentu je nedôveryhodný. Validuj ho na hranici, príkazy nespájaj do shellového textu a dáta nemeň na kód cez eval."], "callout": "Dynamika Ruby nie je dôvod vzdať sa kontraktov. Jasné mená, malé metódy a testy sú ešte dôležitejšie."}]}},
    {"key": "foundations", "parent_key": "", "kind": "chapter", "position": 10, "title": "Hodnoty, metódy a bloky", "summary": "Skripty, objekty, mená, riadenie toku, metódy, keyword argumenty a bloky.", "content": {"lead": "Ruby má dynamické typy, ale pomenované hodnoty a presné vstupy metód stále tvoria kontrakt programu. Čitateľná metóda ukáže, čo očakáva a čo môže meniť.", "sections": [{"title": "V tejto kapitole", "bullets": ["Spustenie skriptu a návratový stav.", "nil, pravdivosť, text a čísla.", "Vetvy, iterácie, metódy a bloky."]}]}},
    {"key": "program", "parent_key": "foundations", "kind": "lesson", "position": 20, "title": "Prvý skript a vstupný bod", "summary": "ruby main.rb, puts, warn, ARGV, exit a oddelenie logiky od spustenia.", "content": {"lead": "Ruby skript spustíš príkazom ruby main.rb. puts zapisuje bežný výstup a warn diagnostiku; vstupný kód drž krátky, aby logika ostala samostatne testovateľná.", "sections": [{"title": "Spustenie", "paragraphs": ["ARGV obsahuje argumenty príkazového riadka. Návratový stav nastav cez exit alebo nech skript prirodzene skončí úspešne; chybu neschovávaj len výpisom textu.", "require načíta knižnicu alebo vlastný súbor. Vedľajšie účinky pri require drž minimálne, aby bol import predvídateľný."], "bullets": ["puts pridá nový riadok.", "warn patrí na stderr.", "freeze string literal nie je univerzálna náhrada návrhu nemennosti."]}, {"title": "Čitateľný štart", "paragraphs": ["Väčší skript zvyčajne zabalí štart do metódy main a na konci ju explicitne zavolá. Testy potom volajú čisté metódy bez napodobňovania konzoly."], "callout": "Nespúšťaj dlhú prácu pri načítaní súboru iba preto, že sa to zdá pohodlné. require má sprístupniť rozhranie, nie potajme meniť svet."}]}},
    {"key": "values", "parent_key": "foundations", "kind": "lesson", "position": 30, "title": "Objekty, nil a porovnanie", "summary": "Integer, Float, String, Symbol, nil, true/false, ==, eql? a identity.", "content": {"lead": "V Ruby sú iba false a nil nepravdivé. Prázdny text, nula a prázdne pole sú pravdivé, preto podmienka nemá nahrádzať overenie obsahu.", "sections": [{"title": "Hodnoty a mená", "paragraphs": ["Priradenie viaže meno na objekt. String je meniteľný, Symbol sa často používa ako pomenovaný stabilný štítok a nil vyjadruje neprítomnosť, ktorú treba v kontrakte vedome spracovať.", "== porovnáva význam hodnoty podľa implementácie typu. equal? porovnáva identitu a v bežnom aplikačnom kóde je zriedkavý."], "bullets": ["Použi nil? pre otázku na neprítomnosť.", "Operátor || nahradí nil aj false.", "Bezpečná navigácia &. pomôže len pre očakávané voliteľné spojenie."]}, {"title": "Konverzie", "paragraphs": ["Integer(text, exception: false) alebo konkrétne parsovanie oddelia neplatný vstup od aritmetiky. Float nie je presný desatinný typ; pre peniaze zváž BigDecimal a jasnú jednotku."], "callout": "Nevolaj to_i na nedôveryhodnom texte, ak potrebuješ rozlíšiť '0' od neplatného vstupu: neplatný text tiež vráti nulu."}]}},
    {"key": "methods", "parent_key": "foundations", "kind": "lesson", "position": 40, "title": "Metódy, keyword argumenty a bloky", "summary": "def, návratová hodnota, keyword argumenty, yield, Proc, lambda a closure.", "content": {"lead": "Metóda vracia posledný vyhodnotený výraz, no explicitný return je užitočný pre skorý návrat. Keyword argumenty robia volanie čitateľným a blok dáva volajúcemu riadený háčik bez vlastného callbackového protokolu.", "sections": [{"title": "Rozhranie", "paragraphs": ["Povinný keyword parameter bráni zámene argumentov. Predvolená hodnota má byť nemenná alebo sa má vytvoriť v tele metódy, keď ide o meniteľnú kolekciu.", "yield zavolá odovzdaný blok. Metóda má jasne povedať, koľkokrát a s akými hodnotami blok volá; blok so skrytými vedľajšími účinkami sa ťažko skladá."], "bullets": ["each patrí k efektu nad každým prvkom.", "map vracia transformovanú kolekciu.", "lambda kontroluje aritu a return inak než obyčajný Proc."]}, {"title": "Closure", "paragraphs": ["Blok môže zachytiť okolité mená. Ak tieto mená mení, vzniká zdieľaný stav, ktorý treba pomenovať a testovať rovnako ako atribút objektu."], "callout": "Nepoužívaj metaprogramovanie alebo send iba na obídenie nejasného rozhrania. Najprv skús pomenovať normálnu metódu."}]}},
    {"key": "objects", "parent_key": "", "kind": "chapter", "position": 50, "title": "Triedy, moduly a kolekcie", "summary": "Zapuzdrenie, moduly, mixiny, Enumerable, Hash a method lookup.", "content": {"lead": "Ruby trieda určuje, kde objekt hľadá metódu; moduly môžu poskytovať pomenovaný spoločný kód. Kompozícia a malé rozhrania sú často zrozumiteľnejšie než hlboké dedenie.", "sections": [{"title": "V tejto kapitole", "bullets": ["class, initialize, attr_reader a invarianty.", "module, include, prepend a hľadanie metód.", "Array, Hash, Enumerable a lazy iterácia."]}]}},
    {"key": "classes", "parent_key": "objects", "kind": "lesson", "position": 60, "title": "Triedy, stav a invarianty", "summary": "initialize, instance variables, attr_reader, visibility, composition a testovateľné objekty.", "content": {"lead": "initialize vytvorí platný objekt. Atribút čítaj cez attr_reader, no meniteľný stav neposkytuj bez rozmyslu: zmena s doménovým významom má byť vlastná metóda s overením.", "sections": [{"title": "Malý objekt", "paragraphs": ["Inštančná premenná patrí konkrétnemu objektu, triedna premenná má zložitejšie dedičné pravidlá a zvyčajne nie je prvá voľba pre stav. Prednosť má explicitná závislosť odovzdaná do initialize.", "public, private a protected hovoria, ktoré metódy sú súčasťou kontraktu. private nie je bezpečnostná hranica, ale ochrana čitateľnosti a invariantov."], "bullets": ["Kompozícia vloží spolupracujúci objekt.", "Dedenie musí zachovať kontrakt rodiča.", "dup a clone majú vlastné pravidlá; kopírovanie stavu navrhni vedome."]}, {"title": "Chyby návrhu", "paragraphs": ["Objekt, ktorý číta súbor, formátuje HTML, volá sieť a zároveň počíta výsledok, má príliš veľa zodpovedností. Rozdeľ hranice tak, aby čisté jadro šlo testovať bez I/O."], "callout": "attr_accessor pre každý atribút nerobí triedu bezpečnejšou. Často len sprístupní stav bez pravidiel."}]}},
    {"key": "modules", "parent_key": "objects", "kind": "lesson", "position": 70, "title": "Moduly, mixiny a hľadanie metód", "summary": "module, include, prepend, extend, ancestors a konflikty mien.", "content": {"lead": "include vloží modul medzi triedu a jej predka pri hľadaní inštančnej metódy; prepend ho vloží pred triedu. Je to mocné, no zmena poradia môže prekvapiť aj skúseného čitateľa.", "sections": [{"title": "Zdieľanie správania", "paragraphs": ["Modul má vyjadriť jednu schopnosť, nie náhodný košík pomocníkov. Ak potrebuje stav, jasne povedz, ktoré metódy alebo inštančné premenné očakáva.", "extend pridá metódy ako singleton metódy cieľa. Na menné priestory používaj moduly tiež, ale nemiešaj zoskupenie mien s mixinom iba preto, že syntax je rovnaká."], "bullets": ["ancestors ukáže poradie hľadania metód.", "super pokračuje na ďalšiu implementáciu v poradí.", "Konflikt metód rieš návrhom, nie tichým prepisovaním."]}, {"title": "Metaprogramovanie", "paragraphs": ["define_method, method_missing a eval dávajú jazyku flexibilitu, no zhoršujú navigáciu, typovú kontrolu a diagnostiku. Použi ich až keď obyčajná trieda alebo modul nevie vyjadriť problém."], "callout": "method_missing bez respond_to_missing? vytvorí rozhranie, ktoré klame nástroje aj volajúceho."}]}},
    {"key": "collections", "parent_key": "objects", "kind": "lesson", "position": 80, "title": "Array, Hash a Enumerable", "summary": "map, filter, reduce, each_with_object, Hash prístup, mutácia a lazy spracovanie.", "content": {"lead": "Array drží poradie, Hash mapuje kľúče na hodnoty a Enumerable ponúka spoločné operácie nad mnohými kolekciami. Vyber metódu podľa výsledku, nie podľa toho, že sa dá napísať najkratšie.", "sections": [{"title": "Transformácia", "paragraphs": ["map vytvorí nové hodnoty, select vyberie podmnožinu a reduce skladá tok do jedného výsledku. each_with_object je jasný, keď vedome buduješ Hash alebo inú akumuláciu.", "Metódy s ! často menia prijímač, ale nie je to formálna garancia. Pri zdieľanom poli alebo Hashi je mutácia súčasťou kontraktu, nie detail implementácie."], "bullets": ["fetch rozlíši chýbajúci kľúč od hodnoty nil.", "sort_by počíta triediaci kľúč efektívnejšie než sort s drahým porovnaním.", "lazy odkladá prácu na iteráciu."]}, {"title": "Hraničné prípady", "paragraphs": ["Nemeň pole pri iterovaní, ak to algoritmus výslovne nepodporuje. Keď záleží na poradí Hashu alebo dátovom formáte, napíš ho do kontraktu."], "callout": "Symbolické kľúče a textové kľúče nie sú rovnaké. Pri JSON hranici si zvoľ jeden model a nemiešaj ho potichu."}]}},
    {"key": "projects", "parent_key": "", "kind": "chapter", "position": 90, "title": "Projekt, chyby a kvalita", "summary": "Gems, Bundler, výnimky, zdroje, testy, bezpečnosť a výkon.", "content": {"lead": "Praktický Ruby projekt potrebuje opakovateľné závislosti, jasné hranice chýb a testy. Flexibilita jazyka je bezpečná až vtedy, keď projekt má poriadok v vstupoch, výstupoch a vedľajších účinkoch.", "sections": [{"title": "V tejto kapitole", "bullets": ["Gemfile, Bundler, require a štruktúra projektu.", "Výnimky, File, ensure a vlastníctvo zdrojov.", "Minitest, logging, bezpečný vstup a meranie."]}]}},
    {"key": "dependencies", "parent_key": "projects", "kind": "lesson", "position": 100, "title": "Gems, Bundler a štruktúra projektu", "summary": "Gemfile, Gemfile.lock, bundle exec, require a malé moduly.", "content": {"lead": "Gemfile opisuje závislosti projektu a Gemfile.lock zaznamená konkrétne vyriešené verzie. bundle exec spustí nástroj v tom istom prostredí, ktoré projekt deklaruje.", "sections": [{"title": "Opakovateľné prostredie", "paragraphs": ["Gem pridaj s dôvodom, verziou a licenciou. Aktualizácia závislostí má prejsť testami; nepredpokladaj, že globálne nainštalovaný gem existuje aj na inom stroji.", "Súbory rozdeľ podľa zodpovednosti a require drž smerom od vstupu k jadru. Cyklus require často znamená, že dva pojmy sú príliš prepletené."], "bullets": ["bundle install pripraví závislosti.", "bundle exec ruby ... použije projektové verzie.", "Názov gemu nie je dôkaz dôveryhodnosti ani bezpečnosti."]}, {"title": "Konfigurácia", "paragraphs": ["Konfiguráciu načítaj na jednej hranici, over jej tvar a tajomstvá nedávaj do zdroja. Environment premenná je vstup ako každý iný: môže chýbať alebo mať zlý formát."], "callout": "Lockfile nekopíruj naslepo medzi nesúvisiacimi projektmi. Je záznamom konkrétneho dependency grafu."}]}},
    {"key": "errors", "parent_key": "projects", "kind": "lesson", "position": 110, "title": "Výnimky, súbory a bezpečné hranice", "summary": "begin/rescue/ensure, konkrétne chyby, File.open s blokom, JSON a shell.", "content": {"lead": "rescue patrí k chybe, ktorú vieš zmysluplne spracovať. Blok pri File.open uzavrie súbor aj pri výnimke, takže životnosť zdroja ostáva pri mieste jeho použitia.", "sections": [{"title": "Hranica chyby", "paragraphs": ["Zachyť konkrétny typ, pridaj bezpečný kontext a nechaj neočakávanú chybu dôjsť k poslednej aplikačnej hranici. ensure patrí k nutnému uprataniu, keď blok nie je vhodný.", "JSON.parse číta formát, nie doménový model. Po parse over kľúče, typy a povinné hodnoty; YAML a Marshal z nedôveryhodného zdroja môžu mať oveľa vážnejšie následky."], "bullets": ["File.open(path, 'r') { |file| ... } uzavrie súbor.", "system s poľom argumentov neprejde shellom.", "Log neobsahuje heslá ani tokeny."]}, {"title": "Bezpečnosť", "paragraphs": ["Text od používateľa nepatrí do SQL, HTML ani shellu bez API, ktoré vie správne pracovať s parametrami alebo escapingom daného kontextu."], "callout": "rescue StandardError => error; bez rozhodnutia o obnove iba skryje problém. Výnimku nelikviduj prázdnym blokom."}]}},
    {"key": "quality", "parent_key": "projects", "kind": "lesson", "position": 120, "title": "Testy, diagnostika a výkon", "summary": "Minitest, assertions, warning, logging, debugger, Benchmark a profilovanie.", "content": {"lead": "Test chráni správanie, nie náhodný spôsob implementácie. Ruby má Minitest v štandardnej knižnici; čisté metódy sa testujú bez súborov, siete a náhodného času.", "sections": [{"title": "Spätná väzba", "paragraphs": ["Napíš test pre bežný vstup, hranicu a chybový tvar. Chyba testu má pomenovať kontrakt, nie iba interný krok, ktorý sa náhodou dnes používa.", "warning a logging oddeľ od dátového výstupu. Debugger zodpovie otázku o konkrétnom priebehu, Benchmark pomôže porovnať malý scenár a profiler odhalí skutočný hot path."], "bullets": ["Minitest::Test je súčasťou Ruby.", "RuboCop je externý nástroj štýlu a statickej analýzy.", "Meraj reprezentatívny vstup, nie jeden pohodlný príklad."]}, {"title": "Odolnosť", "paragraphs": ["Závislosti aktualizuj spolu s testami a pravidelne kontroluj bezpečnostné advisories. Vnútorný objekt môže predpokladať overený model; validácia má byť sústredená pri vstupe."], "callout": "Optimalizácia, ktorá znečitateľní kód bez nameraného prínosu, je dlh, nie výkonová výhra."}]}},
]

RUBY_LEARNING_GOALS = {
    "program": ("Spustiť Ruby skript s jasným vstupným bodom.", "Rozlíšiť bežný výstup, diagnostiku a návratový stav."),
    "values": ("Rozlíšiť nil, false a ostatné pravdivé hodnoty.", "Bezpečne spracovať textový vstup bez straty významu."),
    "methods": ("Navrhnúť metódu s čitateľnými keyword argumentmi.", "Použiť blok s jasným okamihom a počtom volaní."),
    "classes": ("Navrhnúť objekt s malým rozhraním a invariantom.", "Rozlíšiť kompozíciu od dedenia."),
    "modules": ("Vysvetliť rozdiel medzi include, prepend a extend.", "Predpovedať, kde Ruby hľadá metódu."),
    "collections": ("Vybrať each, map, select alebo reduce podľa výsledku.", "Rozpoznať mutáciu kolekcie a chýbajúci Hash kľúč."),
    "dependencies": ("Vysvetliť úlohu Gemfile, lockfile a bundle exec.", "Oddeliť konfiguráciu a tajomstvá od zdrojového kódu."),
    "errors": ("Zachytiť konkrétnu chybu na zmysluplnej hranici.", "Použiť blok pri File.open na jasnú životnosť zdroja."),
    "quality": ("Napísať malý test pre kontrakt metódy.", "Vybrať debugger, benchmark alebo profiler podľa otázky."),
}

RUBY_VISUALIZATION_IDS = {
    "modules": ("ruby-method-lookup",),
}

RUBY_EXAMPLES = [
    {"key": "first-program", "page_key": "program", "position": 10, "title": "Pozdrav z Ruby skriptu", "description": "Metóda main drží vstupný krok oddelene od vlastnej logiky.", "source": "def main\n  puts 'Ahoj, svet!'\nend\n\nmain\n", "stdin": "", "standard": "ruby"},
    {"key": "optional-name", "page_key": "values", "position": 10, "title": "Voliteľné meno bez zamenenia nuly", "description": "Bezpečná navigácia zohľadní nil bez všeobecnej náhrady hodnoty.", "source": "profile = { name: 'Ada' }\nname = profile[:name]&.strip\n\nputs name || 'neznámy'\n", "stdin": "", "standard": "ruby"},
    {"key": "keyword-score", "page_key": "methods", "position": 10, "title": "Keyword argument s predvolenou hodnotou", "description": "Pomenovaný argument ukazuje význam hodnoty priamo pri volaní.", "source": "def label(name:, score: 0)\n  \"#{name}: #{score}\"\nend\n\nputs label(name: 'Ada', score: 9)\n", "stdin": "", "standard": "ruby"},
    {"key": "bounded-score", "page_key": "classes", "position": 10, "title": "Trieda, ktorá chráni rozsah", "description": "Inicializácia odmietne skóre mimo doménového rozsahu.", "source": "class Score\n  attr_reader :value\n\n  def initialize(value)\n    raise ArgumentError, 'skóre je od 0 po 100' unless (0..100).cover?(value)\n\n    @value = value\n  end\nend\n\nputs Score.new(86).value\n", "stdin": "", "standard": "ruby"},
    {"key": "auditable-mixin", "page_key": "modules", "position": 10, "title": "Mixin s pomenovanou schopnosťou", "description": "include sprístupní metódu modulu inštancii triedy.", "source": "module Auditable\n  def audit_label\n    \"audit: #{name}\"\n  end\nend\n\nclass Report\n  include Auditable\n  attr_reader :name\n\n  def initialize(name)\n    @name = name\n  end\nend\n\nputs Report.new('súhrn').audit_label\n", "stdin": "", "standard": "ruby"},
    {"key": "group-scores", "page_key": "collections", "position": 10, "title": "Súčet bodov podľa mena", "description": "each_with_object buduje Hash s jasným počiatočným stavom.", "source": "scores = [['Ada', 4], ['Linus', 3], ['Ada', 5]]\ntotals = scores.each_with_object(Hash.new(0)) do |(name, score), result|\n  result[name] += score\nend\n\ntotals.each { |name, total| puts \"#{name}: #{total}\" }\n", "stdin": "", "standard": "ruby"},
    {"key": "safe-file", "page_key": "errors", "position": 10, "title": "Súbor uzavretý blokom", "description": "Tempfile sa otvorí iba na potrebný blok a následne sa automaticky zavrie.", "source": "require 'tempfile'\n\nTempfile.create('lesson') do |file|\n  file.write(\"Ahoj\\n\")\n  file.rewind\n  puts file.readline\nend\n", "stdin": "", "standard": "ruby"},
    {"key": "minitest", "page_key": "quality", "position": 10, "title": "Malý test cez Minitest", "description": "Test overí bežný aj hraničný výsledok čistej metódy.", "source": "require 'minitest/autorun'\n\ndef maximum(left, right)\n  left > right ? left : right\nend\n\nclass MaximumTest < Minitest::Test\n  def test_values\n    assert_equal 3, maximum(2, 3)\n    assert_equal(-2, maximum(-2, -2))\n  end\nend\n", "stdin": "", "standard": "ruby"},
]
