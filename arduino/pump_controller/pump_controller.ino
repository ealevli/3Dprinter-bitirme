// Pin definitions
const int stepPin   = 3;
const int dirPin    = 4;
const int enablePin = 2;   // A4988 EN — active LOW (LOW = enabled)

bool isPumping    = false;
int  currentSpeed = 100;
bool dirForward   = true;
unsigned long stepDelay = 5000;

long primeTotal = 0;
long primeCount = 0;
bool isPriming  = false;

void calculateDelay(int speed) {
  if (speed <= 0) return;
  stepDelay = 1000000UL / ((unsigned long)speed * 2UL);
}

void setup() {
  pinMode(stepPin,   OUTPUT);
  pinMode(dirPin,    OUTPUT);
  pinMode(enablePin, OUTPUT);
  digitalWrite(enablePin, LOW);   // A4988 aktif et
  digitalWrite(dirPin, HIGH);
  digitalWrite(stepPin, LOW);
  Serial.begin(9600);
  calculateDelay(currentSpeed);
  Serial.println("READY");
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "START") {
      isPriming  = false;
      isPumping  = true;
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
      if (newSpeed > 0 && newSpeed <= 1000) {
        currentSpeed = newSpeed;
        calculateDelay(currentSpeed);
        Serial.println("OK");
      } else {
        Serial.println("ERROR:Invalid speed");
      }
    } else if (command.startsWith("DIR:")) {
      int d = command.substring(4).toInt();
      dirForward = (d != 0);
      digitalWrite(dirPin, dirForward ? HIGH : LOW);
      Serial.println("OK");
    } else if (command.startsWith("PRIME:")) {
      long steps = command.substring(6).toInt();
      if (steps > 0) {
        primeTotal  = steps;
        primeCount  = 0;
        isPriming   = true;
        isPumping   = false;
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
    }
  }

  if (isPumping) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(stepDelay);
    digitalWrite(stepPin, LOW);
    delayMicroseconds(stepDelay);
  }

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