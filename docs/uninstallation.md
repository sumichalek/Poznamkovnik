# Odinštalovanie a návrat k používaniu

Odinštalátor je pre spravovanú Git inštaláciu vytvorenú cez `install.sh` alebo `server-update.sh`. Nie je to univerzálny čistič celého servera. Spúšťa ho používateľ osobne pod účtom, ktorý vlastní inštaláciu, nie cez sudo. Odinštalátor neotvára vzdialený prístup agentovi.

## Predvolená voľba: zachovať dáta aj zálohy

V hlavnom sprievodcovi vyber **5 – Odinštalovať Poznámkovník**. Alebo spusti nástroj z ponechaného pomocného checkoutu:

```bash
bash "$HOME/poznamkovnik-bootstrap/scripts/uninstall.sh" --root "$HOME/apps/poznamkovnik" --plan
```

Pri vlastnom umiestnení nahraď koreň skutočnou cestou. Režim `--plan` iba prečíta stav a ukáže presné cesty. Nezastavuje službu, nezapisuje súbory, nepoužíva sudo ani nekontaktuje sieťový Git. Zastavenie služby nezačne bez osobného potvrdenia plánu.

Po kontrole plánu:

```bash
bash "$HOME/poznamkovnik-bootstrap/scripts/uninstall.sh" --root "$HOME/apps/poznamkovnik"
```

Predvolene sa:

- zastaví a zakáže konkrétna používateľská služba a odstráni jej jednotka,
- odstránia `current`, `releases/` vrátane Python prostredí a `repository/`,
- **zachová celý `shared/`**, teda účty, databáza, všetky súbory, nastavenia, aplikačné zálohy, `recovery-*` aj história odinštalovania,
- ponechá `.update.lock` na bezpečnú ďalšiu správu toho istého koreňa.

Nástroj neodstraňuje pomocný bootstrap checkout mimo inštalačného koreňa, externé súbory z `backup_paths`, systémový Python, Git, OCR/PDF balíky, SSH kľúče, DNS, Pi-hole ani router. Zachovanie `shared/` nie je nová záloha na inom disku; dôležité zálohy si naďalej ukladaj aj mimo servera.

Inštalačný koreň nesmie obsahovať neznáme súbory. Pri cudzom názve/jednotke služby, jej dodatočných doplnkoch, lokálnych úpravách vydania alebo neoveriteľnom Gite sa nástroj zastaví pred odstraňovaním. Nevypína neznámy proces len preto, že má rovnaký názov. Symbolické odkazy do odstraňovaného kódu a vnorené pripojené súborové systémy treba najprv vyriešiť; odinštalátor cez ne neprejde. Doplnky služby si odlož mimo inštalácie, nie do jej `releases/`.

Skript možno spustiť aj z aktívneho vydania: Bash sa pred samotným odstraňovaním nahradí Python procesom, ktorý má potrebný kód načítaný. Pomocný checkout je však najprehľadnejší nástroj na opätovnú inštaláciu a riešenie poruchy, preto si ho nechaj.

## Výslovné odstránenie aj dát a všetkých aplikačných záloh

Táto voľba je nezvratná. Zmaže sa celý overený inštalačný koreň, vrátane účtov, príloh, databázy, všetkých záloh v `shared/update-backups/`, konfigurácie a odložených stavov `recovery-*`. **Nevytvára sa nová záchranná záloha.** Použi ju iba vtedy, keď tento obsah naozaj nechceš zachovať alebo ho už máš bezpečne uložený mimo koreňa.

Najprv pozri plán:

```bash
bash "$HOME/poznamkovnik-bootstrap/scripts/uninstall.sh" --root "$HOME/apps/poznamkovnik" --delete-data --plan
```

Až potom prípadne skutočné odstránenie:

```bash
bash "$HOME/poznamkovnik-bootstrap/scripts/uninstall.sh" --root "$HOME/apps/poznamkovnik" --delete-data
```

Okrem súhlasu s plánom musíš napísať presnú úplnú cestu zobrazeného koreňa. Nesprávna alebo prázdna odpoveď vymazanie zruší. Odinštalátor neumožňuje `--yes` ani posielanie súhlasov cez pipe. Vymazanie dát naozaj neznamená iba odobratie prihlasovacieho účtu alebo programu.

Systémové zálohy v `/var/backups/poznamkovnik-system-*` a koreňové doklady opísané nižšie nie sú aplikačné zálohy a táto voľba ich nemaže. Automaticky sa nemažú ani žiadne externé súbory mimo presne overeného koreňa.

## Linger a firewall: len s overiteľným pôvodom

Po schválení plánu a prípadnom potvrdení vymazania dát môžeš samostatne súhlasiť s kontrolou systémových zmien cez sudo. Pred každým konkrétnym zásahom uvidíš nový plán a ďalšie potvrdenie. Nová záloha dotknutého systémového nastavenia vznikne pred zmenou, nie až po nej. Heslo sudo patrí iba do terminálu.

Nové inštalácie majú stabilný `installation_id` a koreň v `shared/server.json`. Privilegovaný pomocník zaznamenáva overené zásahy do `/var/lib/poznamkovnik-system/ID.json`, kde záznam môže zapisovať len root. Samotná používateľom upraviteľná konfigurácia aplikácie nie je dôkazom oprávnenia niečo odstrániť.

- **UFW:** odoberie sa iba pravidlo, ktorého pridanie bolo úspešne zaznamenané a ktoré má stále presný port, zdrojovú sieť a jedinečný komentár danej inštalácie. Predtým existujúce pravidlo sa nepreznačí a nepreberie do vlastníctva. Upravené, nejednoznačné alebo neoveriteľné pravidlo zostane. Neobnovuje sa celý starý firewall zo zálohy, pretože by sa tým mohli prepísať novšie pravidlá iných aplikácií.
- **Linger:** vypnutie možno ponúknuť iba vtedy, keď doklad potvrdzuje, že ho tento nástroj zapol z pôvodne vypnutého stavu. Ak má používateľ ďalšie povolené alebo aktívne služby, sockety či časovače, zostane zapnutý. Výnimkou je samotná infraštruktúra používateľskej D-Bus relácie. Vypnutie linger sa týka celého používateľského správcu služieb, preto má vlastné potvrdenie.
- **Balíky:** zdieľané balíky sa automaticky neodstraňujú a nepoužíva sa plošné `autoremove`.

Keď chýba doklad, pochádza zo starej inštalácie, nesúhlasí jeho identifikátor, vlastníctvo alebo aktuálny stav, príslušné systémové nastavenie sa automaticky nemení. Toto je zámerné bezpečné obmedzenie, nie prísľub úplného návratu celého Linuxu do pôvodného stavu.

Ak chceš len prejsť z LAN HTTP na lokálny prístup/SSH tunel, neodinštalovávaj aplikáciu. Použi [voľbu 6 sprievodcu](network-access.md); ponúkne odobratie iba vlastnej výnimky UFW, pričom dáta, účty, kód aj linger zostanú zachované.

Pri viacerých inštanciách môže linger dočasne zostať kvôli druhej aplikácii. Doklad pôvodnej inštancie sa zachová aj po vymazaní jej dát. Keď už iná aplikácia linger nepotrebuje, vieš ho samostatne znovu skontrolovať z bootstrap checkoutu. Použi ID z predchádzajúceho výpisu:

```bash
read -r -p 'ID systémového dokladu z výpisu: ' PN_RECEIPT
sudo python3 -B "$HOME/poznamkovnik-bootstrap/scripts/system_changes.py" cleanup --receipt "$PN_RECEIPT" --plan
```

Až po kontrole prípadne zopakuj bez `--plan`; jednotlivé zmeny sa opäť potvrdzujú. Chýbajúci alebo nedokončený doklad sa nesmie nahradiť odhadom podľa mena služby alebo otvoreného portu.

## Opätovná inštalácia po zachovaní dát

Po predvolenom odinštalovaní existuje `shared/server.json`. Preto v sprievodcovi z bootstrap checkoutu vyber **2 – Aktualizácia**, nie novú inštaláciu:

```bash
bash "$HOME/poznamkovnik-bootstrap/scripts/install.sh" --plan
bash "$HOME/poznamkovnik-bootstrap/scripts/install.sh"
```

Zvoľ presne pôvodný koreň a konkrétny otestovaný tag. Nástroj použije uloženú bezpečnú adresu repozitára, znovu pripraví Git a Python prostredie, zachová existujúce účty a súbory a pred aktiváciou vytvorí novú overenú zálohu. Musí byť dostupný tvoj read-only Git prístup a základné nástroje. Chýbajúce systémové predpoklady priprav osobitne; nástroj ich pri aktualizácii neinštaluje bez otázok.

Odinštalovanie odstraňuje aj staré vydania v `releases/`. Ak chceš následne obnoviť konkrétnu starú zálohu, priprav najprv jej **pôvodné vydanie**, zobrazené v zozname záloh. Potom voľbou Obnova znovu over a obnov danú zálohu. Záloha stále patrí rovnakému koreňu; jej archív sám neobsahuje všetky Git worktrees a Python prostredia. Obnovenie dát na celkom inom serveri alebo v inom koreni vyžaduje samostatný migračný postup.

## Prerušenie alebo chyba

Odinštalovanie zdieľa zámok s aktualizátorom. Súbežná operácia sa odmietne. Po potvrdenom začiatku ukladá kroky do `shared/uninstall-state.json`; aktualizátor pri rozpracovanom alebo neúspešnom odinštalovaní odmietne pokračovať.

Zrušenie pred vykonaním plánu nič nezmení. Po začiatku sa už dokončené odstraňovanie ani osobitne schválené systémové kroky automaticky nevracajú. Pri chybe sa ďalšie kroky zastavia. Skontroluj posledný výpis a stav; nespúšťaj službu ani aktualizáciu naslepo. Pokiaľ zostala konfigurácia, po vyriešení príčiny možno odinštalovanie zopakovať z bootstrap checkoutu do rovnakého koreňa. Chýbajúce už odstránené súčasti nie sú dôvodom na vymazanie iných priečinkov.

Pri výslovnom úplnom vymazaní môže byť v závere odstránený aj samotný stavový súbor — potom vychádzaj zo záverečného výpisu a prípadných root dokladov. Bez nezávislej kópie dát ich tento nástroj nevie obnoviť. Jednorazový starý skript na upratanie Korunky nie je všeobecný odinštalátor a pri ďalších inštaláciách sa nepoužíva.
