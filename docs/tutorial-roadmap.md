# Učebnica – odložený plán

Stav: pozastavené na žiadosť používateľa. Aktuálna implementácia a používateľské dáta sa zachovávajú.

## Najbližšie pokračovanie

1. Pokračovať v systematickom dopĺňaní C podľa existujúcej osnovy, pričom každá lekcia má mať výklad, referenčné poznámky, úplné spustiteľné príklady, kontrolnú otázku a praktické cvičenie.
2. Po lekcii o viacrozmerných poliach doplniť zostávajúce medzery v dátových typoch, pamäti, rozhraniach medzi prekladovými jednotkami, štandardnej knižnici, prenositeľnosti a diagnostike.
3. Pri každom C príklade zachovať prísny profil C17, varovania, hraničné testy a spustenie v existujúcom izolovanom laboratóriu.
4. Rozšíriť rýchlu referenciu: vyhľadateľné tabuľky hlavičiek, funkcií, formátovacích špecifikátorov, celočíselných limitov, pravidiel životnosti a častých chýb.
5. Prepojiť súvisiace lekcie, zdroje, používateľské poznámky a vývojové projekty tak, aby sa z príkladu dalo pokračovať v Dielni vývoja bez straty kontextu.
6. Až po stabilizovaní hĺbky C uplatniť rovnaký pedagogický rámec na ďalšie už založené jazyky; obsah nemá byť iba stručný katalóg syntaxe.

## Pravidlá kvality

- Kanonický príklad v texte a spustiteľný príklad musia používať ten istý zdrojový kód.
- Očakávaný výstup sa overuje testom, nie iba opisom.
- Chybové cesty, hranice, vlastníctvo a prenositeľnosť sa vysvetľujú tam, kde vznikajú.
- Aktualizácia vstavaného obsahu nesmie zmazať postup, odpovede, poznámky ani používateľské varianty kódu.
- Nové témy musia prejsť kompletným `npm run check` a podľa potreby testom skutočného sandboxu.

## Posledný dokončený smer

Lekcia „Viacrozmerné polia a čítanie deklarácií“ pokrýva obdĺžnikové matice, kontrolu oboch indexov, parameter typu ukazovateľ na riadok, rozdiel oproti `int **`, tri úplné príklady, kontrolnú otázku a variabilné cvičenie.
