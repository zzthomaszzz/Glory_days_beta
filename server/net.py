# server/net.py

import asyncio
import json
import socket

from server.game_state import GameState
from shared.protocol import make_snapshot


class GameServer:
    def __init__(self, host, port, snapshot_interval, game_state: GameState):
        self.host = host
        self.port = port
        self.snapshot_interval = snapshot_interval
        self.game_state = game_state

        self.writers = {}
        self.next_player_id = 0

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
        team = 1 if player_id % 2 == 0 else 2
        self.writers[player_id] = writer

        welcome = {"type": "welcome", "player_id": player_id, "team": team}
        writer.write((json.dumps(welcome) + "\n").encode())
        await writer.drain()

        try:
            hero_line = await reader.readline()
            if not hero_line:
                self.writers.pop(player_id, None)
                writer.close()
                return
            hero_msg = json.loads(hero_line.decode())
            hero_name = hero_msg.get("hero", "Player") if hero_msg.get("type") == "hero_select" else "Player"
        except Exception:
            self.writers.pop(player_id, None)
            writer.close()
            return

        self.game_state.add_player(player_id, team, hero_name)
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
            )
            data = (json.dumps(snapshot) + "\n").encode()

            for writer in list(self.writers.values()):
                try:
                    writer.write(data)
                except Exception:
                    pass

            await asyncio.sleep(self.snapshot_interval)