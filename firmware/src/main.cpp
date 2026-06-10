#include <Arduino.h>

// Correct Shrike Lite RP2040 Pins
const uint LED1_PWM_PIN = 4; // RP_IO4 (The actual onboard RP2040 LED)
const uint LED2_BLINK_PIN =
    5; // RP_IO5 (Stand-in header pin, since we can't use the FPGA LED)

uint8_t current_pwm_target = 0;
uint32_t blink_interval_ms = 500;
bool led2_state = false;
unsigned long last_blink_time = 0;

void setup() {
  Serial.begin(115200);

  pinMode(LED1_PWM_PIN, OUTPUT);
  pinMode(LED2_BLINK_PIN, OUTPUT);
  digitalWrite(LED2_BLINK_PIN, LOW);
}

void update_pwm(uint8_t brightness) {
  // Native Arduino function prevents timer collisions and keeps USB stable
  analogWrite(LED1_PWM_PIN, brightness);
}

void process_serial() {
  static uint8_t buffer[3];
  static int index = 0;

  while (Serial.available() > 0) {
    int c = Serial.read();
    if (c != -1) {
      buffer[index++] = (uint8_t)c;

      if (index == 3) {
        // The Goodbye Routine
        if (buffer[0] == 0x00 && buffer[1] == 0x00 && buffer[2] == 0x00) {
          current_pwm_target = 0;
          blink_interval_ms = 0;
          update_pwm(0);
          digitalWrite(LED2_BLINK_PIN, LOW);
        } else {
          current_pwm_target = buffer[0];     // Byte 0: Brightness
          blink_interval_ms = buffer[1] * 10; // Byte 1: Blink Rate
          update_pwm(current_pwm_target);
        }
        index = 0;
      }
    }
  }
}

void loop() {
  process_serial();

  // Non-blocking Timer check for LED 2
  if (blink_interval_ms > 0) {
    unsigned long current_time = millis();
    if (current_time - last_blink_time >= blink_interval_ms) {
      led2_state = !led2_state;
      digitalWrite(LED2_BLINK_PIN, led2_state ? HIGH : LOW);
      last_blink_time = current_time;
    }
  } else {
    digitalWrite(LED2_BLINK_PIN, LOW);
  }
}