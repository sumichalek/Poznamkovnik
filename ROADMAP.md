# Roadmap

## Odložené úpravy

- Rozdeliť súčasnú kontrastnú tému na dve samostatné voľby: kontrastnú tmavú a kontrastnú svetlú.

## Ukončenie pracovného dňa

Pri správe „Na dnes končíme“ uzavrieť rozpracovaný blok, nezačínať ďalší:

- Zhrnúť dokončené zmeny a výsledky overenia; jasne uviesť preskočené testy a známe obmedzenia.
- Aktualizovať panel Úlohy a zapísať konkrétny bod pokračovania. Nedokončené veľké úlohy neoznačovať za hotové.
- Skontrolovať stav Gitu a bezpečné uloženie práce. Existujúce zmeny nevracať späť a lokálny commit nezamieňať s odoslaním na GitHub.
- Do štatistiky vždy pridať veľkosť verzovaných súborov, lokálneho úložiska .git a celého projektu na disku.
- Veľkosť na disku rozpísať aspoň na zálohy, používateľské prílohy, databázu, lokálne nástroje, závislosti a zdrojové súbory či zostavené prostriedky.
- Pri zálohách uviesť počet a ich podiel na celkovej veľkosti. Rozlišovať logickú veľkosť súborov a skutočne obsadené bloky disku; nezamieňať MiB/GiB s MB/GB.
- Nevykonávať automatické čistenie záloh, používateľských dát ani histórie Gitu. Lokálny server ponechať dostupný, pokiaľ používateľ nepožiada o vypnutie.

## Stav Pri Uzavretí 2026-09-10

Posledný dokončený blok učebnice C:

- Podrobný výklad vstupu/výstupu a chybových kontraktov vrátane poradia kontrol, EOF, rozsahu a vlastníctva zdrojov.
- Tri nové a dve opravené spustiteľné ukážky; päť variantov cvičenia riadkov a štyri varianty chybového kontraktu.
- Oprava prijímania samotných medzier ako čísla a tichého prijatia skráteného riadka.
- Overené zachovanie poznámok, rozpracovaných príkladov, odpovedí a postupu pri aktualizácii obsahu.
- Overenie: 122 úspešných Python testov, 4 preskočené pre nedostupné jazykové nástroje; 3 úspešné frontendové testovacie súbory.
- Zostavenie frontendu v dočasnom adresári je zhodné s nasadenými assets/app.js a assets/app.css.
- Obe kapitoly overené v prehliadači pri šírkach 1440, 875 a 390 bodov. Všetkých päť programov spustených aj cez skúšobňu.

Zostávajúce upozornenia: testy vypisujú ResourceWarning k uzatváraniu spojení SQLite; generovaný bundle obsahuje dva riadky s koncovými medzerami. Nie sú to zlyhania testov a pri uzavretí sa nemenil generovaný obsah.

Nasledujúci blok: rozšíriť kapitoly C o nedefinovanom správaní, testovaní a ladení. Použiť konkrétne chybné programy, vysvetlenie príčiny, opravu, hraničné prípady a ukážky práce s debuggerom. Priebežnú diagnostiku počas písania nepridávať; používateľ ju výslovne nechce.

Učebnice ostatných jazykov a mikrokontrolérov zostávajú rozpracovanou dlhodobou úlohou. Tento kontrolný bod zahŕňa aj nahromadené zmeny Vývoja a učebnice od predchádzajúceho commitu; nejde o tvrdenie, že všetky vznikli v poslednom pracovnom bloku.

## Oprava Spúšťania Vývoja 2026-09-11

- Pôvodná chyba potvrdená v bežiacej službe: GET /api/development sa ukončil bez HTTP odpovede. FirmwareBuildRunner._limit_process prijímal jeden argument, spoločný spúšťač odovzdával dva; výnimka vznikla v preexec_fn ešte pred spustením sandboxu.
- Spoločný spúšťač aj debugger teraz nastavujú limity cez prlimit bez Python callbacku po fork. Limity CPU, pamäte, súborov a otvorených deskriptorov platia aj pre obalové procesy. Limit počtu procesov zostáva vo vnútri izolovaného používateľského priestoru. Chyby pri vytvorení procesu sa menia na zrozumiteľný stav nedostupnosti alebo JSON chybu.
- Firmvérové kroky explicitne zachovávajú limit artefaktu 4 MiB; limit výpisu zostáva 64 KiB. Chýbajúci prlimit nikdy nespôsobí spustenie bez obmedzení.
- Pridaných 18 Python testov: spúšťanie z vlákien, skutočné limity a izolácia, HTTP požiadavky, nedostupné nástroje, chybové vetvy a spustenie debuggeru. Existujúci test firmvéru kontroluje limity všetkých krokov zostavenia.
- npm run check prešiel: 140 úspešných Python testov a 4 preskočené; 10 frontendových testov úspešných. HTTP testy potrebujú povolenie na lokálne sokety.
- Nasadená služba po reštarte vracia Vývoj bez pádu. Príklad C overený cez API aj tlačidlo Spustiť v Chromium. Kontrola pri šírkach 1440/875/390: výstup správny, bez JavaScript výnimiek a bez pretekania celého dokumentu.
- Na šírke 390 zostáva stiesnené rozloženie častí konzoly; ide o samostatnú otvorenú úlohu, nie o dokončenú mobilnú úpravu. CSS sa v tomto bloku nemenilo.
- Chýbajúce AVR a ARM toolchainy sa korektne oznamujú; reálny cross-build ani zápis na zariadenie sa neoveroval. Služba teraz hlási dostupný debugger, ale úplné krokovanie nebolo predmetom tejto kontroly.
- Dočasné testovacie projekty a relácie odstránené, pôvodný stav projektov nezmenený. Snímky a podrobný lokálny report: /tmp/poznamkovnik-runtime-verification/ (dočasné súbory, nie trvalá záloha).

Ďalej pokračovať učebnicou C: nedefinované správanie, testovanie a ladenie. Mobilné rozloženie konzoly a overenie skutočných firmvérových nástrojov riešiť ako samostatné bloky.

## Učebnica C: Bezpečnosť A Testovanie 2026-09-11

- Rozšírené obe lekcie: logická chyba verzus UB, poradie kontrol, hranice poľa a aritmetiky, životnosť, vedľajšie účinky, assert/NDEBUG, tabuľkové a regresné testy, sanitizéry a konkrétny postup v GDB.
- Dve existujúce ukážky opravené pri zachovaní identifikátorov: bezpečný index používa úplný riadok a kontrolovaný prevod; assert ukážka pri NDEBUG nehlási úspech testov, ktoré neprebehli.
- Tri nové spustiteľné programy: kontrolované delenie, sedem hraničných testov a zámerná logická chyba na krokovanie. Posledný program má očakávaný neúspešný návrat a výstup expected=1 actual=2, nie UB.
- Nové cvičenie bezpečného indexovania a zmysluplná náhrada cvičenia testovania, každé so štyrmi variantmi; nová kontrolná otázka o poradí kontroly a prístupu. Diagnostika počas písania sa nepridávala.
- Pridaných 10 Python testov: hranice, NULL, zachovanie výstupu, NDEBUG vrátane hodnoty 0, známe mutácie algoritmu, oprava logickej chyby a všetky varianty cvičení. Rozšírený test zachovania poznámok, konceptov, odpovedí a postupu pri opakovanom nasadení.
- npm run check: 150 Python testov úspešných, 4 preskočené pre nedostupné nástroje; všetkých 10 frontendových testov úspešných. Zostavené assets bez zmeny. Existujúce upozornenia ResourceWarning k SQLite zostávajú.
- Po reštarte overených všetkých päť programov cez API aj tlačidlo Spustiť a osem riešení cvičení cez API. Obe lekcie skontrolované v Chromium pri šírkach 1440/875/390 bez pretekania čítačky či dokumentu a bez JavaScript výnimiek. Používateľský stav učebnice zostal nezmenený.
- Skutočné GDB overilo step, podmienený breakpoint, next, hodnoty, zásobník a finish na dočasnom programe. Toto nie je overenie celého debuggerového rozhrania Vývoja. ASan nebol spustený v sandboxe a limity sandboxu sa nemenili.
- Snímky, API report a záznam GDB: /tmp/poznamkovnik-tutorial-safety-verification/ (dočasné overenie, nie trvalá záloha).

Technické pravidlá boli skontrolované proti primárnym zdrojom: význam celočíselného delenia a assert v [návrhu WG14 N1570, oddiely 6.5.5 a 7.2](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf), režim pokračovania sanitizéra v [dokumentácii GCC](https://gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html), virtuálny adresný priestor v [obmedzeniach ASan](https://clang.llvm.org/docs/AddressSanitizer.html#limitations) a krokovanie v [dokumentácii GDB](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Continuing-and-Stepping.html). N1570 je návrh C11, nie vydanie normy C17; programy sa overovali v režime C17.

Ďalší obsahový blok: rozšíriť rýchlu referenciu C pre string.h a stdlib.h o kontrakty, kapacity, prekrývanie oblastí a testované príklady. Učebnice ako celok zostávajú rozpracované. Mobilná konzola a reálne firmvérové toolchainy naďalej patria do samostatných úloh.

## Referencia C: string.h A stdlib.h 2026-09-11

- Rozšírené dve referenčné stránky pri zachovaní kľúčov, názvov a identifikátorov. string.h pokrýva bajty verzus reťazce, kapacitu, prefixy, ohraničené hľadanie nuly, chyby strncpy/strncat a oba smery prekrytia. stdlib.h dopĺňa vlastníctvo, realloc, kontrolované prevody, bezpečný porovnávač, qsort a bsearch.
- Šesť spustiteľných ukážok zhodných s výkladom: dve existujúce rozšírené, tri nové programy a opätovné použitie overeného rastu poľa z kapitoly o pamäti. Prevod využíva spoločný INT_PARSER, nie novú implementáciu.
- Dve nové cvičenia so štyrmi variantmi: kopírovanie so zachovaním cieľa pri chybe a porovnávač odolný proti pretečeniu. Dve kontrolné otázky k miestu pre koncovú nulu a znamienku výsledku porovnávača.
- Pridaných 10 Python testov. Kopírovanie preverené na 880 kombináciách dĺžky, zdrojového rozsahu a kapacity, na 294 kombináciách pozícií a dĺžok vrátane prekrytia aj kopírovania na rovnaké miesto, pri NULL, vloženej nule a neukončenom poli. Overené presné zaplnenie, odmietnutie krátkeho cieľa a nedotknutý obsah pri chybe.
- Triedenie a hľadanie overené s INT_MIN/INT_MAX, duplicitami, prázdnym rozsahom, nesprávnymi porovnávačmi a správnym porovnávačom vracajúcim aj iné hodnoty než -1/1. Zámerne chybný rozdiel a - b sa overuje diagnostikou UBSan, nie náhodným číselným výsledkom.
- npm run check: 160 Python testov úspešných, 4 preskočené pre nedostupné nástroje; 10 frontendových testov úspešných. Zostavené assets bez zmeny; existujúce SQLite ResourceWarning zostávajú mimo tohto obsahového bloku.
- Po reštarte všetkých šesť príkladov overených cez API aj tlačidlo Spustiť, osem riešení cvičení cez API. Obe referencie skontrolované v Chromium pri 1440/875/390 bez pretekania čítačky či dokumentu a bez JavaScript výnimiek. Opakovaná kontrola úspešne ukončila aj dočasný prehliadač.
- Test opakovaného nasadenia rozšírený o obe referencie: zachované poznámky, koncepty, postup, odpovede a čas vytvorenia. Aj kontrolný odtlačok používateľského stavu v živej databáze zostal nezmenený.
- Dočasné snímky a report: /tmp/poznamkovnik-tutorial-reference-verification/. Diagnostika počas písania, CSS, sandbox a firmvérové nástroje sa nemenili.

Kontrakty pamäte, vyhľadávania a kopírovania boli skontrolované proti [WG14 N1570, oddielom 7.22.3, 7.22.5 a 7.24](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf). Tento dokument je návrh C11; príklady sa prekladali v režime C17 a nepoužívajú osobitné správanie realloc s nulovou veľkosťou.

Ďalej: doplniť zostávajúcu referenciu C pre stdio.h a čísla/znaky o snprintf, kontrolu formátov, limity typov a správne argumenty ctype.h. Dlhodobá úloha učebníc zostáva rozpracovaná; mobilnú konzolu a skutočné firmvérové toolchainy riešiť oddelene.

## Referencia C: stdio.h, Limity A Znaky 2026-09-11

- Rozšírené dve referenčné stránky pri zachovaní identifikátorov: návraty a formáty stdio, snprintf vrátane nulovej kapacity, hranice fgets, aktualizačné prúdy, binárny prenos a chybové cesty; limity typov, inttypes, kontrolované prevody, doména ctype, EOF, locale a hranice bajtového spracovania UTF-8.
- Šesť spustiteľných ukážok zhodných s výkladom: dve existujúce rozšírené, tri nové programy a opätovné použitie overeného čítania riadkov. Pridané dve cvičenia so štyrmi variantmi a dve kontrolné otázky. Vyhodnotenie výstupu cvičenia ctype výslovne nie je dôkazom správnej domény argumentov.
- Pridaných 12 Python testov: kapacity 0/1/8/9, záporný návrat a chyba formátovania bez čítania poškodeného cieľa, odmietnutie nesprávnych formátov prekladačom, binárne dáta s nulou, deväť simulovaných chybových ciest vrátane súčasnej chyby zápisu a uzavretia. Po otvorení sa prúd uzavrie práve raz, neúspešné otvorenie sa neuzatvára.
- Všetkých 256 hodnôt osembitového bajtu overených na hostiteľskej platforme so znamienkovým aj neznamienkovým char. Skontrolované čisté EOF aj chyba čítania, kontrolované argumenty ctype a nenulové výsledky iné než 1. Prevody testujú hranice, NULL a zachovanie výstupného objektu pri odmietnutí; výklad nepredpokladá rovnaké šírky typov na každej platforme.
- npm run check: 172 Python testov úspešných, 4 preskočené pre nedostupné C#/Go/Java/Rust nástroje; 10 frontendových testov úspešných. Zostavené assets bez zmeny. Existujúce SQLite ResourceWarning zostávajú mimo tohto obsahového bloku.
- Po reštarte služby všetkých šesť programov prešlo cez API aj tlačidlo Spustiť, osem riešení cvičení cez API. Obe stránky overené v Chromium pri 1440/875/390 bez pretekania čítačky či dokumentu a bez JavaScript výnimiek. Na úzkom mobile zostáva existujúca úzka čítačka; dlhé riadky kódu sa posúvajú v bloku, nejde o novú mobilnú úpravu.
- Test opakovaného nasadenia pokrýva poznámky, koncepty, postup, odpovede a čas vytvorenia aj pre tieto dve stránky. Odtlačok používateľského stavu v živej databáze zostal nezmenený. Dočasný prehliadač aj jeho overovacia relácia boli ukončené, služba na porte 1111 zostáva spustená.
- Dočasné snímky a report: /tmp/poznamkovnik-tutorial-stdio-numeric-verification/. Diagnostika počas písania, CSS, sandbox a firmvérové nástroje sa nemenili.

Kontrakty boli skontrolované proti [WG14 N1570, oddielom 7.4, 7.20 a 7.21](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf), najmä snprintf v 7.21.6.5 a blokovému prenosu v 7.21.8. Dokument je návrh C11; príklady a regresné testy používajú režim C17. Nejde o overenie na viacerých architektúrach.

Ďalej: rozvinúť zatiaľ stručné lekcie C o callbackoch a prenositeľnosti. Doplniť callback s kontextom a jasnou životnosťou, pravidlá variadických argumentov a konkrétne prenositeľné dátové prevody s testami. Dlhodobá úloha učebníc zostáva rozpracovaná; mobilná konzola, súbežnosť a reálne firmvérové toolchainy zostávajú samostatnými blokmi.

## Učebnica C: Callbacky A Prenositeľnosť 2026-09-11

- Rozšírené obe lekcie pri zachovaní identifikátorov. Callbacky pokrývajú presný podpis, NULL, synchrónny požičaný kontext, poradie volaní, zastavenie, chybu a životnosť. Variadický príklad vysvetľuje povýšenia argumentov, protokol počtu a typov, dva kurzory cez va_copy a príslušné va_end.
- Prenositeľnosť dopĺňa dostupnosť presných typov, least alternatívu, explicitný dvojoktetový big-endian formát, kontrolu rozsahu a kapacity pred zápisom a rozlíšenie nešpecifikovaného poradia od UB. Formát výslovne vyžaduje CHAR_BIT == 8; nejde o predpoklad platný pre každú implementáciu C.
- Šesť spustiteľných ukážok zhodných s výkladom: dve existujúce rozšírené a štyri nové. Pridané dve cvičenia so štyrmi variantmi a dve kontrolné otázky. Každý variant callbacku skúša rovnosť s limitom aj plné počítadlo; každý variant kódovania obsahuje asymetrické bajty a chyby kapacity aj rozsahu.
- Pridaných 14 Python testov. Overené jediné volanie apply, nevolanie pri chybe, 75 kombinácií dĺžky, miesta zastavenia a návratovej akcie, oddelené kontexty, hraničné hodnoty a zachovanie stavu. Variadické testy pokrývajú povýšené argumenty, krajné int, prázdny vstup a párovanie inicializácie/ukončenia kurzorov pri opakovaných volaniach.
- Všetkých 65536 hodnôt formátu otestovaných na troch posunutých bajtových adresách: známe očakávané oktety, spätný prevod a nezmenené okolie cieľa. Ďalšie testy pokrývajú NULL, kapacity 0/1/2, väčší buffer, 65536 a maximum pracovného typu. Testy cvičení odmietajú štartovací kód, zámenu >= za > a obrátené bajtové poradie vo všetkých variantoch.
- Neprítomnosť presného typu a nesplnenie požiadavky CHAR_BIT boli simulované pre vetvu a diagnostiku prekladu. Poradie volaní overené s GCC pri -O0 aj -O2; test pripúšťa obe dovolené permutácie. Nejde o beh na inom ABI či big-endian procesore. Chybné podpisy a priame neusporiadané inkrementy sa overujú odmietnutím prekladu s varovaniami ako chybami, nie vykonaním UB.
- npm run check: 186 Python testov úspešných, 4 preskočené pre nedostupné C#/Go/Java/Rust nástroje; 10 frontendových testov úspešných. Cielená sada po sprísnení hraničných prípadov: 36 úspešných testov. Zostavené assets bez zmeny; existujúce SQLite ResourceWarning zostávajú mimo obsahového bloku.
- Po reštarte služby všetkých šesť programov prešlo cez API aj tlačidlo Spustiť, osem riešení cvičení cez API. Obe lekcie skontrolované v Chromium pri 1440/875/390 bez pretekania čítačky či dokumentu a bez JavaScript výnimiek. Test obnovy aj odtlačok živej databázy potvrdili zachovanie poznámok, konceptov, postupu a odpovedí.
- Dočasné snímky a report: /tmp/poznamkovnik-tutorial-callbacks-portability-verification/. Overovacia relácia a prehliadač ukončené, služba na porte 1111 ponechaná spustená. Diagnostika počas písania, CSS a sandbox sa nemenili.

Pravidlá volania a variadických argumentov boli skontrolované proti [WG14 N1570, oddielom 6.3.2.3, 6.5.2.2 a 7.16](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf); ide o návrh C11, príklady sa overujú v režime C17. Dva spotrebované va_list sa nezamieňajú za jednu opakovane použiteľnú kópiu.

Ďalej: samostatný blok súbežnosti C nad existujúcim úvodom do atomiky. Overiť dostupnosť threads.h a pripraviť životnosť dát vlákien, mutex pre súvisiaci stav a atomické počítadlo; jasne oddeliť atomickosť od publikovania okolitých dát. Dlhodobá úloha učebníc zostáva rozpracovaná. Mobilná konzola a reálne firmvérové toolchainy zostávajú oddelené.

## Učebnica C: Vlákna, Mutexy A Atomika 2026-09-11

- Pridané dve nadväzujúce lekcie: Vlákna, životnosť dát a mutexy; Atomické operácie a publikovanie dát. Existujúce stránky a identifikátory zostali zachované. Každá nová lekcia má výklad, učebný rámec, ciele, cvičenie so štyrmi variantmi a kontrolnú otázku.
- Päť nových spustiteľných programov zhodných s výkladom: maximum v požičanom objekte, spoločný počet a súčet pod mutexom, deterministický model strateného atomického zvýšenia, skutočné atomické počítadlo dvoch pracovníkov a jednorazová schránka release/acquire.
- Podpora threads.h, mutexu a atomiky overená v oboch existujúcich spúšťačoch ešte pred doplnením obsahu. Príklady nepotrebovali zmenu limitov, argumentov prekladača ani sandboxu. Samostatné natívne testy používajú GCC s -pthread; výklad rozlišuje miestnu dostupnosť od požiadaviek iného cieľa.
- Pri čiastočnej chybe vytvárania sa pripoja všetky už spustené vlákna. Výsledok join sa odlišuje od výsledku pracovníka. Mutex sa ničí až po skončení pracovníkov. Pri neúspešnom join alebo unlock samostatná ukážka ukončí proces cez _Exit, pretože nie je potvrdená životnosť dát či vlastníctvo zámku; nejde o predstierané bežné upratanie.
- Pridaných 16 Python testov: 40 opakovaných natívnych behov štyroch vláknových programov, skutočné vytváranie a join pri simulovaných chybách prvého/druhého štartu a pracovníka, chyby mutexu a zachovanie rozsahov count/total bez čiastočnej zmeny. Pri fatálnej chybe sa testuje nevrátenie k rušeniu zdrojov.
- Jednovláknový model potvrdzuje stratené zvýšenie aj pri seq_cst. Schránka má test stavov, NULL a krajných int; ďalších osem výmen drží producenta nažive až do čítania pred join. Opakované publikovanie či viacerí producenti nie sú súčasťou kontraktu schránky.
- Všetky varianty cvičení overené správnym riešením a odmietnutím bezpečného štartovacieho kódu. Maximum so začiatkom na nule zlyhá v každom variante. Test pamäťového poradia výslovne ukazuje, že relaxed môže prejsť jednovláknovým porovnaním výstupu; samostatná kontrola operácií ho odmietne. Inicializácia atomic_init sa odlišuje od release publikácie.
- npm run check: 202 Python testov úspešných, 4 preskočené pre nedostupné C#/Go/Java/Rust nástroje; 10 frontendových testov úspešných. Finálna samostatná sada súbežnosti: všetkých 16 úspešných. Zostavené assets bez zmeny; existujúce SQLite ResourceWarning zostávajú mimo obsahového bloku.
- Po reštarte služby všetkých päť príkladov prešlo cez API aj tlačidlo Spustiť, osem riešení cvičení cez API. Obe lekcie overené v Chromium pri 1440/875/390 bez pretekania čítačky či dokumentu a bez JavaScript výnimiek. Test obnovy aj odtlačok živej databázy potvrdili zachovanie poznámok, konceptov, postupu a odpovedí.
- Dočasné snímky a report: /tmp/poznamkovnik-tutorial-concurrency-verification/. Overovacia relácia aj prehliadač ukončené, služba na porte 1111 ponechaná spustená. Diagnostika počas písania, CSS a nastavenia sandboxu sa nemenili. ThreadSanitizer sa nespúšťal; UBSan ani opakovanie behov nie sú dôkazom neprítomnosti všetkých dátových pretekov či pokrytím všetkých rozvrhov.

Pravidlá synchronizácie a životnosti boli skontrolované proti [WG14 N1570, oddielom 5.1.2.4, 7.17 a 7.26](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf). Ide o návrh C11; zdroje sa overujú v režime C17. Použitie -pthread pri preklade aj linkovaní opisuje [dokumentácia GCC](https://gcc.gnu.org/onlinedocs/gcc/Link-Options.html).

Ďalej: podmienkové premenné a ohraničená fronta producent/konzument, kontrola predikátu v slučke, prebúdzanie a ukončenie bez aktívneho čakania. Samostatne riešiť chybové cesty a dokončenie už spustených pracovníkov. Dlhodobá úloha učebníc zostáva rozpracovaná; mobilnú konzolu a reálne firmvérové toolchainy neoznačovať za dokončené.

## Učebnica C: Podmienkové Premenné A Fronta 2026-09-11

- Pridané dve lekcie: Podmienkové premenné a čakanie na stav; Ohraničená fronta producent/konzument. Tri úplné spustiteľné príklady zhodné s výkladom, osem variantov cvičení, dve kontrolné otázky, konkrétne ciele a učebné rámce. Existujúce identifikátory a obsah sa nemenili.
- Brána vysvetľuje predikát pod mutexom, cnd_wait v slučke, predčasné prebudenie aj publikáciu pred vznikom pracovníka. Signal nie je uložené povolenie; prebudenie nenahrádza kontrolu stavu ani join. Fatálna chyba synchronizácie je oddelená od bežnej chyby vytvárania či výpočtu.
- Fronta má pevnú kapacitu tri, FIFO, oddelené not_empty/not_full a idempotentné uzavretie. Nové položky odmietne, prijaté dovolí dočítať a pri konci nemení výstupný objekt. Uzavretie pod mutexom prebúdza všetkých z oboch skupín. Dvanásť položiek v skutočných vláknach dá count=12 total=78 bez aktívneho čakania.
- Pri zlyhaní druhej inicializácie podmienky sa zrušia len predchádzajúce úspešne vytvorené objekty v opačnom poradí. Pri čiastočnom štarte sa fronta uzavrie pred join. Konzument pri chybe hodnoty, počtu či súčtu uzavrie frontu pred návratom, aby nezostal blokovaný producent. Všetky vytvorené vlákna sa pripoja pred zrušením zdrojov.
- Pridaných 17 Python testov: 30 opakovaných behov troch programov, 100 pretočení fronty s INT_MIN/0/INT_MAX, zachovanie FIFO a výstupu pri konci. Riadené predčasné prebudenia odhalia if namiesto while aj chýbajúci ukončovací predikát. Skutočné dva čakajúce konzumenty a dva producenty sa koordinujú s testom cez mutex a podmienku, bez časového odhadu sleep. Kontrola operácií odmietne signal namiesto každého broadcast aj neuzavretý stav pod zámkom.
- npm run check: 219 Python testov úspešných, 4 preskočené pre nedostupné C#/Go/Java/Rust nástroje; všetkých 10 frontendových testov úspešných. Cielená sada: 17 úspešných testov. Testy obnovy chránia poznámky, koncepty, postup, odpovede aj časy vytvorenia nových stránok. Zostavené assets bez zmeny; existujúce SQLite ResourceWarning zostávajú mimo obsahového bloku.
- Po reštarte všetky tri príklady prešli cez API aj tlačidlo Spustiť, osem riešení cvičení cez API. Obe lekcie skontrolované v Chromium pri 1440/875/390 bez pretekania čítačky či dokumentu a bez JavaScript výnimiek. Odtlačok používateľského stavu zostal nezmenený. Dočasná relácia a prehliadač ukončené, služba na porte 1111 ponechaná spustená.
- Dočasné snímky a report: /tmp/poznamkovnik-tutorial-conditions-verification/. Mobilná čítačka zostáva pri 390 úzka a dlhý kód sa posúva v bloku; nejde o mobilnú úpravu. CSS, diagnostika počas písania, sandbox ani firmvérové nástroje sa nemenili. ThreadSanitizer sa nespúšťal; UBSan a riadené rozvrhy nie sú dôkazom neprítomnosti všetkých dátových pretekov či zárukou férovosti.

Kontrakty inicializácie, čakania, prebúdzania a životnosti boli skontrolované proti [WG14 N1570, oddielu 7.26](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf). N1570 je návrh C11; nešpecifikované prebudenia výslovne zohľadňuje [oprava DR 480 zaradená pre C17](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n2396.htm#dr_480). Príklady aj natívne testy sa prekladajú v režime C17. Cvičenia otvorene rozlišujú porovnanie výpisu od samostatnej kontroly protokolu čakania a prebúdzania.

Ďalej: časovo obmedzené čakanie cez cnd_timedwait a kooperatívne zastavenie pracovníkov. Vysvetliť jeden absolútny termín, opätovnú kontrolu predikátu, odlíšenie timeoutu od uzavretia a dokončenie pred zrušením zdrojov. Dlhodobá úloha učebníc zostáva rozpracovaná; mobilnú konzolu a skutočné firmvérové toolchainy riešiť oddelene.

## Učebnica C: Termíny A Kooperatívne Zastavenie 2026-09-11

- Pridané dve lekcie: Časovo obmedzené čakanie; Kooperatívne zastavenie pracovníkov. Tri úplné spustiteľné príklady zhodné s výkladom, osem variantov cvičení, dve kontrolné otázky, učebné rámce a ciele. Staré identifikátory ostali zachované. Rozdelenie zdrojového fragmentu push/pop umožnilo opätovné použitie; všetkých 78 pôvodných zdrojových konštánt zostalo doslova zhodných s predchádzajúcim commitom.
- queue_pop_until odlišuje položku, koniec a timeout. Čakacia funkcia opakovane používa pôvodný absolútny termín TIME_UTC, po thrd_timedout kontroluje stav pod mutexom a uprednostní dostupné dáta alebo uzavretie. Pri konci a timeoute nemení výstup; neočakávaná chyba synchronizácie sa nezamieňa za bežný výsledok.
- Výklad rozlišuje kalendárny a monotónny čas, nanosekundový zápis od presnosti hodín a limit čakania od celkovej doby návratu vrátane získavania mutexu. Úplné ukážky používajú zámerne okamžitý termín z overeného timespec_get, bez nekontrolovanej aritmetiky time_t. Všeobecný prevod relatívneho trvania na budúci termín ani monotónne platformové rozhranie nie sú implementované.
- Timeout sám frontu nezatvára ani neukončuje vlákno. Druhý program ukazuje až explicitné rozhodnutie pracovníka uzavrieť frontu. Tretí program po tretej položke zastaví prijímanie, dočíta prijaté dáta a kontroluje rovnosť počtov až po oboch join. Prijatých môže byť tri až šesť podľa rozvrhu; výpis nepredstiera jediný presný počet.
- Pridaných 17 Python testov: 30 opakovaných natívnych behov, osem riadených kombinácií návratu čakania a stavu fronty, zachovaný termín cez viac prebudení, prednosť položky aj po timeoute či uzavretí a nezmenený výstup pri odmietnutí. Časovaný odber prejde 100 plných cyklov fronty a po odobratí signalizuje producenta ešte pod mutexom. Mutácie odhalia if namiesto while, okamžité vrátenie timeoutu bez kontroly, obnovovanie termínu, predčasný zápis do výstupu aj upozornenie nesprávnej skupiny čakajúcich.
- Skutočný pracovník s budúcim termínom sa koordinovane dostane do cnd_timedwait a následne sa zobudí položkou alebo uzavretím. Len tento hostiteľský test používa Linux TIME_UTC/POSIX epochu z Pythonu; nejde o tvrdenie prenositeľnosti číselnej epochy v C. Testy nevyžadujú návrat na konkrétnu milisekundu ani nepoužívajú sleep ako koordináciu.
- Chyba hodín nesmie inicializovať frontu ani použiť neplatný termín. Preverené sú tri body inicializácie, prvý a druhý štart a fatálna chyba join. Požiadavka pred štartom je pozorovaná skutočnými pracovníkmi. Riadený producent prejde všetkých 13 hraníc od nuly po 12 prijatých položiek; odmietnutú nezapočíta. Konzument musí dočítať aj položky uložené pred zastavením.
- npm run check: 236 Python testov úspešných, 4 preskočené pre nedostupné C#/Go/Java/Rust nástroje; všetkých 10 frontendových testov úspešných. Nová cielená sada má 17 úspešných testov. Rozšírený test opakovaného nasadenia chráni poznámky, koncepty, odpovede, postup a časy vytvorenia oboch nových stránok. Zostavené assets bez zmeny; existujúce SQLite ResourceWarning zostávajú mimo obsahového bloku.
- Po reštarte tri príklady prešli cez API aj tlačidlo Spustiť, osem riešení cvičení cez API. Obe lekcie skontrolované v Chromium pri 1440/875/390 bez pretekania čítačky či dokumentu a bez JavaScript výnimiek. Odtlačok používateľského stavu zostal nezmenený. Dočasná relácia a prehliadač ukončené; služba na porte 1111 ponechaná spustená.
- Dočasné snímky a report: /tmp/poznamkovnik-tutorial-deadlines-verification/. Existujúca úzka mobilná čítačka ani konzola sa neupravovali. Diagnostika počas písania, CSS, sandbox a firmvérové nástroje sa nemenili. ThreadSanitizer sa nespúšťal; UBSan, výstup ani vybrané riadené rozvrhy nie sú dôkazom neprítomnosti všetkých dátových pretekov.

Časová báza, timespec_get a výsledky čakania boli overené v [návrhu WG14 N1570, oddieloch 7.26.3.5, 7.27.1 a 7.27.2.5](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf). Dokument je návrh C11; možnosť nešpecifikovaných prebudení zohľadňuje [oprava DR 480 pre C17](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n2396.htm#dr_480). Zdrojové programy sa prekladajú v režime C17. Priorita dostupného stavu pred timeoutom je explicitný kontrakt našej fronty, nie dôkaz, že položka bola vložená pred termínom.

Ďalej: koordinácia viacerých producentov, vlastník bežného uzavretia po dokončení celej skupiny a čiastočne úspešný štart. Zachovať spotrebiteľa schopného dočítať frontu počas pripájania producentov a oddeliť predčasné zastavenie od bežného konca. Dlhodobá úloha učebníc zostáva rozpracovaná; mobilnú konzolu a skutočné firmvérové toolchainy riešiť oddelene.

## Učebnica C: Skupina Producentov 2026-09-11

- Pridaná lekcia Skupina producentov a spoločné ukončenie, dva úplné spustiteľné programy, štyri varianty cvičenia a kontrolná otázka. Existujúce identifikátory a všetkých 92 pôvodných zdrojových konštánt zostali nezmenené. Fronta s kapacitou tri sa používa bez úprav.
- Koordinátor vytvorí konzumenta pred producentmi. Počas pripájania producentov konzument ďalej odoberá; bežné uzavretie príde až za ich slučkou join. Prvý dokončený producent frontu nezatvára. Pri chybe štartu alebo pracovníka sa uzavrie skôr a pripoja sa všetky úspešne vytvorené vlákna pred zrušením synchronizačných objektov.
- Tri nemenné požičané dávky prenesú 12 položiek so súčtom 1110. Každý producent má vlastný stabilný kontext a počítadlo. Výklad rozlišuje poradie v jednej dávke od nešpecifikovaného prepletenia dávok. Samostatný výsledný súhrn sa zapíše až po úspechu celej skupiny; pri bežnom chybovom návrate ostáva nezmenený.
- Druhý program overuje nulovú skupinu a chybnú dávku NULL s nenulovým počtom. Pracovník oznamujúci chybu musí sám uzavrieť frontu pred návratom, aby odblokoval partnerov. Koordinátor totiž môže čakať na iného producenta pri plnej fronte. Ukážka očakávanú chybu overí a sama skončí úspešne; nepredstiera úspešné spracovanie chybných dávok.
- Pridaných 16 Python testov: 14 pre obsah, skupinu a skutočný sandbox, dva pre oddelenie limitov prekladu a behu. Natívne testy používajú prísne varovania ako chyby a UBSan. Symbolický model preveruje 40 kombinácií počtu producentov, skoršej chyby, chyby producenta a konzumenta; mutácie odmietajú predčasné uzavretie, stratenú chybu aj predčasný návrat z pripájania.
- Riadené skutočné vlákna dokončia prácu prvého producenta pred štartom ďalších. Druhý rozvrh zadrží konzumenta aj neskorších producentov, kým prvý nečaká na plnej fronte; chybný druhý producent ho následne odblokuje uzavretím. Synchronizácia testov nepoužíva sleep. Ďalšie testy kontrolujú všetky štyri chyby štartu a join, tri chyby inicializácie, hraničné stavy konzumenta, prázdne a zdieľané vstupy a každú prenesenú hodnotu práve raz v poradí vlastnej dávky.
- Integračné overenie odhalilo chybu vo vývojovom spúšťači: C preklad s -g1 a UBSan vytvoril približne 85 KiB dočasného assembleru, ale dostával limit súboru určený pre beh programu, 64 KiB. Vetva C v DevelopmentCodeRunner teraz používa existujúci 8 MiB limit prekladu rovnako ako C++. Limity behu, výstupu, pamäte, času a počtu procesov zostali nezmenené; UBSan aj diagnostika sa zachovali. Jednoduchý CCodeRunner pre cvičenia sa nemenil.
- Regresné testy preverujú samostatný preklad aj vykonanie v debug/release pre C a C++. Skutočný program v oboch profiloch číta mäkký aj tvrdý RLIMIT_FSIZE a pokusom o nadlimitný zápis potvrdzuje pôvodných 64 KiB. Tento test limitov je určený pre hostiteľský linuxový sandbox, nie je ukážkou prenositeľného C.
- npm run check: 252 Python testov úspešných, 4 preskočené pre nedostupné C#/Go/Java/Rust nástroje; všetkých 10 frontendových testov úspešných. Cielená sada skupiny a spúšťača: 26 úspešných testov. Rozšírený test opakovaného nasadenia chráni poznámky, koncepty, postup, odpovede a časy vytvorenia novej lekcie. Zostavené assets bez zmeny.
- Po oprave a reštarte oba programy prešli cez API aj tlačidlo Spustiť; všetky štyri riešenia cvičenia cez API. Chromium pri 1440/875/390 bez pretekania dokumentu či čítačky a bez JavaScript výnimiek. Odtlačok používateľského stavu zostal nezmenený. Snímky a report sú v /tmp/poznamkovnik-tutorial-groups-verification/. Overovacia relácia aj prehliadač sú ukončené, služba na porte 1111 zostáva spustená.
- Mobilná čítačka zostáva úzka a dlhé riadky kódu sa posúvajú v bloku; CSS ani mobilná konzola sa neupravovali. ThreadSanitizer sa nespúšťal. UBSan, opakované behy ani vybrané riadené rozvrhy nie sú dôkazom neprítomnosti všetkých dátových pretekov alebo zárukou férovosti plánovania.

Synchronizácia pri vytvorení a úspešnom pripojení vlákna bola skontrolovaná proti [WG14 N1570, oddielom 7.26.5.1 a 7.26.5.6](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf). Ide o návrh C11; príklady sa prekladajú v režime C17. Vlastník bežného uzavretia a politika skorého ukončenia pri chybe sú kontrakty tejto skupiny, nie ďalšie pravidlá štandardnej knižnice.

Ďalej: vlastníctvo položiek prenášaných frontou. Určiť okamih odovzdania dynamicky alokovanej položky, zachovanie vlastníctva pri odmietnutom vložení a uvoľnenie prijatých aj zostávajúcich položiek pri chybe, až po ukončení pracovníkov. Začať samostatnou malou ukážkou s jedným producentom a konzumentom; nezamieňať kópiu ukazovateľa za kópiu dát. Dlhodobá úloha zostáva rozpracovaná, mobilná konzola a firmvérové toolchainy sú samostatné bloky. Popis úlohy sa približuje limitu 10000 znakov; ďalšie podrobnosti viesť v tomto súbore bez orezania histórie úlohy.

## Ohraničenie Prvej Verzie C

Po otázke na zostávajúcu prácu sme oddelili dokončenie praktickej učebnice od ďalších pokročilých rozšírení. Pracovný odhad pred týmto blokom bol 8–12 blokov, orientačne 20–30 hodín s rezervou, nie záväzný termín. Používateľ vybral prácu na hodinu; prvý ohraničený blok je rekurzia. Ďalšie pokračovania majú uzatvárať tento rozsah, nie automaticky pridávať nadväzujúce špeciality súbežnosti.

- [x] Rekurzia: základný prípad, postup ku koncu, návraty, vlastný lokálny stav a porovnanie s cyklom.
- [x] Argumenty programu: argc/argv, hranice prístupu, kontrolované spracovanie a chybné vstupy.
- [ ] Viacrozmerné polia a zložitejšie deklarácie: rozšíriť existujúce základy a príklady.
- [ ] union a jednoduché vlastné kolekcie: pomenovaný stav, kopírovanie, vlastníctvo a uvoľnenie zdrojov.
- [ ] Praktické desatinné výpočty, math.h a doplnenie knižničnej referencie v rozsahu bežných úloh.
- [ ] Dva súhrnné malé projekty spájajúce viac kapitol, s cvičeniami a testami.
- [ ] Záverečný audit nadväznosti a správnosti celého obsahu, vrátane skrátených výrezov a pokrytia cvičeniami. Pri výreze increment v lekcii functions preveriť kontrakt pre INT_MAX.

Vlastnené položky v súbežnej fronte, ďalšie vláknové protokoly, úplná referencia každej funkcie, POSIX, sieťovanie a firmvér sú voliteľné ďalšie rozšírenia. Tento rozsah nahrádza predchádzajúci automatický bod pokračovania s frontou. Mobilné úpravy aplikácie zostávajú samostatnou úlohou.

## Učebnica C: Rekurzia 2026-09-11

- Pridaná samostatná lekcia Rekurzia a návrat z volania medzi funkcie a rozsah/životnosť. Dva spustiteľné programy, jedno cvičenie so štyrmi variantmi, kontrolná otázka, učebný rámec a ciele. Pôvodná lekcia funkcií a jej cvičenie sa nemenili; všetkých 101 predchádzajúcich zdrojových konštánt zostalo zhodných.
- Prvá ukážka vypíše cestu volaní sum_to dovnútra aj späť. Prijíma iba 0 až 10; väčší vstup odmietne pred prvým enter. Výklad rozlišuje základný prípad, vlastné automatické objekty jednotlivých volaní, návrat hodnoty a zdieľanú statickú premennú. Zásobník volaní je vysvetľujúci model, nie prísľub konkrétneho rozloženia pamäte.
- Druhý program porovnáva rekurzívny a iteratívny Euklidov algoritmus. Kontrola b == 0 predchádza operácii %, rekurzívny krok zmenší druhý argument. Nulové vstupy aj zvolený výsledok gcd(0, 0) == 0 majú explicitný kontrakt. Výklad odlišuje matematické ukončenie od obmedzených zdrojov prostredia; nesľubuje optimalizáciu koncového volania.
- Pridaných 11 Python testov. Natívne programy prešli s UBSan a varovaniami ako chybami, hlavné výpisy pri -O0 aj -O2/NDEBUG. Overený celý rozsah výpisu 0..10 aj opakované volania v jednom procese, odmietnutie 11 a UINT_MAX, chyby výpisu a záverečného flush. Obe verzie gcd súhlasia s nezávislou tabuľkou math.gcd pre všetkých 4096 dvojíc 0..63; ďalšie prípady pokrývajú UINT_MAX, susedné hodnoty, nuly, rovnosť a dlhší reťazec zvyškov.
- Samostatná kontrola skutočných volaní vyžaduje (48,18), (18,12), (12,6), (6,0). Odmietne nezmenené argumenty aj nahradenie rekurzie cyklom. Skúšobňa cvičenia naďalej hodnotí iba výstup; test aj zadanie výslovne priznávajú, že správny cyklus môže výstupovou kontrolou prejsť. Každý variant odmieta bezpečný štartovací kód a chybný základný návrat.
- Cielená sada rekurzie a obnovy obsahu: 27 testov úspešných. npm run check: 263 Python testov úspešných, 4 preskočené pre nedostupné C#/Go/Java/Rust nástroje; 10 frontendových testov úspešných. Rozšírený test opakovaného nasadenia chráni poznámky, koncepty, postup, odpovede a časy vytvorenia novej stránky.
- Oba programy prešli cez skutočný debug sandbox, API aj tlačidlo Spustiť; štyri riešenia cvičenia cez API. Chromium pri 1440/875/390 bez pretekania dokumentu a čítačky a bez JavaScript výnimiek. Používateľský stav zostal nezmenený, dočasný prehliadač a relácia ukončené. Report a snímky: /tmp/poznamkovnik-tutorial-recursion-verification/.
- CSS, mobilné rozloženie, spúšťače aj limity sa nemenili, zostavené assets ostali zhodné. Úzka mobilná čítačka zostáva existujúcim obmedzením. Dlhodobá úloha učebníc ostáva rozpracovaná; jej popis s 9994 znakmi sa neorezával ani ďalej nepredlžoval. Podrobný postup pokračuje tu.

Prípustnosť priamych aj nepriamych rekurzívnych volaní a vznik samostatných automatických objektov boli overené v [WG14 N1570, oddieloch 6.5.2.2 a 6.2.4](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf). Ide o návrh C11; ukážky a testy sa prekladajú v režime C17.

Ďalej: jeden ohraničený blok argumentov programu argc/argv, vrátane nulového počtu používateľských argumentov, hraníc a kontrolovaného prevodu čísla. Najprv preveriť, ako ich poskytuje existujúca skúšobňa; nezamieňať stdin s argumentmi ani nerozširovať sandbox. Po tomto hodinovom výbere nezačínať automaticky ďalšiu tému.

## Učebnica C: Argumenty Programu 2026-09-12

- Pridaná lekcia Argumenty programu argc a argv medzi vstup/výstup a spracovanie chýb. Tri úplné spustiteľné programy, cvičenie so štyrmi variantmi, kontrolná otázka, ciele a učebný rámec. Všetkých 108 predchádzajúcich zdrojových konštánt, 38 stránok a 68 príkladov zostalo nezmenených; nové položky majú vlastné identifikátory.
- Výklad odlišuje argc od počtu používateľských argumentov, pripúšťa argc == 0, vysvetľuje obmedzenia argv[0], hranicu i < argc, nulový ukazovateľ argv[argc] a prázdny reťazec. Prvý program vypíše skutočné argumenty procesu cez pevný formát. Druhý vyžaduje presne jedno číslo a po kontrole počtu deleguje prevod na existujúci parse_int bez jeho zmeny. Chyby počtu, textu a rozsahu majú odlišnú diagnostiku; neúspech nemení výstupný objekt.
- Malá skúšobňa odovzdáva iba stdin. Prvý program v nej vypíše arguments=0, druhý zámerne zlyhá s Usage: number INTEGER; opis aj výklad na to upozorňujú. Skutočné argumenty sa zadávajú cez existujúce pole Parametre spúšťania vo Vývoji. Tretí program a cvičenie používajú výslovne označené vlastné testovacie polia, nie predstierané argumenty procesu. API, schéma dát, koncepty, spúšťače a sandbox sa nemenili.
- Pridaných 13 Python testov. Natívne C programy prešli s UBSan a prísnymi varovaniami ako chybami. Overené sú medzery v jednom argumente, prázdny argument, pevný formát pri %s, doslovné shellové metaznaky, stdin nezávislý od argv, chýbajúce a nadbytočné argumenty, znamienka, nula, chybný koniec, INT_MIN/INT_MAX a hodnoty tesne mimo rozsahu. Samostatné kontroly pokrývajú nulový počet, prázdne meno programu, NULL rozhrania, zachovanie výsledku a chyby výstupu. Testovací program prešiel pri -O0 aj -O2/NDEBUG; všetky varianty cvičenia odmietajú štartovací kód, povolenie nadbytočných argumentov a nesprávny index.
- Integračné testy používajú skutočné argumenty cez API Vývoja, vrátane úvodzoviek, prázdnej hodnoty a odmietnutia neuzavretých úvodzoviek. Cielená sada argumentov, obnovy učebného stavu a API: 35 testov úspešných. npm run check: 276 Python testov úspešných, 4 preskočené pre nedostupné C#/Go/Java/Rust nástroje; všetkých 10 frontendových testov úspešných. Zostavené assets bez zmeny.
- Po reštarte tri príklady overené cez API aj tlačidlo Spustiť, štyri riešenia cvičenia cez API. V Chromium overené otvorenie príkladu vo Vývoji cez dočasný prepojený projekt a štyri behy s parametrami: -7, žiadny argument, 42x a jedno číslo s okolitými medzerami. Nezávislý stdin obsahoval 999. Dočasný projekt bol odstránený; celý používateľský vývojový priestor aj odtlačky poznámok, konceptov, postupu a odpovedí zostali zhodné.
- Lekcia skontrolovaná pri 1440/875/390 bez vodorovného pretekania dokumentu či čítačky a bez JavaScript výnimiek. Existujúca úzka mobilná čítačka a vodorovné posúvanie dlhého kódu sa nemenili. Snímky a report: /tmp/poznamkovnik-tutorial-arguments-verification/. Overovací prehliadač a relácia ukončené, služba na porte 1111 ostáva spustená. Dlhodobá úloha je naďalej rozpracovaná; jej popis s 9994 znakmi sa nepredlžoval ani neorezával.

Kontrakt main a argv bol overený proti [WG14 N1570, oddielu 5.1.2.2.1](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf). Ide o návrh C11; ukážky sa prekladajú ako C17. Pravidlá zoskupovania parametrov vo Vývoji vychádzajú z existujúceho spúšťača a [oficiálnej dokumentácie shlex](https://docs.python.org/3/library/shlex.html): lexikálne rozdelenie nie je vykonanie shellu. Cvičenie overuje výsledky explicitných prípadov, nie úplnú správnosť ľubovoľného riešenia.

Ďalej: jeden ohraničený blok viacrozmerných polí a zložitejších deklarácií. Nadviazať na existujúce lekcie polí a ukazovateľov, vysvetliť rozmer riadka, ukazovateľ na pole oproti poľu ukazovateľov a vhodné parametre funkcií. Zachovať kontrolu hraníc, doplniť spustiteľné príklady a cvičenie; nezačínať automaticky kolekcie ani ďalšiu súbežnosť.
