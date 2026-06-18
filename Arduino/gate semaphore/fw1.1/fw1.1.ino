/*
 Martin Pihrt a David Netušil ©2025
 FW: 1.1 11.12.2025
 Dva semafory + laserové brány + false-start logic
*/

// ============================================================================
// CONFIG
// ============================================================================
const int lightsA[] = {9, 10, 11};    // Semafor A (pwm pins)
const int piezoA     = 12;
const int beamA      = 22;

const int lightsB[] = {3, 5, 6};      // Semafor B (pwm pins)
const int piezoB     = 4;
const int beamB      = 24;

const int lightCount = 3; 

const int RS485_EN = 2;
const int button = 8;

// Fade maximálně 100 ms
int fadeInTime  = 100;
int fadeOutTime = 100;

int stepTime    = 800;    // pauza mezi světly
int holdTime    = 3000;   // po všech světlech

int beepShort   = 100;
int beepLong    = 1100;

// false-start varování
int warnDurationMs = 2000;     // 2 sekundy varování
int warnBeepOnMs   = 100;      // 100ms ON
int warnBeepOffMs  = 100;      // 100ms OFF
int warnStepMs     = 120;      // chase step per LED (ms)

// LOGIKA LASER BÁNE (konfigurovatelně)
bool laserActiveLow = true;   // true  -> LOW znamená přerušení paprsku
bool laserActiveHigh = false; // true  -> HIGH znamená přerušení paprsku
bool useInternalPullup = true; // true => pinMode(INPUT_PULLUP) pro brány

const int BAUD  = 9600;
//bool DEBUG = true;
bool DEBUG = false;

// ============================================================================
// GLOBALS
// ============================================================================
unsigned long now;
bool okSent = false; // zda byl poslán celkový "ok\n" (po dokončení obou semaforů)

// forward
void rs485Send(String msg);

// ============================================================================
// HELPER: beam check (konfigurovatelná logika)
// ============================================================================
bool isBeamBrokenRaw(int pin) {
  int v = digitalRead(pin);
  if (laserActiveLow)  return (v == LOW);
  if (laserActiveHigh) return (v == HIGH);
  return false;
}

// ============================================================================
// TRAFFIC LIGHT CLASS
// ============================================================================
struct TrafficLight {
  // pins
  const int* leds; // pointer to array of three leds
  int piezo;
  int beamPin;
  int id; // 0 or 1 for logging

  // state machine
  enum State { IDLE, FADE_IN, STEP_WAIT, HOLD, FADE_OUT, FALSE_START } state;
  unsigned long stateTimer;
  unsigned long fadeTimer;
  int fadeLevel;
  int currentLED;
  bool fadeBeepStarted;

  // beep (per-light)
  bool beepActive;
  unsigned long beepEnd;

  // false-start warning
  bool warnActive;
  unsigned long warnEnd;
  unsigned long warnTick;
  int warnPhase; // 0.. for chase index or beep toggling

  // completion marker (long tone started)
  bool completedLong;

  bool finishedForOk;   // nový flag pro OK (zelená NEBO chyba)

  // constructor-like init
  void init(const int* l, int p, int b, int _id) {
    leds = l; piezo = p; beamPin = b; id = _id;
    state = IDLE;
    stateTimer = fadeTimer = 0;
    fadeLevel = 0;
    currentLED = 0;
    fadeBeepStarted = false;
    beepActive = false;
    beepEnd = 0;
    warnActive = false;
    warnEnd = 0;
    warnTick = 0;
    warnPhase = 0;
    completedLong = false;
    finishedForOk = false;
  }

  void resetOutputs() {
    for (int i = 0; i < lightCount; i++) analogWrite(leds[i], 0);
    digitalWrite(piezo, LOW);
  }

  void start() {
    if (state != IDLE) return;
    state = FADE_IN;
    currentLED = 0;
    fadeLevel = 0;
    fadeTimer = now;
    fadeBeepStarted = false;
    completedLong = false;
    finishedForOk = false;
    if (DEBUG) {
      Serial.print(F("[TL] start semafor ")); Serial.println(id);
    }
  }

  void triggerFalseStart() {
    finishedForOk = true;   // false start = semafor hotový pro účely OK
    // přejít do warn režimu
    state = FALSE_START;
    warnActive = true;
    warnEnd = now + (unsigned long)warnDurationMs;
    warnTick = now;
    warnPhase = 0;
    beepActive = false;
    digitalWrite(piezo, LOW);
    // vypnout všechny LED, budou řízeny během warnu
    for (int i = 0; i < lightCount; i++) analogWrite(leds[i], 0);
    if (DEBUG) {
      Serial.print(F("[TL] FALSE START semafor ")); Serial.println(id);
    }
  }

  void startBeep(int duration) {
    digitalWrite(piezo, HIGH);
    beepActive = true;
    beepEnd = now + duration;
    if (DEBUG) {
      Serial.print(F("[TL] BEEP start id=")); Serial.print(id);
      Serial.print(F(" dur=")); Serial.println(duration);
    }
  }

  void stopBeep() {
    digitalWrite(piezo, LOW);
    beepActive = false;
  }

  // fade in single LED step (non-blocking)
  void fadeInStep() {
    int interval = max(1, fadeInTime / 255);
    if (now - fadeTimer >= interval) {
      fadeTimer = now;
      analogWrite(leds[currentLED], fadeLevel);
      fadeLevel++;
      if (fadeLevel > 255) fadeLevel = 255;
    }
  }

  bool fadeInDone() {
    return (fadeLevel >= 255);
  }

  // fade out all LEDs together
  void fadeOutAllStep() {
    int interval = max(1, fadeOutTime / 255);
    if (now - fadeTimer >= interval) {
      fadeTimer = now;
      fadeLevel--;
      if (fadeLevel < 0) fadeLevel = 0;
      for (int i = 0; i < lightCount; i++)
        analogWrite(leds[i], fadeLevel);
    }
  }

  bool fadeOutDone() {
    return (fadeLevel <= 0);
  }

  // update per-loop
  void update() {
    // handle beeper (short/long tones outside warn)
    if (beepActive && now >= beepEnd) {
      stopBeep();
      if (DEBUG) { Serial.print(F("[TL] beep ended id=")); Serial.println(id); }
    }

    // read beam only when needed: if semafor is running and not yet completedLong and not in false-start
    bool beamBroken = false;

    if (state != IDLE && state != FALSE_START) {
      if (!completedLong) {                     // před zelenou → false start
        if (isBeamBrokenRaw(beamPin)) {
            triggerFalseStart();
            return;
        }
      }
      // completedLong == true  → už se neřeší žádná chyba
    }
    
    switch (state) {
      case IDLE:
        // nothing
        break;

      case FADE_IN:
        if (!fadeBeepStarted) {
          // při posledním LED použijeme dlouhý tón
          if (currentLED == lightCount - 1) {
            startBeep(beepLong);
            // mark completedLong when long beep started
            completedLong = true;
            finishedForOk = true;   // počítá se jako hotový
            if (DEBUG) { Serial.print(F("[TL] long beep started id=")); Serial.println(id); }
          } else {
            startBeep(beepShort);
          }
          fadeBeepStarted = true;
          if (DEBUG) { Serial.print(F("[FSM] FADE_IN LED ")); Serial.print(currentLED); Serial.print(F(" id=")); Serial.println(id); }
        }
        fadeInStep();
        if (fadeInDone()) {
          state = STEP_WAIT;
          stateTimer = now;
          fadeLevel = 0;
          if (DEBUG) { Serial.print(F("[FSM] FADE_IN DONE id=")); Serial.println(id); }
        }
        break;

      case STEP_WAIT:
        if (now - stateTimer >= (unsigned long)stepTime) {
          currentLED++;
          if (currentLED >= lightCount) {
            state = HOLD;
            stateTimer = now;
            if (DEBUG) { Serial.print(F("[FSM] HOLD id=")); Serial.println(id); }
          } else {
            state = FADE_IN;
            fadeTimer = now;
            fadeBeepStarted = false;
            if (DEBUG) { Serial.print(F("[FSM] NEXT LED id=")); Serial.print(id); Serial.print(F(" LED=")); Serial.println(currentLED); }
          }
        }
        break;

      case HOLD:
        if (now - stateTimer >= (unsigned long)holdTime) {
          state = FADE_OUT;
          fadeLevel = 255;
          fadeTimer = now;
          if (DEBUG) { Serial.print(F("[FSM] FADE_OUT id=")); Serial.println(id); }
        }
        break;

      case FADE_OUT:
        fadeOutAllStep();
        if (fadeOutDone()) {
          state = IDLE;
          if (DEBUG) { Serial.print(F("[FSM] DONE id=")); Serial.println(id); }
          resetOutputs();
        }
        break;

      case FALSE_START:
        // warnActive: do chase + beep toggling for warnDurationMs
        if (warnActive) {
          // beep toggling: 100ms ON / 100ms OFF
          if (now - warnTick >= (unsigned long)(warnBeepOnMs + warnBeepOffMs)) {
            warnTick = now;
            // nothing else
          }
          // manage beep ON/OFF within the period
          unsigned long t = (now - (warnEnd - warnDurationMs)); // elapsed since warn start
          unsigned long cycle = warnBeepOnMs + warnBeepOffMs;
          if ((t % cycle) < (unsigned long)warnBeepOnMs) digitalWrite(piezo, HIGH);
          else digitalWrite(piezo, LOW);

          // chase LED effect: iterate LEDs quickly
          // compute step index by time
          unsigned long elapsed = warnEnd - now;
          // simpler: use elapsed from start
          unsigned long elapsedFromStart = (warnDurationMs - (warnEnd - now));
          int step = (elapsedFromStart / warnStepMs) % (lightCount + 1); // extra step = all off
          for (int i = 0; i < lightCount; i++) {
            if (step < lightCount) {
              // light only the step-th led
              analogWrite(leds[i], (i == step) ? 255 : 0);
            } else {
              // all off
              analogWrite(leds[i], 0);
            }
          }

          // end of warn
          if (now >= warnEnd) {
            warnActive = false;
            digitalWrite(piezo, LOW);
            for (int i = 0; i < lightCount; i++) analogWrite(leds[i], 0);
            state = IDLE;
            if (DEBUG) { Serial.print(F("[TL] FALSE START END id=")); Serial.println(id); }
          }
        } else {
          // shouldn't happen, but reset to IDLE
          digitalWrite(piezo, LOW);
          for (int i = 0; i < lightCount; i++) analogWrite(leds[i], 0);
          state = IDLE;
        }
        break;
    } // switch
  } // update()
}; // struct

// ============================================================================
// INSTANCES
// ============================================================================
TrafficLight tlA, tlB;

// ============================================================================
// RS485 SEND
// ============================================================================
void rs485Send(String msg) {
  if (DEBUG) { Serial.print(F("[RS485] TX -> ")); Serial.println(msg); }
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
String rx0 = "";
String rx1 = "";

void handleUART() {
  // UART0
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      rx0.trim();
      if (DEBUG) { Serial.print(F("[UART0] RX: ")); Serial.println(rx0); }
      if (rx0.equalsIgnoreCase("start")) {
        if (DEBUG) Serial.println(F("[FSM] START via UART0"));
        // start both semaphores
        tlA.start();
        tlB.start();
        okSent = false; // reset ok flag
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
        tlA.start();
        tlB.start();
        okSent = false;
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
  if (digitalRead(button) == LOW) {
    if (now - lastButton > debounce) {
      if (DEBUG) Serial.println(F("[BUTTON] Manual START"));
      tlA.start();
      tlB.start();
      okSent = false;
      lastButton = now;
    }
  }
}

// ============================================================================
// SETUP
// ============================================================================
void setup() {
  Serial.begin(BAUD);
  Serial1.begin(BAUD);

  pinMode(RS485_EN, OUTPUT);
  digitalWrite(RS485_EN, LOW);

  pinMode(piezoA, OUTPUT);
  pinMode(piezoB, OUTPUT);
  pinMode(button, INPUT_PULLUP);

  // beams
  if (useInternalPullup) {
    pinMode(beamA, INPUT_PULLUP);
    pinMode(beamB, INPUT_PULLUP);
  } else {
    pinMode(beamA, INPUT);
    pinMode(beamB, INPUT);
  }

  // leds set to 0
  for (int i = 0; i < lightCount; i++) {
    analogWrite(lightsA[i], 0);
    analogWrite(lightsB[i], 0);
  }

  // init traffic lights
  tlA.init(lightsA, piezoA, beamA, 0);
  tlB.init(lightsB, piezoB, beamB, 1);

  if (DEBUG) Serial.println(F("[BOOT] READY"));
}

// ============================================================================
// MAIN LOOP
// ============================================================================
void loop() {
  now = millis();

  handleUART();

  // update both semafory
  tlA.update();
  tlB.update();

  // handle button (start)
  handleSwitch();

  // send global OK once when both semaphores started their long beep (completedLong)
  if (!okSent && tlA.finishedForOk && tlB.finishedForOk){
    okSent = true;
    // send single OK over RS485 and USB
    rs485Send("ok\n");
    Serial.println(F("ok"));
    if (DEBUG) Serial.println(F("[GLOBAL] Sent OK for both semaphores"));
  }
}
