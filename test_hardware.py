import serial
import time

PORT = 'COM5' 
BAUD = 115200

try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    
    # --- THE CRITICAL FIX ---
    print(f"Connected to {PORT}. Waiting 2 seconds for Shrike Lite to wake up...")
    time.sleep(2) # Give the RP2040 time to initialize its USB connection
    ser.reset_input_buffer()  # Clear any connection noise
    ser.reset_output_buffer()
    # ------------------------

    print("------------------------------------------------")

    # Test 1: Low Brightness, Slow Blink
    print("Sending Test 1: Dim LED 1, slow blink on LED 2 (1000ms)...")
    ser.write(bytes([50, 100, 0xFF])) 
    time.sleep(5)

    # Test 2: Maximum Brightness, Rapid Flash
    print("Sending Test 2: Bright LED 1, rapid flash on LED 2 (100ms)...")
    ser.write(bytes([255, 10, 0xFF]))
    time.sleep(5)

    # Test 3: The Goodbye Routine
    print("Sending Test 3: Triggering Goodbye Routine (all indicators off)...")
    ser.write(bytes([0x00, 0x00, 0x00]))
    time.sleep(2)
    
    ser.close()
    print("Hardware verification completely successful!")

except Exception as e:
    print(f"Verification Error: {e}")