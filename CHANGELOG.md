# Zmeny vo vydaniach

## 0.57.3

- Opravené falošné odmietnutie UFW pravidiel pre iné porty bez uvedeného protokolu alebo s UDP, napríklad DNS `53` na serveri s Pi-hole. Nejednoznačné pravidlá pre port aplikácie zostávajú chránené a cudzie pravidlá sa nepreberajú ani nemažú.
- Regresný test používa skutočný formát výpisu z Korunky a overuje pridanie, opakovanie aj odobratie iba vlastnej TCP výnimky pri zachovaní DNS, DHCP, SSH a webového portu.
- Pri skutočne nejednoznačnom pravidle sa zobrazí konkrétny blokujúci riadok; návod vysvetľuje samostatné dokončenie firewallu bez opakovania inštalácie.

## 0.57.2

- Lokálne pripravený interaktívny Bash sprievodca s režimom plánovania bez zmien a samostatnými potvrdeniami prípravy, zálohy a aktivácie.
- Sprievodca ponúka stav/diagnostiku a výber zálohy na obnovu, opakuje chybné vstupy a oddeľuje rozšírené nastavenia.
- Kontrola cesty, oprávnení, miesta, voľného portu a čítania konkrétneho Git tagu pred vykonaním; URL s vloženým heslom alebo tokenom sa odmietajú.
- Návody na privátny Git s read-only deploy key, samostatnú obsluhu a obnovu bez prístupu agenta; DNS a Pi-hole sa automaticky nemenia.
- Všeobecný interaktívny odinštalátor s plánom bez zmien; predvolene zachová účty, dáta a všetky zálohy, výslovné úplné vymazanie vyžaduje napísanie presného koreňa.
- Linger a UFW majú root doklady vlastníctva; existujúce, zdieľané a pozmenené nastavenia sa neodoberajú naslepo. Systémové balíky ani SSH kľúče sa automaticky nemažú.
- Zachovanie Git zdroja v konfigurácii umožní opätovnú inštaláciu po odstránení kódu; rozpracované odinštalovanie blokuje aktualizáciu, kým sa bezpečne nedokončí.
- Testy zahŕňajú celý cyklus aktualizácie, obnovy, odinštalovania a opätovnej inštalácie, zachovanie účtov, ochranu pred cudzou službou, odkazmi a pripojenými diskami.
- Priame meniace príkazy predvolene vyžadujú terminál a potvrdenia; automatizáciu povoľuje iba explicitné `--yes`.
- Opravené blokovanie súkromných statických ciest pri percentovom kódovaní URL pre požiadavky GET aj HEAD.
- Regresný HTTP test overuje, že skryté adresáre a backend zostanú neprístupné aj cez zakódované cesty, pričom verejná stránka funguje.

## 0.57.1

- Opravená cesta `WorkingDirectory` vo vygenerovanej systemd službe, ktorá blokovala prvý štart vydania 0.57.0.
- Obnova zvládne neaktívnu službu s neplatnou konfiguráciou a príkaz `recover` obnoví aj stav spred prvej inštalácie.
- Pribudlo overenie vygenerovanej služby skutočným parserom systemd v testoch aj pri kontrole vydania.

## 0.57.0

- Aktualizácie domáceho servera cez konkrétne Git tagy, samostatné adresáre vydaní a virtuálne Python prostredia.
- Povinná nová overená záloha dát a nastavení pred aktiváciou; automatická obnova pôvodného stavu pri neúspešnom štarte a príkaz na ručný návrat.
- Jednotné číslo verzie v `VERSION`, uzamknuté Python runtime závislosti a HTTP kontrola vydania a pripravenosti.
- OCR v Dielni PDF vrátane úloh na pozadí, zrušenia a okamžitého textového indexovania výstupu.
- Import EPUB do Dielne PDF a čítačka so záložkami, uloženou pozíciou a nastaveniami zahrnutými do záloh.
- Opravené zahrnutie súborov rozpracovaných projektov Dielne PDF do úplného aplikačného exportu.
- Rozšírená lekcia C o viacrozmerné polia, deklarácie, spustiteľné príklady a overované cvičenia.
- Dokumentácia lokálneho vývoja, vydávania, inštalácie a obnovy servera.
