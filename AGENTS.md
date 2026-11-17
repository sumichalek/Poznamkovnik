# Práca na Poznámkovníku

## Inštalácia a nasadenie

- Predvolený používateľský postup je interaktívny sprievodca `bash scripts/install.sh`; režim `--plan` nesmie meniť systém.
- Pri príprave inštalátora pracuj lokálne a testuj na dočasných dátach a simulovaných službách. Ak si používateľ chce inštaláciu vyskúšať, nechaj ho spustiť a potvrdzovať jednotlivé kroky osobne.
- Príprava skriptu sama osebe neautorizuje nasadenie, preinštalovanie, zverejnenie Git tagu ani meniace príkazy cez SSH. Tieto akcie musia byť výslovne súčasťou zadania.
- Nepoužívaj `--yes` ako spôsob obídenia používateľského skúšania sprievodcu. Je určené pre výslovne požadovanú bezobslužnú automatizáciu.
- Pred aktiváciou každej verzie musí vzniknúť nová overená záloha dát aj aplikačných a serverových nastavení; pri chybe zálohy sa aktivácia nevykoná.
- Systémové kroky (balíky, linger, firewall) majú vlastný zrozumiteľný plán, potvrdenie a príslušnú zálohu. DNS sa neopravuje potichu.
- Inštalátor nemení DNS, router ani Pi-hole, ani ich neobchádza verejným resolverom. Zlyhanie prekladu názvov nie je úplnou diagnózou konfigurácie Pi-hole.
- Privátny Git na serveri používa používateľom nastavený read-only deploy key. Je odlišný od kľúča na prihlásenie na server; súkromná časť vzniká na serveri a neposiela sa agentovi. Heslo ani token nepatria do Git URL.
- Prevádzku musí vedieť používateľ zvládnuť sám podľa dokumentácie vrátane ručných kontrol a obnovy. Návody ani bežný pracovný postup nesmú predpokladať SSH prístup agenta.
- Existujúcu inštaláciu ani jej dáta neodstraňuj na účely skúšky bez výslovnej požiadavky. Ponúkni samostatný priečinok, službu a port pre skúšobnú inštanciu.
- Heslá zadáva používateľ priamo do svojho terminálu. Neukladaj ich do kódu, logov ani dokumentácie.
- Odinštalovanie je samostatný potvrdený používateľský krok. Predvolene zachová celý shared/; vymazanie dát aj záloh musí byť výslovne zvolené a potvrdené presnou cestou. Nikdy automaticky neodstraňuj zdieľané balíky ani SSH kľúče.
- Systémové nastavenia možno pri odinštalovaní odobrať iba podľa root dokladu a aktuálne overeného vlastníctva. Neobnovuj celý starý firewall cez novšie pravidlá iných aplikácií; pri neistote zmenu ponechaj a oznám to.
