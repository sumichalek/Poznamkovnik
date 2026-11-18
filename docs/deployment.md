# Domáci server a aktualizácie cez Git

Projekt obsahuje aktualizačný nástroj `scripts/server-update.sh`. Používa Git tagy, samostatné vydania a povinnú novú zálohu dát aj nastavení pred každou aktiváciou. Je určený pre Linux so systemd používateľskou službou. Vývojový postup je v [development.md](development.md).

Pre osobnú inštaláciu je primárny [interaktívny sprievodca](interactive-installation.md): `bash scripts/install.sh --plan` vypíše plán bez zmien a `bash scripts/install.sh` vedie používateľa potvrdeniami. Nasledujúce priame príkazy sú tiež predvolene interaktívne; pri vzdialenom spúšťaní potrebujú `ssh -t`. Pre vedomú automatizáciu sa musí výslovne uviesť `--yes` pred podpríkazom. Povinná záloha zostáva aj v tomto režime.

## Ako to funguje

```text
vývoj → testy a build → commit a tag → GitHub
                                         ↓ fetch
server: releases/v0.57.0/ ← current
                 ↓
           shared/data/
```

Git repozitár na GitHube je privátny. Server používa vlastný read-only deploy key a SSH alias podľa [úvodného návodu](private-git-access.md), napríklad `git@github-poznamkovnik:sumichalek/Poznamkovnik.git`. Anonymné HTTPS na jeho stiahnutie nestačí. Tag vyberá konkrétny otestovaný commit. Na prvú inštaláciu používaj najmenej `v0.57.5`, ktorá opravuje aj vytváranie položiek cez LAN HTTP a obsahuje predchádzajúce opravy prihlásenia a UFW. Pred použitím musí byť príslušný tag skutočne zverejnený. Táto implementácia sama nevytvára commity ani nič neposiela na GitHub.

```text
~/apps/poznamkovnik/
├── repository/                  Git na načítanie tagov
├── releases/
│   ├── v0.57.0/                 kód + vlastné .venv/
│   └── v0.57.1/
├── current -> releases/v0.57.1
└── shared/
    ├── data/                    databáza, účty, nastavenia a všetky súbory
    ├── server.json              nastavenie správy tejto inštalácie
    ├── config.env              voliteľné premenné prostredia služby
    ├── update-state.json        výsledok poslednej operácie
    ├── uninstall-state.json     priebeh/výsledok prípadného odinštalovania
    ├── update-backups/          nové úplné zálohy pred aktiváciou
    └── recovery-*/              zachovaný stav po obnove
```

Vydania na serveri sa neupravujú. Aktualizátor odmietne lokálne úpravy, neexistujúci tag, nesúlad tagu so súborom `VERSION` aj súbežnú aktualizáciu. Požiadavka na už aktívny tag je bez zmeny; neinštaluje znovu jeho bežiace Python prostredie.

## Vytvorenie vydania tu vo vývoji

Jediným zdrojom čísla verzie je `VERSION`. Zostavenie ho vloží do JavaScriptu, HTML a odkazov na CSS/JS. Backend číta ten istý súbor. Python runtime balíky sú presne určené v `requirements.lock`; pri zmene závislostí aktualizuj aj tento súbor a over ich v čistom virtuálnom prostredí.

```bash
source .venv/bin/activate
python -m pip install -r requirements.lock
npm ci
npm run check
git diff --check
git status --short
```

Pri zmenách súvisiacich s LAN HTTP over aj skutočný prehliadač. Ak je nainštalované Chromium, nasledujúci voliteľný test spustí aplikáciu na dočasnom loopback porte s vlastnými dátami a profilom prehliadača. Iba pre túto inštanciu Chromium namapuje skúšobný názov `poznamkovnik.test` na loopback, aby stránka naozaj nemala bezpečný kontext ani `randomUUID()`. Systémové DNS, Pi-hole a domáci server nemení:

```bash
env POZNAMKOVNIK_BROWSER_TESTS=1 python3 -B -m unittest tests.test_lan_http_browser -v
```

Test cez skutočný formulár vytvorí knižnicu so štítkom a overí jej uloženie v API. Vyžaduje aktuálne zostavený frontend (`npm run build`), právo otvoriť lokálny port a spustiť sandbox Chromium. Všetky jeho dáta sú dočasné.

Vybrané zmeny ulož do commitu vrátane zostavených `assets/` a aktualizovaného HTML. Potom over samotný obsah commitu v čistom prostredí:

```bash
python3 scripts/check-release.py HEAD
```

Kontrola vytvorí dočasnú kópiu z Gitu, overí prítomnosť inštalátora, odinštalátora a návodov aj štart menu v režime plánu. Nainštaluje `requirements.lock` do nového virtuálneho prostredia, overí vygenerovanú službu parserom `systemd-analyze --user verify` a spustí aplikáciu s prázdnymi skúšobnými dátami na dočasnom lokálnom porte. Overí databázu, verziu, HTTP kontrolu aj zostavený frontend; po skončení skúšobnú inštanciu odstráni. Potrebuje `systemd-analyze`, prístup k Python balíkom a možnosť otvoriť lokálny port. Produkčné dáta nepoužíva.

Pred vytvorením tagu musí byť pracovný strom čistý a číslo tagu musí zodpovedať `VERSION`. Príklad pre verziu `0.57.1`:

```bash
git tag -a v0.57.1 -m "Poznamkovnik 0.57.1"
git push origin HEAD
git push origin v0.57.1
```

Zverejnené tagy sa neprepisujú. Oprava dostane nové číslo. Domáci server sa zverejnením tagu automaticky neprepne.

## Prvá inštalácia servera

Potrebné sú Python 3.11 alebo novší s `venv` a `pip`, Git, systemd používateľská služba a právo čítať privátny Git repozitár. Najprv osobne priprav [samostatný deploy key](private-git-access.md); ten nie je prihlasovacím kľúčom agenta na server. Node.js na serveri netreba, frontend je zostavený v Gite. OCR a ostatné voliteľné funkcie potrebujú aj svoje [systémové nástroje](development.md#voliteľné-systémové-nástroje).

Po zverejnení prvého tagu načítaj projekt do samostatného pomocného priečinka na serveri:

```bash
git clone --branch v0.57.5 --single-branch git@github-poznamkovnik:sumichalek/Poznamkovnik.git "$HOME/poznamkovnik-bootstrap"
cd "$HOME/poznamkovnik-bootstrap"
bash scripts/install.sh --plan
bash scripts/install.sh
```

Predvolená inštalácia vznikne v `~/apps/poznamkovnik`, služba sa volá `poznamkovnik.service`, adresa je `127.0.0.1` a port `1111`. Pri prvej inštalácii nástroj pripraví aj systemd unit a overí štart. Sprievodca nechá používateľa vybrať automatické spúšťanie; pri priamom CLI `./scripts/server-update.sh init v0.57.5` ho možno vypnúť pomocou `--no-autostart`. Pre beh aj bez prihlásenia je samostatný krok `loginctl enable-linger MENO_UCTU`.

Nástroj odmietne prevziať už existujúcu službu. Pre ďalšiu inštanciu použi vlastný názov, port a koreň:

```bash
./scripts/server-update.sh --root "$HOME/apps/poznamkovnik-test" init v0.57.5 --service poznamkovnik-test.service --port 1112
```

Adresa `127.0.0.1` je vhodná pre SSH tunel alebo reverzný proxy. Pre priamy prístup v domácej sieti nastav pri inštalácii `--host` na LAN adresu servera a povoľ zvolený port. Pri vzdialenom prístupe používaj HTTPS na proxy serveri.

Ak máš ďalšie konfiguračné súbory, môžeš ich pridať pri inštalácii opakovaným `--backup-path /absolutna/cesta`. Serverový účet musí mať právo ich čítať aj obnoviť. Tento parameter je určený pre konkrétne nastavenia, napríklad konfiguračný súbor proxy; celý domovský alebo systémový priečinok sa ako záloha nastavení nepoužíva. Zoznam je uložený v `shared/server.json`.

### Prenos existujúcich dát

Pôvodnú službu zastav a celý jej dátový priečinok skopíruj do nového `shared/data/` ešte pred príkazom `init`. Zachovaj skryté súbory aj prípadné SQLite WAL/journal súbory. Nástroj pri inštalácii existujúce dáta zachová a pred prvým spustením vytvorí ich zálohu. Prázdny dátový priečinok znamená nové vytvorenie účtu.

Pri prechode z pôvodnej lokálnej služby zvoľ pre novú službu iný názov, napríklad `--service poznamkovnik-git.service`. Pôvodný port sa môže použiť po zastavení starej služby. Nové umiestnenie over pred vypnutím automatického spúšťania starej služby. Po prenose pokračuj v používaní jednej dátovej kópie; obsah dvoch nezávislých inštancií sa nesynchronizuje.

Pri zlyhaní úplne prvej inštalácie sa obnovia dáta a nastavenia, ale v novej inštalácii ešte neexistuje staré Git vydanie, ktoré by bolo možné spustiť. Pôvodná nespravovaná služba zostáva samostatná.

## Aktualizácia jedným príkazom

Na serveri:

```bash
"$HOME/apps/poznamkovnik/current/scripts/server-update.sh" update v0.57.5
```

Pri vlastnej inštalačnej ceste pridaj `--root` pred podpríkaz. Prepínače a pomoc sa zobrazia cez `--help`.

Aktualizácia má tieto kroky:

1. Načíta tag cez Git a vytvorí samostatný worktree vydania.
2. V jeho vlastnom `.venv/` nainštaluje `requirements.lock`, overí závislosti a importy. Pôvodná služba zatiaľ beží.
3. Po samostatnom potvrdení zastaví službu a vytvorí novú úplnú zálohu dát, konfigurácie a pôvodného Git commitu.
4. Overí kontrolné súčty všetkých uložených súborov a čitateľnosť celého dátového archívu.
5. Po potvrdení aktivácie prepne `current`, spustí službu a overí `/api/health`: správny commit, verziu, dátový adresár aj dostupnosť databázy a súborového úložiska.
6. Zapíše výsledok do `shared/update-state.json`.

Pred aktualizáciou nechaj dobehnúť OCR, nahrávanie a ostatné úlohy. Zastavenie služby ukončí aj jej rozpracované procesy. Počas aktivácie a kontroly štartu je krátka odstávka; celkové trvanie závisí najmä od objemu dát na zálohovanie.

### Povinná nová záloha

Pred každou aktiváciou vrátane ručného návratu verzie sa vytvorí nová záloha na serveri. Staršia ani pravidelná automatická záloha ju nenahrádza. Neexistuje prepínač na preskočenie tejto podmienky.

Záloha zahŕňa celý `shared/data/`, teda databázu, účty a relácie, používateľské nastavenia, poznámky, prílohy, dokumenty, hudbu a ostatné uložené dáta. Samostatne zachová `server.json`, systemd unit, jeho lokálne doplnky, prípadný `config.env` a všetky pridané konfiguračné cesty. Zaznamená aj to, ktoré voliteľné nastavenia pred aktualizáciou neexistovali, aby pri obnove nezostali nové doplnky omylom aktívne.

```text
shared/update-backups/before-CAS-IDENTIFIKATOR/
├── data.tar.gz
├── settings/
├── manifest.json               pôvodné vydanie, cesty a SHA-256 súborov
└── VERIFIED                    kontrolný súčet manifestu
```

Zálohy sú dostupné iba serverovému účtu a automaticky sa nemažú. Zabezpeč dostatok miesta a pravidelne kopíruj overenú zálohu aj mimo disku servera. Prenosný ZIP export z aplikácie nenahrádza túto technickú zálohu, pretože neobsahuje účty a relácie.

Ak sa záloha nedá vytvoriť alebo overiť, nové vydanie sa neaktivuje a pôvodná služba sa znova spustí, ak predtým bežala. Nástroj odmietne symbolické odkazy a špeciálne súbory v dátach a externých nastaveniach, aby sa pod úplnou zálohou neskrývali nezálohované externé závislosti. Spravovaný systemd odkaz automatického spúšťania sa zachová osobitne. Ak používaš ďalšie odkazy, treba dátové rozloženie najprv vyriešiť.

## Kontrola a obnova

```bash
"$HOME/apps/poznamkovnik/current/scripts/server-update.sh" status
"$HOME/apps/poznamkovnik/current/scripts/server-update.sh" verify /ABSOLUTNA/CESTA/K/ZALOHE
"$HOME/apps/poznamkovnik/current/scripts/server-update.sh" rollback /ABSOLUTNA/CESTA/K/ZALOHE
```

`status` zobrazí aktívne vydanie, stav služby, poslednú operáciu a zálohy. `verify` znova kontroluje celú konkrétnu zálohu. `rollback` vytvorí novú zálohu aktuálneho stavu a obnoví vydanie, dáta aj nastavenia z vybranej staršej zálohy. Záloha patrí ku konkrétnej inštalácii a pôvodné vydanie musí zostať v `releases/`.

Ak nový štart alebo HTTP kontrola zlyhá, aktualizátor automaticky zastaví neúspešnú verziu, obnoví celú zálohu a znovu spustí pôvodnú verziu, ak predtým bežala. Stav po pokuse zachová v `shared/recovery-*/`.

Obnova vracia obsah do okamihu vytvorenia vybranej zálohy. Prípadné novšie zápisy sa zachovajú v novej zálohe a v odloženom stave; do aktívnej databázy sa automaticky nezlučujú. Preto nové vydanie over ešte pred pokračovaním v bežnej práci.

### Prerušenie alebo chyba obnovy

Pri tvrdom prerušení procesu sa automatická obnova nemusí vykonať. Nástroj ukladá stav operácie; ďalší update pri nedokončenej aktivácii odmietne, aby neprepísal údaje potrebné na obnovu.

Pozri `status` a cestu `snapshot` v `shared/update-state.json`. Ak je záloha hotová, over ju a použi `rollback`. Ak prerušenie nastalo pred dokončením zálohy, aktívne dáta ani odkaz ešte neboli zmenené; po kontrole stavu možno pôvodnú službu spustiť cez `systemctl --user start NAZOV.service`. Pred ďalšou aktualizáciou vyrieš aj záznam nedokončenej operácie. Pri chybe samotnej obnovy ponechaj službu zastavenú a použi zachované zálohy a adresáre obnovy.

Ak zlyhala úplne prvá inštalácia a záloha ešte neobsahuje predchádzajúce Git vydanie, použi z pomocného checkoutu verzie 0.57.1 alebo novšej `./scripts/server-update.sh recover /ABSOLUTNA/CESTA/K/ZALOHE`. Príkaz najprv vytvorí novú zálohu aktuálneho stavu a potom obnoví aj stav bez aktívneho vydania. Inštaláciu môžeš zopakovať príkazom `update v0.57.1`.

Aplikácia zatiaľ používa migrácie v `Database.initialize()`. Automatický návrat obnovuje aj predmigračnú databázu, preto nezávisí od spätnej kompatibility novej schémy so starým kódom. Samostatná evidencia číslovaných migrácií zostáva ďalším rozšírením.

## Prevádzkové poznámky

Používaj serverový účet s prístupom k dátam a jeho systemd používateľskú službu. Existujúci `scripts/poznamkovnik-daemon.sh install` slúži pre lokálny vývojový priečinok; na Git inštalácii by prepísal správne cesty služby.

`GET /api/version` vracia číslo verzie a prípadný Git commit. `GET /api/health` je verejná základná kontrola pripravenosti bez používateľských údajov a bez zobrazenia dátovej cesty. Dostupnosť OCR či konkrétnych kompilátorov sa overuje osobitne v aplikácii.

Staré vydania ani zálohy sa automaticky neprerezávajú. Ponechaj aspoň predchádzajúce overené vydanie a príslušné zálohy. Neodstraňuj vydanie, na ktoré ukazuje `current` alebo ktoré potrebuješ na obnovu. Automatické mazanie a nasadzovanie pri každom pushi nie sú súčasťou tejto verzie nástroja.

Výnimkou je osobitne potvrdené [odinštalovanie](uninstallation.md), ktoré odoberie kód a službu, predvolene však zachová celý `shared/`. Konfigurácia nových inštalácií obsahuje aj zdroj repozitára, stabilný `installation_id` a koreň. Vďaka uloženému zdroju vie príkaz `update` po odinštalovaní znovu pripraviť kód v tom istom koreni, pred aktiváciou však opäť vytvorí novú overenú zálohu. Na obnovu starej zálohy priprav jej pôvodné vydanie; samotný dátový archív neobsahuje všetky Git worktrees.

Návod na samostatnú správu vrátane ručných príkazov a riešenia porúch je v [server-operations.md](server-operations.md). DNS, Pi-hole, jeho upstreamy ani router sa inštalátorom nemenia. Zlyhanie Gitu alebo sťahovania balíkov nie je dôvodom na automatickú náhradu DNS.
