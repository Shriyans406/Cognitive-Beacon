import asyncio
import serial

class SerialWorker:
    def __init__(self, port="COM5", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.queue = asyncio.Queue()
        self.ser = None
        self.running = False
        
        # --- PHASE 4 LOW-PASS FILTER TUNING ---
        self.smoothed_pwm = 0.0
        # Alpha 0.15 creates a smooth, cinematic "breathing" effect
        self.alpha = 0.15  

    async def start(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0)
            print(f"[Serial] Successfully connected to Shrike Lite on {self.port}")
            await asyncio.sleep(2)
            self.running = True
            asyncio.create_task(self.loop())
        except Exception as e:
            print(f"[Serial Error] Could not open port {self.port}: {e}")

    async def send_state(self, target_pwm: float, blink_rate: int):
        """Drops exact hardware targets into the queue."""
        if self.running:
            await self.queue.put((target_pwm, blink_rate))

    async def loop(self):
        print("[Serial] Background worker loop is now running.")
        while self.running:
            try:
                target_pwm, blink_rate = await self.queue.get()

                # Apply the smoothing filter to the brightness
                self.smoothed_pwm = (self.alpha * target_pwm) + ((1.0 - self.alpha) * self.smoothed_pwm)
                
                pwm_byte = int(max(0, min(255, self.smoothed_pwm)))
                blink_byte = int(max(0, min(255, blink_rate)))

                packet = bytes([pwm_byte, blink_byte, 0xFF])
                
                if self.ser and self.ser.is_open:
                    self.ser.write(packet)
                    self.ser.flush()

                self.queue.task_done()
                await asyncio.sleep(0.05) # 50ms loop ensures no CPU overloading

            except Exception as e:
                print(f"[Serial Loop Error] {e}")
                await asyncio.sleep(1)

    async def stop(self):
        print("[Serial] Stopping worker and sending Goodbye Routine...")
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.write(bytes([0x00, 0x00, 0x00]))
            self.ser.flush()
            await asyncio.sleep(0.2)
            self.ser.close()
        print("[Serial] Port closed successfully.")
