# Maticový LED displej MAX7219

Firmware `matrix_display/matrix_display.ino` je pro Arduino UNO nebo Nano a řetězec 4, 8 nebo 12 modulů MAX7219 s maticí 8×8. Výchozí sestava používá 8 modulů; před nahráním změňte `MATRIX_MODULES` na `4`, `8` nebo `12` podle skutečného panelu.

Zapojte DIN na D11, CLK na D13, CS/LOAD na D10, VCC na 5 V a GND na GND. Delší řetězec napájejte stabilním externím zdrojem 5 V se společnou zemí s Arduinem; nenapájejte více modulů pouze z USB Arduina.

Sériová linka je 115200 Bd. Podporované příkazy jsou `TXT:text`, `SCR:text`, `FIX:pevný text|rolovaný text`, `SPD:milisekundy`, `BRI:0-15`, `CLS`, `TEST`, `PING` a `VER`. Text je v UTF-8; firmware vykreslí tisknutelné ASCII znaky a běžnou českou i evropskou latinkovou diakritiku. Delší text se automaticky roluje. Příkaz `SCR:` přivádí text zprava a posouvá jej doleva; počáteční mezery zachová, takže `SCR:      Text` nechá panel nejdřív prázdný a teprve potom přivede slovo zprava. Příkaz `FIX:` nechá levou část trvale svítit a roluje pouze část za svislítkem. Horní řádek je vyhrazený pro háčky a čárky, proto jsou všechny znaky posunuté o řádek dolů.

V Playoff nastavte tento panel v Nastavení → USB spojení a panely jako Maticový displej ID-3 nebo ID-4. Každému panelu lze samostatně vybrat obsah pro PLAYOFF a LAPS: odpočet, stopky A/B, tým A/B se jménem soutěžícího nebo statický tým s rolovaným jménem. Dvanáctimodulový panel umí také zobrazit odpočet vlevo a stopky A nebo B vpravo.
