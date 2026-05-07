/*
 Martin Pihrt
 FW: 1.3 07.05.2026
 Dva semafory + laserové brány + false-start logic
 Přidaná podpora pro počítadla kol v app
 Odesílání:
   finish_a
   finish_b

PYTHON ---> start ----> ARDUINO
ARDUINO ---> ok ------------> PYTHON
ARDUINO ---> finish_a ------> PYTHON
ARDUINO ---> finish_b ------> PYTHON
ARDUINO ---> race_finished -> PYTHON   
*/

// ============================================================================
// CONFIG
// ============================================================================
const int lightsA[] = {9, 10, 11};
const int piezoA     = 12;
const int beamA      = 22;

const int lightsB[] = {3, 5, 6};
const int piezoB     = 4;
const int beamB      = 24;

const int lightCount = 3;

const int RS485_EN = 2;
const int button = 8;

int fadeInTime  = 100;
int fadeOutTime = 100;

int stepTime    = 800;
int holdTime    = 3000;

int beepShort   = 100;
int beepLong    = 1100;

int warnDurationMs = 2000;
int warnBeepOnMs   = 100;
int warnBeepOffMs  = 100;
int warnStepMs     = 120;

bool laserActiveLow = true;
bool laserActiveHigh = false;
bool useInternalPullup = true;

const int BAUD  = 9600;

bool DEBUG = false;

// ============================================================================
// GLOBALS
// ============================================================================
unsigned long now;

bool okSent = false;

// závod aktivní
bool raceRunning = false;

// finish flags
bool finishASent = false;
bool finishBSent = false;

// debounce finish bran
unsigned long lastFinishA = 0;
unsigned long lastFinishB = 0;

const unsigned long finishDebounce = 150;

// forward
void rs485Send(String msg);

// ============================================================================
// HELPER
// ============================================================================
bool isBeamBrokenRaw(int pin) {
  int v = digitalRead(pin);

  if (laserActiveLow)  return (v == LOW);
  if (laserActiveHigh) return (v == HIGH);

  return false;
}

// ============================================================================
// FINISH DETECTION
// ============================================================================
void handleFinishA() {

  if (!raceRunning) return;
  if (finishASent) return;

  if (isBeamBrokenRaw(beamA)) {

    if (now - lastFinishA < finishDebounce) return;

    lastFinishA = now;

    finishASent = true;

    Serial.println(F("finish_a"));
    rs485Send("finish_a\n");

    if (DEBUG) {
      Serial.println(F("[RACE] FINISH A"));
    }
  }
}

void handleFinishB() {

  if (!raceRunning) return;
  if (finishBSent) return;

  if (isBeamBrokenRaw(beamB)) {

    if (now - lastFinishB < finishDebounce) return;

    lastFinishB = now;

    finishBSent = true;

    Serial.println(F("finish_b"));
    rs485Send("finish_b\n");

    if (DEBUG) {
      Serial.println(F("[RACE] FINISH B"));
    }
  }
}

void handleRaceFinished() {

  if (!raceRunning) return;

  if (finishASent && finishBSent) {

    raceRunning = false;

    Serial.println(F("race_finished"));
    rs485Send("race_finished\n");

    if (DEBUG) {
      Serial.println(F("[RACE] FINISHED"));
    }
  }
}

// ============================================================================
// TRAFFIC LIGHT CLASS
// ============================================================================
struct TrafficLight {

  const int* leds;
  int piezo;
  int beamPin;
  int id;

  enum State {
    IDLE,
    FADE_IN,
    STEP_WAIT,
    HOLD,
    FADE_OUT,
    FALSE_START
  } state;

  unsigned long stateTimer;
  unsigned long fadeTimer;

  int fadeLevel;
  int currentLED;

  bool fadeBeepStarted;

  bool beepActive;
  unsigned long beepEnd;

  bool warnActive;
  unsigned long warnEnd;
  unsigned long warnTick;
  int warnPhase;

  bool completedLong;

  bool finishedForOk;

  void init(const int* l, int p, int b, int _id) {

    leds = l;
    piezo = p;
    beamPin = b;
    id = _id;

    state = IDLE;

    stateTimer = 0;
    fadeTimer = 0;

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

    for (int i = 0; i < lightCount; i++) {
      analogWrite(leds[i], 0);
    }

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
      Serial.print(F("[TL] start semafor "));
      Serial.println(id);
    }
  }

  void triggerFalseStart() {

    finishedForOk = true;

    state = FALSE_START;

    warnActive = true;

    warnEnd = now + (unsigned long)warnDurationMs;

    warnTick = now;

    warnPhase = 0;

    beepActive = false;

    digitalWrite(piezo, LOW);

    for (int i = 0; i < lightCount; i++) {
      analogWrite(leds[i], 0);
    }

    if (DEBUG) {
      Serial.print(F("[TL] FALSE START semafor "));
      Serial.println(id);
    }
  }

  void startBeep(int duration) {

    digitalWrite(piezo, HIGH);

    beepActive = true;

    beepEnd = now + duration;
  }

  void stopBeep() {

    digitalWrite(piezo, LOW);

    beepActive = false;
  }

  void fadeInStep() {

    int interval = max(1, fadeInTime / 255);

    if (now - fadeTimer >= interval) {

      fadeTimer = now;

      analogWrite(leds[currentLED], fadeLevel);

      fadeLevel++;

      if (fadeLevel > 255) {
        fadeLevel = 255;
      }
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

      if (fadeLevel < 0) {
        fadeLevel = 0;
      }

      for (int i = 0; i < lightCount; i++) {
        analogWrite(leds[i], fadeLevel);
      }
    }
  }

  bool fadeOutDone() {
    return (fadeLevel <= 0);
  }

  void update() {

    if (beepActive && now >= beepEnd) {
      stopBeep();
    }

    if (state != IDLE && state != FALSE_START) {

      if (!completedLong) {

        if (isBeamBrokenRaw(beamPin)) {

          triggerFalseStart();

          return;
        }
      }
    }

    switch (state) {

      case IDLE:
        break;

      case FADE_IN:

        if (!fadeBeepStarted) {

          if (currentLED == lightCount - 1) {

            startBeep(beepLong);

            completedLong = true;

            finishedForOk = true;

          } else {

            startBeep(beepShort);
          }

          fadeBeepStarted = true;
        }

        fadeInStep();

        if (fadeInDone()) {

          state = STEP_WAIT;

          stateTimer = now;

          fadeLevel = 0;
        }

        break;

      case STEP_WAIT:

        if (now - stateTimer >= (unsigned long)stepTime) {

          currentLED++;

          if (currentLED >= lightCount) {

            state = HOLD;

            stateTimer = now;

          } else {

            state = FADE_IN;

            fadeTimer = now;

            fadeBeepStarted = false;
          }
        }

        break;

      case HOLD:

        if (now - stateTimer >= (unsigned long)holdTime) {

          state = FADE_OUT;

          fadeLevel = 255;

          fadeTimer = now;
        }

        break;

      case FADE_OUT:

        fadeOutAllStep();

        if (fadeOutDone()) {

          state = IDLE;

          resetOutputs();
        }

        break;

      case FALSE_START:

        if (warnActive) {

          unsigned long t = (now - (warnEnd - warnDurationMs));

          unsigned long cycle = warnBeepOnMs + warnBeepOffMs;

          if ((t % cycle) < (unsigned long)warnBeepOnMs) {
            digitalWrite(piezo, HIGH);
          } else {
            digitalWrite(piezo, LOW);
          }

          unsigned long elapsedFromStart =
            (warnDurationMs - (warnEnd - now));

          int step =
            (elapsedFromStart / warnStepMs) % (lightCount + 1);

          for (int i = 0; i < lightCount; i++) {

            if (step < lightCount) {
              analogWrite(leds[i], (i == step) ? 255 : 0);
            } else {
              analogWrite(leds[i], 0);
            }
          }

          if (now >= warnEnd) {

            warnActive = false;

            digitalWrite(piezo, LOW);

            for (int i = 0; i < lightCount; i++) {
              analogWrite(leds[i], 0);
            }

            state = IDLE;
          }

        } else {

          digitalWrite(piezo, LOW);

          for (int i = 0; i < lightCount; i++) {
            analogWrite(leds[i], 0);
          }

          state = IDLE;
        }

        break;
    }
  }
};

// ============================================================================
// INSTANCES
// ============================================================================
TrafficLight tlA;
TrafficLight tlB;

// ============================================================================
// RS485
// ============================================================================
void rs485Send(String msg) {

  digitalWrite(RS485_EN, HIGH);

  delayMicroseconds(40);

  Serial1.print(msg);

  Serial1.flush();

  delayMicroseconds(40);

  digitalWrite(RS485_EN, LOW);
}

// ============================================================================
// UART
// ============================================================================
String rx0 = "";
String rx1 = "";

void startRace() {

  tlA.start();
  tlB.start();

  okSent = false;

  raceRunning = false;

  finishASent = false;
  finishBSent = false;

  lastFinishA = 0;
  lastFinishB = 0;

  if (DEBUG) {
    Serial.println(F("[RACE] START"));
  }
}

void handleUART() {

  while (Serial.available()) {

    char c = Serial.read();

    if (c == '\n') {

      rx0.trim();

      if (rx0.equalsIgnoreCase("start")) {

        startRace();
      }

      rx0 = "";

    } else {

      rx0 += c;
    }
  }

  while (Serial1.available()) {

    char c = Serial1.read();

    if (c == '\n') {

      rx1.trim();

      if (rx1.equalsIgnoreCase("start")) {

        startRace();
      }

      rx1 = "";

    } else {

      rx1 += c;
    }
  }
}

// ============================================================================
// BUTTON
// ============================================================================
unsigned long lastButton = 0;

const int debounce = 50;

void handleSwitch() {

  if (digitalRead(button) == LOW) {

    if (now - lastButton > debounce) {

      startRace();

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

  if (useInternalPullup) {

    pinMode(beamA, INPUT_PULLUP);
    pinMode(beamB, INPUT_PULLUP);

  } else {

    pinMode(beamA, INPUT);
    pinMode(beamB, INPUT);
  }

  for (int i = 0; i < lightCount; i++) {

    analogWrite(lightsA[i], 0);
    analogWrite(lightsB[i], 0);
  }

  tlA.init(lightsA, piezoA, beamA, 0);
  tlB.init(lightsB, piezoB, beamB, 1);

  if (DEBUG) {
    Serial.println(F("[BOOT] READY"));
  }
}

// ============================================================================
// LOOP
// ============================================================================
void loop() {

  now = millis();

  handleUART();

  tlA.update();
  tlB.update();

  handleSwitch();

  // OK po zelené
  if (!okSent && tlA.finishedForOk && tlB.finishedForOk) {

    okSent = true;

    raceRunning = true;

    rs485Send("ok\n");

    Serial.println(F("ok"));

    if (DEBUG) {
      Serial.println(F("[GLOBAL] OK"));
    }
  }

  // finish detekce
  handleFinishA();
  handleFinishB();

  // konec závodu
  handleRaceFinished();
}