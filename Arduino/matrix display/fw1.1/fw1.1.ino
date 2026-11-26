/*
  Playoff Matrix Display
  Arduino UNO/Nano + 4, 8 or 12 MAX7219 8x8 modules.

  FW 1.1
  Safe UTF-8 decoding, Turkish letters and serial overflow recovery

  Serial commands at 115200 Bd:
    TXT:Text in UTF-8
    SCR:Text in UTF-8
    SPD:250
    BRI:8
    CLS | TEST | PING | VER
*/

#include <SPI.h>

// Change only this value before upload. The same firmware supports 4, 8 and 12 modules.
#define MATRIX_MODULES 12

#if MATRIX_MODULES < 4 || MATRIX_MODULES > 12
#error "MATRIX_MODULES must be between 4 and 12"
#endif

const byte CS_PIN = 10;
const byte MAX_COLUMNS = MATRIX_MODULES * 8;
const byte MAX_TEXT_BYTES = 160;

char message[MAX_TEXT_BYTES] = "";
char fixedPrefix[40] = "";
char rxBuffer[MAX_TEXT_BYTES] = "";
byte rxLength = 0;
bool rxOverflow = false;
uint16_t scrollPeriod = 65;
unsigned long lastScroll = 0;
uint16_t scrollOffset = 0;
bool forceScroll = false;

// Classic 5x7 glyphs for printable ASCII (32..126), stored as vertical columns.
const byte font5x7[][5] PROGMEM = {
  {0,0,0,0,0},{0,0,95,0,0},{0,7,0,7,0},{20,127,20,127,20},{36,42,127,42,18},{35,19,8,100,98},{54,73,85,34,80},{0,5,3,0,0},{0,28,34,65,0},{0,65,34,28,0},{20,8,62,8,20},{8,8,62,8,8},{0,80,48,0,0},{8,8,8,8,8},{0,96,96,0,0},{32,16,8,4,2},
  {62,81,73,69,62},{0,66,127,64,0},{66,97,81,73,70},{33,65,69,75,49},{24,20,18,127,16},{39,69,69,69,57},{60,74,73,73,48},{1,113,9,5,3},{54,73,73,73,54},{6,73,73,41,30},{0,54,54,0,0},{0,86,54,0,0},{8,20,34,65,0},{20,20,20,20,20},{0,65,34,20,8},{2,1,81,9,6},
  {50,73,121,65,62},{126,17,17,17,126},{127,73,73,73,54},{62,65,65,65,34},{127,65,65,34,28},{127,73,73,73,65},{127,9,9,9,1},{62,65,73,73,122},{127,8,8,8,127},{0,65,127,65,0},{32,64,65,63,1},{127,8,20,34,65},{127,64,64,64,64},{127,2,12,2,127},{127,4,8,16,127},{62,65,65,65,62},
  {127,9,9,9,6},{62,65,81,33,94},{127,9,25,41,70},{70,73,73,73,49},{1,1,127,1,1},{63,64,64,64,63},{31,32,64,32,31},{63,64,56,64,63},{99,20,8,20,99},{3,4,120,4,3},{97,81,73,69,67},{0,127,65,65,0},{2,4,8,16,32},{0,65,65,127,0},{4,2,1,2,4},{64,64,64,64,64},
  {0,1,2,4,0},{32,84,84,84,120},{127,72,68,68,56},{56,68,68,68,32},{56,68,68,72,127},{56,84,84,84,24},{8,126,9,1,2},{12,82,82,82,62},{127,8,4,4,120},{0,68,125,64,0},{32,64,68,61,0},{127,16,40,68,0},{0,65,127,64,0},{124,4,24,4,120},{124,8,4,4,120},{56,68,68,68,56},
  {124,20,20,20,8},{8,20,20,24,124},{124,8,4,4,8},{72,84,84,84,32},{4,63,68,64,32},{60,64,64,32,124},{28,32,64,32,28},{60,64,48,64,60},{68,40,16,40,68},{12,80,80,80,60},{68,100,84,76,68},{0,8,54,65,0},{0,0,127,0,0},{0,65,54,8,0},{16,8,8,16,8}
};

struct Glyph { char base; byte accent; };
enum { ACCENT_NONE, ACCENT_ACUTE, ACCENT_CARON, ACCENT_RING, ACCENT_UMLAUT, ACCENT_GRAVE, ACCENT_CIRCUMFLEX, ACCENT_TILDE, ACCENT_CEDILLA };

uint32_t utf8Char(const char *&text) {
  byte first = (byte)*text++;
  if (first < 0x80) return first;
  byte count;
  uint32_t code;
  uint32_t minimum;
  if (first >= 0xC2 && first <= 0xDF) { count = 1; code = first & 0x1F; minimum = 0x80; }
  else if (first >= 0xE0 && first <= 0xEF) { count = 2; code = first & 0x0F; minimum = 0x800; }
  else if (first >= 0xF0 && first <= 0xF4) { count = 3; code = first & 0x07; minimum = 0x10000; }
  else return 0xFFFD;
  while (count--) {
    byte next = (byte)*text;
    if (!next || (next & 0xC0) != 0x80) return 0xFFFD;
    text++;
    code = (code << 6) | (next & 0x3F);
  }
  if (code < minimum || code > 0x10FFFF || (code >= 0xD800 && code <= 0xDFFF)) return 0xFFFD;
  return code;
}

Glyph latinGlyph(uint32_t code) {
  if (code < 127) return {(char)code, ACCENT_NONE};
  switch (code) {
    // Czech, Slovak and common European accented letters.
    case 0x00C0: case 0x00E0: return {'A', ACCENT_GRAVE}; case 0x00C1: case 0x00E1: return {'A', ACCENT_ACUTE};
    case 0x00C2: case 0x00E2: return {'A', ACCENT_CIRCUMFLEX}; case 0x00C3: case 0x00E3: return {'A', ACCENT_TILDE};
    case 0x00C4: case 0x00E4: return {'A', ACCENT_UMLAUT}; case 0x00C5: case 0x00E5: return {'A', ACCENT_RING};
    case 0x010C: case 0x010D: return {'C', ACCENT_CARON}; case 0x00C7: case 0x00E7: return {'C', ACCENT_CEDILLA};
    case 0x010E: case 0x010F: return {'D', ACCENT_CARON}; case 0x00C8: case 0x00E8: return {'E', ACCENT_GRAVE};
    case 0x00C9: case 0x00E9: return {'E', ACCENT_ACUTE}; case 0x00CA: case 0x00EA: return {'E', ACCENT_CIRCUMFLEX};
    case 0x00CB: case 0x00EB: return {'E', ACCENT_UMLAUT}; case 0x011A: case 0x011B: return {'E', ACCENT_CARON};
    case 0x00CC: case 0x00EC: return {'I', ACCENT_GRAVE}; case 0x00CD: case 0x00ED: return {'I', ACCENT_ACUTE};
    case 0x00CE: case 0x00EE: return {'I', ACCENT_CIRCUMFLEX}; case 0x00CF: case 0x00EF: return {'I', ACCENT_UMLAUT};
    case 0x0147: case 0x0148: return {'N', ACCENT_CARON}; case 0x00D1: case 0x00F1: return {'N', ACCENT_TILDE};
    case 0x00D2: case 0x00F2: return {'O', ACCENT_GRAVE}; case 0x00D3: case 0x00F3: return {'O', ACCENT_ACUTE};
    case 0x00D4: case 0x00F4: return {'O', ACCENT_CIRCUMFLEX}; case 0x00D5: case 0x00F5: return {'O', ACCENT_TILDE};
    case 0x00D6: case 0x00F6: return {'O', ACCENT_UMLAUT}; case 0x0158: case 0x0159: return {'R', ACCENT_CARON};
    case 0x0160: case 0x0161: return {'S', ACCENT_CARON}; case 0x00DA: case 0x00FA: return {'U', ACCENT_ACUTE};
    case 0x00D9: case 0x00F9: return {'U', ACCENT_GRAVE}; case 0x00DB: case 0x00FB: return {'U', ACCENT_CIRCUMFLEX};
    case 0x00DC: case 0x00FC: return {'U', ACCENT_UMLAUT}; case 0x016E: case 0x016F: return {'U', ACCENT_RING};
    case 0x00DD: case 0x00FD: return {'Y', ACCENT_ACUTE}; case 0x0178: case 0x00FF: return {'Y', ACCENT_UMLAUT};
    case 0x017D: case 0x017E: return {'Z', ACCENT_CARON}; case 0x00DF: return {'S', ACCENT_NONE};
    case 0x011E: case 0x011F: return {'G', ACCENT_CARON}; // Approximate breve in one pixel row.
    case 0x0130: return {'I', ACCENT_ACUTE}; case 0x0131: return {'I', ACCENT_NONE};
    case 0x015E: case 0x015F: return {'S', ACCENT_CEDILLA};
    case 0x0152: case 0x0153: return {'O', ACCENT_NONE}; case 0x00C6: case 0x00E6: return {'A', ACCENT_NONE};
  }
  return {'?', ACCENT_NONE};
}

void sendAll(byte reg, byte value) {
  digitalWrite(CS_PIN, LOW);
  for (byte module = 0; module < MATRIX_MODULES; module++) { SPI.transfer(reg); SPI.transfer(value); }
  digitalWrite(CS_PIN, HIGH);
}

void initializeMatrices() {
  for (byte reg = 1; reg <= 8; reg++) sendAll(reg, 0);
  sendAll(0x0F, 0);  // test off
  sendAll(0x0C, 1);  // normal operation
  sendAll(0x0B, 7);  // all rows
  sendAll(0x09, 0);  // no BCD decoding
  sendAll(0x0A, 4);  // brightness 0..15
}

uint16_t messageWidth() {
  uint16_t width = 0;
  const char *p = message;
  while (*p && width < 1000) { uint32_t code = utf8Char(p); width += code == 0x00DF ? 12 : 6; }
  return width;
}

uint16_t textWidth(const char *text) {
  uint16_t width = 0;
  while (*text && width < 1000) { uint32_t code = utf8Char(text); width += code == 0x00DF ? 12 : 6; }
  return width;
}

void render() {
  byte columns[MAX_COLUMNS];
  memset(columns, 0, sizeof(columns));
  // Rolování vždy přivádí první znak zprava a posouvá jej doleva.
  // Počáteční mezery příkazu SCR: tak zůstávají vědomým odsazením.
  int cursor = forceScroll ? MAX_COLUMNS - scrollOffset : 0;
  int scrollStart = 0;
  if (fixedPrefix[0]) {
    const char *prefix = fixedPrefix;
    int fixedCursor = 0;
    while (*prefix) {
      uint32_t code = utf8Char(prefix);
      Glyph glyph = latinGlyph(code);
      char base = glyph.base >= 'a' && glyph.base <= 'z' ? glyph.base - 32 : glyph.base;
      if (base < 32 || base > 126) base = '?';
      for (byte col = 0; col < 5; col++) if (fixedCursor + col < MAX_COLUMNS) columns[fixedCursor + col] = pgm_read_byte(&font5x7[base - 32][col]) << 1;
      fixedCursor += 6;
      if (code == 0x00DF) {
        for (byte col = 0; col < 5; col++) if (fixedCursor + col < MAX_COLUMNS) columns[fixedCursor + col] = pgm_read_byte(&font5x7['S' - 32][col]) << 1;
        fixedCursor += 6;
      }
    }
    // The participant always enters from the invisible right edge, never next
    // to or across the fixed team label.
    cursor = MAX_COLUMNS - scrollOffset;
    scrollStart = fixedCursor;
  }
  const char *p = message;
  while (*p) {
    uint32_t code = utf8Char(p);
    Glyph glyph = latinGlyph(code);
    char base = glyph.base;
    if (base >= 'a' && base <= 'z') base -= 32;
    if (base < 32 || base > 126) base = '?';
    for (byte col = 0; col < 5; col++) {
      int x = cursor + col;
      if (x >= scrollStart && x < MAX_COLUMNS) columns[x] = pgm_read_byte(&font5x7[base - 32][col]) << 1;
    }
    if (glyph.accent != ACCENT_NONE) {
      int accentX = cursor + 2;
      if (accentX >= scrollStart && accentX >= 0 && accentX < MAX_COLUMNS) {
        // Bit 0 is the newly reserved top row. Glyphs use rows 1..7, so
        // every Czech accent stays above its own letter and cannot overwrite
        // the fixed team label while the participant text scrolls in.
        if (glyph.accent == ACCENT_CARON) {
          if (accentX - 1 >= scrollStart) columns[accentX - 1] |= 0x01;
          if (accentX + 1 < MAX_COLUMNS) columns[accentX + 1] |= 0x01;
        } else if (glyph.accent == ACCENT_UMLAUT) {
          if (accentX - 1 >= scrollStart) columns[accentX - 1] |= 0x01;
          if (accentX + 1 < MAX_COLUMNS) columns[accentX + 1] |= 0x01;
        } else {
          columns[accentX] |= 0x01;
        }
      }
    }
    cursor += 6;
    // Render German sharp s as SS using two existing 5x7 characters.
    if (code == 0x00DF) {
      for (byte col = 0; col < 5; col++) {
        int x = cursor + col;
        if (x >= scrollStart && x < MAX_COLUMNS) columns[x] = pgm_read_byte(&font5x7['S' - 32][col]) << 1;
      }
      cursor += 6;
    }
    if (cursor >= MAX_COLUMNS && !forceScroll) break;
  }
  for (byte row = 0; row < 8; row++) {
    digitalWrite(CS_PIN, LOW);
    // Modules are physically chained left to right when viewed from the LEDs.
    // Sending them in the same order prevents a horizontally mirrored message.
    for (byte module = 0; module < MATRIX_MODULES; module++) {
      byte value = 0;
      // This MAX7219 panel is wired with column 0 on the right when viewed
      // from the LEDs. Keep module order, but reverse columns inside a module.
      for (byte col = 0; col < 8; col++) value |= ((columns[module * 8 + col] >> row) & 1) << (7 - col);
      SPI.transfer(row + 1); SPI.transfer(value);
    }
    digitalWrite(CS_PIN, HIGH);
  }
}

void setMessage(const char *text, bool scrolling) {
  fixedPrefix[0] = 0;
  strncpy(message, text, sizeof(message) - 1);
  message[sizeof(message) - 1] = 0;
  scrollOffset = 0;
  forceScroll = scrolling;
  render();
}

void setFixedMessage(char *text) {
  char *separator = strchr(text, '|');
  if (!separator) { setMessage(text, true); return; }
  *separator = 0;
  strncpy(fixedPrefix, text, sizeof(fixedPrefix) - 1);
  fixedPrefix[sizeof(fixedPrefix) - 1] = 0;
  strncpy(message, separator + 1, sizeof(message) - 1);
  message[sizeof(message) - 1] = 0;
  scrollOffset = 0;
  forceScroll = true;
  render();
}

void processCommand(char *command) {
  if (!strcmp(command, "CLS")) { setMessage("", false); Serial.println(F("OK")); return; }
  if (!strcmp(command, "TEST")) { for (byte row = 1; row <= 8; row++) sendAll(row, 255); Serial.println(F("OK")); return; }
  if (!strcmp(command, "PING")) { Serial.println(F("PONG")); return; }
  if (!strcmp(command, "VER")) { Serial.println(F("MATRIX FW 1.1")); return; }
  if (!strncmp(command, "TXT:", 4)) { setMessage(command + 4, false); Serial.println(F("OK")); return; }
  if (!strncmp(command, "SCR:", 4)) { setMessage(command + 4, true); Serial.println(F("OK")); return; }
  if (!strncmp(command, "FIX:", 4)) { setFixedMessage(command + 4); Serial.println(F("OK")); return; }
  if (!strncmp(command, "SPD:", 4)) { scrollPeriod = constrain(atoi(command + 4), 20, 2000); Serial.println(F("OK")); return; }
  if (!strncmp(command, "BRI:", 4)) { sendAll(0x0A, constrain(atoi(command + 4), 0, 15)); Serial.println(F("OK")); return; }
  Serial.println(F("ERR"));
}

void setup() {
  pinMode(CS_PIN, OUTPUT);
  SPI.begin();
  initializeMatrices();
  Serial.begin(115200);
  delay(1000);
  setMessage("", false);
  Serial.println(F("OK"));
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      rxBuffer[rxLength] = 0;
      if (rxOverflow) Serial.println(F("ERR:TOO_LONG"));
      else if (rxLength) processCommand(rxBuffer);
      rxLength = 0;
      rxOverflow = false;
    }
    else if (!rxOverflow && rxLength < sizeof(rxBuffer) - 1) rxBuffer[rxLength++] = c;
    else rxOverflow = true;
  }
  uint16_t width = messageWidth();
  if (message[0] && (forceScroll || width > MAX_COLUMNS) && millis() - lastScroll >= scrollPeriod) {
    lastScroll = millis();
    scrollOffset++;
    if (scrollOffset >= width + MAX_COLUMNS) scrollOffset = 0;
    render();
  }
}
