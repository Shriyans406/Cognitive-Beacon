#include "hardware/pwm.h"
#include <Arduino.h>


// Shrike Lite User LED pins
const uint LED1_PWM_PIN = 14;
const uint LED2_BLINK_PIN = 15;

uint8_t current_pwm_target = 0;
uint32_t blink_interval_ms = 500;
bool led2_state = false;

// Non-blocking timing tracking variables
unsigned long last_blink_time = 0;

void setup_hardware() {
  // Initialize USB Serial communication
  Serial.begin(115200);

  // Setup LED 1 for Hardware PWM
  gpio_set_function(LED1_PWM_PIN, GPIO_FUNC_PWM);
  uint slice_num = pwm_gpio_to_slice_num(LED1_PWM_PIN);
  pwm_set_wrap(slice_num, 255);
  pwm_set_chan_level(slice_num, pwm_gpio_to_channel(LED1_PWM_PIN), 0);
  pwm_set_enabled(slice_num, true);

  // Setup LED 2 as a standard digital output
  pinMode(LED2_BLINK_PIN, OUTPUT);
  digitalWrite(LED2_BLINK_PIN, LOW);
}

void update_pwm(uint8_t brightness) {
  uint slice_num = pwm_gpio_to_slice_num(LED1_PWM_PIN);
  pwm_set_chan_level(slice_num, pwm_gpio_to_channel(LED1_PWM_PIN), brightness);
}

void process_serial() {
  static uint8_t buffer[3];
  static int index = 0;

  // Check if bytes are waiting in the serial buffer
  while (Serial.available() > 0) {
    int c = Serial.read();
    if (c != -1) {
      buffer[index++] = (uint8_t)c;

      // Once we receive our strict 3-byte contract packet
      if (index == 3) {
        // Check for "Goodbye Routine" payload [0x00, 0x00, 0x00]
        if (buffer[0] == 0x00 && buffer[1] == 0x00 && buffer[2] == 0x00) {
          current_pwm_target = 0;
          blink_interval_ms = 0;
          update_pwm(0);
          digitalWrite(LED2_BLINK_PIN, LOW);
        } else {
          current_pwm_target = buffer[0];     // Byte 0: Brightness (0-255)
          blink_interval_ms = buffer[1] * 10; // Byte 1: Blink Rate Multiplier
          update_pwm(current_pwm_target);
        }
        index = 0; // Reset packet index buffer
      }
    }
  }
}

void setup() {
  setup_hardware();
  last_blink_time = millis();
}

void loop() {
  // 1. Constantly check for incoming bytes (Never blocks execution)
  process_serial();

  // 2. Non-blocking Timer check for LED 2
  if (blink_interval_ms > 0) {
    unsigned long current_time = millis();
    if (current_time - last_blink_time >= blink_interval_ms) {
      led2_state = !led2_state;
      digitalWrite(LED2_BLINK_PIN, led2_state ? HIGH : LOW);
      last_blink_time = current_time;
    }
  } else {
    digitalWrite(LED2_BLINK_PIN, LOW); // Force off if interval is 0
  }
}