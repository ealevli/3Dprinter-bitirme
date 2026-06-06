// ── Pump Controller Firmware ─────────────────────────────────────────────────
// Controls an A4988 stepper driver (NEMA 17) for the syringe pump.
//
// Serial protocol (9600 baud, newline-terminated):
//   Commands  → START | STOP | SPEED:<n> | DIR:<0/1> | PRIME:<steps> | STATUS
//   Responses ← OK   | ERROR:<msg> | STATUS:<state>:<speed>:<dir>
//
// Pin assignments (matching physical wiring):
//   D2 = A4988 ENABLE  (active LOW  → LOW  = motor enabled)
//   D3 = STEP
//   D4 = DIR

#include <avr/wdt.h>   // watchdog — lets us survive a hung loop

// ── Pin definitions ───────────────────────────────────────────────────────────
const int stepPin   = 3;
const int dirPin    = 4;
const int enablePin = 2;   // A4988 EN — LOW = enabled

// ── State ─────────────────────────────────────────────────────────────────────
bool          isPumping    = false;
int           currentSpeed = 200;          // default step/s (safe starting point)
bool          dirForward   = true;
unsigned long stepDelay    = 2500;         // µs per half-step

long primeTotal = 0;
long primeCount = 0;
bool isPriming  = false;

// ── Helpers ───────────────────────────────────────────────────────────────────
void calculateDelay(int speed) {
  if (speed <= 0) return;
  stepDelay = 1000000UL / ((unsigned long)speed * 2UL);
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  wdt_disable();   // disable watchdog first — avoids reset loops after upload

  pinMode(stepPin,   OUTPUT);
  pinMode(dirPin,    OUTPUT);
  pinMode(enablePin, OUTPUT);

  digitalWrite(enablePin, LOW);   // A4988 aktif (enabled)
  digitalWrite(dirPin, HIGH);
  digitalWrite(stepPin, LOW);

  Serial.begin(9600);
  Serial.setTimeout(500);         // readStringUntil waits max 0.5 s, not 1 s
                                  // → keeps motor smoother during commands
  calculateDelay(currentSpeed);
  Serial.println("READY");
}

// ── Main loop ─────────────────────────────────────────────────────────────────
void loop() {

  // ── Serial command handling ──────────────────────────────────────────────
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command.length() == 0) {
      // empty line — ignore silently
    }
    else if (command == "START") {
      isPriming = false;
      isPumping = true;
      digitalWrite(enablePin, LOW);
      Serial.println("OK");

    } else if (command == "STOP") {
      isPumping  = false;
      isPriming  = false;
      primeCount = 0;
      primeTotal = 0;
      Serial.println("OK");

    } else if (command.startsWith("SPEED:")) {
      int newSpeed = command.substring(6).toInt();
      if (newSpeed > 0 && newSpeed <= 5000) {
        currentSpeed = newSpeed;
        calculateDelay(currentSpeed);
        Serial.println("OK");
      } else {
        Serial.println("ERROR:Invalid speed (1-5000)");
      }

    } else if (command.startsWith("DIR:")) {
      int d = command.substring(4).toInt();
      dirForward = (d != 0);
      digitalWrite(dirPin, dirForward ? HIGH : LOW);
      Serial.println("OK");

    } else if (command.startsWith("PRIME:")) {
      long steps = command.substring(6).toInt();
      if (steps > 0) {
        primeTotal = steps;
        primeCount = 0;
        isPriming  = true;
        isPumping  = false;
        digitalWrite(enablePin, LOW);
        Serial.println("OK");
      } else {
        Serial.println("ERROR:Invalid steps");
      }

    } else if (command == "STATUS") {
      Serial.print("STATUS:");
      Serial.print((isPumping || isPriming) ? "running" : "stopped");
      Serial.print(":");
      Serial.print(currentSpeed);
      Serial.print(":");
      Serial.println(dirForward ? "fwd" : "rev");

    } else {
      // Unknown command — acknowledge so Python doesn't hang waiting
      Serial.print("ERROR:Unknown command: ");
      Serial.println(command);
    }
  }

  // ── Continuous pumping ───────────────────────────────────────────────────
  if (isPumping) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(stepDelay);
    digitalWrite(stepPin, LOW);
    delayMicroseconds(stepDelay);
  }

  // ── Prime (fixed number of steps) ────────────────────────────────────────
  if (isPriming) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(stepDelay);
    digitalWrite(stepPin, LOW);
    delayMicroseconds(stepDelay);
    primeCount++;
    if (primeCount >= primeTotal) {
      isPriming  = false;
      primeCount = 0;
      primeTotal = 0;
      Serial.println("PRIME_DONE");
    }
  }
}
