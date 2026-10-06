#include <SoftwareSerial.h>

// Bluetooth module (HC-05 style) on software serial: RX = 11, TX = 12
SoftwareSerial Aisha(11, 12);

const int ledpin = 13;   // LED on D13
const int hall_1 = 9;    // hall sensor 1
const int hall_2 = 10;   // hall sensor 2

int BluetoothData = 0;   // data received over Bluetooth
int HallState_1, HallState_2;
int Phs1, Phs2;

void setup() {
  Aisha.begin(9600);          // Bluetooth module runs at 9600 baud
  pinMode(ledpin, OUTPUT);
  pinMode(hall_1, INPUT);
  pinMode(hall_2, INPUT);
}

void loop() {
  if (Aisha.available()) {
    BluetoothData = Aisha.read();
  }

  Phs1 = HallState_1;
  Phs2 = HallState_2;
  HallState_1 = digitalRead(hall_1);
  HallState_2 = digitalRead(hall_2);

  // Send the new key combination whenever either hall sensor changes
  if (Phs1 != HallState_1 || Phs2 != HallState_2) {
    if (HallState_1 == LOW && HallState_2 == LOW)  Aisha.write(1);
    if (HallState_1 == HIGH && HallState_2 == LOW) Aisha.write(2);
    if (HallState_1 == LOW && HallState_2 == HIGH) Aisha.write(3);
    if (HallState_1 == HIGH && HallState_2 == HIGH) Aisha.write(4);
  }

  // 'y' / 'n' sent from the desktop app toggles the LED
  if (BluetoothData == 'y') digitalWrite(ledpin, HIGH);
  if (BluetoothData == 'n') digitalWrite(ledpin, LOW);
}
