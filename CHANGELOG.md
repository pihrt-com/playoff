# Historie změn

## 1.0.17 – 05. 11. 2026

- Tabulka účastníků se při zapnutém předkole skládá z předkola i Kola 1 a duplicitní ID zobrazí pouze jednou.
- Tabulka zobrazuje ID, školu nebo adresu školy, jméno soutěžícího a nejlepší čas jízdy; její společný nadpis i všechna záhlaví lze kliknutím upravit a uloží se do projektu.
- Řádky tabulky účastníků mají opět kompaktní pevnou výšku, aby se vešel seznam až 24 účastníků.
- Dialog Pojmenování týmů a import/export Excelu podporují čtyři volitelné údaje a zachovávají kompatibilitu se staršími dvousloupcovými sešity i projekty.
- Všechna vyskakovací okna aplikace používají ikonu Playoffu místo výchozí ikony Tkinteru.
- Nastavení odpočtu v režimech PLAYOFF i LAPS je vlastní dialog s ikonou Playoffu.
- Škola a jméno soutěžícího jsou v hlavní tabulce vykreslené menším písmem, které se v případě potřeby přizpůsobí šířce sloupce bez zvětšení řádku.
- Každý záznam měření v režimu LAPS lze samostatně označit jako neplatný bez smazání nebo přečíslování; přeškrtnutý záznam se nezapočítává do nejlepšího zeleně zvýrazněného kola a lze jej obnovit.

## 1.0.16 – 03. 11. 2026

- Bránu i oba LED displeje lze v dialogu USB nastavení samostatně vypnout volbou „Nepoužívat“.
- LED displeje lze připojit a otestovat bez přítomné měřicí brány.
- Aplikace odmítne použití stejného COM portu pro více zařízení a zobrazí konkrétní chybovou zprávu.
- Rozšířený dialog USB nastavení zobrazuje nalezenou bránu a LED displeje a zachová nezměněná spojení po uložení.
- Do horní lišty bylo přidáno stejně velké tlačítko `PROMO` pro propagační text na všech dostupných LED displejích.
- Propagační text nabízí plynulou rotaci kompatibilní s firmwarem 1.0, rolování řízené panelem a statické zobrazení.
- Posuvník nastavuje rychlost propagačního textu od 1 do 20 znaků za sekundu.
- Text, režim a rychlost se ukládají do uživatelského JSON i do souboru projektu.
- START a potvrzená změna režimu PLAYOFF/LAPS zastaví propagaci a obnoví původní chování displejů.
- Přidán firmware LED displeje 1.1 s plynulou kruhovou rotací a zachováním mezer.
- Kontrola aktualizací porovnává číselné části verze a nikdy nenabídne starší vydání jako aktualizaci.

## 1.0.15 – 19. 10. 2026

- Do horní lišty LAPS bylo mezi mazání A a B přidáno červené potvrzované tlačítko `SMAZAT A+B`, které smaže záznamy a obnoví číslování obou drah.
- Inicializace LED displejů je nyní nezávislá pro A a B; neúspěšné nebo opožděné otevření jednoho portu neblokuje druhý a neúspěšný port zůstává připravený k dalšímu pokusu.
- Uložení USB nastavení nyní vždy znovu připojí měřicí bránu, takže změna COM portu začne fungovat ihned bez restartu aplikace.

## 1.0.14 – 19. 10. 2026

- Přidán opakovaný odpočet do režimu LAPS, umístěný dole uprostřed nad poli A a B.
- Levé tlačítko spustí cyklus od nastaveného maxima nebo běžící cyklus kdykoliv resetuje.
- Po vypršení se nastavený interval automaticky obnoví a spustí další cyklus.
- Posledních 10 sekund střídá odpočet černé a červené pozadí při zachování bílého textu.
- Pravé tlačítko nadále nastavuje společný interval `MM:SS`, který se ukládá do uživatelského nastavení i projektu.
- Vypnutí odpočtu nebo opuštění režimu LAPS cyklus zastaví a vrátí zobrazení na nastavené maximum.
- Jednorázový odpočet režimu PLAYOFF a jeho spouštění přes START/OK zůstávají beze změny.

## 1.0.13 – 18. 10. 2026

- Přidáno samostatné grafické okno updateru s průběhem stahování v procentech a zobrazením stažené velikosti.
- Doplněny stavové zprávy pro připojení, stahování, ověření souboru a spuštění instalátoru.
- Doplněny srozumitelné české chyby včetně HTTP 404, nedostupného serveru, timeoutu, oprávnění a poškozeného souboru.
- Přidána možnost stahování zopakovat nebo po chybě znovu spustit původní Playoff.
- Stahování používá bezpečný dočasný `.part` soubor a probíhá v pracovním vlákně, aby okno zůstalo aktivní.
- Aktualizační manifest nově předává velikost a SHA-256 instalačního souboru, které updater před spuštěním ověří.
- README doplněno o živé badge stabilní verze, celkových stažení, testů a licence.
- Přidán Windows GitHub Actions workflow pro automatické testy na větvi `main` a v pull requestech.

## 1.0.12 – 18. 10. 2026

- Přidáno zatržítko „Odesílat na LED průběžný čas“.
- Přidána volba rychlosti obnovování od 0,1 s do 1,0 s.
- Doplněno nezávislé průběžné zobrazování pro dráhy A a B v režimech PLAYOFF a LAPS.
- Sjednoceno nulování LED displejů při obou způsobech startu.
- Doplněna omezená fronta, která při pomalém USB ponechá pouze nejnovější čas.
- Doplněno vybírání odpovědí LED displejů, aby se vstupní buffer při průběžném provozu nehromadil.
- Nové volby se ukládají do uživatelského nastavení i do souboru projektu.
- Rozšířena nápověda v aplikaci, README a automatické testy USB komunikace a časování.
