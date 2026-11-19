# Maticový LED displej MAX7219

Firmware `matrix_display/matrix_display.ino` je pro Arduino UNO nebo Nano a řetězec 4, 8 nebo 12 modulů MAX7219 s maticí 8×8. Výchozí sestava používá 8 modulů; před nahráním změňte `MATRIX_MODULES` na `4`, `8` nebo `12` podle skutečného panelu.

Zapojte DIN na D11, CLK na D13, CS/LOAD na D10, VCC na 5 V a GND na GND. Delší řetězec napájejte stabilním externím zdrojem 5 V se společnou zemí s Arduinem; nenapájejte více modulů pouze z USB Arduina.

Sériová linka je 115200 Bd. Podporované příkazy jsou `TXT:text`, `SCR:text`, `SPD:milisekundy`, `BRI:0-15`, `CLS`, `TEST`, `PING` a `VER`. Text je v UTF-8; firmware vykreslí tisknutelné ASCII znaky a běžnou českou i evropskou latinkovou diakritiku. Delší text se automaticky roluje.

V Playoff nastavte tento panel v Nastavení → USB spojení a panely jako Maticový displej ID-3 nebo ID-4. Každému panelu lze vybrat odpočet, stopky A/B nebo tým A/B se jménem soutěžícího.
