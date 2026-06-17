# Playoff

Zde naleznete aplikaci pro MS Windows (instalace i portable verze), dokumentaci hardware (zapojení, 3D modely, STL soubory) a firmware pro Arduino.

V aplikaci lze generovat pavouka až pro 28 týmů. Levým tlačítkem zadáváme číslo nebo název týmu, pravým tlačítkem postupujeme tým do dalšího kola. Výsledný pavouk lze uložit, načíst, exportovat do PDF a propojit se startovními semafory.

## Aplikace

Magnetická tabule (takto to nemá vypadat)

[![](https://github.com/pihrt-com/playoff/blob/main/Example/table.jpg?raw=true)](https://github.com/pihrt-com/playoff/blob/main/Example/table.jpg)

App (takto vypadá okno aplikace)

[![](https://github.com/pihrt-com/playoff/blob/main/Example/ex1.png?raw=true)](https://github.com/pihrt-com/playoff/blob/main/Example/ex1.png)

---

# Hardware (Arduino MEGA)

Projekt používá dva nezávislé semafory, dvě laserové brány a komunikaci RS485.

## Pinout

### Semafor A

| Pin | Funkce |
|------|---------|
| D9 | Red 1 |
| D10 | Red 2 |
| D11 | Green |
| D12 | Piezo A |
| D22 | Laserová brána A |
| D25 | WS2812B A (16 LED) |

### Semafor B

| Pin | Funkce |
|------|---------|
| D3 | Red 1 |
| D5 | Red 2 |
| D6 | Green |
| D4 | Piezo B |
| D24 | Laserová brána B |
| D23 | WS2812B B (16 LED) |

### Ostatní

| Pin | Funkce |
|------|---------|
| D8 | START tlačítko |
| D2 | RS485 EN |
| D26 | Piezo SUM |
| RX0/TX0 | USB |
| RX1/TX1 | RS485 |

---

# WS2812B LED pásky

Každý semafor používá samostatný pásek 16 LED.

- LED 0–7 = RED1
- LED 8–15 = RED2
- GREEN = všech 16 LED zeleně

Používá se plynulý náběh a doběh (fade in / fade out) stejně jako u klasických LED výstupů.

---

# Komunikace

## PC → Arduino

```text
start
```

## Arduino → PC

```text
ok
finish_a
finish_b
race_finished
```

---

# False Start

Během odpočtu je sledována laserová brána.

Pokud jezdec vyjede předčasně:

- vyhlásí se FALSE START
- spustí se světelná a zvuková signalizace
- návrat vozidla na start se ignoruje

Vyhodnocení cíle:

### Bez false startu

1. průjezd = odjezd ze startu
2. průjezd = cíl

### Po false startu

1. průjezd = false start
2. průjezd = návrat na start
3. průjezd = cíl

---

# Firmware

### FW 1.0
- jeden semafor

### FW 1.1
- dva semafory
- dvě laserové brány

### FW 1.2
- odesílání průjezdů do aplikace

### FW 1.3
- RGB WS2812B pásky
- opravy false start logiky

### FW 1.4
- dva RGB pásky (16 LED + 16 LED)
- piezo SUM
- ochrana proti držení START tlačítka
- rozšířená false start logika
- stabilnější měření kol
- debounce průjezdu bránou

---

# 3D tisk

Semafory se skládají z:

- základny s elektronikou
- základny bez elektroniky
- držáků světel
- průhledných světelných prstenců

Modely jsou připraveny pro 3D tisk.

---

# ROBO 2026

Ukázka použití ze soutěže ROBO 2026 – Techmania a SOUE Plzeň

[![](https://github.com/pihrt-com/playoff/blob/main/Example/fin1.jpg?raw=true)](https://github.com/pihrt-com/playoff/blob/main/Example/jpg1.png)

[![](https://github.com/pihrt-com/playoff/blob/main/Example/fin2.jpg?raw=true)](https://github.com/pihrt-com/playoff/blob/main/Example/jpg2.png)

[![](https://github.com/pihrt-com/playoff/blob/main/Example/fin3.jpg?raw=true)](https://github.com/pihrt-com/playoff/blob/main/Example/jpg3.png)

[![](https://github.com/pihrt-com/playoff/blob/main/Example/fin4.jpg?raw=true)](https://github.com/pihrt-com/playoff/blob/main/Example/jpg4.png)

---

# Kredity

- Arduino MEGA
- Python
- Tkinter
- Adafruit NeoPixel
- Martin Pihrt (APP, FW)
- David Netušil (HW, 3D)

---

# Printables

https://www.printables.com/model/1658726-playoff-semaphore-for-robocompetition

# PIHRT.COM

https://pihrt.com/elektronika/493-playoff-app-pro-robovehicle