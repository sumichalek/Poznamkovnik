"""Vstavaný, používateľovi nezávislý obsah prvej učebnice C."""

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
            "lead": "Základy C sú krátke, ale presné: program pozostáva z deklarácií a funkcií, pričom vykonávanie začína vo funkcii main.",
            "sections": [
                {"title": "V tejto kapitole", "bullets": ["Stavba programu a kompilácia.", "Typy, rozsahy a konverzie.", "Podmienky, cykly a funkcie."]}
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
            "lead": "Prekladateľ zoberie zdrojový súbor, preverí jeho syntax a vytvorí spustiteľný program. Funkcia main je jeho štandardný vstupný bod.",
            "sections": [
                {
                    "title": "Minimálny tvar",
                    "paragraphs": [
                        "#include sprístupní deklarácie z hlavičkového súboru. Funkcia printf je deklarovaná v stdio.h.",
                        "int main(void) znamená, že main neprijíma argumenty a vracia celé číslo operačnému systému. Návrat 0 bežne znamená úspech."
                    ],
                    "callout": "Nepridávaj deklarácie funkcií ručne namiesto správnej hlavičky. Prekladateľ by potom nemusel odhaliť nesúlad argumentov."
                },
                {
                    "title": "Varovania sú súčasťou práce",
                    "paragraphs": ["Pre bežnú lokálnu kompiláciu používaj aspoň -Wall -Wextra -Wpedantic. Varovanie často upozorní na chybu skôr než test."],
                    "bullets": ["Zdroj: main.c", "Preklad: gcc -std=c17 -Wall -Wextra -Wpedantic main.c -o program", "Spustenie: ./program"]
                }
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
            "lead": "Typ určuje veľkosť, rozsah a pravidlá operácií s hodnotou. Premenná v C má vždy deklarovaný typ.",
            "sections": [
                {
                    "title": "Základné typy",
                    "paragraphs": ["Najčastejšie použiješ int pre bežné celé číslo, double pre výpočty s desatinnou časťou a char pre jeden znak. Presné šírky poskytuje stdint.h: int32_t, uint64_t a podobne."],
                    "bullets": ["const vyjadruje, že hodnotu cez dané meno nebudeš meniť.", "sizeof vracia veľkosť v bajtoch; výsledok má typ size_t.", "Pri delení dvoch int vznikne celočíselný výsledok. Pre desatinný použi aspoň jeden operand typu double."]
                },
                {
                    "title": "Konverzie",
                    "paragraphs": ["Implicitná konverzia môže zahodiť časť hodnoty alebo zmeniť znamienko. Explicitný pretypovací operátor ju síce zapíše, ale sám o sebe nerieši stratu dát."],
                    "callout": "Nikdy nepredpokladaj, že int má konkrétny počet bitov. Ak na šírke záleží, použi typ z stdint.h."
                }
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
            "lead": "Podmienka v C považuje nulu za nepravdu a každú nenulovú hodnotu za pravdu. Pre čitateľnosť však používaj výrazy, ktoré prirodzene vracajú porovnanie.",
            "sections": [
                {
                    "title": "Výber vetvy",
                    "paragraphs": ["if je vhodné pre všeobecné podmienky. switch je pre výber z diskrétnych hodnôt; nezabudni na break, inak vykonávanie pokračuje do ďalšieho prípadu."],
                    "bullets": ["Použi zátvorky aj pri jedinom príkaze, keď tým zlepšíš čitateľnosť.", "Rozlišuj = (priradenie) a == (porovnanie).", "default v switch ošetrí hodnoty, ktoré nepatria do žiadneho case."]
                },
                {"title": "Opakovanie", "paragraphs": ["for sa hodí pri známom počte krokov, while pri opakovaní, ktorého koniec závisí od podmienky. Vždy si pomenuj invariant: čo musí zostať pravda po každom priechode."]}
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
            "lead": "Výraz vypočíta hodnotu. Operátory ju kombinujú, porovnávajú alebo menia. Najmä v podmienkach je dôležité, aby bol zápis zrozumiteľný aj bez memorovania celej tabuľky priorít.",
            "sections": [
                {"title": "Porovnanie a logika", "paragraphs": ["Porovnávacie operátory <, <=, >, >=, == a != vracajú 0 alebo 1. Logické &&, || a ! z nich skladajú podmienky."], "bullets": ["&& skončí hneď pri prvej nepravdivej časti.", "|| skončí hneď pri prvej pravdivej časti.", "Toto skrátené vyhodnocovanie je užitočné pri kontrole ukazovateľa pred jeho použitím."]},
                {"title": "Priorita a zátvorky", "paragraphs": ["Násobenie sa vyhodnocuje pred sčítaním, porovnanie pred logickým && a priradenie patrí medzi operátory s nízkou prioritou. Ak má výraz obsahovať rozhodnutie, zátvorky sú často lacnejšie než neskoršie hľadanie chyby."], "callout": "Do podmienky nepíš vedľajší účinok, ak ho vieš vykonať samostatným príkazom. Zápis if ((value = read()) > 0) je možný, ale ľahko sa prehliadne."},
                {"title": "Ternárny operátor", "paragraphs": ["Podmienka ? hodnota_ak_pravda : hodnota_ak_nepravda je praktická pre krátky výber jednej hodnoty. Pre viac príkazov alebo zložité vetvy použi obyčajné if a else."]}
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
            "lead": "Funkcie v C predávajú parametre hodnotou. Aj ukazovateľ sa teda skopíruje, no umožní funkcii pracovať s objektom, na ktorý ukazuje.",
            "sections": [
                {"title": "Rozhranie funkcie", "paragraphs": ["Deklarácia v hlavičke opisuje, ako sa funkcia používa; definícia v zdrojovom súbore opisuje jej vykonanie. Návratová hodnota by mala vyjadriť výsledok alebo stav chyby."], "bullets": ["Funkcia void nič nevracia.", "Statická funkcia je viditeľná iba v jednom zdrojovom súbore.", "Nevracaj ukazovateľ na lokálnu premennú; po návrate funkcie už neexistuje."]},
                {"title": "Kontrakty", "paragraphs": ["Zapíš si, ktoré ukazovatele môžu byť NULL, kto vlastní alokovanú pamäť a aký stav znamená návratová hodnota. Takéto pravidlá sú dôležitejšie než samotná syntax."]}
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
            "lead": "Rozsah určuje, odkiaľ môžeš používať meno premennej alebo funkcie. Životnosť hovorí, ako dlho existuje samotný objekt. Sú to dve príbuzné, ale odlišné veci.",
            "sections": [
                {"title": "Lokálne a statické objekty", "paragraphs": ["Lokálna premenná vzniká pri vstupe do bloku a po jeho opustení už neexistuje. Lokálna premenná so static si uchová hodnotu medzi volaniami funkcie, ale jej meno ostáva viditeľné iba vo funkcii."], "bullets": ["Premenné definované v zložených zátvorkách platia iba v danom bloku.", "static pri funkcii obmedzí jej viditeľnosť na jeden zdrojový súbor.", "Globálne dáta používaj striedmo; skrývajú závislosti medzi časťami programu."]},
                {"title": "Čo znamená const", "paragraphs": ["const int limit znamená, že cez dané meno limit nepriradíš novú hodnotu. const int *text chráni hodnotu, na ktorú ukazovateľ smeruje; int *const text chráni samotný ukazovateľ pred presmerovaním."], "callout": "const nie je náhrada vlastníctva ani kontroly platnosti ukazovateľa. Pomáha vyjadriť úmysel rozhrania a nechať prekladateľ zachytiť časť omylov."}
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
            "lead": "Pole obsahuje prvky rovnakého typu v súvislej pamäti. Index prvého prvku je 0 a platný posledný index je počet prvkov mínus jedna.",
            "sections": [
                {"title": "Hranice", "paragraphs": ["Prístup mimo poľa má nedefinované správanie. Prekladateľ ho nemusí vedieť odhaliť a program môže zdanlivo fungovať, kým sa prostredie nezmení."], "bullets": ["sizeof pole funguje iba tam, kde je premenná naozaj poľom, nie po odovzdaní do funkcie.", "&hodnota vytvorí adresu objektu.", "*ukazovatel pristupuje k objektu na danej adrese.", "NULL znamená, že ukazovateľ neukazuje na platný objekt."]},
                {"title": "Parameter poľa", "paragraphs": ["V parametri funkcie sa pole správa ako ukazovateľ na prvý prvok. Veľkosť preto odovzdaj samostatne, obvykle ako size_t."]}
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
            "lead": "C reťazec je pole char ukončené znakom \\0. Jeho dĺžka nie je uložená oddelene, preto funkcie zo string.h prechádzajú pamäť, kým nulový znak nenájdu.",
            "sections": [
                {"title": "Dôležité pravidlo", "paragraphs": ["Pole char meno[32] môže obsahovať najviac 31 viditeľných znakov a koncový nulový znak. Pri načítaní cez scanf musí šírka formátu rešpektovať toto miesto."], "bullets": ["strlen nepočíta koncový nulový znak.", "strcpy je bezpečné iba vtedy, keď už vieš, že cieľ je dosť veľký.", "Na riadkový vstup uprednostni fgets a potom over výsledok."]},
                {"title": "Textové literály", "paragraphs": ["Literál \"ahoj\" sa nemá meniť. Pre vlastné upraviteľné pole použi char text[] = \"ahoj\"."]}
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
            "lead": "Ukazovateľ uchováva adresu objektu. Sám objekt nemení, ale operátor * umožní pristúpiť k hodnote na danej adrese. Používaj ho vtedy, keď funkcia potrebuje zmeniť objekt volajúceho alebo pracovať s dátovým blokom.",
            "sections": [
                {"title": "Adresa a dereferencovanie", "paragraphs": ["&value vytvorí adresu premennej value. Ak int *number túto adresu uchováva, *number je opäť samotné celé číslo. Typ ukazovateľa musí zodpovedať objektu, na ktorý ukazuje."], "bullets": ["Ukazovateľ môže byť NULL, ak nemá platný cieľ.", "Pred dereferencovaním over NULL, pokiaľ ho kontrakt nevylučuje.", "Adresa lokálnej premennej je platná iba do skončenia jej životnosti."]},
                {"title": "Výstupný parameter", "paragraphs": ["Funkcia môže vrátiť stav cez návratovú hodnotu a výsledok zapísať cez ukazovateľ. Takéto rozhranie najprv overí vstupné ukazovatele a až potom mení výstup."], "callout": "Ukazovateľ nie je len technický detail. V názve, dokumentácii alebo type má byť jasné, či funkcia údaje iba číta, mení, preberá ich vlastníctvo alebo vracia nový objekt."},
                {"title": "Aritmetika ukazovateľov", "paragraphs": ["Pri poli môžeš posunúť ukazovateľ o prvky rovnakého typu. Platí to iba v rámci daného poľa a tesne za jeho koncom; dereferencovať smieš iba ukazovateľ na skutočný prvok."]}
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
            "lead": "struct spája hodnoty, ktoré spolu tvoria jeden koncept. enum vyjadruje malú pomenovanú množinu stavov. typedef môže zjednodušiť opakované názvy typov.",
            "sections": [
                {"title": "Štruktúra", "paragraphs": ["Prístup k členu hodnoty je bodkou: bod.x. Ak máš ukazovateľ na štruktúru, použi šípku: bod_ptr->x."], "bullets": ["Inicializuj všetky členy, ideálne menovanou inicializáciou.", "Nevkladaj do struct nejasné vlastníkstvo ukazovateľov bez jasného deštruktora.", "enum zlepšuje čitateľnosť stavu, ale nie je automatickou kontrolou všetkých neplatných celočíselných hodnôt."]},
                {"title": "Návrh dát", "paragraphs": ["Dobrý dátový typ má jasné invarianty: napríklad počet prvkov nikdy nepresiahne kapacitu a ukazovateľ je buď NULL, alebo smeruje na platnú alokáciu."]}
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
            "lead": "Bitové operátory pracujú priamo s binárnym zápisom neznamienkových celých čísel. Hodí sa to pre príznaky, protokoly, zariadenia a kompaktné uloženie viacerých stavov.",
            "sections": [
                {"title": "Masky príznakov", "paragraphs": ["Operátory & a | vyberajú alebo nastavujú bity, ^ ich prepína a ~ ich invertuje. Konštantu pre jeden príznak vytvoríš napríklad ako 1u << 3."], "bullets": ["Zapnutie: flags |= FEATURE_SAVE.", "Overenie: (flags & FEATURE_SAVE) != 0u.", "Vypnutie: flags &= ~FEATURE_SAVE."]},
                {"title": "Posuny a typy", "paragraphs": ["Používaj neznamienkové literály, napríklad 1u, a ak záleží na šírke, typy uint32_t alebo uint64_t z stdint.h. Posun o záporný počet, alebo o počet aspoň taký veľký ako šírka typu, má nedefinované správanie."], "callout": "Bitové operátory nie sú náhradou booleovských podmienok. Pre bežné rozhodovanie používaj && a ||; bitové masky si nechaj tam, kde modeluješ konkrétne bity."},
                {"title": "Hranice čísel", "paragraphs": ["<limits.h> obsahuje INT_MIN, INT_MAX a hranice ďalších základných typov. Znamienkové pretečenie je nedefinované správanie, preto rozsah prever skôr než hodnotu sčítaš alebo vynásobíš."]}
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
            "lead": "Dynamická pamäť je potrebná, keď veľkosť dát nepoznáš pri preklade alebo keď objekt musí prežiť návrat z funkcie. Každá úspešná alokácia potrebuje jedno zodpovedajúce free.",
            "sections": [
                {"title": "Životný cyklus", "paragraphs": ["malloc rezervuje neinitializovanú pamäť, calloc ju zároveň vynuluje. Vždy kontroluj NULL. free uvoľní blok; po free už ukazovateľ nesmieš dereferencovať."], "bullets": ["Po free je užitočné nastaviť vlastný ukazovateľ na NULL.", "realloc môže vrátiť inú adresu; výsledok najprv drž v dočasnej premennej.", "Veľkosť počítaj cez počet prvkov krát sizeof *ukazovatel, nie cez ručne napísané číslo typu."]},
                {"title": "Vlastník", "paragraphs": ["Pri každom ukazovateli si polož otázku: kto ho uvoľní? Ak odpoveď nie je jednoznačná, rozhranie funkcie ešte nie je hotové."], "callout": "Dvojité free, prístup po free a zabudnuté free patria medzi najčastejšie chyby v C."}
            ]
        }
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
            "lead": "Hlavičkový súbor opisuje verejné rozhranie modulu. Zdrojový súbor obsahuje jeho implementáciu. Takéto rozdelenie drží závislosti pod kontrolou.",
            "sections": [
                {"title": "Praktická štruktúra", "bullets": ["math_utils.h: deklarácie, ktoré používajú iné moduly.", "math_utils.c: definície týchto funkcií.", "main.c: používa rozhranie cez #include \"math_utils.h\"."], "paragraphs": ["Každú hlavičku chráň include guardom alebo #pragma once. Ak je funkcia určená len pre jeden .c súbor, označ jej definíciu static a nedávaj ju do hlavičky."]},
                {"title": "Linkovanie", "paragraphs": ["Preklad jednotlivých .c súborov vytvorí objektové súbory; linker ich spojí. Chyba undefined reference obvykle znamená, že deklarácia existuje, ale príslušná definícia nebola pridaná do linkovania."]}
            ]
        }
    },
    {
        "key": "io",
        "parent_key": "tooling",
        "kind": "lesson",
        "position": 130,
        "title": "Vstup a výstup",
        "summary": "printf, fgets, sscanf, návratové hodnoty a kontrola chýb.",
        "content": {
            "lead": "Štandardný vstup a výstup poskytuje stdio.h. Formátovacie funkcie sú praktické, ale vyžadujú presnú zhodu medzi formátom a typom argumentu.",
            "sections": [
                {"title": "Načítanie vstupu", "paragraphs": ["fgets načíta najviac daný počet znakov do poľa a pridá nulový znak. Následne môžeš text spracovať cez sscanf alebo strtol."], "bullets": ["Kontroluj návratovú hodnotu fgets aj sscanf.", "Pri printf používaj správne formáty: %d pre int, %zu pre size_t, %f pre double.", "Neber vstup ako dôveryhodný len preto, že ho zadal človek."]},
                {"title": "Súbory", "paragraphs": ["fopen môže zlyhať; vždy over, či nevrátil NULL. Každý úspešne otvorený FILE * zavri cez fclose, aj pri chybových vetvách."]}
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
            "sections": [
                {"title": "Typické príčiny", "bullets": ["Prístup mimo poľa.", "Dereferencovanie NULL alebo neinitializovaného ukazovateľa.", "Použitie hodnoty po free.", "Pretečenie znamienkového int.", "Nesprávny formát printf alebo scanf."]},
                {"title": "Postup pri chybe", "paragraphs": ["Najskôr reprodukuj čo najmenší prípad, potom zapni varovania a sanitizéry vo vlastnom vývojovom prostredí. Kontroluj hranice, návratové hodnoty a invarianty dátových štruktúr."], "callout": "Skúšobňa je určená na krátke príklady. Na skutočné ladenie viac-súborových programov patrí projektový build, testy a debugger."}
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
            "lead": "Chyba je súčasť bežného toku programu: súbor sa neotvorí, vstup neplatí alebo nie je dosť pamäte. Rozhranie funkcie má presne povedať, ako ju volajúci rozpozná a čo po nej ostáva platné.",
            "sections": [
                {"title": "Stav oddelene od hodnoty", "paragraphs": ["Ak výsledok môže byť aj nulový alebo záporný, nepreťažuj ho chybou. Funkcia môže vrátiť enum so stavom a hodnotu zapísať cez výstupný ukazovateľ."], "bullets": ["Pri zlyhaní nemeň výstupný objekt, ak to kontrakt nehovorí inak.", "Všetky rozpoznateľné chyby majú mať pomenovaný stav.", "Hlásenie pre človeka patrí na stderr, dáta programu na stdout."]},
                {"title": "errno a knižnica", "paragraphs": ["Niektoré funkcie nastavujú errno, ale iba ak ich dokumentácia hovorí, že ho používa. Pred volaním strtol nastav errno na 0 a po volaní rozlišuj ERANGE od bežného výsledku."], "callout": "Nikdy nečítaj errno ako všeobecný globálny stav po ľubovoľnej funkcii. Má význam len bezprostredne po operácii, ktorá ho podľa svojho kontraktu nastavuje."},
                {"title": "Kontrakt na papieri", "paragraphs": ["Pre každú verejnú funkciu si poznač platné vstupy, vlastníctvo dát, možné návratové hodnoty a vedľajšie účinky. Takýto krátky kontrakt výrazne zjednoduší používanie aj testovanie funkcie."]}
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
            "sections": [
                {"title": "Čo testovať", "paragraphs": ["Pre každú funkciu vyber typický prípad, hranice a neplatné vstupy. Ak funkcia pracuje s poľom, vyskúšaj prázdne pole, jeden prvok a najväčší očakávaný počet prvkov."], "bullets": ["Test očakáva konkrétny výsledok, nie iba to, že program nespadol.", "Chybu zmenši na čo najkratší reprodukovateľný príklad.", "Názov testu má opisovať správanie, nie implementáciu."]},
                {"title": "assert a nástroje", "paragraphs": ["assert je dobrý pre interné predpoklady a malé výukové testy. Pre ladenie v lokálnom prostredí pridaj sanitizéry, napríklad -fsanitize=address,undefined, a nechaj zapnuté varovania."], "callout": "assert môže byť v produkčnom builde vypnutý cez NDEBUG. Kontrolu chýb, od ktorej závisí bezpečný beh programu, preto zapisuj obyčajnou podmienkou."},
                {"title": "Debugger", "paragraphs": ["Debugger ukáže aktuálne hodnoty a zásobník volaní, ale nenahrádza predstavu o správnom správaní. Najprv si stanov očakávané vstupy a výstupy, potom sleduj miesto, kde sa od nich program odchýli."]}
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
        "summary": "Formátovaný výstup, riadkový vstup a práca so súbormi.",
        "content": {
            "lead": "stdio.h je rozhranie k štandardnému vstupu, výstupu a súborom.",
            "sections": [
                {"title": "printf", "paragraphs": ["int printf(const char *format, ...); vypíše formátovaný text a pri úspechu vracia počet zapísaných znakov, pri chybe zápornú hodnotu."], "bullets": ["%d: int", "%u: unsigned int", "%ld: long", "%zu: size_t", "%c: char", "%s: nulou ukončený reťazec"]},
                {"title": "fgets", "paragraphs": ["char *fgets(char *buffer, int count, FILE *stream); vráti buffer alebo NULL. Načítaný nový riadok obvykle ostáva v texte, pokiaľ sa zmestil."], "callout": "Nikdy nevolaj strlen ani printf s %s na poli, o ktorom nevieš, či obsahuje koncový nulový znak."}
            ]
        }
    },
    {
        "key": "stdlib-reference",
        "parent_key": "reference",
        "kind": "reference",
        "position": 170,
        "title": "stdlib.h: malloc, free a strtol",
        "summary": "Alokácia pamäte, prevod textu na číslo a návratové kódy.",
        "content": {
            "lead": "stdlib.h obsahuje základné nástroje pre dynamickú pamäť, konverzie a riadenie programu.",
            "sections": [
                {"title": "malloc a free", "paragraphs": ["void *malloc(size_t size); vráti adresu nového bloku alebo NULL. void free(void *ptr); uvoľní blok z malloc, calloc alebo realloc; free(NULL) je bezpečné."], "bullets": ["Alokuj počet * sizeof *ukazovatel.", "Nepriraď výsledok realloc priamo do jediného ukazovateľa.", "V C výsledok malloc nepretypovávaj."]},
                {"title": "strtol", "paragraphs": ["long strtol(const char *text, char **end, int base); umožní zistiť, kde prevod skončil. Je vhodnejší než atoi, pretože poskytuje kontrolu chyby a zvyšku textu."]}
            ]
        }
    },
    {
        "key": "string-reference",
        "parent_key": "reference",
        "kind": "reference",
        "position": 165,
        "title": "string.h: dĺžka, porovnanie a kopírovanie",
        "summary": "strlen, strcmp, strncmp, memcpy a bezpečné hranice polí.",
        "content": {
            "lead": "Funkcie z string.h pracujú s poľami. Časť z nich očakáva reťazec ukončený nulovým znakom, časť pracuje s ľubovoľnými bajtami a vždy potrebuje presnú dĺžku.",
            "sections": [
                {"title": "Reťazcové funkcie", "bullets": ["strlen(text) vráti počet znakov pred prvým nulovým znakom.", "strcmp(left, right) vráti zápornú, nulovú alebo kladnú hodnotu podľa lexikografického poradia.", "strncmp(left, right, count) porovná najviac count znakov."], "paragraphs": ["Na zistenie zhody kontroluj strcmp(left, right) == 0, nie konkrétnu zápornú alebo kladnú hodnotu."]},
                {"title": "Kopírovanie bajtov", "paragraphs": ["memcpy(target, source, count) skopíruje presne count bajtov, ale oblasti sa nesmú prekrývať. Pri prekrývaní použi memmove. Ani jedna z funkcií nepridáva nulový znak."], "callout": "strcpy a strcat nepoznajú veľkosť cieľa. Prednostne navrhuj rozhrania, ktoré vždy prijímajú aj kapacitu výstupného poľa."},
                {"title": "Bezpečné hranice", "paragraphs": ["Ak môže byť text dlhší než cieľové pole, najprv rozhodni, či ho chceš odmietnuť, skrátiť alebo dynamicky alokovať. Nech je toto pravidlo viditeľné v kontrakte funkcie."]}
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
            "sections": [
                {"title": "Hranice a presná šírka", "paragraphs": ["limits.h obsahuje hranice typov ako INT_MAX a CHAR_BIT. stdint.h pridáva typy int32_t a uint64_t, ak ich daná platforma podporuje, a najmenej široké typy int_least32_t."], "bullets": ["size_t je určený pre veľkosti a indexy.", "Pri výpise size_t použi %zu.", "Pri výpise typov z stdint.h sú prenositeľné makrá z inttypes.h, napríklad PRIu64."]},
                {"title": "ctype.h", "paragraphs": ["isdigit, isspace, toupper a podobné funkcie prijímajú hodnotu EOF alebo hodnotu, ktorú možno reprezentovať ako unsigned char. Pri obyčajnom char preto pred volaním bezpečne pretypuj na unsigned char."], "callout": "Nespoliehaj sa na to, že char je vždy znamienkový alebo vždy neznamienkový. Táto vlastnosť je závislá od implementácie."},
                {"title": "Konverzie", "paragraphs": ["Pri prechode medzi znamienkovými a neznamienkovými typmi najprv over rozsah. Tichá konverzia záporného čísla na unsigned typ dá veľkú kladnú hodnotu podľa pravidiel modulo aritmetiky."]}
            ]
        }
    }
]

C_EXAMPLES = [
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
        "description": "fgets načíta riadok a strtol ho prevedie s kontrolou rozsahu.",
        "source": "#include <ctype.h>\n#include <errno.h>\n#include <limits.h>\n#include <stdio.h>\n#include <stdlib.h>\n\nstatic int parse_int(const char text[], int *result)\n{\n    char *end = NULL;\n    long value = 0L;\n\n    errno = 0;\n    value = strtol(text, &end, 10);\n    while (*end != '\\0' && isspace((unsigned char) *end)) {\n        ++end;\n    }\n\n    if (end == text || *end != '\\0' || errno == ERANGE || value < INT_MIN || value > INT_MAX) {\n        return 0;\n    }\n\n    *result = (int) value;\n    return 1;\n}\n\nint main(void)\n{\n    char line[64] = \"\";\n    int number = 0;\n\n    fputs(\"Číslo: \", stdout);\n    if (fgets(line, sizeof line, stdin) == NULL || !parse_int(line, &number)) {\n        fputs(\"Očakávam celé číslo.\\n\", stderr);\n        return 1;\n    }\n\n    printf(\"Načítaná hodnota: %d\\n\", number);\n    return 0;\n}\n",
        "stdin": "21\n",
    },
    {
        "key": "safe-index",
        "page_key": "safety",
        "position": 10,
        "title": "Kontrola indexu poľa",
        "description": "Index sa overí ešte pred pretypovaním na size_t a prístupom do poľa.",
        "source": "#include <stddef.h>\n#include <stdio.h>\n\nint main(void)\n{\n    const int values[] = {10, 20, 30, 40};\n    const size_t count = sizeof values / sizeof values[0];\n    long requested = 0L;\n\n    fputs(\"Index: \", stdout);\n    if (scanf(\"%ld\", &requested) != 1) {\n        fputs(\"Očakávam celé číslo.\\n\", stderr);\n        return 1;\n    }\n\n    if (requested < 0L || (size_t) requested >= count) {\n        fputs(\"Index je mimo poľa.\\n\", stderr);\n        return 1;\n    }\n\n    printf(\"Hodnota: %d\\n\", values[(size_t) requested]);\n    return 0;\n}\n",
        "stdin": "2\n",
    },
    {
        "key": "parse-positive",
        "page_key": "errors",
        "position": 10,
        "title": "Stav a výstupný parameter",
        "description": "Funkcia rozlíši chybu vstupu od úspechu bez miešania stavu s hodnotou.",
        "source": "#include <ctype.h>\n#include <errno.h>\n#include <limits.h>\n#include <stdio.h>\n#include <stdlib.h>\n\ntypedef enum {\n    PARSE_OK,\n    PARSE_INVALID,\n    PARSE_RANGE\n} ParseStatus;\n\nstatic ParseStatus parse_positive(const char text[], int *result)\n{\n    char *end = NULL;\n    long value = 0L;\n\n    if (result == NULL) {\n        return PARSE_INVALID;\n    }\n\n    errno = 0;\n    value = strtol(text, &end, 10);\n    while (*end != '\\0' && isspace((unsigned char) *end)) {\n        ++end;\n    }\n\n    if (end == text || *end != '\\0' || value <= 0L) {\n        return PARSE_INVALID;\n    }\n    if (errno == ERANGE || value > INT_MAX) {\n        return PARSE_RANGE;\n    }\n\n    *result = (int) value;\n    return PARSE_OK;\n}\n\nint main(void)\n{\n    int value = 0;\n    ParseStatus status = parse_positive(\"24\", &value);\n\n    if (status != PARSE_OK) {\n        fprintf(stderr, \"Chyba spracovania: %d\\n\", status);\n        return 1;\n    }\n\n    printf(\"Prijatá hodnota: %d\\n\", value);\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "assert-maximum",
        "page_key": "testing",
        "position": 10,
        "title": "Malé testy cez assert",
        "description": "Samostatná funkcia sa otestuje pre bežné aj hraničné vstupy.",
        "source": "#include <assert.h>\n#include <stdio.h>\n\nstatic int maximum(int left, int right)\n{\n    return left > right ? left : right;\n}\n\nstatic void test_maximum(void)\n{\n    assert(maximum(2, 3) == 3);\n    assert(maximum(5, 5) == 5);\n    assert(maximum(-4, -1) == -1);\n}\n\nint main(void)\n{\n    test_maximum();\n    puts(\"Všetky testy prešli.\");\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "snprintf-message",
        "page_key": "stdio-reference",
        "position": 10,
        "title": "Formátovanie s kapacitou",
        "description": "snprintf oznámi aj to, že sa výsledok do poľa nezmestil celý.",
        "source": "#include <stdio.h>\n\nint main(void)\n{\n    const char *name = \"Jana\";\n    char message[32] = \"\";\n    int written = snprintf(message, sizeof message, \"Ahoj, %s!\", name);\n\n    if (written < 0 || (size_t) written >= sizeof message) {\n        fputs(\"Správa sa nezmestila do poľa.\\n\", stderr);\n        return 1;\n    }\n\n    puts(message);\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "strtol-reference",
        "page_key": "stdlib-reference",
        "position": 10,
        "title": "Prevod textu na číslo",
        "description": "strtol dovolí overiť koniec prevodu aj chybu rozsahu.",
        "source": "#include <errno.h>\n#include <stdio.h>\n#include <stdlib.h>\n\nint main(void)\n{\n    const char text[] = \"42\";\n    char *end = NULL;\n    long value = 0L;\n\n    errno = 0;\n    value = strtol(text, &end, 10);\n    if (end == text || *end != '\\0' || errno == ERANGE) {\n        fputs(\"Neplatné celé číslo.\\n\", stderr);\n        return 1;\n    }\n\n    printf(\"Hodnota: %ld\\n\", value);\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "compare-strings",
        "page_key": "string-reference",
        "position": 10,
        "title": "Porovnanie textov",
        "description": "strcmp vracia nulu vtedy, keď sú oba reťazce rovnaké.",
        "source": "#include <stdio.h>\n#include <string.h>\n\nint main(void)\n{\n    const char expected[] = \"C17\";\n    const char entered[] = \"C17\";\n\n    if (strcmp(expected, entered) == 0) {\n        puts(\"Texty sú rovnaké.\");\n    } else {\n        puts(\"Texty sa líšia.\");\n    }\n\n    return 0;\n}\n",
        "stdin": "",
    },
    {
        "key": "classify-character",
        "page_key": "numeric-reference",
        "position": 10,
        "title": "Bezpečná práca so znakom",
        "description": "Funkcie z ctype.h dostanú hodnotu pretypovanú na unsigned char.",
        "source": "#include <ctype.h>\n#include <stdio.h>\n\nint main(void)\n{\n    char character = 'c';\n\n    if (isdigit((unsigned char) character)) {\n        puts(\"Je to číslica.\");\n    } else {\n        printf(\"%c -> %c\\n\", character, (char) toupper((unsigned char) character));\n    }\n\n    return 0;\n}\n",
        "stdin": "",
    },
]
