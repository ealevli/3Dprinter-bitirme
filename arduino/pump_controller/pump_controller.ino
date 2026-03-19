/**
 * pump_controller.ino
 * Arduino Uno — Syringe Pump Controller
 *
 * Controls a NEMA 17 stepper motor via A4988 driver to drive the syringe pump.
 *
 * Serial protocol (9600 baud, newline-terminated):
 *   Commands → Replies
 *   START    → OK
 *   STOP     → OK
 *   SPEED:N  → OK  (N = steps/sec, 1–1000)
 *   STATUS   → STATUS:running:N  or  STATUS:stopped:0
 *
 * Wiring:
 *   STEP  → Pin 3
 *   DIR   → Pin 4
 *   EN    → Pin 5  (LOW = enabled)
 */

// ── Pin definitions ────────────────────────────────────────────────────────
const int STEP_PIN  = 3;
const int DIR_PIN   = 4;
const int ENABLE_PIN = 5;

// ── State ─────────────────────────────────────────────────────────────────
bool  isRunning    = false;
int   stepsPerSec  = 150;          // default speed

// Timing
unsigned long lastStepMicros = 0;
unsigned long stepIntervalUs = 0;  // updated whenever stepsPerSec changes

// Serial input buffer
String inputBuffer = "";

// ── Helpers ───────────────────────────────────────────────────────────────
void updateInterval() {
  if (stepsPerSec > 0) {
    stepIntervalUs = 1000000UL / stepsPerSec;
  }
}

void enableMotor() {
  digitalWrite(ENABLE_PIN, LOW);   // A4988: LOW = enabled
}

void disableMotor() {
  digitalWrite(ENABLE_PIN, HIGH);
}

// ── Setup ─────────────────────────────────────────────────────────────────
void setup() {
  pinMode(STEP_PIN,   OUTPUT);
  pinMode(DIR_PIN,    OUTPUT);
  pinMode(ENABLE_PIN, OUTPUT);

  digitalWrite(DIR_PIN, HIGH);     // forward direction
  disableMotor();

  Serial.begin(9600);
  updateInterval();
}

// ── Command handler ───────────────────────────────────────────────────────
void handleCommand(String cmd) {
  cmd.trim();

  if (cmd == "START") {
    enableMotor();
    isRunning = true;
    Serial.println("OK");

  } else if (cmd == "STOP") {
    isRunning = false;
    disableMotor();
    Serial.println("OK");

  } else if (cmd.startsWith("SPEED:")) {
    int val = cmd.substring(6).toInt();
    if (val > 0 && val <= 1000) {
      stepsPerSec = val;
      updateInterval();
      Serial.println("OK");
    } else {
      Serial.println("ERROR:invalid speed (1-1000)");
    }

  } else if (cmd == "STATUS") {
    if (isRunning) {
      Serial.print("STATUS:running:");
    } else {
      Serial.print("STATUS:stopped:");
    }
    Serial.println(stepsPerSec);

  } else {
    Serial.println("ERROR:unknown command");
  }
}

// ── Main loop ─────────────────────────────────────────────────────────────
void loop() {
  // Read serial commands (non-blocking, newline-delimited).
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (inputBuffer.length() > 0) {
        handleCommand(inputBuffer);
        inputBuffer = "";
      }
    } else {
      inputBuffer += c;
    }
  }

  // Step the motor when running.
  if (isRunning && stepIntervalUs > 0) {
    unsigned long now = micros();
    if (now - lastStepMicros >= stepIntervalUs) {
      lastStepMicros = now;
      digitalWrite(STEP_PIN, HIGH);
      delayMicroseconds(2);          // A4988 minimum pulse width
      digitalWrite(STEP_PIN, LOW);
    }
  }
}
