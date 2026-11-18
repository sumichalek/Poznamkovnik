# Poznámkovník

Webový poznámkovník s knižnicami, zdrojmi a dokumentmi, Dielňou PDF, OCR, čítačkou EPUB, úlohami, kalendárom, hudbou a učebnicou programovania. Python server poskytuje rozhranie aj API; používateľské dáta sú uložené lokálne v SQLite a v súborovom úložisku.

## Dokumentácia

- [Lokálny vývoj, spustenie a testy](docs/development.md)
- [Inštalácia domáceho servera a aktualizácie cez Git](docs/deployment.md)
- [Interaktívny sprievodca pod kontrolou používateľa](docs/interactive-installation.md)
- [Prvé stiahnutie z privátneho Gitu iba na čítanie](docs/private-git-access.md)
- [Samostatná obsluha, aktualizácia, obnova a Pi-hole](docs/server-operations.md)
- [Lokálny prístup, SSH tunel a prepínanie LAN HTTP](docs/network-access.md)
- [Odinštalovanie, zachovanie dát a opätovná inštalácia](docs/uninstallation.md)
- [Zmeny vo vydaniach](CHANGELOG.md)
- [Odložený plán učebnice](docs/tutorial-roadmap.md)

## Spôsob vydávania

Vývoj prebieha v pracovnom Git priečinku. Overený commit dostane označenie vydania, napríklad `v0.57.0`. Domáci server si cez Git načíta tento tag a spustí ho zo samostatného adresára; trvalé dáta používa zo spoločného dátového adresára mimo kódu.

Pred každou aktualizáciou je povinná nová overená záloha dát aj aplikačných a serverových nastavení. Pri chybe zálohy sa nové vydanie neaktivuje.

Nasadenie a aktualizácie zabezpečuje `scripts/server-update.sh` s príkazmi `init`, `update`, `configure-access`, `status`, `verify`, `rollback` a `recover`. Nástroj overí novú zálohu dát aj nastavení, aktivuje vydanie a skontroluje `/api/health`. Pri neúspešnom štarte obnoví pôvodný stav. Číslo verzie určuje `VERSION`, Python runtime závislosti `requirements.lock`. Prvá inštalácia a všetky príkazy sú opísané v dokumentácii nasadenia.

Pre používateľskú inštaláciu spusti `bash scripts/install.sh --plan` a prejdi si plán bez zmien. Skutočný postup cez `bash scripts/install.sh` sa pýta pred prípravou, odstávkou so zálohou aj aktiváciou. Voliteľné systémové kroky používateľ potvrdzuje osobitne.

Repozitár je privátny: pred prvým stiahnutím si používateľ pripraví samostatný read-only deploy key. Ten umožní serveru čítať GitHub, nie agentovi pristupovať na server. Menu sprievodcu zahŕňa aj lokálnu diagnostiku a výber zálohy na obnovu. DNS, Pi-hole ani router inštalátor nenastavuje. Príprava vydania neznamená jeho automatické zverejnenie alebo nasadenie.

Voľba 6 umožňuje existujúcu inštaláciu prepnúť medzi lokálnym/SSH a LAN HTTP prístupom bez preinštalovania. Pred zmenou zálohuje pôvodné dáta a nastavenia; prípadná zmena UFW je samostatne potvrdený krok. Výnimku odoberie iba pri preukázanom vlastníctve a nikdy tým nemení linger, SSH alebo Pi-hole.

Voľba 5 sprievodcu alebo `bash scripts/uninstall.sh --plan --root CESTA` ponúkne odinštalovanie. Predvolene odstráni len službu a kód, zachová celý `shared/` s účtami, dátami a zálohami. Úplné vymazanie cez `--delete-data` vyžaduje ďalšie potvrdenie presnou cestou koreňa. Systémové zmeny sa odoberajú iba samostatne potvrdenými krokmi s root dokladom vlastníctva; balíky a SSH kľúče sa automaticky nemažú.
