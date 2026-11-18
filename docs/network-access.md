# Lokálny prístup, SSH tunel a LAN HTTP

Spôsob prístupu volíš pri inštalácii a neskôr ho môžeš zmeniť voľbou **6 – Zmeniť spôsob prístupu**. Netreba novú inštaláciu ani nový účet. Táto voľba vyžaduje sprievodcu, ktorý ju obsahuje; vydanie 0.57.5 ju ešte nemalo. Použi novší overený pomocný checkout, nie ručné úpravy v `releases/`.

## Dva odlišné režimy

- **Lokálny prístup / SSH tunel:** aplikácia počúva na `127.0.0.1`. Z iného počítača ju priamo cez LAN neotvoríš; použiješ vlastné SSH prihlásenie a tunel. Pre aplikačný port netreba novú výnimku firewallu. Tento režim je predvolený.
- **LAN cez HTTP:** aplikácia počúva na `0.0.0.0`, teda všetkých IPv4 rozhraniach servera. Otváraš napríklad `http://Korunka:1112` alebo IP servera. HTTP nešifruje heslá ani obsah počas prenosu. UFW môže samostatne povoliť TCP port len z konkrétnej siete alebo počítača (`/32`).

Vynechať vytvorenie pravidla UFW **nie je to isté** ako nastaviť lokálny režim. Prístup môže už povoľovať staršie alebo širšie pravidlo, prípadne vypnutý firewall. Ani nová úzka výnimka nezúži iné existujúce pravidlá. `0.0.0.0` samo neznamená „iba moja domáca sieť“ a nie je to adresa na zadanie do prehliadača.

Sprievodca nepovoľuje ani neresetuje celý firewall, neotvára port na routeri a nemení SSH server, DNS ani Pi-hole. Nevytvára vzdialený prístup agentovi. Lokálny režim nebráni prístupu iným oprávneným lokálnym procesom alebo tvojmu prípadnému existujúcemu proxy; nenahrádza zabezpečenie servera.

## Zmena existujúcej inštalácie

V pomocnom checkout-e na serveri najprv otvor plán:

```bash
bash scripts/install.sh --plan
```

Vyber **6**, skutočný inštalačný koreň a nový režim. Na Korunke je to podľa doterajšej skúšky `/home/michal/Doplnky/Poznámkovník-skuska`, nie priečinok pomocného checkoutu `/home/michal/Doplnky/Poznámkovník`.

Plán ukáže starú aj novú adresu a samostatný zámer UFW. Nič nezapisuje, nevolá sudo ani sieťový Git. Skontroluje miestne vydanie, konfiguráciu a načítanú systemd jednotku. Cudziu alebo ručne upravenú jednotku či doplnky (drop-ins) automaticky neprepisuje. Pri nedokončenej aktualizácii alebo obnove najprv vyrieš [stav operácie](server-operations.md#ak-sa-niečo-pokazí).

Na vykonanie spusti `bash scripts/install.sh` a vyber rovnaké voľby. Port, názov služby, identita inštalácie, aktívne vydanie, účty, dáta aj automatické spúšťanie zostávajú zachované. Git tag sa nesťahuje a Python prostredie sa neinštaluje znova. Nechaj dobehnúť OCR a ostatné rozpracované úlohy.

Potvrdzuješ osobitne plán, prípravu prestavenia, odstávku s novou overenou zálohou a až potom aktiváciu novej adresy. Záloha obsahuje celé dáta aj **pôvodné** nastavenia a jednotku služby. Ak záloha alebo jej overenie zlyhá, konfigurácia sa neprepíše. Odmietnutie aktivácie obnoví pôvodný beh; neúspešná aktivácia sa pokúsi obnoviť pôvodné dáta a nastavenia. Výsledok vždy skontroluj. Predtým vypnutá služba sa pri kontrole krátko spustí a potom znova vypne; autostart sa nemení.

Ak zvolená adresa už platí, aplikačná časť nič neaktivuje ani nezastavuje a nevytvára zbytočnú zálohu. Stále možno samostatne dokončiť UFW. Pri novej zmene alebo obnove je nová overená záloha opäť povinná.

### Firewall sa potvrdzuje zvlášť

Po úspešnom aplikačnom kroku sa vykoná len UFW krok, ktorý si zvolil a osobitne potvrdíš cez sudo. Samotný root pomocník ukáže presný zásah a vyžiada ďalšie potvrdenie; pred zmenou vytvorí novú systémovú zálohu.

- Pri LAN môže pridať výnimku pre konkrétnu IPv4 sieť alebo jeden počítač. Ak zvolíš túto výnimku a UFW chýba alebo nie je aktívny, postup skončí ešte pred prestavením aplikácie. Firewall si musíš pripraviť osobne alebo vedome vybrať plán bez jeho zmeny.
- Pri lokálnom režime môže odobrať **iba vlastnú nezmenenú výnimku** pre túto inštaláciu, overenú root dokladom. Cudzie, predtým existujúce alebo pozmenené pravidlá zostávajú. Linger, SSH a pravidlá Pi-hole/DNS/DHCP sa nemenia. Aj pri ponechanej výnimke aplikácia v lokálnom režime nepočúva na LAN adrese.

Zlyhanie alebo odmietnutie tohto kroku nevracia úspešnú zmenu adresy aplikácie. Neopakuj prvú inštaláciu; [skontroluj službu a UFW](server-operations.md#zlyhal-iba-krok-firewallu-po-aktivácii). Celý starý firewall sa automaticky neobnovuje cez novšie pravidlá. Po oprave môžeš znovu vybrať rovnaký režim a dokončiť iba UFW.

Inštalácia eviduje jednu vlastnú zdrojovú výnimku. Ak ju chceš zmeniť z celej siete na `/32` alebo na inú sieť, najprv výslovne odober pôvodnú vlastnú výnimku. Najjednoduchšie je prepnúť na lokálny režim s jej odobratím a potom na LAN s novou sieťou. Doklad sa nesmie naslepo prepísať a cudzie pravidlá sa neodstraňujú.

Samostatné odobratie vlastnej výnimky z pomocného checkoutu má najprv plán; použi vlastný koreň:

```bash
sudo bash scripts/server-system.sh firewall-remove "$HOME/Doplnky/Poznámkovník-skuska" --plan
```

Až po kontrole prípadne zopakuj bez `--plan`. Tento samostatný krok nemení adresu aplikácie, dáta ani linger. Nezamieňaj ho s `cleanup`, ktoré je určené aj na kontrolu ostatných systémových zmien pri odinštalovaní.

## Otvorenie prehliadača cez SSH tunel

Príkaz spusti **na počítači s prehliadačom**, nie v shelli na Korunke. Pre doterajšiu skúšobnú inštanciu na porte 1112:

```bash
ssh -N -o ExitOnForwardFailure=yes -o ForwardAgent=no -L 127.0.0.1:18112:127.0.0.1:1112 michal@Korunka
```

Používaš svoje bežné SSH prihlásenie na server, nie read-only deploy key ku GitHubu. Ak názov Korunka klient nepozná, použi jej overenú aktuálnu IP. Nový alebo zmenený SSH hostiteľský odtlačok najprv over; nevypínaj kontrolu hostiteľského kľúča.

Po úspešnom prihlásení otvor na tom istom počítači `http://127.0.0.1:18112`. Tiché čakanie v termináli je normálne: `-N` neotvára vzdialený shell. Terminál nechaj otvorený. `Ctrl+C` ukončí tunel, nie aplikáciu na serveri. Spojenie medzi klientom a serverom je šifrované cez SSH; HTTP je na koncoch lokálne. Aplikácia si naďalej vyžaduje vlastné prihlásenie. Lokálna adresa má iný pôvod než LAN adresa, preto sa môžeš musieť prihlásiť znova; účet nevytváraj nanovo.

Prvé `18112` je voľný port **klienta**, posledné `1112` je port aplikácie **na serveri**. Ak je klientsky port obsadený, zmeň iba `18112` v príkaze aj adrese prehliadača. Explicitné `127.0.0.1` pred portom nevystavuje tunel ostatným počítačom v LAN. `ExitOnForwardFailure` odhalí chybu vytvorenia presmerovania, nie každý neskorší problém aplikácie; pri nedostupnej stránke skontroluj aj službu. Nepoužívaj `-g` ani otvorenie klientského portu do celej siete.

### Kratší príkaz na zapamätanie

Voliteľne si **osobne na klientovi** pridaj samostatný blok do `~/.ssh/config`. Existujúce bloky neprepisuj; názov aliasu musí byť nový. Inštalátor tento súbor nemení.

```sshconfig
Host korunka-poznamkovnik
    HostName Korunka
    User michal
    LocalForward 127.0.0.1:18112 127.0.0.1:1112
    ExitOnForwardFailure yes
    ForwardAgent no
```

Potom stačí `ssh -N korunka-poznamkovnik` a rovnaká adresa prehliadača. Uprav meno, porty a prípadné vlastné nastavenia prihlásenia podľa seba. Alias `github-poznamkovnik` zo servera je niečo iné: slúži Gitu na čítanie repozitára, nie tomuto tunelu.

## Ručné overenie bez zmien

Na serveri (názov služby a port nahraď svojimi):

```bash
systemctl --user is-active poznamkovnik-skuska.service
ss -ltn 'sport = :1112'
sudo env LC_ALL=C /usr/sbin/ufw status numbered
```

V lokálnom režime očakávaj listener `127.0.0.1:1112`, pri LAN `0.0.0.0:1112`. Vypnutá služba nepočúva. HTTP zdravie preverí voľba 3 sprievodcu; dostupnosť cez LAN over aj z druhého počítača. Pre tunel otvor klientsku lokálnu adresu, nie pôvodnú LAN záložku.
