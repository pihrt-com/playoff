# Historie změn

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
