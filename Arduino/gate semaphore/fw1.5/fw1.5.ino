#include <Adafruit_NeoPixel.h>

/*
 Martin Pihrt
 FW: 1.5 23.06.2026
 Dva semafory + laserové brány + false-start logic
 Přidaná podpora pro počítadla kol v app
 Odesílání:
   finish_a
   finish_b

 přidaný 2x výstup pro WS28B12 pásek (2x8 LED jako semafor R,R,G)
 přidaný výstup piezo sum (piezo A+B)
 přidaný rezim playoff/laps pro odesilani dat (prujezdu kol) do pythonu

prepnuti rezimu playoff/laps
PYTHON ---> mode_playoff ----> ARDUINO
PYTHON ---> mode_laps ----> ARDUINO

komunikace playoff
PYTHON ---> start ----> ARDUINO
ARDUINO ---> ok ------------> PYTHON
ARDUINO ---> finish_a ------> PYTHON
ARDUINO ---> finish_b ------> PYTHON
ARDUINO ---> race_finished -> PYTHON   
-----------------

START
↓
běží semafor

1. přerušení během odpočtu
↓
FALSE START

OK
↓
závod běží

1. přerušení
↓
auto vyjelo ze startu
↓
ignorovat

2. přerušení
↓
auto projelo cílem
↓
finish_a
-----------------

piezo sum:
Semafor A pípá
→ piezoA
→ piezoSUM

Semafor B pípá
→ piezoB
→ piezoSUM

Pípají oba
→ piezoA
→ piezoB
→ piezoSUM

Jeden skončí
→ piezoSUM stále hraje

Skončí oba
→ piezoSUM ztichne
*/

// ============================================================================
// CONFIG
// ============================================================================
const int lightsA[]  = {9, 10, 11};
const int piezoA     = 12;
const int beamA      = 22;

const int lightsB[]  = {3, 5, 6};
const int piezoB     = 4;
const int beamB      = 24;

const int piezoSUM   = 26; // piezo sum A+B (only one piezo)

const int lightCount = 3;

const int RS485_EN   = 2;
const int button     = 8;

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

bool laserActiveLow = false;
bool laserActiveHigh = true;
bool useInternalPullup = true;

const long BAUD  = 115200;

bool DEBUG = false; //true;

// ============================================================================
// RGB LED WS28B12 2x (2x8 RGB LED)
// ============================================================================
#define WS_PIN_A 25
#define WS_PIN_B 23

#define WS_COUNT 16

Adafruit_NeoPixel wsA(
    WS_COUNT,
    WS_PIN_A,
    NEO_GRB + NEO_KHZ800
);

Adafruit_NeoPixel wsB(
    WS_COUNT,
    WS_PIN_B,
    NEO_GRB + NEO_KHZ800
);

// ============================================================================
// GLOBALS
// ============================================================================
unsigned long now;
bool okSent = false;
// race running flag
bool raceRunning = false;
// finish flags
bool finishASent = false;
bool finishBSent = false;
// debounce finish gate
unsigned long lastFinishA = 0;
unsigned long lastFinishB = 0;
const unsigned long finishDebounce = 3500;
// counter for beam interrupt
byte beamCountA = 0;
byte beamCountB = 0;
bool falseStartA = false;
bool falseStartB = false;
bool sumBeepA = false;
bool sumBeepB = false;
bool lastButtonState = HIGH;
bool lapRunningA = false;
bool lapRunningB = false;
bool lastBeamStateA = false;
bool lastBeamStateB = false;

void rs485Send(String msg);

enum RunMode
{
  MODE_PLAYOFF,
  MODE_LAPS
};

RunMode runMode = MODE_PLAYOFF;

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
  if (!isBeamBrokenRaw(beamA)) return;
  if (now - lastFinishA < finishDebounce) return;
  lastFinishA = now;
  beamCountA++;
  if (DEBUG) {
    Serial.print(F("[A] beam count = "));
    Serial.println(beamCountA);
  }
  byte requiredCount = falseStartA ? 3 : 2;
  if (beamCountA < requiredCount)
    return;
  finishASent = true;
  Serial.println(F("finish_a"));
  rs485Send("finish_a\n");
  falseStartA = false;
}

void handleFinishB() {
  if (!raceRunning) return;
  if (finishBSent) return;
  if (!isBeamBrokenRaw(beamB)) return;
  if (now - lastFinishB < finishDebounce) return;
  lastFinishB = now;
  beamCountB++;
  if (DEBUG) {
    Serial.print(F("[B] beam count = "));
    Serial.println(beamCountB);
  }
  byte requiredCount = falseStartB ? 3 : 2;
  if (beamCountB < requiredCount)
    return;
  finishBSent = true;
  Serial.println(F("finish_b"));
  rs485Send("finish_b\n");
  falseStartB = false;
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

  Adafruit_NeoPixel* strip;
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

  void showLapIdle(){
    analogWrite(leds[0], 0);
    analogWrite(leds[1], 0);
    analogWrite(leds[2], 255);
    for (int i = 0; i < 16; i++)
        strip->setPixelColor(i, strip->Color(0,255,0));
    strip->show();
  }

  void showLapRunning(){
    analogWrite(leds[0], 255);
    analogWrite(leds[1], 255);
    analogWrite(leds[2], 0);
    for (int i = 0; i < 16; i++)
        strip->setPixelColor(i, strip->Color(255,120,0));
    strip->show();
  }

  void updateSumPiezo(){
    digitalWrite(piezoSUM,(sumBeepA || sumBeepB) ? HIGH : LOW);
  }

  void init(const int* l, int p, int b, int _id, Adafruit_NeoPixel* ws){
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
    strip = ws;
  }

  void resetOutputs() {
    for (int i = 0; i < lightCount; i++) {
      analogWrite(leds[i], 0);
    }
    digitalWrite(piezo, LOW);
    wsOff();
    if (id == 0)
      sumBeepA = false;
    else
      sumBeepB = false;
    updateSumPiezo();
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
    if (id == 0)
      sumBeepA = false;
    else
      sumBeepB = false;
    updateSumPiezo();
    for (int i = 0; i < lightCount; i++) {
      analogWrite(leds[i], 0);
    }
    wsOff();
    if (DEBUG) {
      Serial.print(F("[TL] FALSE START semafor "));
      Serial.println(id);
    }
    if (id == 0) falseStartA = true;
    if (id == 1) falseStartB = true;
  }

  void startBeep(int duration) {
    digitalWrite(piezo, HIGH);
    beepActive = true;
    beepEnd = now + duration;
    if (id == 0)
      sumBeepA = true;
    else
      sumBeepB = true;
    updateSumPiezo();
  }

  void stopBeep() {
    digitalWrite(piezo, LOW);
    beepActive = false;
    if (id == 0)
      sumBeepA = false;
    else
      sumBeepB = false;
    updateSumPiezo();
  }

  void fadeInStep() {
    int interval = max(1, fadeInTime / 255);
    if (now - fadeTimer >= interval) {
      fadeTimer = now;
      analogWrite(leds[currentLED], fadeLevel);
      if (currentLED < 2)
      {
        setWsBrightness(255, 0, fadeLevel);
      }
      else
      {
        setWsBrightness(0, 255, fadeLevel);
      }
      fadeLevel++;
      if (fadeLevel > 255)
        fadeLevel = 255;
    }
  }

  bool fadeInDone() {
    return (fadeLevel == 255);
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
      if (currentLED >= 2)
        {
          setWsBrightness(0, 255, fadeLevel);
        }
        else
        {
          setWsBrightness(255, 0, fadeLevel);
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
          bool warnBeep = ((t % cycle) < (unsigned long)warnBeepOnMs);
          digitalWrite(piezo, warnBeep);
          if (id == 0)
            sumBeepA = warnBeep;
          else
            sumBeepB = warnBeep;
          updateSumPiezo();
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

          // WS2812 false start animace
          if (step == 0)
          {
            // první červená
            for (int i = 0; i < 8; i++)
              strip->setPixelColor(i, strip->Color(255, 0, 0));
            for (int i = 8; i < 16; i++)
              strip->setPixelColor(i, 0);
          }
          else if (step == 1)
          {
            // druhá červená
            for (int i = 0; i < 16; i++)
              strip->setPixelColor(i, strip->Color(255, 0, 0));
          }
          else if (step == 2)
          {
            // zelená
            for (int i = 0; i < 16; i++)
              strip->setPixelColor(i, strip->Color(0, 255, 0));
          }
          else
          {
            strip->clear();
          }
          strip->show();

          if (now >= warnEnd) {
            warnActive = false;
            digitalWrite(piezo, LOW);
            if (id == 0)
              sumBeepA = false;
            else
              sumBeepB = false;
            updateSumPiezo();
            for (int i = 0; i < lightCount; i++) {
              analogWrite(leds[i], 0);
            }
            wsOff();
            state = IDLE;
          }
        } else {
          digitalWrite(piezo, LOW);
          if (id == 0)
            sumBeepA = false;
          else
            sumBeepB = false;
          updateSumPiezo();
          for (int i = 0; i < lightCount; i++) {
            analogWrite(leds[i], 0);
          }
          wsOff();
          state = IDLE;
        }
        break;
    }
  }

  void setWsBrightness(uint8_t red, uint8_t green, uint8_t level)
  {
    uint32_t color =  strip->Color((red   * level) / 255, (green * level) / 255, 0);
    if (currentLED == 0)
    {
      // RED1 = LED 0-7
      for (int i = 0; i < 8; i++)
          strip->setPixelColor(i, color);
      for (int i = 8; i < 16; i++)
          strip->setPixelColor(i, 0);
    }
    else if (currentLED == 1)
    {
      // RED1 + RED2
      for (int i = 0; i < 16; i++)
        strip->setPixelColor(i, color);
    }
    else
    {
      // GREEN
      uint32_t greenColor = strip->Color(0, level, 0);
      for (int i = 0; i < 16; i++)
        strip->setPixelColor(i, greenColor);
    }
    strip->show();
  }

  void wsOff()
  {
    strip->clear();
    strip->show();
  }
};

// ============================================================================
// INSTANCES
// ============================================================================
TrafficLight tlA;
TrafficLight tlB;

void handleLapsA(){
  if (runMode != MODE_LAPS)
    return;
  bool beamNow = isBeamBrokenRaw(beamA);
  if (beamNow && !lastBeamStateA){
    if (now - lastFinishA >= finishDebounce) {
      lastFinishA = now;
      if (!lapRunningA) {
        lapRunningA = true;
        tlA.showLapRunning();
        Serial.println(F("start_a"));
        rs485Send("start_a\n");
      }
      else
      {
        lapRunningA = false;
        tlA.showLapIdle();
        Serial.println(F("stop_a"));
        rs485Send("stop_a\n");
      }
    }
  }
  lastBeamStateA = beamNow;
}

void handleLapsB(){
  if (runMode != MODE_LAPS)
    return;
  bool beamNow = isBeamBrokenRaw(beamB);
  if (beamNow && !lastBeamStateB){
    if (now - lastFinishB >= finishDebounce) {
      lastFinishB = now;
      if (!lapRunningB) {
        lapRunningB = true;
        tlB.showLapRunning();
        Serial.println(F("start_b"));
        rs485Send("start_b\n");
      }
      else
      {
        lapRunningB = false;
        tlB.showLapIdle();
        Serial.println(F("stop_b"));
        rs485Send("stop_b\n");
      }
    }
  }
  lastBeamStateB = beamNow;
}

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
  tlA.resetOutputs();
  tlB.resetOutputs();
  tlA.start();
  tlB.start();
  okSent = false;
  raceRunning = false;
  finishASent = false;
  finishBSent = false;
  lastFinishA = 0;
  lastFinishB = 0;
  beamCountA = 0;
  beamCountB = 0;
  falseStartA = false;
  falseStartB = false;
  if (DEBUG) {
    Serial.println(F("[RACE] START"));
  }
}

void handleUART() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      rx0.trim();
      if (rx0.equalsIgnoreCase("start"))
      {
        startRace();
      }
      else if (rx0.equalsIgnoreCase("mode_playoff"))
      {
        runMode = MODE_PLAYOFF;
      }
      else if (rx0.equalsIgnoreCase("mode_laps"))
      {
        runMode = MODE_LAPS;
        lapRunningA = false;
        lapRunningB = false;
        lastFinishA = 0;
        lastFinishB = 0;
        tlA.showLapIdle();
        tlB.showLapIdle();
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
      if (rx1.equalsIgnoreCase("start"))
      {
        startRace();
      }
      else if (rx1.equalsIgnoreCase("mode_playoff"))
      {
        runMode = MODE_PLAYOFF;
      }
      else if (rx1.equalsIgnoreCase("mode_laps"))
      {
        runMode = MODE_LAPS;
        lapRunningA = false;
        lapRunningB = false;
        lastFinishA = 0;
        lastFinishB = 0; 
        tlA.showLapIdle();
        tlB.showLapIdle();       
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

void handleSwitch(){
  if (runMode != MODE_PLAYOFF)
    return;
    
  bool currentState = digitalRead(button);
  // reakce pouze na přechod HIGH -> LOW
  if (lastButtonState == HIGH && currentState == LOW)
  {
    if (now - lastButton > debounce)
    {
      startRace();
      lastButton = now;
    }
  }
  lastButtonState = currentState;
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
  pinMode(piezoSUM, OUTPUT);
  digitalWrite(piezoSUM, LOW);
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
  tlA.init(lightsA, piezoA, beamA, 0, &wsA);
  tlB.init(lightsB, piezoB, beamB, 1, &wsB);

  wsA.begin();
  wsB.begin();
  wsA.clear();
  wsB.clear();
  wsA.show();
  wsB.show();

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
  if (runMode == MODE_PLAYOFF)  {
    handleFinishA();
    handleFinishB();
    handleRaceFinished();
  }
  else {
    handleLapsA();
    handleLapsB();
  }
}//end loop
