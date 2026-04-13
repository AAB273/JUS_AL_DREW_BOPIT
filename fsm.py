import random
import asyncio
from bleak import BleakClient, BleakScanner

# ── Config ──────────────────────────────────────────────
DEVICE_NAME = "Bluefruit"  # change if yours is named differently
UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e" # Bluefruit UART notify

# ── Game State ───────────────────────────────────────────
score = 0
level = 1

# level config

ppl = 20

def timeLimit(level: int) -> float:
    return max(1.5, 6.0 - (level - 1) * 0.5)

# ── FSM ─────────────────────────────────────────────────
class BopItFSM:
    def __init__(self):
        self.current_state = "idle"
        self.current_prompt = None
        self._timeout_task = None
        self._prompt_task = None
        self.loop = None
        
    def prompt(self):
        global level
        self.current_prompt = random.choice(["ATTACK", "BLOCK"])
        self.current_state = "waiting"
        time_lim = timeLimit(level)
        
        print(f"\n>>> {self.current_prompt}! (Level {level} - {time_lim:.1f}s)")
        
        if self._timeout_task:
            self._timeout_task.cancel()
        self._timeout_task = asyncio.create_task(self._timeout_after(time_lim))
    
    async def _timeout_after(self, seconds: float):
        await asyncio.sleep(seconds)
        if self.current_state == "waiting":
            print("Too Slow!")
            print(f"Score: {score}")
            self.current_state = "idle"
            await asyncio.sleep(1.0)
            self.prompt()

    def evaluate(self, detected: str):
        global score, level
        if self.current_state != "waiting":
            return
        
        if self._timeout_task:
            self._timeout_task.cancel()
            self._timeout_task = None
        
        if detected == self.current_prompt:
            print("✓ Correct!")
            score += 1
            
            if score % ppl == 0:
                level += 1
                print("Level Up")
                
        else:
            print(f"✗ Wrong! Expected {self.current_prompt}, got {detected}")
        
        print(f"Score: {score} | Level: {level}")
        self.current_state = "idle"
        asyncio.create_task(self._next_prompt())
    
    async def _next_prompt(self):
        await asyncio.sleep(1.0)
        self.prompt()
        
    def reset(self):
        global score, level
        if self._timeout_task:
            self._timeout_task.cancel()
        score = 0
        level = 1
        self.current_state = "idle"
        print("Game reset.")
             
# ── BLE Data Handler ─────────────────────────────────────
ble_buffer = ""



def on_data(sender, data: bytearray):
    global ble_buffer
    ble_buffer += data.decode("utf-8", errors="ignore")
    while True:
        ble_buffer = ble_buffer.strip()
        if not ble_buffer:
            break
        if ble_buffer.startswith("ATTACK") or "ATTACK" in ble_buffer:
            print("[BLE] Received: ATTACK")
            fsm.evaluate("ATTACK")
            ble_buffer = ble_buffer.replace("ATTACK", "", 1).strip()
        elif ble_buffer.startswith("BLOCK") or "BLOCK" in ble_buffer:
            print("[BLE] Received: BLOCK")
            fsm.evaluate("BLOCK")
            ble_buffer = ble_buffer.replace("BLOCK", "", 1).strip()
        else:
            break
    
fsm = BopItFSM()
# ── Main ─────────────────────────────────────────────────
async def main():
    print("Scanning for Bluefruit...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME)
    if not device:
        print(f"Could not find '{DEVICE_NAME}'. Is it powered on?")
        return

    print(f"Found {device.name}, connecting...")

    async with BleakClient(device) as client:
        print("Connected! Starting game...\n")
        await client.start_notify(UART_RX_UUID, on_data)
        
        fsm.prompt()  # kick off first round

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nGame over!")
            print(f"Final score: {score}")
            await client.stop_notify(UART_RX_UUID)

asyncio.run(main())
