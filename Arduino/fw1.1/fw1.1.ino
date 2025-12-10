/*
 Martin Pihrt a David Netušil ©2025 
 FW: 1.1 10.12.2025
 Neblokující 2x semafor a laserová brána pro ROBOxx 
*/

// ============================================================================
// CONFIG
// ============================================================================
const int lights[] = {9, 10, 11};
const int lightCount = 3;

const int piezo = 12;
const int RS485_EN = 2;
const int button = 8;

// Fade maximálně 100 ms
int fadeInTime  = 100;
int fadeOutTime = 100;

int stepTime    = 1000;   // pauza mezi světly
int holdTime    = 3000;   // po všech světlech

int beepShort   = 100;
int beepLong    = 1500;

const int BAUD  = 9600;
bool DEBUG = false;

// ============================================================================
// VARIABLES
// ============================================================================
unsigned long now;

String rx0 = "";
String rx1 = "";

// Stavový automat
enum State {
  IDLE,
  FADE_IN,
  STEP_WAIT,
  HOLD,
  FADE_OUT
};

State state = IDLE;

int currentLED = 0;
unsigned long stateTimer = 0;
unsigned long fadeTimer  = 0;
int fadeLevel = 0;
bool fadeBeepStarted = false;

// ============================================================================
// RS485 SEND
// ============================================================================
void rs485Send(String msg) {
  if (DEBUG) { Serial.println(F("[RS485] TX -> ")); Serial.println(msg); }
  digitalWrite(RS485_EN, HIGH);
  delayMicroseconds(40);
  Serial1.print(msg);
  Serial1.flush();
  delayMicroseconds(40);
  digitalWrite(RS485_EN, LOW);
}

// ============================================================================
// UART HANDLING (non-blocking)
// ============================================================================
void handleUART() {
  if (state != IDLE) return;
  // UART0
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      rx0.trim();
      if (DEBUG) { Serial.print(F("[UART0] RX: ")); Serial.println(rx0); }
      if (rx0.equalsIgnoreCase("start")) {
        if (DEBUG) Serial.println(F("[FSM] START via UART0"));
        state = FADE_IN;
        currentLED = 0;
        fadeLevel = 0;
        fadeTimer = now;
        fadeBeepStarted = false;
      }
      rx0 = "";
    } else rx0 += c;
  }

  // UART1
  while (Serial1.available()) {
    char c = Serial1.read();
    if (c == '\n') {
      rx1.trim();
      if (DEBUG) { Serial.print(F("[UART1] RX: ")); Serial.println(rx1); }
      if (rx1.equalsIgnoreCase("start")) {
        if (DEBUG) Serial.println(F("[FSM] START via RS485"));
        state = FADE_IN;
        currentLED = 0;
        fadeLevel = 0;
        fadeTimer = now;
        fadeBeepStarted = false;
      }
      rx1 = "";
    } else rx1 += c;
  }
}

// ============================================================================
// BUTTON HANDLING (with debounce)
// ============================================================================
unsigned long lastButton = 0;
const int debounce = 50;

void handleSwitch() {
  if (state != IDLE) return;
  if (digitalRead(button) == LOW) {
    if (now - lastButton > debounce) {
      if (DEBUG) Serial.println(F("[BUTTON] Manual START"));
      state = FADE_IN;
      currentLED = 0;
      fadeLevel = 0;
      fadeTimer = now;
      lastButton = now;
      fadeBeepStarted = false;
    }
  }
}

// ============================================================================
// PIEZO (non-blocking)
// ============================================================================
bool beepActive = false;
unsigned long beepEnd = 0;

void startBeep(int duration) {
  digitalWrite(piezo, HIGH);
  beepActive = true;
  beepEnd = now + duration;
  if (DEBUG) { Serial.print(F("[BEEP] START ")); Serial.println(duration); }
  if (duration > 1000) {
    rs485Send("ok\n");
    Serial.println(F("ok"));
  }
}

void handleBeep() {
  if (beepActive && now >= beepEnd) {
    digitalWrite(piezo, LOW);
    beepActive = false;
    if (DEBUG) Serial.println(F("[BEEP] STOP"));
  }
}

// ============================================================================
// FADES (non-blocking)
// ============================================================================
void fadeInStep(int pin) {
  int interval = max(1, fadeInTime / 255);
  if (now - fadeTimer >= interval) {
    fadeTimer = now;
    analogWrite(pin, fadeLevel);
    fadeLevel++;
    if (fadeLevel > 255) fadeLevel = 255;
  }
}

bool fadeInDone() {
  return (fadeLevel >= 255);
}

void fadeOutAllStep() {
  int interval = max(1, fadeOutTime / 255);
  if (now - fadeTimer >= interval) {
    fadeTimer = now;
    fadeLevel--;
    if (fadeLevel < 0) fadeLevel = 0;
    for (int i = 0; i < lightCount; i++)
      analogWrite(lights[i], fadeLevel);
  }
}

bool fadeOutDone() {
  return (fadeLevel <= 0);
}

// ============================================================================
// SETUP
// ============================================================================
void setup() {
  Serial.begin(BAUD);
  Serial1.begin(BAUD);

  pinMode(RS485_EN, OUTPUT);
  digitalWrite(RS485_EN, LOW);

  pinMode(piezo, OUTPUT);
  pinMode(button, INPUT_PULLUP);

  for (int i = 0; i < lightCount; i++)
    analogWrite(lights[i], 0);

  if (DEBUG) Serial.println(F("[BOOT] READY"));

  // todo test led
}

// ============================================================================
// LOOP
// ============================================================================
void loop() {
  now = millis();
  handleUART();
  handleBeep();
  handleSwitch();

  switch (state) {
  case IDLE:
    break;

  // ----------------------------------------------------
  case FADE_IN:
    // Spuštění beep pouze 1×
    if (!fadeBeepStarted) {
      if (currentLED == lightCount - 1) startBeep(beepLong);
      else startBeep(beepShort);
      fadeBeepStarted = true;
      if (DEBUG) { Serial.print(F("[FSM] FADE_IN LED ")); Serial.println(currentLED); }
    }
    fadeInStep(lights[currentLED]);
    if (fadeInDone()) {
      state = STEP_WAIT;
      stateTimer = now;
      fadeLevel = 0;
      if (DEBUG) Serial.println(F("[FSM] FADE_IN DONE"));
    }
    break;

  // ----------------------------------------------------
  case STEP_WAIT:
    if (now - stateTimer >= stepTime) {
      currentLED++;
      if (currentLED >= lightCount) {
        state = HOLD;
        stateTimer = now;
        if (DEBUG) Serial.println(F("[FSM] HOLD"));
      } else {
        state = FADE_IN;
        fadeTimer = now;
        fadeBeepStarted = false;
        if (DEBUG) { Serial.print(F("[FSM] NEXT LED ")); Serial.println(currentLED); }
      }
    }
    break;

  // ----------------------------------------------------
  case HOLD:
    if (now - stateTimer >= holdTime) {
      state = FADE_OUT;
      fadeLevel = 255;
      fadeTimer = now;
      if (DEBUG) Serial.println(F("[FSM] FADE_OUT"));
    }
    break;

  // ----------------------------------------------------
  case FADE_OUT:
    fadeOutAllStep();
    if (fadeOutDone()) {
      state = IDLE;
      if (DEBUG) Serial.println(F("[FSM] DONE – back to IDLE"));
      for (int i = 0; i < lightCount; i++)
        analogWrite(lights[i], 0);
    }
    break;
  }
}
