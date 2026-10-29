# Lokálny vývoj

Súvisiaci postup: [server a aktualizácie cez Git](deployment.md).

## Príprava

Potrebné sú Git, Python 3.11+ s modulmi `venv` a `pip` a Node.js s npm. Aktuálne prostredie projektu bolo overené s Pythonom 3.13 a Node.js 20. Závislosti frontendu určuje `package-lock.json`; presné Python runtime verzie sú v `requirements.lock`, povolené rozsahy v `requirements.txt`.

V pracovnom priečinku projektu:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
npm ci
npm run build
```

Priečinky `.venv/`, `node_modules/`, `.local/` a `data/` sú ignorované Gitom. Prihlasovacie údaje ani databázy sa neukladajú do repozitára.

## Spustenie počas vývoja

Pre vývoj používaj vlastné dáta. Ak tu už beží bežná aplikácia na porte 1111, vývoj môže dočasne bežať na porte 1112:

```bash
source .venv/bin/activate
python server.py --host 127.0.0.1 --port 1112 --data-dir .local/dev-data
```

Otvor `http://127.0.0.1:1112`. Nový dátový priečinok znamená novú inštaláciu s vytvorením účtu. Prihlasovacie údaje produkčného servera zostávajú v jeho vlastnej databáze.

Pri úprave JavaScriptu alebo editorových štýlov znovu spusti `npm run build` a obnov stránku. Po úprave Python backendu reštartuj vývojový server. `server.py` momentálne neposkytuje automatické znovunačítanie backendu.

Predvolené spustenie `python server.py` používa port 1111 a `data/` pri zdrojovom kóde. Túto možnosť používaj iba vtedy, keď zámerne chceš pracovať s týmito dátami.

## Overenie zmien

```bash
source .venv/bin/activate
npm run check
git diff --check
git status --short
```

`npm run check` zostaví frontend a spustí frontendové aj Python testy. HTTP integračné testy potrebujú možnosť otvoriť lokálny port. Niektoré testy kompilácie sa preskočia, ak chýba príslušný voliteľný kompilátor alebo izolované prostredie.

Pre cielenú kontrolu dokumentov:

```bash
python -m unittest tests.test_document_workshop tests.test_document_workshop_api tests.test_source_text -v
```

Vygenerované `assets/` sú sledované Gitom. Ak sa zmenil frontend, ulož do rovnakého vydania zdroje aj zodpovedajúci zostavený výstup. Server potom na beh nepotrebuje Node.js ani `node_modules/`.

Číslo vydania meň iba v súbore `VERSION`. `npm run build` ho vloží do bundlu aj HTML; backend číta ten istý súbor. Pri úprave Python závislostí zmeň zodpovedajúce rozsahy v `requirements.txt` a overené presné verzie v `requirements.lock`.

## Git počas práce

```bash
git status
git diff
```

Súvisiace zmeny ukladaj do samostatných commitov. Pred operáciami, ktoré menia pracovný strom, najprv vyrieš rozpracované úpravy. Vývojový a serverový priečinok sú dve samostatné pracovné kópie; každá má vlastné dáta.

Postup vytvorenia Git tagu a jeho nasadenia je v [dokumentácii servera](deployment.md#vytvorenie-vydania-tu-vo-vývoji).

## Voliteľné systémové nástroje

`requirements.txt` zahŕňa Python balíky, nie všetky systémové programy. Podľa používaných funkcií potrebuje prostredie aj:

- OCRmyPDF, Tesseract a jazykové dáta `slk` a `eng` pre OCR;
- LibreOffice pre prevod kancelárskych dokumentov;
- Poppler, najmä `pdftoppm`, pre náhľady PDF;
- FFmpeg a ffprobe pre prácu s audiozáznamami;
- kompilátory a izolačné nástroje vyžadované Dielňou vývoja pre spúšťanie kódu.

Názvy inštalačných balíkov závisia od distribúcie. Dostupnosť OCR vie aplikácia hlásiť cez `GET /api/documents/runtime` po prihlásení. Dostupnosť vývojových nástrojov sa zobrazuje v Dielni vývoja.
