# Poznámkovník

Webový poznámkovník s knižnicami, zdrojmi a dokumentmi, Dielňou PDF, OCR, čítačkou EPUB, úlohami, kalendárom, hudbou a učebnicou programovania. Python server poskytuje rozhranie aj API; používateľské dáta sú uložené lokálne v SQLite a v súborovom úložisku.

## Dokumentácia

- [Lokálny vývoj, spustenie a testy](docs/development.md)
- [Inštalácia domáceho servera a aktualizácie cez Git](docs/deployment.md)
- [Zmeny vo vydaniach](CHANGELOG.md)
- [Odložený plán učebnice](docs/tutorial-roadmap.md)

## Spôsob vydávania

Vývoj prebieha v pracovnom Git priečinku. Overený commit dostane označenie vydania, napríklad `v0.57.0`. Domáci server si cez Git načíta tento tag a spustí ho zo samostatného adresára; trvalé dáta používa zo spoločného dátového adresára mimo kódu.

Pred každou aktualizáciou je povinná nová overená záloha dát aj aplikačných a serverových nastavení. Pri chybe zálohy sa nové vydanie neaktivuje.

Nasadenie a aktualizácie zabezpečuje `scripts/server-update.sh` s príkazmi `init`, `update`, `status`, `verify`, `rollback` a `recover`. Nástroj overí novú zálohu dát aj nastavení, aktivuje vydanie a skontroluje `/api/health`. Pri neúspešnom štarte obnoví pôvodný stav. Číslo verzie určuje `VERSION`, Python runtime závislosti `requirements.lock`. Prvá inštalácia a všetky príkazy sú opísané v dokumentácii nasadenia.
