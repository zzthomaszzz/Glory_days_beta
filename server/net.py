# TCP server: connection handling, version check, broadcast loop, and game reset

import asyncio
import json
import socket

from server.game_state import GameState
from shared.protocol import make_snapshot
from shared.constants import GAME_VERSION


class GameServer:
    def __init__(self, host, port, snapshot_interval, game_state: GameState):
        self.host = host
        self.port = port
        self.snapshot_interval = snapshot_interval
        self.game_state = game_state

        self.writers = {}
        self.next_player_id = 0
        self._end_timer = None

    async def run(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        print(f"GloryDay server running on {self.host}:{self.port}")

        await asyncio.gather(
            server.serve_forever(),
            self.broadcast_loop(),
        )

    async def handle_client(self, reader, writer):
        sock = writer.get_extra_info('socket')
        if sock:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        peer = writer.get_extra_info('peername', ('?', 0))
        print(f"[+] TCP connection from {peer[0]}:{peer[1]}")
        player_id = self.next_player_id
        self.next_player_id += 1
        team = self._assign_team()

        try:
            hero_name = "Player"
            deadline = asyncio.get_event_loop().time() + 15.0
            while True:
                remaining = max(0.1, deadline - asyncio.get_event_loop().time())
                hero_line = await asyncio.wait_for(reader.readline(), timeout=remaining)
                if not hero_line:
                    writer.close()
                    return
                stripped = hero_line.strip()
                if not stripped:
                    continue
                try:
                    hero_msg = json.loads(stripped.decode())
                    if hero_msg.get("type") == "status":
                        reply = {
                            "type":         "status_reply",
                            "player_count": len(self.game_state.players),
                            "max_players":  6,
                            "game_phase":   self.game_state.game_phase,
                        }
                        writer.write((json.dumps(reply) + "\n").encode())
                        await writer.drain()
                        writer.close()
                        return
                    if hero_msg.get("type") != "hero_select":
                        break
                    if hero_msg.get("version") != GAME_VERSION:
                        reply = {"type": "error", "msg": f"Version mismatch — server requires v{GAME_VERSION}. Please update your client."}
                        writer.write((json.dumps(reply) + "\n").encode())
                        await writer.drain()
                        writer.close()
                        return
                    hero_name = hero_msg.get("hero", "Player")
                    break
                except Exception:
                    continue
        except Exception as e:
            print(f"[!] Player {player_id} handshake failed: {e}")
            writer.close()
            return

        if self.game_state.game_phase == "ended":
            reply = {"type": "error", "msg": "Server is resetting after the last game. Try again in a moment."}
            writer.write((json.dumps(reply) + "\n").encode())
            await writer.drain()
            writer.close()
            return

        self.game_state.add_player(player_id, team, hero_name)
        self.writers[player_id] = writer

        welcome = {"type": "welcome", "player_id": player_id, "team": team}
        writer.write((json.dumps(welcome) + "\n").encode())
        await writer.drain()
        print(f"Player {player_id} connected as {hero_name} (team {team})")

        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                msg = json.loads(line.decode())
                self.game_state.apply_input(player_id, msg)

        except Exception as e:
            print(f"Player {player_id} error: {e}")

        finally:
            self.game_state.remove_player(player_id)
            self.writers.pop(player_id, None)
            writer.close()
            print(f"Player {player_id} disconnected")

    async def broadcast_loop(self):
        while True:
            self.game_state.match_time += self.snapshot_interval
            self.game_state.update(self.snapshot_interval)

            snapshot = make_snapshot(
                self.game_state.match_time,
                self.game_state.players,
                self.game_state.buildings,
                projectiles=self.game_state.projectiles,
                player_turrets=self.game_state.player_turrets,
                fireball_projectiles=self.game_state.fireball_projectiles,
                burning_areas=self.game_state.burning_areas,
                banners=self.game_state.banners,
                shops=self.game_state.shops,
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
            data = (json.dumps(snapshot) + "\n").encode()

            for writer in list(self.writers.values()):
                try:
                    writer.write(data)
                except Exception:
                    pass

            await asyncio.sleep(self.snapshot_interval)

            if self.game_state.game_phase == "ended":
                if self._end_timer is None:
                    self._end_timer = 8.0
                else:
                    self._end_timer -= self.snapshot_interval
                    if self._end_timer <= 0:
                        await self._reset_game()
            elif self.game_state.game_phase in ("live", "countdown") and not self.writers:
                print("[server] All players left — resetting lobby")
                await self._reset_game()

    def _assign_team(self):
        counts = {1: 0, 2: 0}
        for p in self.game_state.players.values():
            if p.team in counts:
                counts[p.team] += 1
        return 1 if counts[1] <= counts[2] else 2

    async def _reset_game(self):
        for writer in list(self.writers.values()):
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        self.writers.clear()
        self.game_state = GameState(solo_mode=self.game_state.solo_mode)
        self.next_player_id = 0
        self._end_timer = None
        print("[server] Game reset — new lobby ready")