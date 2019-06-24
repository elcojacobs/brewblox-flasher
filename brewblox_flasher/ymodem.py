"""
Communicates with devices using the YMODEM protocol
"""

import asyncio
import math
import os
from logging import getLogger
from typing import Awaitable, ByteString, List, NamedTuple

import aiofiles

from brewblox_flasher import serial_connection
from brewblox_flasher.serial_connection import Connection

YMODEM_TRIGGER_BAUD_RATE = 28800
YMODEM_TRANSFER_BAUD_RATE = 9600

LOGGER = getLogger(__name__)


class SendState(NamedTuple):
    seq: int
    response: int


class FileSenderProtocol(asyncio.Protocol):
    def __init__(self):
        self._loop = asyncio.get_event_loop()
        self._connection_made_event = asyncio.Event()
        self._queue = asyncio.Queue()

    @property
    def message(self) -> Awaitable[ByteString]:
        return self._queue.get()

    @property
    def connected(self) -> Awaitable:
        return self._connection_made_event.wait()

    def connection_made(self, transport):
        self._connection_made_event.set()

    def connection_lost(self, exc):
        pass

    def data_received(self, data):
        LOGGER.info(f'recv: {data}')
        self._loop.create_task(self._queue.put(data))

    def clear(self):
        for i in range(self._queue.qsize()):
            self._queue.get_nowait()


class FileSender():
    """
    Receive_Packet
    - first byte SOH/STX (for 128/1024 byte size packets)
    - EOT (end)
    - CA CA abort
    - ABORT1 or ABORT2 is abort
    Then 2 bytes for seq-no (although the sequence number isn't checked)
    Then the packet data
    Then CRC16?
    First packet sent is a filename packet:
    - zero-terminated filename
    - file size (ascii) followed by space?
    """

    SOH = 1     # 128 byte blocks
    STX = 2     # 1K blocks
    EOT = 4
    ACK = 6
    NAK = 0x15
    CA = 0x18           # 24
    CRC16 = 0x43        # 67
    ABORT1 = 0x41       # 65
    ABORT2 = 0x61       # 97

    PACKET_MARK = STX
    DATA_LEN = 1024 if PACKET_MARK == STX else 128
    PACKET_LEN = DATA_LEN + 5

    def __init__(self, device: str = None, id: str = None):
        self._device = device
        self._id = id

    async def transfer(self, filename: str):
        conn = await self._connect()

        try:
            LOGGER.info(f'Controller is in transfer mode, sending file {filename}')
            async with aiofiles.open(filename, 'rb') as file:
                await file.seek(0, os.SEEK_END)
                fsize = await file.tell()
                num_packets = math.ceil(fsize / FileSender.DATA_LEN)
                await file.seek(0, os.SEEK_SET)

                LOGGER.info('Sending header...')
                state: SendState = await self._send_header(conn, 'binary', fsize)

                if state.response != FileSender.ACK:
                    raise ConnectionAbortedError(f'Failed with code {state.response} while sending header')

                for i in range(num_packets):
                    current = i + 1  # packet 0 was the header
                    LOGGER.info(f'Sending packet {current} / {num_packets}')
                    data = await file.read(FileSender.DATA_LEN)
                    state = await self._send_data(conn, current, list(data))

                    if state.response != FileSender.ACK:
                        raise ConnectionAbortedError(
                            f'Failed with code {state.response} while sending package {current}')

                await self._send_close(conn)

        finally:
            conn.transport.close()

    async def _connect(self):
        # Trigger listening mode
#        conn = await serial_connection.connect(self._device, self._id, YMODEM_TRIGGER_BAUD_RATE)
#        conn.transport.close()

        # Connect
        conn = await serial_connection.connect(self._device, self._id, YMODEM_TRANSFER_BAUD_RATE, FileSenderProtocol)
        await conn.protocol.connected

        # Trigger YMODEM mode
#        buffer = ''
#        conn.transport.write(b'f')
#        for i in range(10):
#            buffer += (await conn.protocol.message).decode()
#            if '\n' in buffer:
#                break
#        else:
#            raise TimeoutError('Controller did not enter file transfer mode')

#        if 'Waiting for the binary file' not in buffer:
#           raise ConnectionAbortedError(f'Failed to enter transfer mode: {buffer}')

        ack = 0
        while ack < 2:
            conn.transport.write(b' ')
            if (await conn.protocol.message)[0] == FileSender.ACK:
                ack += 1

        return conn

    async def _send_close(self, conn: Connection):
        # Send End Of Transfer
        assert await self._send_packet(conn, [FileSender.EOT]) == FileSender.ACK
        assert await self._send_packet(conn, [FileSender.EOT]) == FileSender.ACK

        # Signal end of connection
        await self._send_data(conn, 0, [])

    async def _send_header(self, conn: Connection, name: str, size: int) -> Awaitable[SendState]:
        data = [FileSender.PACKET_MARK, *name.encode(), 0, *f'{size} '.encode()]
        return await self._send_data(conn, 0, data)

    async def _send_data(self, conn: Connection, seq: int, data: List[int]) -> Awaitable[SendState]:
        packet_data = data + [0] * (FileSender.DATA_LEN - len(data))
        packet_seq = seq & 0xFF
        packet_seq_neg = 0xFF - packet_seq
        crc16 = [0, 0]

        packet = [FileSender.PACKET_MARK, packet_seq, packet_seq_neg, *packet_data, *crc16]
        if len(packet) != FileSender.PACKET_LEN:
            raise RuntimeError(f'Packet length mismatch: {len(packet)} / {FileSender.PACKET_LEN}')

        response = await self._send_packet(conn, packet)

        if response == FileSender.NAK:
            LOGGER.info('retrying packet...')
            await asyncio.sleep(1)
            response = await self._send_packet(conn, packet)

        return SendState(seq, response)

    async def _send_packet(self, conn: Connection, packet: str) -> int:
        conn.protocol.clear()
        conn.transport.write(bytes(packet))
        while True:
            retv = [int(i) for i in await conn.protocol.message][0]
            if retv != FileSender.CRC16:
                break

        return retv
