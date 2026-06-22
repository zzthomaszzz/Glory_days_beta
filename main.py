# Root entry point for Pygbag (browser build).
# PyInstaller uses client/main.py directly via main.spec; this file is for pygbag only.
import asyncio
from client.main import main

asyncio.run(main())
