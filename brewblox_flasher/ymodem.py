"""
Communicates with devices using the YMODEM protocol
"""

import asyncio
import re
from logging import getLogger
from typing import Awaitable

from brewblox_flasher import serial_connection

YMODEM_TRIGGER_BAUD_RATE = 28800

LOGGER = getLogger(__name__)


class FileSenderProtocol(asyncio.Protocol):
    def __init__(self, loop: asyncio.BaseEventLoop):
        self._loop = loop
        self._connection_made_event = asyncio.Event()
        self._queue = asyncio.Queue(loop=loop)
        self._buffer = ''

    @property
    def message(self) -> Awaitable[str]:
        return self._queue.get()

    @property
    def connected(self) -> Awaitable:
        return self._connection_made_event.wait()

    def connection_made(self, transport):
        self._connection_made_event.set()

    def connection_lost(self, exc):
        pass

    def data_received(self, data):
        self._buffer += data.decode()

        def extract_message(matchobj) -> str:
            msg = matchobj.group('message').rstrip()
            self._loop.create_task(self._queue.put(msg))
            return ''

        while re.search(r'.*^.*\n', self._buffer):
            self._buffer = re.sub(
                pattern=r'^(?P<message>[^^]*?)\n',
                repl=extract_message,
                string=self._buffer,
                count=1
            )

    def on_data(self, msg: str):
        LOGGER.info(f'msg: {msg}')
        if msg.startswith('Waiting for the binary file'):
            self._readable_event.set()


async def trigger_ymodem(device: str = None, id: str = None):
    conn = await serial_connection.connect(device, id, YMODEM_TRIGGER_BAUD_RATE)
    conn.transport.close()


async def send_file(filename: str, device: str = None, id: str = None):
    loop = asyncio.get_event_loop()
    conn = await serial_connection.connect(
        device,
        id,
        YMODEM_TRIGGER_BAUD_RATE,
        lambda: FileSenderProtocol(loop),
    )
    await conn.protocol.connected
    conn.transport.write(b'f')
    while not (await conn.protocol.message).startswith('Waiting for the binary file'):
        pass
    conn.transport.close()
    await conn.protocol.disconnected
