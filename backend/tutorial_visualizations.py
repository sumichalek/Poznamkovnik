"""Malé, ovládateľné modely pre javy, ktoré samotný zdrojový kód neukáže.

Modely nie sú emulátory C ani konkrétnej implementácie. Každý ich krok preto
obsahuje aj stručné pomenovanie zjednodušenia a rovnaký stav sa dá prečítať v
tabuľke buniek bez akejkoľvek animácie.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


TUTORIAL_VISUALIZATION_MODELS: dict[str, tuple[dict[str, Any], ...]] = {
    "c": (
        {
            "id": "c-memory-lifetime",
            "title": "Ukazovateľ, objekt a životnosť",
            "summary": "Sleduj, čo označuje meno, čo drží ukazovateľ a čo sa po uvoľnení už nesmie čítať.",
            "simplification": "Adresy sú len symbolické. Skutočné rozloženie pamäte a číselné adresy určuje konkrétne spustenie programu.",
            "steps": (
                {
                    "title": "Lokálny objekt vznikne v rámci main",
                    "code": "int value = 7;",
                    "explanation": "Premenná value je samostatný objekt s hodnotou 7. Žije, kým neskončí blok funkcie main.",
                    "groups": (
                        {"label": "Stack: main", "rows": (("value", "7"),)},
                    ),
                },
                {
                    "title": "Ukazovateľ drží adresu objektu",
                    "code": "int *pointer = &value;",
                    "explanation": "pointer neobsahuje druhú kópiu čísla 7. Obsahuje adresu objektu value, na ktorý ukazuje.",
                    "groups": (
                        {"label": "Stack: main", "rows": (("value", "7"), ("pointer", "&value -> value"))},
                    ),
                },
                {
                    "title": "Dereferencovanie mení označený objekt",
                    "code": "*pointer = 12;",
                    "explanation": "Operátor * ide na objekt označený ukazovateľom. Mení teda value, nie hodnotu adresy v pointer.",
                    "groups": (
                        {"label": "Stack: main", "rows": (("value", "12"), ("pointer", "&value -> value"))},
                    ),
                },
                {
                    "title": "Dynamický objekt má samostatného vlastníka",
                    "code": "int *heap_value = malloc(sizeof *heap_value);\n*heap_value = 25;",
                    "explanation": "heap_value žije na stacku, ale ukazuje na nový objekt v dynamickej pamäti. Po úspešnom malloc je zodpovedný za jeho uvoľnenie.",
                    "groups": (
                        {"label": "Stack: main", "rows": (("value", "12"), ("pointer", "&value -> value"), ("heap_value", "heap -> dynamický objekt"))},
                        {"label": "Dynamická pamäť", "rows": (("*heap_value", "25"),)},
                    ),
                },
                {
                    "title": "Po free už objekt neexistuje",
                    "code": "free(heap_value);\nheap_value = NULL;",
                    "explanation": "free ukončí životnosť dynamického objektu. Nastavenie ukazovateľa na NULL zabráni omylu, že stále označuje platný objekt.",
                    "groups": (
                        {"label": "Stack: main", "rows": (("value", "12"), ("pointer", "&value -> value"), ("heap_value", "NULL"))},
                        {"label": "Dynamická pamäť", "rows": (("bývalý objekt", "uvoľnený - nečítať ani nezapisovať"),)},
                    ),
                },
            ),
        },
        {
            "id": "c-call-stack",
            "title": "Volanie funkcie a stack frame",
            "summary": "Kroky ukážu, ktoré lokálne premenné patria ktorej funkcii a kedy sa výsledok vráti volajúcej funkcii.",
            "simplification": "Skutočné uloženie parametrov a návratovej adresy závisí od ABI, optimalizácie a architektúry. Model ukazuje logický stav volania.",
            "steps": (
                {
                    "title": "main pripraví hodnotu",
                    "code": "int x = 41;",
                    "explanation": "Aktívna je iba funkcia main. Jej lokálna premenná x patrí do jej vlastného rámca zásobníka.",
                    "groups": (
                        {"label": "Aktívne rámce: vrch zásobníka", "rows": (("main: x", "41"),)},
                    ),
                },
                {
                    "title": "Volanie vytvorí nový rámec",
                    "code": "int answer = add_one(x);",
                    "explanation": "main čaká na návratovú hodnotu. Pre add_one vznikne nový rámec s vlastným parametrom input.",
                    "groups": (
                        {"label": "Aktívne rámce: vrch zásobníka", "rows": (("add_one: input", "41"),)},
                        {"label": "Čakajúci rámec", "rows": (("main: x", "41"), ("main: answer", "čaká na návrat"))},
                    ),
                },
                {
                    "title": "Funkcia pracuje vo vlastnom rámci",
                    "code": "int result = input + 1;",
                    "explanation": "result je lokálna premenná add_one. Nemení x v main; obe funkcie majú oddelené mená aj lokálny stav.",
                    "groups": (
                        {"label": "Aktívne rámce: vrch zásobníka", "rows": (("add_one: input", "41"), ("add_one: result", "42"))},
                        {"label": "Čakajúci rámec", "rows": (("main: x", "41"), ("main: answer", "čaká na návrat"))},
                    ),
                },
                {
                    "title": "Návrat odstráni rámec add_one",
                    "code": "return result;",
                    "explanation": "Hodnota 42 sa odovzdá do výrazu volania. Lokálne mená input a result po návrate prestanú existovať.",
                    "groups": (
                        {"label": "Aktívne rámce: vrch zásobníka", "rows": (("main: x", "41"), ("main: answer", "42"))},
                    ),
                },
            ),
        },
    ),
    "cpp": (
        {
            "id": "cpp-raii-lifetime",
            "title": "RAII, presun a životnosť zdroja",
            "summary": "Krokovo ukazuje, ako unique_ptr vytvorí jediného vlastníka, ako sa vlastníctvo presunie a prečo sa zdroj uvoľní aj pri odchode z rozsahu.",
            "simplification": "Model zobrazuje logické vlastníctvo, nie fyzickú adresu alokácie ani konkrétnu implementáciu unique_ptr. Skutočné optimalizácie a detaily alokátora sú závislé od implementácie.",
            "steps": (
                {
                    "title": "Lokálny vlastník vytvorí zdroj",
                    "code": "auto file = std::make_unique<File>(\"report.txt\");",
                    "explanation": "file je lokálny RAII objekt a jediný vlastník vytvoreného File. Vytvorenie objektu a prevzatie zodpovednosti sa stanú v jednom kroku.",
                    "groups": (
                        {"label": "Rozsah main", "rows": (("file", "unique_ptr -> File(report.txt)"),)},
                        {"label": "Vlastníctvo zdroja", "rows": (("File(report.txt)", "vlastní file"),)},
                    ),
                },
                {
                    "title": "Funkcia dostane vlastníctvo presunom",
                    "code": "process(std::move(file));",
                    "explanation": "std::move povie, že file môže odovzdať svoj zdroj. Samotný presun vykoná konštruktor alebo parameter unique_ptr v process; dvaja vlastníci nevzniknú.",
                    "groups": (
                        {"label": "Rozsah main", "rows": (("file", "presunutý - už nevlastní File"),)},
                        {"label": "Rozsah process", "rows": (("input", "unique_ptr -> File(report.txt)"),)},
                        {"label": "Vlastníctvo zdroja", "rows": (("File(report.txt)", "vlastní input"),)},
                    ),
                },
                {
                    "title": "Výnimka nepreskočí deštruktor",
                    "code": "throw ProcessingError{};",
                    "explanation": "Ak process vyhodí výnimku, začína odvíjanie zásobníka. Lokálny input sa zničí a jeho deštruktor unique_ptr uvoľní vlastnený File.",
                    "groups": (
                        {"label": "Odvíjanie rozsahu process", "rows": (("input", "deštruktor unique_ptr sa vykoná"),)},
                        {"label": "Vlastníctvo zdroja", "rows": (("File(report.txt)", "zatvorený a uvoľnený"),)},
                    ),
                },
                {
                    "title": "Po návrate nezostane vlastník ani zdroj",
                    "code": "// file je po std::move prázdny",
                    "explanation": "Po ukončení process je zdroj uvoľnený. Premenná file v main stále existuje, ale po presune už nevlastní objekt a jej deštruktor nemá čo uvoľniť.",
                    "groups": (
                        {"label": "Rozsah main", "rows": (("file", "prázdny unique_ptr"),)},
                        {"label": "Vlastníctvo zdroja", "rows": (("File(report.txt)", "už neexistuje"),)},
                    ),
                },
            ),
        },
        {
            "id": "cpp-iterator-invalidation",
            "title": "Vector a invalidácia iteratorov",
            "summary": "Sleduj, prečo pointer alebo iterator do vectoru po realokácii už nesmieš použiť, hoci stará hodnota môže zdanlivo ostať na obrazovke.",
            "simplification": "Kapacita a adresy sú symbolické. Skutočný okamih realokácie, presný rast kapacity a fyzické adresy určuje implementácia štandardnej knižnice.",
            "steps": (
                {
                    "title": "Vector má voľnú kapacitu",
                    "code": "std::vector<int> values{10, 20};\nvalues.reserve(4);",
                    "explanation": "Vector vlastní súvislý blok s kapacitou pre štyri prvky. Aktuálna veľkosť je dva, preto ešte dve vloženia nevyžadujú nový blok.",
                    "groups": (
                        {"label": "Vector", "rows": (("veľkosť / kapacita", "2 / 4"), ("prvky", "10, 20"))},
                        {"label": "Externé odkazy", "rows": (("stav", "žiadne"),)},
                    ),
                },
                {
                    "title": "Iterator ukazuje na prvý prvok",
                    "code": "auto first = values.begin();",
                    "explanation": "first označuje prvok 10 v súčasnom bloku vectoru. Je platný, kým operácie vectoru nezmenia pravidlá jeho platnosti.",
                    "groups": (
                        {"label": "Vector", "rows": (("veľkosť / kapacita", "2 / 4"), ("prvky", "10, 20"))},
                        {"label": "Externé odkazy", "rows": (("first", "iterator -> 10, platný"),)},
                    ),
                },
                {
                    "title": "Vloženie v rámci kapacity iterator zachová",
                    "code": "values.push_back(30);",
                    "explanation": "Veľkosť narastie, no v pôvodnom bloku ešte je miesto. Tento konkrétny iterator na prvý prvok ostáva platný.",
                    "groups": (
                        {"label": "Vector", "rows": (("veľkosť / kapacita", "3 / 4"), ("prvky", "10, 20, 30"))},
                        {"label": "Externé odkazy", "rows": (("first", "iterator -> 10, platný"),)},
                    ),
                },
                {
                    "title": "Realokácia zneplatní staré odkazy",
                    "code": "values.push_back(40);\nvalues.push_back(50);",
                    "explanation": "Piate vloženie potrebuje väčší blok. Vector presunie alebo skopíruje prvky do nového priestoru a starý blok skončí; first už nesmieš dereferencovať.",
                    "groups": (
                        {"label": "Vector", "rows": (("veľkosť / kapacita", "5 / viac než 4"), ("prvky", "10, 20, 30, 40, 50"))},
                        {"label": "Externé odkazy", "rows": (("first", "neplatný - nepoužiť"),)},
                    ),
                },
            ),
        },
    ),
    "ruby": (
        {
            "id": "ruby-method-lookup",
            "title": "Hľadanie metódy cez triedu a mixin",
            "summary": "Sleduj, v akom poradí Ruby hľadá metódu po include modulu a prečo metóda triedy môže mať prednosť pred rovnomennou metódou mixinu.",
            "simplification": "Model ukazuje bežné vyhľadávanie inštančnej metódy cez ancestors. Nezahŕňa singleton class, prepend, refinements ani method_missing, ktoré môžu poradie zmeniť.",
            "steps": (
                {
                    "title": "Objekt patrí triede Report",
                    "code": "class Report\n  def label = 'report'\nend",
                    "explanation": "Inštancia report hľadá metódy najprv v Report a potom v jej predkoch. Zatiaľ neexistuje žiadny mixin medzi triedou a Object.",
                    "groups": (
                        {"label": "Volanie", "rows": (("report.label", "hľadá sa"),)},
                        {"label": "Poradie predkov", "rows": (("Report.ancestors", "Report -> Object -> Kernel -> BasicObject"),)},
                    ),
                },
                {
                    "title": "include vloží modul za triedu",
                    "code": "module Auditable\n  def audit_label = 'audit'\nend\n\nclass Report\n  include Auditable\nend",
                    "explanation": "include pridá Auditable do reťazca predkov za Report. Metódy modulu sa správajú ako inštančné metódy, no trieda má pri rovnakom mene prednosť.",
                    "groups": (
                        {"label": "Volanie", "rows": (("report.audit_label", "hľadá sa"),)},
                        {"label": "Poradie predkov", "rows": (("Report.ancestors", "Report -> Auditable -> Object -> Kernel -> BasicObject"),)},
                    ),
                },
                {
                    "title": "Ruby nájde metódu v module",
                    "code": "report.audit_label  # => 'audit'",
                    "explanation": "Report metódu audit_label nemá, preto vyhľadávanie pokračuje do Auditable. Nájde implementáciu a zavolá ju s report ako self.",
                    "groups": (
                        {"label": "Cesta hľadania", "rows": (("Report", "audit_label nenájdená"), ("Auditable", "audit_label nájdená"))},
                        {"label": "Výsledok", "rows": (("report.audit_label", "\"audit\""),)},
                    ),
                },
                {
                    "title": "Trieda prepisuje rovnomennú metódu mixinu",
                    "code": "class Report\n  def audit_label = 'report audit'\nend",
                    "explanation": "Pri ďalšom volaní Ruby nájde audit_label už v Report, preto sa do Auditable nedostane. Takéto prekrytie má byť vedomou časťou návrhu, nie náhodou.",
                    "groups": (
                        {"label": "Cesta hľadania", "rows": (("Report", "audit_label nájdená"), ("Auditable", "už sa nehľadá"))},
                        {"label": "Výsledok", "rows": (("report.audit_label", "\"report audit\""),)},
                    ),
                },
            ),
        },
    ),
    "csharp": (
        {
            "id": "csharp-linq-deferred",
            "title": "LINQ dopyt a okamih vykonania",
            "summary": "Ukazuje, že Where a Select môžu vytvoriť iba dopyt nad zdrojom a výsledok sa číta až pri iterácii alebo materializácii.",
            "simplification": "Model používa List<int> v pamäti. LINQ provider nad databázou alebo vzdialeným API môže mať iné pravidlá prekladania, chyby a okamih vykonania.",
            "steps": (
                {
                    "title": "Zdroj je konkrétny zoznam",
                    "code": "var scores = new List<int> { 3, 7, 10 };",
                    "explanation": "scores je hotová, meniteľná kolekcia. Zatiaľ neexistuje žiadny LINQ dopyt ani transformovaný výsledok.",
                    "groups": (
                        {"label": "Zdroj dát", "rows": (("scores", "[3, 7, 10]"),)},
                        {"label": "Dopyt a výsledok", "rows": (("stav", "nič nie je vytvorené"),)},
                    ),
                },
                {
                    "title": "Where vytvorí odložený dopyt",
                    "code": "var passing = scores.Where(score => score >= 5);",
                    "explanation": "passing opisuje operáciu, nie nový List. Predikát sa ešte nemusel zavolať nad žiadnym prvkom.",
                    "groups": (
                        {"label": "Zdroj dát", "rows": (("scores", "[3, 7, 10]"),)},
                        {"label": "Dopyt a výsledok", "rows": (("passing", "IEnumerable: filter score >= 5"), ("stav", "bez iterácie"))},
                    ),
                },
                {
                    "title": "Zmena zdroja pred iteráciou je viditeľná",
                    "code": "scores.Add(8);",
                    "explanation": "Keďže passing ešte nie je snapshot, neskoršia iterácia nad ním uvidí aj hodnotu 8. To môže byť výhoda alebo zdroj nenápadnej zmeny správania.",
                    "groups": (
                        {"label": "Zdroj dát", "rows": (("scores", "[3, 7, 10, 8]"),)},
                        {"label": "Dopyt a výsledok", "rows": (("passing", "stále iba filter nad scores"), ("stav", "bez iterácie"))},
                    ),
                },
                {
                    "title": "ToList vytvorí stabilný výsledok",
                    "code": "var snapshot = passing.ToList();",
                    "explanation": "Iterácia teraz vykoná filter a vytvorí nový zoznam. snapshot má vlastné prvky [7, 10, 8] a neskoršia zmena scores už jeho obsah nezmení.",
                    "groups": (
                        {"label": "Zdroj dát", "rows": (("scores", "[3, 7, 10, 8]"),)},
                        {"label": "Dopyt a výsledok", "rows": (("passing", "filter nad scores"), ("snapshot", "[7, 10, 8] - materializovaný List"))},
                    ),
                },
            ),
        },
        {
            "id": "csharp-async-task",
            "title": "Task, await a zrušenie",
            "summary": "Krokovo ukazuje vytvorenie Tasku, odovzdanie riadenia cez await, úspešné pokračovanie a samostatnú cestu korektného rušenia.",
            "simplification": "Model nezobrazuje konkrétne vlákna ani SynchronizationContext. Task môže dokončiť I/O, timer alebo inú prácu; podstatný je jeho stav a vlastník výsledku.",
            "steps": (
                {
                    "title": "Asynchrónna operácia vráti Task",
                    "code": "Task<string> request = LoadNameAsync(token);",
                    "explanation": "Volajúci dostane reprezentáciu prebiehajúcej práce. Task ešte nemá výsledok, no musí existovať kód, ktorý spracuje jeho úspech, chybu alebo zrušenie.",
                    "groups": (
                        {"label": "Volajúca metóda", "rows": (("request", "Task<string>, čaká"), ("token", "CancellationToken aktívny"))},
                        {"label": "Operácia", "rows": (("LoadNameAsync", "I/O prebieha"),)},
                    ),
                },
                {
                    "title": "await uvoľní volajúcu cestu",
                    "code": "string name = await request;",
                    "explanation": "await nečíta nehotový výsledok. Metóda sa pozastaví a runtime môže vykonávať inú pripravenú prácu; po dokončení Tasku pokračuje za await.",
                    "groups": (
                        {"label": "Volajúca metóda", "rows": (("name", "čaká na výsledok"), ("stav", "pozastavená pri await"))},
                        {"label": "Operácia", "rows": (("LoadNameAsync", "I/O prebieha"),)},
                    ),
                },
                {
                    "title": "Úspech pokračuje s hodnotou",
                    "code": "// Task dokončí: \"Ada\"\nConsole.WriteLine(name);",
                    "explanation": "Task sa splní hodnotou a await ju odovzdá do name. Výnimka by sa na tomto mieste znovu vyhodila, aby o nej rozhodla volajúca hranica.",
                    "groups": (
                        {"label": "Volajúca metóda", "rows": (("name", "\"Ada\""), ("stav", "pokračuje po await"))},
                        {"label": "Operácia", "rows": (("request", "RanToCompletion"),)},
                    ),
                },
                {
                    "title": "Zrušenie je samostatný výsledok",
                    "code": "tokenSource.Cancel();\n// await vyhodí OperationCanceledException",
                    "explanation": "CancellationToken žiada kooperatívne ukončenie. Operácia má upratať vlastný stav a volajúci rozlíši očakávané zrušenie od chyby, ktorú treba nahlásiť.",
                    "groups": (
                        {"label": "Volajúca metóda", "rows": (("token", "zrušenie vyžiadané"), ("spracovanie", "OperationCanceledException"))},
                        {"label": "Operácia", "rows": (("request", "Canceled po cleanup"))},
                    ),
                },
            ),
        },
    ),
    "python": (
        {
            "id": "python-object-references",
            "title": "Mená, objekty a mutácia",
            "summary": "Sleduj, ako dve mená môžu označovať ten istý zoznam, prečo sa zmena ukáže cez obe a čo zmení plytká kópia.",
            "simplification": "Označenia objektov sú symbolické. Python používa vlastnú správu pamäte a konkrétne identifikátory ani čas uvoľnenia objektov nie sú súčasťou kontraktu programu.",
            "steps": (
                {
                    "title": "Meno sa naviaže na jeden objekt",
                    "code": "languages = ['C', 'Python']",
                    "explanation": "languages nie je zásobník s vlastnou kópiou zoznamu. Je to meno, ktoré označuje nový meniteľný objekt typu list.",
                    "groups": (
                        {"label": "Mená v module", "rows": (("languages", "-> list A"),)},
                        {"label": "Objekty", "rows": (("list A", "['C', 'Python']"),)},
                    ),
                },
                {
                    "title": "Priradenie nevytvorí kópiu",
                    "code": "alias = languages",
                    "explanation": "Alias dostane odkaz na ten istý objekt list A. Neexistujú dva zoznamy; existujú dve mená, ktorými sa k nemu dá dostať.",
                    "groups": (
                        {"label": "Mená v module", "rows": (("languages", "-> list A"), ("alias", "-> list A"))},
                        {"label": "Objekty", "rows": (("list A", "['C', 'Python']"),)},
                    ),
                },
                {
                    "title": "Mutácia sa ukáže cez obe mená",
                    "code": "alias.append('Rust')",
                    "explanation": "append mení list A na mieste. Preto neskôr languages aj alias ukážu na obsah s Rust; priradenie mena sa pritom nezmenilo.",
                    "groups": (
                        {"label": "Mená v module", "rows": (("languages", "-> list A"), ("alias", "-> list A"))},
                        {"label": "Objekty", "rows": (("list A", "['C', 'Python', 'Rust']"),)},
                    ),
                },
                {
                    "title": "Kópia dostane nový vonkajší list",
                    "code": "snapshot = languages.copy()\nlanguages.append('Go')",
                    "explanation": "copy vytvorí nový list B s rovnakými prvkami. Neskorší append zmení iba list A; pri vnorených meniteľných hodnotách by však plytká kópia naďalej zdieľala ich vnútro.",
                    "groups": (
                        {"label": "Mená v module", "rows": (("languages", "-> list A"), ("alias", "-> list A"), ("snapshot", "-> list B"))},
                        {"label": "Objekty", "rows": (("list A", "['C', 'Python', 'Rust', 'Go']"), ("list B", "['C', 'Python', 'Rust']"))},
                    ),
                },
            ),
        },
        {
            "id": "python-generator-flow",
            "title": "Generátor po krokoch",
            "summary": "Krokovo ukazuje, že generátor nespustí telo pri vytvorení, zastaví sa pri yield a pokračuje až pri ďalšej požiadavke na hodnotu.",
            "simplification": "Model zobrazuje jednu generátorovú inštanciu a jej logický stav. Skutočný interpreter drží rámec a hodnoty interne; model nenahrádza debugger ani meranie pamäte.",
            "steps": (
                {
                    "title": "Definícia ešte nič nevypočíta",
                    "code": "def labels():\n    yield 'prvá'\n    yield 'druhá'",
                    "explanation": "def vytvorí funkciu. Telo sa nespustí a hodnoty sa ešte nevytvoria, pretože yield z nej robí generátorovú funkciu.",
                    "groups": (
                        {"label": "Mená v module", "rows": (("labels", "generátorová funkcia"),)},
                        {"label": "Generátorový rámec", "rows": (("stav", "neexistuje"),)},
                    ),
                },
                {
                    "title": "Volanie vytvorí neštartovaný generátor",
                    "code": "stream = labels()",
                    "explanation": "Volanie nevráti prvý text, ale generátorový objekt. Telo labels stále čaká na prvé next alebo iteráciu cez for.",
                    "groups": (
                        {"label": "Mená v module", "rows": (("labels", "generátorová funkcia"), ("stream", "-> generátor G"))},
                        {"label": "Generátorový rámec G", "rows": (("stav", "vytvorený, pred prvým riadkom"),)},
                    ),
                },
                {
                    "title": "Prvé next dôjde po prvý yield",
                    "code": "next(stream)  # 'prvá'",
                    "explanation": "Generátor začne vykonávať telo a zastaví sa na prvom yield. Hodnota 'prvá' sa odovzdá volajúcemu, no rámec G zostane pripravený pokračovať.",
                    "groups": (
                        {"label": "Mená v module", "rows": (("stream", "-> generátor G"),)},
                        {"label": "Generátorový rámec G", "rows": (("stav", "pozastavený po prvom yield"), ("naposledy vydané", "'prvá'"))},
                    ),
                },
                {
                    "title": "Ďalšie next pokračuje a potom skončí",
                    "code": "next(stream)  # 'druhá'\nnext(stream)  # StopIteration",
                    "explanation": "Druhé next obnoví rovnaký rámec až po druhý yield. Po poslednej hodnote už generátor nemá kam pokračovať a ďalšia požiadavka signalizuje StopIteration.",
                    "groups": (
                        {"label": "Mená v module", "rows": (("stream", "-> generátor G"),)},
                        {"label": "Generátorový rámec G", "rows": (("stav", "ukončený"), ("vydané hodnoty", "'prvá', 'druhá'"))},
                    ),
                },
            ),
        },
    ),
    "javascript": (
        {
            "id": "js-event-loop",
            "title": "Event loop, tasky a microtasky",
            "summary": "Krokovo sleduj, prečo sa reakcia Promise vykoná pred callbackom z timeru, hoci sa oba naplánujú počas toho istého skriptu.",
            "simplification": "Model ukazuje jednu task frontu a jednu microtask frontu. Skutočné runtime majú viac zdrojov úloh, pravidlá timerov a interné fázy, ktoré sa medzi prehliadačom a Node líšia.",
            "steps": (
                {
                    "title": "Skriptu patrí call stack",
                    "code": "console.log('začiatok');",
                    "explanation": "Súčasný skript je na call stacku a výpis sa vykoná okamžite. Fronty zatiaľ neobsahujú žiadnu čakajúcu prácu.",
                    "groups": (
                        {"label": "Call stack", "rows": (("aktuálna práca", "hlavný skript"),)},
                        {"label": "Microtask queue", "rows": (("stav", "prázdna"),)},
                        {"label": "Task queue", "rows": (("stav", "prázdna"),)},
                        {"label": "Výstup", "rows": (("console", "začiatok"),)},
                    ),
                },
                {
                    "title": "Promise naplánuje microtask",
                    "code": "Promise.resolve().then(() => console.log('promise'));",
                    "explanation": "Callback then sa nevykoná priamo v tejto inštrukcii. Keď sa Promise splní, jeho reakcia čaká vo fronte microtasks.",
                    "groups": (
                        {"label": "Call stack", "rows": (("aktuálna práca", "hlavný skript"),)},
                        {"label": "Microtask queue", "rows": (("1", "vypíš promise"),)},
                        {"label": "Task queue", "rows": (("stav", "prázdna"),)},
                        {"label": "Výstup", "rows": (("console", "začiatok"),)},
                    ),
                },
                {
                    "title": "Timer naplánuje task",
                    "code": "setTimeout(() => console.log('timer'), 0);",
                    "explanation": "Nulové oneskorenie neznamená okamžité volanie. Callback timeru sa stane pripraveným taskom až po návrate riadenia runtime.",
                    "groups": (
                        {"label": "Call stack", "rows": (("aktuálna práca", "hlavný skript"),)},
                        {"label": "Microtask queue", "rows": (("1", "vypíš promise"),)},
                        {"label": "Task queue", "rows": (("1", "vypíš timer"),)},
                        {"label": "Výstup", "rows": (("console", "začiatok"),)},
                    ),
                },
                {
                    "title": "Súčasný skript skončí",
                    "code": "console.log('koniec');",
                    "explanation": "Ešte počas hlavného skriptu sa vypíše koniec. Až po vyprázdnení call stacku runtime vyberie ďalšiu prácu z frontov.",
                    "groups": (
                        {"label": "Call stack", "rows": (("stav", "prázdny"),)},
                        {"label": "Microtask queue", "rows": (("1", "vypíš promise"),)},
                        {"label": "Task queue", "rows": (("1", "vypíš timer"),)},
                        {"label": "Výstup", "rows": (("console", "začiatok\nkoniec"),)},
                    ),
                },
                {
                    "title": "Najprv sa vyčerpá microtask queue",
                    "code": "// reakcia Promise sa vykoná pred ďalším taskom",
                    "explanation": "Po skončení aktuálnej práce runtime pred ďalším taskom vyčerpá microtasks. Preto sa callback Promise dostane na rad pred timerom.",
                    "groups": (
                        {"label": "Call stack", "rows": (("práve skončil", "callback Promise"),)},
                        {"label": "Microtask queue", "rows": (("stav", "prázdna"),)},
                        {"label": "Task queue", "rows": (("1", "vypíš timer"),)},
                        {"label": "Výstup", "rows": (("console", "začiatok\nkoniec\npromise"),)},
                    ),
                },
                {
                    "title": "Potom príde timer",
                    "code": "// runtime vyberie ďalší pripravený task",
                    "explanation": "Až keď nezostala microtask, runtime vykoná čakajúci callback timeru. Výsledné poradie je začiatok, koniec, promise, timer.",
                    "groups": (
                        {"label": "Call stack", "rows": (("práve skončil", "callback timeru"),)},
                        {"label": "Microtask queue", "rows": (("stav", "prázdna"),)},
                        {"label": "Task queue", "rows": (("stav", "prázdna"),)},
                        {"label": "Výstup", "rows": (("console", "začiatok\nkoniec\npromise\ntimer"),)},
                    ),
                },
            ),
        },
        {
            "id": "js-scope-closures",
            "title": "Scope a closure",
            "summary": "Sleduj, ktoré meno po návrate funkcie stále existuje preto, že ho zachytila vrátená funkcia.",
            "simplification": "Model neukazuje fyzickú pamäť ani optimalizácie JavaScript engine. Ukazuje iba logické lexikálne prostredia a väzby mien, ktoré vysvetľujú správanie closure.",
            "steps": (
                {
                    "title": "Vonkajšia funkcia vytvorí lokálny stav",
                    "code": "function createCounter() {\n  let count = 0;",
                    "explanation": "Pri volaní createCounter vznikne vlastné lexikálne prostredie. Meno count patrí iba tomuto volaniu, nie globálnemu priestoru.",
                    "groups": (
                        {"label": "Aktívne prostredie", "rows": (("createCounter: count", "0"),)},
                        {"label": "Globálne prostredie", "rows": (("createCounter", "funkcia"),)},
                    ),
                },
                {
                    "title": "Vnútorná funkcia zachytí count",
                    "code": "  return () => ++count;\n}",
                    "explanation": "Arrow function používa count z vonkajšieho lexikálneho prostredia. Vrátená hodnota preto nesie odkaz na tento stav, nie iba zdrojový text funkcie.",
                    "groups": (
                        {"label": "Closure", "rows": (("funkcia", "() => ++count"), ("zachytené meno", "count -> 0"))},
                        {"label": "Globálne prostredie", "rows": (("createCounter", "funkcia"),)},
                    ),
                },
                {
                    "title": "Po návrate ostáva zachytený stav živý",
                    "code": "const next = createCounter();",
                    "explanation": "Volanie createCounter už skončilo, ale jeho prostredie nebolo odstránené, pretože ho stále používa funkcia uložená v next.",
                    "groups": (
                        {"label": "Globálne prostredie", "rows": (("next", "closure"),)},
                        {"label": "Zachytené prostredie", "rows": (("count", "0"),)},
                    ),
                },
                {
                    "title": "Každé volanie mení ten istý zachytený stav",
                    "code": "next(); // 1\nnext(); // 2",
                    "explanation": "Obe volania používajú rovnaké prostredie konkrétneho closure. Nové volanie createCounter by vytvorilo iné počítadlo s vlastným count.",
                    "groups": (
                        {"label": "Globálne prostredie", "rows": (("next", "closure"),)},
                        {"label": "Zachytené prostredie", "rows": (("count", "2"),)},
                        {"label": "Výsledky", "rows": (("prvé volanie", "1"), ("druhé volanie", "2"))},
                    ),
                },
            ),
        },
    ),
}


def visualization_models_for_language(code: str) -> list[dict[str, Any]]:
    """Vráti nezdieľané modely dostupné v konkrétnej učebnici."""
    return deepcopy(list(TUTORIAL_VISUALIZATION_MODELS.get(code, ())))
