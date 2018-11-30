"""
Entrypoint for brewblox_flasher
"""

import asyncio
import logging

from brewblox_flasher import ymodem


async def main():
    logging.basicConfig(level=logging.INFO)
    await ymodem.FileSender().transfer('brewblox.bin')


if __name__ == '__main__':
    asyncio.run(main())
