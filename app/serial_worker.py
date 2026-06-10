import asyncio
import serial

class SerialWorker:
    def __init__(self, port="COM5", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.queue = asyncio.Queue()
        self.ser = None
        self.running = False
        
        # Low-Pass Filter State Variable
        self.smoothed_speed = 0.0
        # Alpha determines smoothing: closer to 1 = fast/flickery, closer to 0 = smooth/cinematic
        self.alpha = 0.3  

    async def start(self):
        """Opens the serial port and starts the background processing loop."""
        try:
            # Open serial port non-blockingly
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0)
            print(f"[Serial] Successfully connected to Shrike Lite on {self.port}")
            # Wait 2 seconds for the RP2040 USB circuit to finish initializing
            await asyncio.sleep(2)
            self.running = True
            # Start the background loop task
            asyncio.create_task(self.loop())
        except Exception as e:
            print(f"[Serial Error] Could not open port {self.port}: {e}")

    async def send_metrics(self, raw_speed: float, blink_rate: int):
        """Public method for other files to drop metrics into the queue."""
        if self.running:
            await self.queue.put((raw_speed, blink_rate))

    async def loop(self):
        """Constantly monitors the queue and updates the hardware smoothly."""
        print("[Serial] Background worker loop is now running.")
        while self.running:
            try:
                # Wait until something is added to the queue
                raw_speed, blink_rate = await self.queue.get()

                # Apply Low-Pass Filter: Smoothed = (Alpha * Raw) + ((1 - Alpha) * OldSmoothed)
                self.smoothed_speed = (self.alpha * raw_speed) + ((1.0 - self.alpha) * self.smoothed_speed)
                
                # Scale the smoothed token speed (0 to 50 tokens/sec) into a 0-255 PWM byte
                pwm_val = int(max(0, min(255, self.smoothed_speed * 5)))
                
                # Ensure values fit perfectly into a single byte (0-255)
                pwm_byte = max(0, min(255, pwm_val))
                blink_byte = max(0, min(255, blink_rate))

                # Pack into our strict 3-byte contract: [PWM, Blink, ActiveFrame]
                packet = bytes([pwm_byte, blink_byte, 0xFF])
                
                if self.ser and self.ser.is_open:
                    self.ser.write(packet)
                    self.ser.flush()

                # Tell the queue we finished processing this item
                self.queue.task_done()
                
                # Small pause to let the hardware process and prevent high CPU usage
                await asyncio.sleep(0.05)

            except Exception as e:
                print(f"[Serial Loop Error] {e}")
                await asyncio.sleep(1)

    async def stop(self):
        """Triggers the Goodbye Routine and closes down the port safely."""
        print("[Serial] Stopping worker and sending Goodbye Routine...")
        self.running = False
        if self.ser and self.ser.is_open:
            # Send the Goodbye packet [0x00, 0x00, 0x00]
            self.ser.write(bytes([0x00, 0x00, 0x00]))
            self.ser.flush()
            await asyncio.sleep(0.2)
            self.ser.close()
        print("[Serial] Port closed successfully.")