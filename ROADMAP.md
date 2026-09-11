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
