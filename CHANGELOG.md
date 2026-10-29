# Zmeny vo vydaniach

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
