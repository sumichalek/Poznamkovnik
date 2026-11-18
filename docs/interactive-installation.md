# Inštalácia pod kontrolou používateľa

Sprievodcu spúšťa používateľ osobne v termináli počítača, na ktorom chce aplikáciu nainštalovať. Agent ani vzdialený automat nespúšťa nasadenie za neho. Staršie vydania 0.57.0 a 0.57.1 tohto sprievodcu ešte neobsahujú. Použi vydanie aspoň 0.57.4, ktoré zahŕňa opravu prihlásenia po vytvorení prvého účtu aj kontroly UFW pre existujúce pravidlá DNS a DHCP.

Pred prvým stiahnutím z privátneho repozitára prejdi [read-only prístup ku Gitu](private-git-access.md). Pre každodennú správu aj výpadok je pripravená [samostatná obsluha servera](server-operations.md). Ani jeden postup nevyžaduje prihlasovací kľúč agenta na server.

## Najprv skúška bez zmien

V priečinku projektu:

```bash
bash scripts/install.sh --plan
```

Sprievodca sa opýta na operáciu, priečinok, vydanie, port, sieťový prístup a voliteľné funkcie. Vlastná Git adresa a názov služby sú v rozšírených nastaveniach. Nakoniec vypíše plán a skončí. Tento režim nič nesťahuje, nevytvára inštalačný priečinok ani import cache, nepoužíva sudo a nemení služby. Dostupnosť Gitu a presného tagu, miesto a voľný port sa overia pred vykonaním po schválení plánu; plán nie je potvrdením, že nezverejnený tag už existuje.

## Skutočná inštalácia alebo aktualizácia

```bash
bash scripts/install.sh
```

Spúšťaj ho pod bežným používateľským účtom. Najprv uvidíš názov počítača, používateľa, nájdenú inštaláciu a aktívnu verziu. Menu ponúkne:

1. Novú inštaláciu alebo samostatnú skúšobnú inštanciu.
2. Aktualizáciu existujúcej inštalácie so zachovaním jej nastavení.
3. Stav a lokálnu diagnostiku bez zmien; sieťová kontrola čítania Gitu má vlastné potvrdenie.
4. Obnovu Poznámkovníka zo zálohy, nie obnovu celého operačného systému.
5. Odinštalovanie s predvoleným zachovaním dát aj záloh.
0. Skončenie bez zmien (predvolená voľba).

Chybná voľba, tag, port alebo odpoveď na otázku sa nevykoná; sprievodca otázku zopakuje. Spustenie zo spravovaného vydania predvyberie jeho vlastný koreň inštalácie, aj keď nejde o predvolenú cestu.

Ak už predvolená inštalácia existuje a zvolíš novú, navrhne sa samostatná skúšobná inštancia: iný priečinok, služba a port. Môžeš ich zmeniť. Existujúca inštalácia sa nepreberá automaticky.

Po otázkach nasleduje plán s cestami k dátam a zálohám, verziou, službou a adresou. Používateľ potvrdzuje tieto kroky:

1. Súhlas s plánom a prípadné chýbajúce systémové predpoklady.
2. Prípravu konkrétneho Git vydania a jeho Python prostredia.
3. Zastavenie služby a vytvorenie novej overenej zálohy dát aj nastavení. Až tu začína odstávka.
4. Aktiváciu až po zobrazení cesty k úspešne overenej zálohe.

Prázdna odpoveď na potvrdenie znamená nie. Ak aktiváciu odmietneš po zálohe, pôvodná služba sa znova spustí, pokiaľ predtým bežala. Pripravené vydanie a záloha zostanú uložené. Pri neúspešnom štarte schválenej novej verzie zostáva zachovaná automatická obnova pôvodného stavu.

Zrušenie neskoršieho kroku neodinštaluje systémové balíky, ktoré si predtým samostatne schválil, a neodstraňuje už pripravené súbory. Sprievodca ukazuje, ktorá časť bola dokončená; nevykonáva automatické upratovanie používateľských dát.

Záloha je povinná. Používateľ môže zastaviť celý postup, ale nemôže potvrdiť aktiváciu s vynechanou alebo neoverenou zálohou.

## Samostatné systémové kroky

Pri novej inštalácii vie sprievodca ponúknuť chýbajúci Git, Python venv a voliteľné nástroje OCR/PDF cez apt-get. Najprv ukáže, čo sa bude vykonávať, a vyžiada si potvrdenie. DNS neopravuje ani neprepisuje automaticky; nefunkčné pripojenie treba vyriešiť vedome ako samostatný systémový problém.

Kontrola Git prístupu používa iba `ls-remote`, nie push. Oprávnenie iba na čítanie musíš nastaviť na GitHube; úspešné stiahnutie nedokazuje, že kľúč nemá aj zápisové oprávnenie. URL s heslom alebo tokenom sprievodca odmietne. Ak už je Git dostupný, prístup a tag sa preveria ešte pred prípadným inštalovaním balíkov.

Pri systémových balíkoch sa zobrazí aj simulácia APT a skutočná inštalácia má jeho vlastné potvrdenie bez `-y`. Skontroluj aj navrhované aktualizácie závislostí. Voľba OCR je samostatná; podpora EPUB používa aplikačné Python závislosti. Node.js na serveri netreba, frontend je zostavený vo vydaní.

Automatické spúšťanie je voľba používateľa. Ak chce beh aj bez prihlásenia, sprievodca vysvetlí nastavenie linger a ponúkne osobitne potvrdený krok cez sudo.

Pri sieťovom prístupe a aktívnom UFW sa môže ponúknuť pravidlo pre zvolený port a konkrétnu zdrojovú IPv4 sieť. Používateľ zadá CIDR, uvidí príkaz a ešte ho potvrdí. Pred úpravou firewallu sa zálohuje jeho pôvodná konfigurácia.

Tieto administrátorské kroky vykonáva samostatný `scripts/server-system.sh`. Pred zmenou uloží súkromnú zálohu relevantných nastavení do `/var/backups/poznamkovnik-system-*`. Heslo sudo zadáva používateľ priamo do svojho terminálu; skripty ho nečítajú ani neukladajú.

Pre nové zásahy do linger a UFW zapisuje pomocník `system_changes.py` aj koreňový doklad do `/var/lib/poznamkovnik-system/`. Doklad viaže zásah na identifikátor inštalácie a zachováva informáciu, či nastavenie existovalo už predtým. Existujúce pravidlo UFW sa nepreznačí len kvôli evidencii. Bez dôkazu vytvorenia odinštalátor systémové nastavenie neodoberie.

Na serveri s Pi-hole sa nemení jeho konfigurácia, resolver Linuxu, router ani DNS port. Problém s prekladom názvov sa oznámi, nie obíde verejným DNS. Podrobnosti rozlišovania resolvera a Pi-hole sú v [obsluhe servera](server-operations.md#dns-a-pi-hole).

## Obnova a výsledok

Voľba obnovy zobrazí zálohy s časom a pôvodným vydaním. Zoznam vychádza zo značky overenia; pred obnovou sa znova overí celý archív a kontrolné súčty. Voľba 0 skončí bez zmien. Pred obnovením staršieho stavu vznikne nová overená záloha aktuálnych dát a nastavení. Novšie záznamy sa so staršou databázou nezlučujú; zostanú v novej zálohe a odloženom stave `recovery-*`. Potrebné staršie vydanie musí zostať v `releases/`.

Po dokončení sa zobrazí stav, cesty, adresa a príkaz na ďalšie otvorenie sprievodcu. LAN dostupnosť treba overiť aj z druhého počítača; lokálna HTTP kontrola ju nezaručuje. Pri novej prázdnej inštalácii vytvoríš účet osobne v prehliadači. Inštalátor negeneruje spoločné predvolené heslo. Zálohy, databázu ani diagnostické výpisy neodosiela na GitHub alebo agentovi.

## Priame príkazy a automatizácia

Aj priame príkazy `server-update.sh init`, `update`, `rollback` a `recover` majú predvolene potvrdenia. Bez interaktívneho terminálu zmeny odmietnu. Pri SSH preto používaj terminál cez `ssh -t`.

Pre vedomú automatizáciu existuje explicitné `--yes` pred podpríkazom, napríklad `server-update.sh --yes update v0.57.4`. Toto vypína otázky, nikdy nie zálohu. Sprievodca `install.sh` tento prepínač nepoužíva a neumožňuje ho obísť posielaním odpovedí cez pipe.

## Odinštalovanie

Voľba 5 otvorí plán odinštalovania konkrétnej inštalácie. Predvolene odstráni službu, vydania a Git metadáta, ale ponechá celý `shared/` vrátane dát, účtov, konfigurácie a záloh. Samostatný nástroj `bash scripts/uninstall.sh --root CESTA --plan` umožňuje to isté bez prechádzania hlavného menu. Odinštalovanie nemá `--yes`; výslovná voľba `--delete-data` vyžaduje navyše potvrdenie presnou cestou a odstráni aj všetky aplikačné zálohy, bez vytvorenia novej. Úplný postup aj opätovná inštalácia sú v [uninstallation.md](uninstallation.md).

## Osobná skúška na Korunke

Predchádzajúci prihlasovací kľúč agenta na Korunku bol odobratý. Stav prípadnej starej inštalácie overuje používateľ osobne; odmietnutie SSH kľúča nie je dôkazom odstránenia všetkých súborov alebo balíkov. Nová inštalácia nič neodinštaluje automaticky; odstránenie je samostatná výslovná voľba 5. Ak na stroji ešte existuje inštalácia, možno vybrať samostatnú skúšobnú inštanciu.

DNS ponechané po predchádzajúcej skúške ani aktuálna verzia Pythonu sa pri novej inštalácii nemenia. Vhodnosť DNS vzhľadom na Pi-hole sa bez samostatnej kontroly nedá uzavrieť. Najprv nastav vlastný read-only Git prístup a prejdi `--plan`. Nový sprievodca sa na server dostane až po samostatnom rozhodnutí o zverejnení jeho verzie a tvojom stiahnutí; príprava skriptov v tomto priečinku server nemení.
