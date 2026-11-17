# Prvý prístup k privátnemu Gitu

Cieľ: server smie čítať iba repozitár Poznámkovníka, nemusí vedieť zapisovať na GitHub a nikomu tým nepovoľuješ prihlásenie na server. Kroky vykonávaš osobne. Súkromné kľúče a heslá neposielaj do chatu.

Tento návod musíš mať dostupný ešte pred stiahnutím projektu — napríklad otvorený na svojom vývojovom počítači. Aj samotný inštalátor je totiž v privátnom repozitári. Nepoužívame verejný repozitár ani spúšťanie stiahnutého skriptu cez `curl | bash`.

## 1. Prihlásenie a základné nástroje

Zo svojho terminálu sa prihlás svojím bežným spôsobom, napríklad:

```bash
ssh michal@Korunka
```

V ďalších krokoch pracuješ na serveri, pod bežným účtom, nie ako root. Over nástroje:

```bash
hostname
git --version
ssh -V
python3 --version
```

Potrebujeme Linux so systemd a Python 3.11 alebo novší. Ak základné nástroje chýbajú, ich doinštalovanie je samostatná administrátorská operácia; na Debiane sú to balíky `git`, `openssh-client` a `python3`. Najprv si pozri návrh balíkov cez `sudo apt-get --simulate install git openssh-client python3`. Skutočnú zmenu a prípadnú aktualizáciu závislostí musíš schváliť sám. Funkčný systémový Python nenahrádzaj inou verziou naslepo. Python venv a OCR potom vie samostatne ponúknuť sprievodca.

Pri nefunkčnom DNS nepokračuj menením resolvera; pozri [obsluhu a Pi-hole](server-operations.md#dns-a-pi-hole).

## 2. Samostatný kľúč iba pre tento repozitár

```bash
install -d -m 700 "$HOME/.ssh"
ssh-keygen -t ed25519 -f "$HOME/.ssh/poznamkovnik_github_ed25519" -C 'poznamkovnik-github-readonly'
```

Odporúčaná je heslová fráza, ktorú zadáš iba do terminálu. Pri sťahovaní ňou odomkneš kľúč; netreba ju vkladať do skriptov. Ak sa nástroj opýta na prepísanie existujúceho kľúča, odpovedz nie a najprv over, na čo sa používa. Nepoužívaj bývalý kľúč určený na prihlásenie agenta na server.

Zobraz iba **verejný** súbor s koncovkou `.pub`:

```bash
cat "$HOME/.ssh/poznamkovnik_github_ed25519.pub"
```

Na GitHube otvor repozitár Poznámkovníka → **Settings → Deploy keys → Add deploy key**. Zadaj názov napríklad `Korunka – iba čítanie`, vlož verejný kľúč a **nezaškrtni Allow write access**. Ide o prístup k jednému repozitáru, nie k celému tvojmu účtu. Čítanie zahŕňa aj históriu; kľúč nie je obmedzený na jediný tag. Pozri [oficiálny návod GitHub](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys).

Súkromný súbor bez `.pub` zostáva na Korunke. Jeho držiteľ môže čítať repozitár; chráň ho aj pri zálohovaní servera.

## 3. Vybrať správny kľúč pre Git

Vo svojom terminálovom editore otvor `~/.ssh/config`. Existujúci obsah neprepisuj. Ak už nasledujúci alias existuje, skontroluj ho namiesto pridávania druhej kópie. Pridaj:

```sshconfig
Host github-poznamkovnik
    HostName github.com
    User git
    IdentityFile ~/.ssh/poznamkovnik_github_ed25519
    IdentitiesOnly yes
    ForwardAgent no
```

```bash
chmod 600 "$HOME/.ssh/config" "$HOME/.ssh/poznamkovnik_github_ed25519"
git ls-remote git@github-poznamkovnik:sumichalek/Poznamkovnik.git HEAD
```

Pri prvom spojení môže SSH požiadať o potvrdenie identity GitHub servera. Odtlačok porovnaj s [oficiálnymi SSH odtlačkami GitHubu](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints); nevypínaj overovanie hostiteľa. Úspech znamená riadok s identifikátorom commitu a `HEAD`.

Toto preveruje čítanie, nie zákaz zápisu. Ten skontroluješ v nastavení deploy key na GitHube. Inštalátor nevykonáva skúšobný push. Read-only kľúč môžeš kedykoľvek odobrať v GitHube; spustený Poznámkovník tým nezastavíš, ale ďalšie sťahovanie bude potrebovať nový prístup.

## 4. Stiahnuť a osobne spustiť sprievodcu

Použi nový pomocný priečinok; ak už existuje, najprv skontroluj jeho obsah, neodstraňuj ho naslepo:

```bash
git clone -- git@github-poznamkovnik:sumichalek/Poznamkovnik.git "$HOME/poznamkovnik-bootstrap"
cd "$HOME/poznamkovnik-bootstrap"
git tag --list 'v*' --sort=-version:refname
read -r -p 'Vybraný zverejnený tag: ' PN_RELEASE_TAG
git switch --detach "refs/tags/$PN_RELEASE_TAG"
bash scripts/install.sh --plan
```

Vyber otestované vydanie s novým sprievodcom, nie ľubovoľný vývojový commit. Verzie 0.57.0 a 0.57.1 tento sprievodca neobsahujú. Lokálna príprava 0.57.2 sama osebe neznamená, že tag už existuje na GitHube; musí byť osobitne schválený a zverejnený. Ak `git switch` zlyhá, ďalší krok nespúšťaj z nesprávneho checkoutu.

Po prečítaní plánu spusti:

```bash
bash scripts/install.sh
```

Podrobnosti sú v [návode sprievodcu](interactive-installation.md). Pomocný checkout si nechaj ako záchranný nástroj, keď v spravovanej inštalácii ešte neexistuje funkčný `current`.

## Alternatíva cez HTTPS

Možný je aj fine-grained personal access token pre tento konkrétny repozitár s `Contents: read-only`. Nastavenie je v [oficiálnej dokumentácii GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens). Použi vhodného správcu poverení a nastav platnosť tokenu. Token sa nesmie objaviť v Git URL, shellovej histórii, dokumentácii ani logoch. Sprievodca adresy s vloženými prihlasovacími údajmi odmietne. Na domáci server odporúčame vyššie opísaný samostatný deploy key.
