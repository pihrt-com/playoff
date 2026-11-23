# Historie změn

## 1.0.35 – 23. 11. 2026

- Po návratu USB brány aplikace počká na start Arduina a dvakrát obnoví aktivní režim PLAYOFF nebo LAPS, aby se správně vrátilo měření LAPS.

## 1.0.34 – 23. 11. 2026

- Po návratu odpojené měřicí brány aplikace zavře staré spojení, znovu otevře port, obnoví čtení událostí a odešle aktivní režim PLAYOFF nebo LAPS.
- Indikátor měřicí brány v horní liště se jmenuje GATE; při výpadku je červený, během obnovy žlutý a po úspěšném obnovení zelený.

## 1.0.33 – 23. 11. 2026

- Po návratu odpojeného USB panelu aplikace obnoví pouze tento panel: vyčistí jeho obsah, nastaví uloženou rychlost a odešle aktuální čas nebo text.
- Indikátor ID-1 až ID-4 je při nedostupném portu červený, během obnovy žlutý a zelený až po úspěšném odeslání aktuálního obsahu.

## 1.0.32 – 23. 11. 2026

- Aktualizace přes Setup EXE zachová existující zástupce Playoffu na ploše Windows, včetně jeho umístění; při nové instalaci se zástupce vytvoří a při odinstalaci odstraní.
- Před stažením aktualizace okno zobrazí popis změn nové verze a umožní zvolit Aktualizovat nebo Později.

## 1.0.31 – 23. 11. 2026

- Nabídka Nastavení má barevné ikony u pojmenování týmů, importu ROBO, práce s pozadím, velikosti písma, tloušťky čar, USB panelů a celé obrazovky.
- Položka USB nastavení nyní uvádí, že zahrnuje bránu i panely, a nápověda obsahuje klikací odkaz na GitHub projektu.
- Nejlepší čas v tabulce účastníků používá při velkém písmu kompaktní velikost, takže nezasahuje do sousedních řádků.

## 1.0.30 – 20. 11. 2026

- Každý panel ID-1 až ID-4 má vlastní uloženou rychlost posunu v milisekundách.
- PROMO používá vlastní rychlost a při skončení obnoví rychlost zvolenou pro jednotlivé LED a maticové panely.

## 1.0.29 – 20. 11. 2026

- Odpočet obnovuje jen panely nastavené na odpočet v právě aktivním režimu; statický tým a rolované jméno v druhém režimu se už každou sekundu neresetují.

## 1.0.28 – 20. 11. 2026

- Každý USB panel má samostatnou volbu obsahu pro PLAYOFF a LAPS; přepnutí režimu panely ihned obnoví.
- Maticové panely ID-3 a ID-4 umí na dvanácti modulech zobrazit odpočet vlevo a stopky A nebo B vpravo.
- Firmware maticového panelu posouvá znaky o řádek dolů a vyhrazuje horní řádek pro háčky a čárky bez překrytí statického týmu.

## 1.0.27 – 19. 11. 2026

- Při přepnutí do LAPS se týmové maticové panely ihned obnoví pro aktivní dvojici týmů.
- Opraveno opakované rolování jména vedle statického názvu týmu a vykreslení diakritiky maticového firmware.

## 1.0.26 – 19. 11. 2026

- Maticové panely nabízejí volbu statického týmu vlevo a rolování pouze jména soutěžícího vpravo.

## 1.0.25 – 19. 11. 2026

- Opravena vodorovně zrcadlená písmena firmware maticového displeje MAX7219.
- Rolování `SCR:` nyní přivádí text zprava doleva a zachovává počáteční mezery jako odsazení.

## 1.0.24 – 19. 11. 2026

- Přidána podpora dvou nezávislých maticových panelů MAX7219 vedle stávajících sedmisegmentových displejů.
- V USB nastavení lze pro každý ze čtyř panelů zvolit COM port, rychlost a obsah: odpočet, stopky A/B nebo tým A/B se jménem soutěžícího.
- Přidán firmware pro Arduino UNO/Nano s konfigurací 4, 8 nebo 12 matic 8×8, UTF-8 textem a evropskou diakritikou.

## 1.0.23 – 19. 11. 2026

- Nabídka Nastavení má malé ikony u počtu týmů, načtení a uložení souboru, zámku editace, PDF exportů, nápovědy a kontroly aktualizace.
- Spojnice importu ROBO z předkola do osmifinále jsou v aplikaci plné stejně jako v PDF.
- Po potvrzení USB nastavení se brána i samostatné LED displeje ihned znovu připojí; stav brány už nehlásí úspěch při neotevřeném portu.
- Výchozí rychlost brány i obou LED displejů je 115200 Bd.

## 1.0.22 – 19. 11. 2026

- Portable verze a instalátor nyní obsahují certifikáty pro HTTPS, takže funguje Kontrola aktualizace i stažení JSON z ROBO.

## 1.0.21 – 18. 11. 2026

- Opraveno přiřazení ikony programu všem hlavním i dialogovým oknům Playoffu.
- Aktualizační manifest nyní odpovídá ověřenému instalačnímu souboru vydání 1.0.20, takže lze přejít na tuto opravu přes Kontrolu aktualizace.

## 1.0.20 – 18. 11. 2026

- Přidán samostatný oddíl Import online z ROBO s nastavením endpointu, API klíče a klikacího klíče předkola i osmifinále.
- Import načte a ověří JSON ROBO v1, před zápisem zobrazí náhled a pracuje pouze při zapnutém předkole a pavouku pro 16 týmů.
- Výchozí klíč vyplní předkolo dvojicemi 9/24 až 16/17 a osm přímo nasazených týmů v osmifinále; navázaná pole vítězů předkola zůstanou prázdná.
- Pravé tlačítko v předkole přenese vítěze do určeného slotu osmifinále. Modré spojnice se zobrazují v pavouku i v PDF exportu.
- Dialogy importu používají ikonu Playoffu, čas vytvoření dat ROBO se zobrazuje v místním formátu a výchozí tloušťka nového pavouka je silná.

## 1.0.19 – 09. 11. 2026

- Nad tabulkami LAPS se pro právě vybranou dvojici zobrazí škola a jméno soutěžícího z Pojmenování týmů, pouze pokud se ID přesně shoduje.
- Nejlepší platný zelený čas LAPS se promítá do sloupce Nejlepší čas jízdy ve tvaru `00:12:500 (12500)` bez uložení formátovaného textu do projektu.
- Export Pojmenování týmů zapisuje do posledního sloupce pouze nejlepší čas v milisekundách; pokud tým nemá platný zelený výsledek, buňka zůstane prázdná.
- Každá stránka PDF exportu LAPS obsahuje školu, jméno soutěžícího a nejlepší platný čas příslušného týmu.
- Informační řádky LAPS mají odstup od ovladačů `Team`, `+` a `−`; název školy používá normální řez písma i tehdy, když soutěžící není vyplněný.

## 1.0.18 – 05. 11. 2026

- Režim LAPS rozlišuje ID týmu a samostatné číslo jízdy.
- Modrá tlačítka `Team`, `+` a `−` přepínají dvojice týmů bez ztráty jejich uložené historie; vedle zvětšených tučných ovladačů se zobrazuje aktuální dvojice.
- Každý tým má vlastní seznam výsledků a pokračující číslování jízd; aktivní dvojice i všechny záznamy se ukládají do projektu.
- Nové podmenu `LAPS` nastavuje sudý maximální počet týmů, ve výchozím stavu 40, a umožňuje vymazat výsledky všech týmů.
- Tlačítka mazání nad tabulkami odstraňují pouze výsledky právě zobrazené dvojice, zatímco `Vymazat všechno` odstraní kompletní historii LAPS.
- Sloupec `Platnost` používá stejný font a velikost jako ostatní záhlaví tabulky.
- Okno updateru používá ikonu `playoff.ico`.
- Původní export byl přejmenován na `Export do PDF PLAYOFF`; nový `Export do PDF LAPS` vytváří jednu grafickou stránku pro každý tým se všemi jeho jízdami.

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
