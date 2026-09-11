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
