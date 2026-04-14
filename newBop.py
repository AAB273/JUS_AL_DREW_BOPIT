import random
import asyncio
import cv2 as cv
import mediapipe as mp
import math
from flask import Flask, Response
from threading import Thread
from bleak import BleakClient, BleakScanner

# ── Config ──────────────────────────────────────────────
DEVICE_NAME = "Bluefruit"
UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
PHONE_IP = "192.168.50.233"

# ── Flask ────────────────────────────────────────────────
flask_app = Flask(__name__)

# ── MediaPipe ────────────────────────────────────────────
mphands = mp.solutions.hands
mpdrawing = mp.solutions.drawing_utils

video = cv.VideoCapture(f"http://{PHONE_IP}:8080/video")
video.set(cv.CAP_PROP_BUFFERSIZE, 1)

frame_width = int(video.get(cv.CAP_PROP_FRAME_WIDTH))
frame_height = int(video.get(cv.CAP_PROP_FRAME_HEIGHT))

fourcc = cv.VideoWriter_fourcc(*'mp4v')
out = cv.VideoWriter('output.mp4', fourcc, 20.0, (frame_width, frame_height))

# ── Game State ───────────────────────────────────────────
score = 0
level = 1
ppl = 20

def timeLimit(level: int) -> float:
    return max(1.5, 6.0 - (level - 1) * 0.5)

# ── FSM ─────────────────────────────────────────────────
class BopItFSM:
    def __init__(self):
        self.current_state = "idle"
        self.current_prompt = None
        self._timeout_task = None

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
                print("Level Up!")
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

fsm = BopItFSM()

# ── Force Detection + Camera Loop ────────────────────────
latest_frame = b''
last_force = False  # debounce — only trigger once per gesture

def camera_loop():
    global latest_frame, last_force

    with mphands.Hands(min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands:
        while True:
            ret, frame = video.read()
            if not ret:
                continue

            rgb_frame = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            process_frames = hands.process(rgb_frame)

            force_detected = False

            if process_frames.multi_hand_landmarks:
                for lm in process_frames.multi_hand_landmarks:
                    mpdrawing.draw_landmarks(frame, lm, mphands.HAND_CONNECTIONS)

                    thumb_tip  = lm.landmark[4]
                    index_tip  = lm.landmark[8]
                    ring_tip   = lm.landmark[16]
                    pinky_tip  = lm.landmark[20]
                    wrist      = lm.landmark[0]
                    mid_mcp    = lm.landmark[9]

                    ref_dist = math.sqrt(
                        (wrist.x - mid_mcp.x)**2 + (wrist.y - mid_mcp.y)**2
                    )

                    norm_distance_1 = math.sqrt(
                        (thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2
                    ) / ref_dist

                    norm_distance_2 = math.sqrt(
                        (ring_tip.x - pinky_tip.x)**2 + (ring_tip.y - pinky_tip.y)**2
                    ) / ref_dist

                    if norm_distance_1 > 0.5 and norm_distance_2 > 0.5:
                        force_detected = True
                        cv.putText(frame, "Using the force",
                                   (frame_width // 2 - 150, 50),
                                   cv.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

            # Debounce: only trigger FSM on the rising edge of force gesture
            if force_detected and not last_force:
                fsm.evaluate("FORCE")
            last_force = force_detected

            # HUD
            cv.putText(frame, f"Score: {score}  Level: {level}",
                       (20, frame_height - 20),
                       cv.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            if fsm.current_prompt:
                cv.putText(frame, f"DO: {fsm.current_prompt}",
                           (20, 50), cv.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 255), 2)

            out.write(frame)
            _, buffer = cv.imencode('.jpg', frame)
            latest_frame = buffer.tobytes()

def generate():
    while True:
        if latest_frame:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                   latest_frame + b'\r\n')

@flask_app.route('/output')
def output():
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# ── BLE Handler ──────────────────────────────────────────
ble_buffer = ""

def on_data(sender, data: bytearray):
    global ble_buffer
    ble_buffer += data.decode("utf-8", errors="ignore")
    while True:
        ble_buffer = ble_buffer.strip()
        if not ble_buffer:
            break
        if "ATTACK" in ble_buffer:
            print("[BLE] Received: ATTACK")
            fsm.evaluate("ATTACK")
            ble_buffer = ble_buffer.replace("ATTACK", "", 1).strip()
        elif "BLOCK" in ble_buffer:
            print("[BLE] Received: BLOCK")
            fsm.evaluate("BLOCK")
            ble_buffer = ble_buffer.replace("BLOCK", "", 1).strip()
        else:
            break

# ── Main ─────────────────────────────────────────────────
async def main():
    # Start camera thread
    cam_thread = Thread(target=camera_loop, daemon=True)
    cam_thread.start()

    # Start Flask thread
    flask_thread = Thread(target=lambda: flask_app.run(
        host='0.0.0.0', port=5000, use_reloader=False), daemon=True)
    flask_thread.start()

    print(f"Stream live at http://[PI-IP]:5000/output")

    # Connect BLE
    print("Scanning for Bluefruit...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME)
    if not device:
        print(f"Could not find '{DEVICE_NAME}'. Running with camera only...")
        fsm.prompt()
        while True:
            await asyncio.sleep(1)
        return

    print(f"Found {device.name}, connecting...")
    async with BleakClient(device) as client:
        print("Connected! Starting game...\n")
        await client.start_notify(UART_RX_UUID, on_data)
        fsm.prompt()
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nGame over!")
            print(f"Final score: {score}")
            out.release()
            video.release()
            await client.stop_notify(UART_RX_UUID)

asyncio.run(main())
