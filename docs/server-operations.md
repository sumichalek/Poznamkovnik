# Samostatná obsluha domáceho servera

Všetky príkazy spúšťaš ty vo svojom termináli po prihlásení na server. Nie je potrebný prístup agenta, GitHub Actions ani automatické nasadenie po pushi. Úvodné stiahnutie z privátneho Gitu opisuje [samostatný návod](private-git-access.md).

Na odstránenie programu slúži samostatný [odinštalátor](uninstallation.md), dostupný aj ako voľba 5 sprievodcu. Predvolene zachová dáta a zálohy; nepoužívaj namiesto neho starý jednorazový čistiaci skript pre Korunku.

## Čo je kde

Pri predvolených voľbách je aplikácia v `~/apps/poznamkovnik` a služba sa volá `poznamkovnik.service`. Ak si zvolil vlastné umiestnenie alebo názov, v príkladoch ich nahraď svojimi hodnotami.

- `releases/`: kód jednotlivých vydaní a ich vlastné Python prostredia. Súbory tu neupravuj.
- `current`: odkaz na aktívne vydanie.
- `shared/data/`: databáza, účty, dokumenty, prílohy a používateľské nastavenia. Toto nie je Git checkout.
- `shared/server.json`: nastavenia tejto inštalácie, napríklad port a názov služby.
- `shared/update-backups/`: úplné overené zálohy pred aktiváciami.
- `shared/update-state.json`: výsledok alebo rozpracovaný stav poslednej operácie.
- `shared/uninstall-state.json`: priebeh/výsledok odinštalovania. Pri zachovaní dát zostáva spolu s konfiguráciou a zdrojom Gitu.
- `shared/recovery-*/`: zachované novšie dáta a nastavenia po obnove. Automaticky sa nezlučujú s aktívnymi dátami.

Git sťahuje program; neposiela databázu ani zálohy na GitHub. Bežiaca aplikácia môže podľa používaných funkcií kontaktovať externé zdroje, napríklad internetové rádio; to je oddelené od aktualizátora. Diagnostické výpisy sa nikam automaticky neodosielajú.

## Otvorenie sprievodcu a kontrola

```bash
bash "$HOME/apps/poznamkovnik/current/scripts/install.sh"
```

Voľba **3 – Stav a diagnostika** ukáže verziu, službu, dostupné nástroje, dátový priečinok a zálohy. Pri aktívnej službe overí aj lokálne HTTP zdravie. Nekontaktuje GitHub, kým osobitne nepotvrdíš sieťovú kontrolu čítania Gitu. Pi-hole ani DNS nenastavuje.

Rovnakú lokálnu diagnostiku môžeš spustiť priamo, aj bez interaktívneho terminálu:

```bash
python3 -B "$HOME/apps/poznamkovnik/current/scripts/install_support.py" diagnose "$HOME/apps/poznamkovnik"
```

Skontroluj aj aplikáciu v prehliadači. Adresa `127.0.0.1` znamená počítač, na ktorom prehliadač beží, nie automaticky Korunku. Pre LAN používaj názov alebo IP servera a zvolený port. Úspešná lokálna kontrola nepotvrdzuje prechod firewallom z iného počítača. Pri zvolenom lokálnom prístupe môžeš použiť vlastný SSH tunel; nevypínaj kvôli tomu firewall.

## Aktualizácia

V sprievodcovi vyber **2 – Aktualizácia**, skontroluj inštalačný priečinok a zadaj konkrétny zverejnený tag. Existujúci port, dáta a služba sa zachovajú. Sprievodca nepovažuje `main` za vydanie a nesťahuje zmeny automaticky pri každom pushi.

Prepnutie pomocného Git checkoutu cez `git switch` mení iba pomocné súbory, nie aplikáciu bežiacu zo samostatného `current`. Preto samotné stiahnutie nového pomocníka na dokončenie UFW neaktualizuje prihlasovanie ani zvyšok aplikácie. Opravu aplikácie na server prenesie až táto potvrdená aktualizácia so zálohou. Po úspešnej aktivácii obnov stránku v prehliadači, aby sa načítal nový frontend.

Pred odstávkou nechaj dobehnúť OCR, nahrávanie a ostatné úlohy. Príprava kódu a Python prostredia ešte nechá starú verziu bežať. Až po samostatnom potvrdení zastaví službu a vytvorí novú overenú zálohu dát aj nastavení. Potom uvidíš cestu k zálohe a osobitne potvrdíš aktiváciu.

Priama alternatíva, napríklad po zverejnení `v0.57.4`:

```bash
"$HOME/apps/poznamkovnik/current/scripts/server-update.sh" --root "$HOME/apps/poznamkovnik" update v0.57.4
```

Aj tento príkaz má potvrdenia. Pri SSH potrebuje terminál, teda `ssh -t`, ak ho spúšťaš priamo zo svojho počítača. Na bežnú obsluhu nepoužívaj `--yes`.

Nová záloha pred každou aktiváciou je povinná, aj keď už existujú iné zálohy. Zahŕňa celý dátový priečinok, `server.json`, systemd jednotku, jej doplnky, prípadný `config.env` a výslovne pridané konfiguračné cesty. Systémové kroky ako UFW alebo linger majú samostatné zálohy v `/var/backups/poznamkovnik-system-*`; technická záloha aplikácie nie je obraz celého Linuxu. Nedostatok miesta alebo chyba overenia blokuje aktiváciu. Staršie zálohy sa automaticky nemažú; kontroluj miesto a dôležité zálohy si kopíruj aj mimo disku servera.

## Obnova Poznámkovníka, nie celého systému

Voľba **4 – Obnova** ponúkne zálohy označené ako overené. Pred ich použitím sa znova skontroluje celý obsah. Zobrazí sa čas zálohy a pôvodné vydanie; pri zálohe spred prvej inštalácie sa výslovne uvedie, že nebude aktívne žiadne vydanie.

Obnova vráti program, dáta a nastavenia do času vybranej zálohy. Novšie poznámky sa nepridajú do staršej databázy automaticky. Pred obnovou preto vznikne nová overená záloha aktuálneho stavu a vytlačené dáta sa navyše zachovajú v `recovery-*`. Rozhodnutie o prípadnom ručnom prenose novších záznamov zostáva na tebe.

Priame príkazy sú tiež interaktívne. Cestu v ďalšom príklade nahraď skutočnou cestou zo zoznamu:

```bash
"$HOME/apps/poznamkovnik/current/scripts/server-update.sh" --root "$HOME/apps/poznamkovnik" status
read -r -p 'Úplná cesta k vybranej zálohe: ' PN_SNAPSHOT
"$HOME/apps/poznamkovnik/current/scripts/server-update.sh" --root "$HOME/apps/poznamkovnik" verify "$PN_SNAPSHOT"
"$HOME/apps/poznamkovnik/current/scripts/server-update.sh" --root "$HOME/apps/poznamkovnik" recover "$PN_SNAPSHOT"
```

Ak overenie zlyhá, obnovu nespúšťaj. Obnova potrebuje zachované príslušné vydanie v `releases/` a zálohu patriacu tejto inštalácii. Nevracia systémový Python, DNS, Pi-hole ani celý operačný systém. Nie je to ešte jedným príkazom riešená migrácia na úplne nový server. Prenosný export z webovej aplikácie nie je rovnaký typ zálohy: technická obnova zachováva aj účty a relácie.

## Ak sa niečo pokazí

- **Po vytvorení účtu a odhlásení zostalo tlačidlo „Vytvoriť pracovnú plochu“:** vo vydaniach do 0.57.3 vrátane mohol formulár zostať v režime prvého vytvorenia účtu. Obnov stránku v prehliadači cez F5; po načítaní existujúceho účtu má ponúknuť „Prihlásiť“. Účet, heslo ani dáta kvôli tomuto hláseniu nemaž a nevytváraj nanovo. Trvalú opravu obsahuje 0.57.4; na server ju prenesie aktualizácia aplikácie, nie iba prepnutie pomocného checkoutu.
- **Git alebo príprava zlyhala pred odstávkou:** stará služba zostáva bežať. Over správny tag, read-only prístup, heslovú frázu kľúča, spojenie a DNS. Nevymazávaj dáta ani konfiguráciu.
- **Zrušenie po zálohe, pred aktiváciou:** pôvodná služba sa znovu spustí, ak predtým bežala. Záloha a pripravené vydanie zostanú.
- **Nové vydanie nenabehlo:** nástroj sa pokúsi automaticky obnoviť predchádzajúce dáta, nastavenia a vydanie. Výpis musí potvrdiť výsledok; nespoliehaj sa iba na návrat do shellu.
- **`recovery_required` alebo tvrdé prerušenie:** nechaj službu zastavenú, pozri `shared/update-state.json` a over uvedenú zálohu. Novú aktualizáciu neopakuj naslepo. Ak je záloha v poriadku, použi potvrdený `recover`.
- **Chýba `current` po neúspešnej prvej inštalácii:** použi sprievodcu z ponechaného pomocného checkoutu: `bash "$HOME/poznamkovnik-bootstrap/scripts/install.sh"`. Vyber skutočný koreň inštalácie. Ak už existuje `server.json`, použiješ aktualizáciu na dokončenie prípravy alebo obnovu, nie novú inštaláciu cez existujúcu konfiguráciu.
- **Chyba samotnej obnovy:** nič nemaž, nespúšťaj službu nad čiastočne obnovenými dátami. Zachovaj zálohy a `recovery-*` a postupuj podľa chybového hlásenia.
- **`uninstalling` alebo `uninstall_failed`:** odinštalovanie sa nedokončilo. Prečítaj `shared/uninstall-state.json`, vyrieš príčinu a dokonči odinštalovanie z pomocného checkoutu. Aktualizácia tento stav zámerne blokuje. Po úspešnom odinštalovaní so zachovanými dátami použiješ Aktualizáciu do rovnakého koreňa na opätovnú inštaláciu.

### Zlyhal iba krok firewallu po aktivácii

Ak už výpis potvrdil aktívne vydanie a až potom zlyhal pomocník UFW, neznamená to neúspešnú inštaláciu aplikácie. Over jej skutočný stav a firewall bez zmien (názov služby nahraď vlastným):

```bash
systemctl --user is-active poznamkovnik.service
sudo env LC_ALL=C /usr/sbin/ufw status numbered
```

Neopakuj prvú inštaláciu, nevypínaj firewall ani nemaž cudzie pravidlá. Vydanie 0.57.2 mohlo chybne odmietnuť už existujúce pravidlo pre iný port, napríklad DNS `53` bez uvedeného protokolu. Opravený pomocník vie odlíšiť samostatný číselný port alebo UDP; pôvodné pravidlá ponecháva nedotknuté. Nejednoznačné profily, rozhrania a rozsahy, pri ktorých nemožno vylúčiť konflikt s portom aplikácie, naďalej vyžadujú osobnú kontrolu. Blokujúci riadok sa vypíše bez jeho komentára.

Po kontrole príčiny môžeš dokončiť iba firewall pomocou samostatného `server-system.sh` z overeného checkoutu zverejneného vydania `v0.57.3` alebo novšieho. Súbory v aktívnom `releases/` neupravuj. V ponechanom pomocnom checkout-e najprv over stav:

```bash
git status --short
```

Ak ukáže lokálne zmeny, zastav sa a najprv ich osobne skontroluj; nič neprepisuj ani neresetuj. Pri čistom checkout-e stiahni presný tag a prepni iba tento pomocný checkout:

```bash
git fetch origin tag v0.57.3 && git switch --detach refs/tags/v0.57.3
```

Nasledujúci príklad predpokladá, že si už v tomto opravenom pomocnom checkout-e; použi skutočný koreň existujúcej inštalácie a vlastnú IPv4 sieť, príklad `192.168.0.0/24` nie je automatická voľba:

```bash
sudo bash scripts/server-system.sh firewall "$HOME/apps/poznamkovnik" 192.168.0.0/24
```

Port sa načíta z existujúceho `shared/server.json`. Pomocník ukáže port, zdrojovú sieť a identifikátor inštalácie, vyžiada si potvrdenie a pred zmenou vytvorí novú zálohu UFW. Zásah zaznamená do koreňového dokladu tejto inštalácie, takže odinštalátor môže neskôr odobrať iba jej vlastnú nezmenenú výnimku. Aplikačné vydanie, jeho dáta ani službu tento samostatný krok neaktivuje znova; lokálnu HTTP kontrolu a prístup z druhého počítača over osobitne.

## Ručné ovládanie služby a logy

Nasledujúce príkazy ovládajú predvolenú službu. `status` môže pri vypnutej službe skončiť nenulovým kódom; to samo osebe nie je chyba diagnostiky.

```bash
systemctl --user status poznamkovnik.service --no-pager
journalctl --user -u poznamkovnik.service -n 80 --no-pager
systemctl --user stop poznamkovnik.service
systemctl --user start poznamkovnik.service
```

Zastavenie preruší rozpracované úlohy. Službu nespúšťaj ručne, ak posledná obnova zlyhala. Logy pred zdieľaním skontroluj — môžu obsahovať cesty alebo informácie o používaní aplikácie. Heslá, tokeny ani súkromné kľúče neposielaj.

## DNS a Pi-hole

Na stroji s Pi-hole treba rozlišovať DNS používané samotným Linuxom, DNS poskytované klientom a upstream servery Pi-hole. Pi-hole po filtrovaní môže preposielať otázky svojmu upstream resolveru; jeho nastavenie nemožno odvodiť iba z `/etc/resolv.conf`. Pozri [oficiálne vysvetlenie Pi-hole](https://docs.pi-hole.net/guides/dns/unbound/).

Pri predchádzajúcej príprave Korunky bol doplnený router `192.168.0.1` do systémového resolvera a do `/etc/resolv.conf.head`. Neskôr bola doplnená informácia, že server používa Pi-hole. To znamená, že bez samostatného preverenia nevieme uzavrieť, či je tento spôsob vhodný pre zamýšľané filtrovanie. Pôvodný problém s prekladom názvov nebol úplnou diagnózou nastavenia Pi-hole. Inštalátor tento zásah nezopakuje ani nebude nastavenie meniť.

Bez zmeny konfigurácie môžeš na serveri overiť:

```bash
getent ahosts github.com
getent ahosts pypi.org
getent ahosts deb.debian.org
```

Pri lokálne nainštalovanom Pi-hole môžeš pozrieť `pihole status` a `systemctl status pihole-FTL --no-pager`. Pri kontajneri použi jeho vlastný spôsob kontroly. Nefunkčný preklad môže znamenať problém resolvera, filtrov, upstreamu alebo siete — samotný neúspech neurčuje príčinu. Neobchádzaj ho automaticky verejným DNS, nevypínaj Pi-hole ani neupravuj router kvôli inštalátoru.
