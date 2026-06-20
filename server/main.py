# Server entry point: starts the TCP listener and runs the asyncio event loop
import asyncio

from shared.constants import SERVER_HOST, SERVER_PORT, SNAPSHOT_INTERVAL
from server.net import GameServer
from server.game_state import GameState

SOLO_MODE = True   # set False on the official server


async def main():
    game_state = GameState(solo_mode=SOLO_MODE)
    server = GameServer(SERVER_HOST, SERVER_PORT, SNAPSHOT_INTERVAL, game_state)
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())