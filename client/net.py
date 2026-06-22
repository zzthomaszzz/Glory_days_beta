import asyncio
import json
import sys
import time

from shared.protocol import make_input_message, make_hero_select_message
from shared.constants import GAME_VERSION

# ── Connection config ────────────────────────────────────────────────────────
DEV_MODE = True
SERVER_URL = "ws://localhost:5555" if DEV_MODE else "wss://YOUR_PLAYIT_URL_HERE"

_IS_BROWSER = sys.platform == "emscripten"

if not _IS_BROWSER:
    import websockets
    import websockets.exceptions

try:
    from pyodide.ffi import create_proxy as _proxy
except ImportError:
    def _proxy(f):
        return f


class NetworkClient:
    def __init__(self, host, port, snapshot_interval):
        self.host = host
        self.port = port
        self.snapshot_interval = snapshot_interval
        self._url = SERVER_URL if _IS_BROWSER else f"ws://{host}:{port}"

        self._ws = None          # native websockets connection
        self._js_ws = None       # JS WebSocket object (browser)
        self._recv_queue = None  # asyncio.Queue for browser messages
        self._proxies = []       # hold refs so JS GC doesn't collect them

        self.latest_snapshot = {}
        self.previous_snapshot = {}
        self.last_snapshot_time = 0.0

        self.my_player_id = None
        self.my_team = None
        self.shops = {}
        self.is_connected = True

    async def connect(self):
        if _IS_BROWSER:
            await self._connect_browser()
        else:
            self._ws = await websockets.connect(self._url)

    async def _connect_browser(self):
        from js import WebSocket as JSWebSocket

        self._recv_queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        connected = loop.create_future()

        def on_open(event):
            if not connected.done():
                connected.set_result(True)

        def on_error(event):
            if not connected.done():
                connected.set_exception(ConnectionError("WebSocket connection failed"))

        def on_message(event):
            self._recv_queue.put_nowait(event.data)

        def on_close(event):
            self.is_connected = False
            self._recv_queue.put_nowait(None)  # unblock receive_loop

        p_open  = _proxy(on_open)
        p_err   = _proxy(on_error)
        p_msg   = _proxy(on_message)
        p_close = _proxy(on_close)
        self._proxies = [p_open, p_err, p_msg, p_close]

        self._js_ws = JSWebSocket.new(self._url)
        self._js_ws.onopen    = p_open
        self._js_ws.onerror   = p_err
        self._js_ws.onmessage = p_msg
        self._js_ws.onclose   = p_close

        await connected

    async def wait_for_welcome(self, timeout=10.0):
        deadline = time.time() + timeout
        while self.my_player_id is None:
            if time.time() > deadline:
                return False
            if not self.is_connected:
                return False
            await asyncio.sleep(0.05)
        return True

    async def receive_loop(self):
        try:
            if _IS_BROWSER:
                await self._receive_loop_browser()
            else:
                await self._receive_loop_native()
        except Exception:
            pass
        self.is_connected = False

    async def _receive_loop_native(self):
        async for raw in self._ws:
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            self._dispatch(msg)

    async def _receive_loop_browser(self):
        while True:
            raw = await self._recv_queue.get()
            if raw is None:
                break
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            self._dispatch(msg)

    def _dispatch(self, msg):
        if msg.get("type") == "welcome":
            self.my_player_id = str(msg["player_id"])
            self.my_team = msg["team"]
            self.shops = msg.get("shops", {})
            return
        self.previous_snapshot = self.latest_snapshot
        self.latest_snapshot = msg
        self.last_snapshot_time = time.time()

    async def _send(self, payload):
        data = json.dumps(payload)
        try:
            if _IS_BROWSER:
                if self._js_ws and self._js_ws.readyState == 1:  # OPEN
                    self._js_ws.send(data)
            else:
                if self._ws and not self._ws.closed:
                    await self._ws.send(data)
        except Exception:
            pass

    async def send_hero_select(self, hero_name):
        payload = make_hero_select_message(hero_name)
        payload["version"] = GAME_VERSION
        await self._send(payload)

    async def send_ready(self):
        await self._send({"type": "ready"})

    async def send_force_start(self):
        await self._send({"type": "force_start"})

    async def send_sell_item(self, slot):
        await self._send({"type": "sell_item", "slot": slot})

    async def send_buy_item(self, item_name):
        await self._send({"type": "buy_item", "item": item_name})

    async def send_input(self, dx, dy, attack=None, ability=None, ability_target=None, ability_target_id=None):
        payload = make_input_message(dx, dy, attack, ability, ability_target, ability_target_id)
        await self._send(payload)

    def get_interpolated_pos(self, category, entity_id):
        latest   = self.latest_snapshot.get(category, {})
        previous = self.previous_snapshot.get(category, {})
        if entity_id not in latest:
            return None
        if entity_id not in previous:
            return latest[entity_id]["pos"]
        elapsed = time.time() - self.last_snapshot_time
        t = min(elapsed / self.snapshot_interval, 1.0)
        prev_x, prev_y = previous[entity_id]["pos"]
        curr_x, curr_y = latest[entity_id]["pos"]
        return [prev_x + (curr_x - prev_x) * t, prev_y + (curr_y - prev_y) * t]

    def get_interpolated_xy(self, category, entity_id):
        latest   = self.latest_snapshot.get(category, {})
        previous = self.previous_snapshot.get(category, {})
        if entity_id not in latest:
            return None
        cur = latest[entity_id]
        if entity_id not in previous:
            return cur["x"], cur["y"]
        elapsed = time.time() - self.last_snapshot_time
        t = min(elapsed / self.snapshot_interval, 1.0)
        prv = previous[entity_id]
        return (
            prv["x"] + (cur["x"] - prv["x"]) * t,
            prv["y"] + (cur["y"] - prv["y"]) * t,
        )

    def get_entity_ids(self, category):
        return list(self.latest_snapshot.get(category, {}).keys())


async def ping_server(host, port, timeout=4.0):
    if _IS_BROWSER:
        return {"online": False}
    url = f"ws://{host}:{port}"
    try:
        t0 = time.perf_counter()
        async with websockets.connect(url, open_timeout=timeout) as ws:
            await ws.send(json.dumps({"type": "status"}))
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            ping_ms = int((time.perf_counter() - t0) * 1000)
            data = json.loads(raw)
            return {"online": True, "ping_ms": ping_ms, **data}
    except Exception:
        return {"online": False}
