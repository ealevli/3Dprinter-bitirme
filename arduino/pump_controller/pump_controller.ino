const int stepPin = 3;
const int dirPin  = 4;

bool isPumping    = false;
int  currentSpeed = 150;        // adım/s
bool dirForward   = true;       // true=ileri(kaplama), false=geri(geri çekme)
unsigned long stepDelay = 3333; // mikrosaniye (1_000_000 / (speed * 2))

// prime modunda atılacak adım sayısı ve sayaç
long primeTotal   = 0;
long primeCount   = 0;
bool isPriming    = false;

void calculateDelay(int speed) {
  if (speed <= 0) return;
  stepDelay = 1000000UL / ((unsigned long)speed * 2);
}

void setup() {
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin,  OUTPUT);
  digitalWrite(dirPin, HIGH);   // varsayılan: ileri
  Serial.begin(9600);
  calculateDelay(currentSpeed);
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "START") {
      isPriming  = false;
      isPumping  = true;
      Serial.println("OK");

    } else if (command == "STOP") {
      isPumping  = false;
      isPriming  = false;
      primeCount = 0;
      primeTotal = 0;
      Serial.println("OK");

    } else if (command.startsWith("SPEED:")) {
      int newSpeed = command.substring(6).toInt();
      if (newSpeed > 0) {
        currentSpeed = newSpeed;
        calculateDelay(currentSpeed);
        Serial.println("OK");
      } else {
        Serial.println("ERROR:Invalid speed");
      }

    } else if (command.startsWith("DIR:")) {
      // DIR:1 = ileri (kaplama), DIR:0 = geri (geri çekme / prime)
      int d = command.substring(4).toInt();
      dirForward = (d != 0);
      digitalWrite(dirPin, dirForward ? HIGH : LOW);
      Serial.println("OK");

    } else if (command.startsWith("PRIME:")) {
      // PRIME:500 → 500 adım ilerlet sonra dur
      long steps = command.substring(6).toInt();
      if (steps > 0) {
        primeTotal  = steps;
        primeCount  = 0;
        isPriming   = true;
        isPumping   = false;
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

  // Normal sürekli pompalama
  if (isPumping) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(stepDelay);
    digitalWrite(stepPin, LOW);
    delayMicroseconds(stepDelay);
  }

  // Prime modu: belirli adım sayısı
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
