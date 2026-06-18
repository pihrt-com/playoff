
/*
  Martin Pihrt
  18.06.2026
  7SEG Display Controller
  Arduino Nano + 7x 74HC595 display chain

  Commands:
    TXT:HELLO
    SCR:AHOJ SVETE
    RAW:7F,7F,7F,7F,7F,7F,7F
    SPD:250
    STAT
    CLS
    TEST
    PING
    VER
    ANI:SPIN
    ANI:BAR
    ANI:WAVE
    ANI:OFF
*/

#define latchPin 4
#define clockPin 3
#define dataPin  2
#define pwmPin   6

#define DISP_DIGITS 7

enum {
  MODE_TEXT,
  MODE_SCROLL,
  MODE_RAW,
  MODE_SPIN,
  MODE_BAR,
  MODE_WAVE
};

uint8_t mode = MODE_TEXT;
uint8_t disp[DISP_DIGITS];

char rxBuf[96];
uint8_t rxPos = 0;

char scrollText[80];
uint8_t scrollLen = 0;
uint8_t scrollPos = 0;

unsigned long animTimer = 0;
uint16_t scrollPeriod = 250;

uint8_t asciiToSeg(char c)
{
  switch(c)
  {
    case '0': return 125;
    case '1': return 12;
    case '2': return 91;
    case '3': return 31;
    case '4': return 46;
    case '5': return 55;
    case '6': return 119;
    case '7': return 28;
    case '8': return 127;
    case '9': return 63;

    case 'A': case 'a': return 126;
    case 'B': case 'b': return 103;
    case 'C': case 'c': return 113;
    case 'D': case 'd': return 79;
    case 'E': case 'e': return 115;
    case 'F': case 'f': return 114;
    case 'G': case 'g': return 125;
    case 'H': case 'h': return 110;
    case 'I': case 'i': return 96;
    case 'J': case 'j': return 77;
    case 'K': case 'k': return 110;
    case 'L': case 'l': return 97;
    case 'M': case 'm': return 124;
    case 'N': case 'n': return 124;
    case 'O': case 'o': return 125;
    case 'P': case 'p': return 122;
    case 'Q': case 'q': return 63;
    case 'R': case 'r': return 66;
    case 'S': case 's': return 55;
    case 'T': case 't': return 99;
    case 'U': case 'u': return 109;
    case 'V': case 'v': return 109;
    case 'W': case 'w': return 109;
    case 'X': case 'x': return 110;
    case 'Y': case 'y': return 47;
    case 'Z': case 'z': return 91;

    case '-': return 2;
    case '_': return 1;
    case '=': return 3;
    default: return 0;
  }
}

void refreshDisplay()
{
  digitalWrite(latchPin, LOW);
  for (uint8_t i=0;i<DISP_DIGITS;i++)
    shiftOut(dataPin, clockPin, MSBFIRST, disp[i]);
  digitalWrite(latchPin, HIGH);
}

void clearDisplay()
{
  memset(disp,0,sizeof(disp));
  refreshDisplay();
}

void displayText(const char *txt)
{
  memset(disp,0,sizeof(disp));
  uint8_t pos=0;

  while(*txt && pos<DISP_DIGITS)
  {
    char c=*txt++;

    if(c=='.')
    {
      if(pos>0) disp[DISP_DIGITS-pos] |= 128;
      continue;
    }

    disp[DISP_DIGITS-1-pos]=asciiToSeg(c);
    pos++;
  }

  refreshDisplay();
}

void startScroll(const char *txt)
{
  strncpy(scrollText,txt,sizeof(scrollText)-1);
  scrollText[sizeof(scrollText)-1]=0;
  scrollLen=strlen(scrollText);
  scrollPos=0;
  mode=MODE_SCROLL;
}

void updateScroll()
{
  char win[8];

  for(uint8_t i=0;i<7;i++)
  {
    uint8_t idx=scrollPos+i;

    if(idx<scrollLen)
      win[i]=scrollText[idx];
    else
      win[i]=' ';
  }

  win[7]=0;
  displayText(win);

  scrollPos++;
  if(scrollPos>scrollLen)
    scrollPos=0;
}

void parseRaw(char *txt)
{
  memset(disp,0,sizeof(disp));

  uint8_t idx=0;
  char *token=strtok(txt,",");

  while(token && idx<7)
  {
    while(*token==' ') token++;
    disp[idx]=(uint8_t)strtoul(token,NULL,16);
    idx++;
    token=strtok(NULL,",");
  }

  refreshDisplay();
}

void updateSpin()
{
  static uint8_t pos=0;
  const uint8_t spinTbl[6]={16,8,4,1,64,32};

  for(uint8_t i=0;i<7;i++)
    disp[i]=spinTbl[pos];

  pos=(pos+1)%6;
  refreshDisplay();
}

void updateBar()
{
  static uint8_t level=0;

  level++;

  if(level > 7)
    level = 1;

  for(uint8_t i=0;i<7;i++)
  {
    disp[i]=(i<level)?127:0;
  }

  refreshDisplay();
}

void updateWave()
{
  static uint8_t pos=0;

  memset(disp,0,sizeof(disp));
  disp[pos]=127;

  pos++;
  if(pos>=7) pos=0;

  refreshDisplay();
}

void processCommand(char *cmd)
{
    // odstraneni CR LF a mezer na konci
  int len = strlen(cmd);

  while(len > 0 &&
       (cmd[len-1] == '\r' ||
        cmd[len-1] == '\n' ||
        cmd[len-1] == ' '))
  {
      cmd[len-1] = 0;
      len--;
  }

  if(strcmp(cmd,"CLS")==0){ mode=MODE_TEXT; clearDisplay(); Serial.println(F("OK")); return; }
  if(strcmp(cmd,"TEST")==0){ for(int i=0;i<7;i++) disp[i]=127; refreshDisplay(); Serial.println(F("OK")); return; }
  if(strcmp(cmd,"PING")==0){ Serial.println(F("PONG")); return; }
  if(strcmp(cmd,"VER")==0){ Serial.println(F("FW 1.0")); return; }

  if(strcmp(cmd,"STAT")==0)
  {
    Serial.print("MODE=");
    switch(mode)
{
  case MODE_TEXT:   Serial.print(F("TEXT")); break;
  case MODE_SCROLL: Serial.print(F("SCROLL")); break;
  case MODE_RAW:    Serial.print(F("RAW")); break;
  case MODE_SPIN:   Serial.print(F("SPIN")); break;
  case MODE_BAR:    Serial.print(F("BAR")); break;
  case MODE_WAVE:   Serial.print(F("WAVE")); break;
}
    Serial.print(F(",SPD="));
    Serial.println(scrollPeriod);
    return;
  }

  if(strncmp(cmd,"SPD:",4)==0)
  {
    scrollPeriod=atoi(cmd+4);
    if(scrollPeriod<20) scrollPeriod=20;
    if(scrollPeriod>5000) scrollPeriod=5000;
    Serial.println(F("OK"));
    return;
  }

  if(strncmp(cmd,"TXT:",4)==0)
  {
    mode=MODE_TEXT;
    displayText(cmd+4);
    Serial.println(F("OK"));
    return;
  }

  if(strncmp(cmd,"SCR:",4)==0)
  {
    startScroll(cmd+4);
     Serial.println(F("OK"));
    return;
  }

  if(strncmp(cmd,"RAW:",4)==0)
  {
    mode=MODE_RAW;
    parseRaw(cmd+4);
     Serial.println(F("OK"));
    return;
  }

  if(strcmp(cmd,"ANI:SPIN")==0){ mode=MODE_SPIN;  Serial.println(F("OK")); return; }
  if(strcmp(cmd,"ANI:BAR")==0){ mode=MODE_BAR;  Serial.println(F("OK")); return; }
  if(strcmp(cmd,"ANI:WAVE")==0){ mode=MODE_WAVE;  Serial.println(F("OK")); return; }
  if(strcmp(cmd,"ANI:OFF")==0){ mode=MODE_TEXT; clearDisplay();  Serial.println(F("OK")); return; }

   Serial.println(F("ERR"));
}

void setup()
{
  Serial.begin(115200);

  pinMode(latchPin, OUTPUT);
  pinMode(clockPin, OUTPUT);
  pinMode(dataPin, OUTPUT);

  pinMode(pwmPin, OUTPUT);
  digitalWrite(pwmPin, LOW);

  clearDisplay();

  Serial.println(F("7SEG READY"));
  mode = 5;
}

void loop()
{
  while(Serial.available())
  {
    char c=Serial.read();

    if(c=='\r') continue;

    if(c=='\n')
    {
      rxBuf[rxPos]=0;

      if(rxPos)
        processCommand(rxBuf);

      rxPos=0;
    }
    else if(rxPos < sizeof(rxBuf)-1)
    {
      rxBuf[rxPos++]=c;
    }
  }

  if(millis()-animTimer >= scrollPeriod)
  {
    animTimer=millis();

    switch(mode)
    {
      case MODE_SCROLL: updateScroll(); break;
      case MODE_SPIN: updateSpin(); break;
      case MODE_BAR: updateBar(); break;
      case MODE_WAVE: updateWave(); break;
    }
  }
}
