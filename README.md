
# Vítejte v playoff!
Zde naleznete aplikaci pro MS Windows (instalace, nebo portable verze), dokumentaci hardware (zapojení, 3D design...) V aplikaci lze vygenerovat pavouka až pro 24 týmů. Levým tlačítkem zadáváme číslo (název) týmu a pravým tlačítkem postupujeme tým do dalšího kola. Seznam kol si můžeme pravým tlačítkem pojmenovat. Na pozadí aplikace se dá vložit obrázek, nebo libovolná barva. Výsledný list můžeme exportovat do PDF pro následný tisk. Pavouka si můžeme připravit dopředu (doma) a před soutěží nahrát ze souboru. Aplikace umí spustit tlačítkem zvukovou a světelnou signalizaci (semafor) pro start utkání. Zároveň lze zobrazit (pod vítězem) odpočet času (nastavuje se pravým tlačítkem myši). Odpočet se spouští tlačítkem "START" spolu se zvukovou a světelnou signalizací.

## Aplikace
Magnetická tabule (takto to nemá vypadat)
[![](https://github.com/pihrt-com/playoff/blob/main/Example/table.jpg?raw=true)](https://github.com/pihrt-com/playoff/blob/main/Example/table.jpg)

App (takto vypadá okno aplikace)
[![](https://github.com/pihrt-com/playoff/blob/main/Example/example_pdf.png?raw=true)](https://github.com/pihrt-com/playoff/blob/main/Example/example_pdf.png)

App (okno nastavení)
[![](https://github.com/pihrt-com/playoff/blob/main/Example/settings.png?raw=true)](https://github.com/pihrt-com/playoff/blob/main/Example/settings.png)

PDF export (takto vypadá list pro tisk)
[![](https://github.com/pihrt-com/playoff/blob/main/Example/example_app.png?raw=true)](https://github.com/pihrt-com/playoff/blob/main/Example/example_app.png)


## Hardware (Arduino)
k desce Arduino MEGA je připojen samovybuzující piezoelement na pin číslo 12. Na semaforu jsou 3 patra LED (2x červený prstenec a 1x zelený) připojené na piny 9, 10, 11 (R, R, G) přes spínací tranzistory (bipolár, unipolár...). Tlačítko pro test (nebo spuštění cyklu zvukové a světelné signalizace) je připojeno z pinu 8 na 0V (gnd). Na piny UART1 (Rx, Tx) je připojen převodník RS485 s pinem EN na vývodu 2. Semafor reaguje na příkaz "START" na USB (UART0) nebo na RS485 (UART1). Rychlost komunikace je 9600 Bd. Přijetí se potvrzuje zpět do aplikace jako "OK". Posloupnost je následující: po stisku tlačítka, nebo příkazem "START" se spustí sekvence. Krátké pípnutí (0,1s) spolu se zapnutím prvního červeného prstence. Po 1s se opět ozve krátké pípnutí (0,1s) spolu se zapnutím druhého červeného prstence. Po 1s se ozve dlouhé pípnutí (1,5s) spolu se zapnutím zeleného prstence. Jízda vozítek může začít. Všechny LED prstence po 3s přejdou metodou fadeout do tmy. LED jsou řízeny PWM z CPU a svitem (zapnutí a vypnutí) simulují žárovky.

## 3D
TODO doplnit 3 díly a foto

## ROBO 2026
> Ukázka použití ze soutěže ROBO 2026 **Techmania a SOUE Plzeň** 
TODO sem dát potom foto a video, pak smazat

## Kredity
- Arduino.cc -> deska mega (samozřejmě by to zvládla i deska uno nebo jiná)
- Python -> pro běh aplikace
- Tkinter -> jako Python interface (grafika)
- Martin Pihrt a David Netušil
