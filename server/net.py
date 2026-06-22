# WebSocket server: connection handling, version check, broadcast loop, and game reset

import asyncio
import json

import websockets
import websockets.exceptions
from websockets.asyncio.server import ServerConnection

from server.game_state import GameState
from shared.protocol import make_snapshot


class _ProxyAwareConnection(ServerConnection):
    """Strip an optional HAProxy/playit.gg PROXY protocol v1 header before
    the WebSocket HTTP handshake.  The old TCP server survived this because
    json.loads() raised and the loop just did `continue`; websockets fails
    immediately because it expects 'GET / HTTP/1.1' as the very first bytes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._proxy_checked = False
        self._proxy_buf = b""

    def data_received(self, data: bytes) -> None:
        if self._proxy_checked:
            super().data_received(data)
            return

        self._proxy_buf += data
        nl = self._proxy_buf.find(b"\n")
        if nl == -1:
            return  # Haven't received the full first line yet — wait

        self._proxy_checked = True
        first_line = self._proxy_buf[: nl + 1]
        rest = self._proxy_buf[nl + 1 :]
        self._proxy_buf = b""

        if not first_line.startswith(b"PROXY "):
            rest = first_line + rest  # Not a PROXY header — keep the bytes

        if rest:
            super().data_received(rest)
from shared.constants import GAME_VERSION


class GameServer:
    def __init__(self, host, port, snapshot_interval, game_state: GameState):
        self.host = host
        self.port = port
        self.snapshot_interval = snapshot_interval
        self.game_state = game_state

        self.sockets = {}        # player_id -> websocket
        self.next_player_id = 0
        self._end_timer = None

    async def run(self):
        async with websockets.serve(
            self.handle_client, self.host, self.port,
            create_connection=_ProxyAwareConnection,
        ):
            print(f"GloryDay server running on ws://{self.host}:{self.port}")
            await self.broadcast_loop()

    async def handle_client(self, websocket):
        try:
            peer = websocket.remote_address
        except Exception:
            peer = ("?", 0)
        print(f"[+] WS connection from {peer[0]}:{peer[1]}")
        player_id = self.next_player_id
        self.next_player_id += 1
        team = self._assign_team()

        try:
            hero_name = "Player"
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 15.0
            while True:
                remaining = max(0.1, deadline - loop.time())
                try:
                    raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    await websocket.close()
                    return
                if not raw:
                    await websocket.close()
                    return
                try:
                    hero_msg = json.loads(raw)
                    if hero_msg.get("type") == "status":
                        reply = {
                            "type":         "status_reply",
                            "player_count": len(self.game_state.players),
                            "max_players":  6,
                            "game_phase":   self.game_state.game_phase,
                        }
                        await websocket.send(json.dumps(reply))
                        await websocket.close()
                        return
                    if hero_msg.get("type") != "hero_select":
                        break
                    if hero_msg.get("version") != GAME_VERSION:
                        client_ver = hero_msg.get("version", "unknown")
                        print(f"[!] Player {player_id} rejected: version mismatch (client={client_ver}, server={GAME_VERSION})")
                        reply = {"type": "error", "msg": f"Version mismatch — server is v{GAME_VERSION} but your client is v{client_ver}. Download the latest version."}
                        await websocket.send(json.dumps(reply))
                        await websocket.close()
                        return
                    hero_name = hero_msg.get("hero", "Player")
                    break
                except Exception:
                    continue
        except websockets.exceptions.ConnectionClosed:
            return
        except Exception as e:
            print(f"[!] Player {player_id} handshake failed: {e}")
            await websocket.close()
            return

        if self.game_state.game_phase == "ended":
            print(f"[!] Player {player_id} rejected: server is resetting after game end")
            reply = {"type": "error", "msg": "Server is resetting after the last game. Try again in a moment."}
            await websocket.send(json.dumps(reply))
            await websocket.close()
            return

        self.game_state.add_player(player_id, team, hero_name)
        self.sockets[player_id] = websocket

        welcome = {
            "type":      "welcome",
            "player_id": player_id,
            "team":      team,
            "shops":     {str(k): s.to_dict() for k, s in self.game_state.shops.items()},
        }
        await websocket.send(json.dumps(welcome))
        print(f"Player {player_id} connected as {hero_name} (team {team})")

        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                self.game_state.apply_input(player_id, msg)

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"Player {player_id} error: {e}")

        finally:
            self.game_state.remove_player(player_id)
            self.sockets.pop(player_id, None)
            print(f"Player {player_id} disconnected")

    async def broadcast_loop(self):
        loop = asyncio.get_running_loop()
        last_tick = loop.time()
        while True:
            now = loop.time()
            dt = now - last_tick
            last_tick = now
            if self.game_state.game_phase == "live":
                self.game_state.match_time += dt
            self.game_state.update(dt)

            snapshot = make_snapshot(
                self.game_state.match_time,
                self.game_state.players,
                self.game_state.buildings,
                projectiles=self.game_state.projectiles,
                player_turrets=self.game_state.player_turrets,
                fireball_projectiles=self.game_state.fireball_projectiles,
                burning_areas=self.game_state.burning_areas,
                banners=self.game_state.banners,
                events=[],
                game_phase=self.game_state.game_phase,
                countdown_timer=self.game_state.countdown_timer,
                ready_players=self.game_state.ready_players,
                wait_elapsed=self.game_state.wait_timer,
                minerals_exhausted=self.game_state._minerals_exhausted(),
                rune=self.game_state.rune,
                traps=self.game_state.traps,
                bolt_projectiles=self.game_state.bolt_projectiles,
                hook_projectiles=self.game_state.hook_projectiles,
                winner=self.game_state.winner,
            )
            text = json.dumps(snapshot)

            stale = []
            for pid, ws in list(self.sockets.items()):
                if ws.closed:
                    stale.append(pid)
                    continue
                try:
                    asyncio.create_task(ws.send(text))
                except Exception:
                    stale.append(pid)

            for pid in stale:
                print(f"[!] Player {pid} dropped — removing")
                self.sockets.pop(pid, None)

            await asyncio.sleep(self.snapshot_interval)

            if self.game_state.game_phase == "ended":
                if self._end_timer is None:
                    self._end_timer = 8.0
                else:
                    self._end_timer -= self.snapshot_interval
                    if self._end_timer <= 0:
                        await self._reset_game()
            elif self.game_state.game_phase in ("live", "countdown") and not self.sockets:
                print("[server] All players left — resetting lobby")
                await self._reset_game()

    def _assign_team(self):
        counts = {1: 0, 2: 0}
        for p in self.game_state.players.values():
            if p.team in counts:
                counts[p.team] += 1
        return 1 if counts[1] <= counts[2] else 2

    async def _reset_game(self):
        for ws in list(self.sockets.values()):
            try:
                await ws.close()
            except Exception:
                pass
        self.sockets.clear()
        self.game_state = GameState(solo_mode=self.game_state.solo_mode)
        self.next_player_id = 0
        self._end_timer = None
        print("[server] Game reset — new lobby ready")
