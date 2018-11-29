"""
Implements a protocol for async serial communication.
"""

import asyncio
import re
import warnings
from logging import getLogger
from typing import Any, Awaitable, Callable, Iterable, NamedTuple, Tuple

import serial
from serial.tools import list_ports
from serial_asyncio import SerialTransport

LOGGER = getLogger(__name__)
DEFAULT_BAUD_RATE = 57600
DFU_TRIGGER_BAUD_RATE = 14400

PortType_ = Any
ProtocolFactory_ = Callable[[], asyncio.Protocol]
ConnectionResult_ = Tuple[Any, asyncio.Transport, asyncio.Protocol]


class DeviceMatch(NamedTuple):
    id: str
    desc: str
    hwid: str


class Connection(NamedTuple):
    address: Any
    transport: asyncio.Transport
    protocol: asyncio.Protocol


KNOWN_DEVICES = {
    DeviceMatch(
        id='Spark Core',
        desc=r'Spark Core.*Arduino.*',
        hwid=r'USB VID\:PID=1D50\:607D.*'),
    DeviceMatch(
        id='Particle Photon',
        desc=r'.*Photon.*',
        hwid=r'USB VID\:PID=2d04\:c006.*'),
    DeviceMatch(
        id='Particle P1',
        desc=r'.*P1.*',
        hwid=r'USB VID\:PID=2B04\:C008.*'),
}


class SerialProtocol(asyncio.Protocol):
    def __init__(self, on_data: Callable[[str], None] = LOGGER.info):
        super().__init__()
        self._connection_made_event = asyncio.Event()
        self._connection_lost_event = asyncio.Event()
        self._on_data = on_data
        self._buffer = ''

    @property
    def connected(self) -> Awaitable:
        return self._connection_made_event.wait()

    @property
    def disconnected(self) -> Awaitable:
        return self._connection_lost_event.wait()

    def connection_made(self, transport):
        self._connection_made_event.set()

    def connection_lost(self, exc):
        self._connection_lost_event.set()
        if exc:
            warnings.warn(f'Protocol connection error: {exc}')

    def data_received(self, data):
        self._buffer += data.decode()

        for data in self._coerce_message_from_buffer(start='^', end='\n'):
            self._on_data(data)

    def _coerce_message_from_buffer(self, start: str, end: str):
        messages = []

        def extract_message(matchobj) -> str:
            msg = matchobj.group('message').rstrip()
            messages.append(msg)
            return ''

        while re.search(f'.*{start}.*{end}', self._buffer):
            self._buffer = re.sub(
                pattern=f'{start}(?P<message>[^{start}]*?){end}',
                repl=extract_message,
                string=self._buffer,
                count=1)

        yield from messages


async def connect(device: str = None,
                  id: str = None,
                  baudrate: int = DEFAULT_BAUD_RATE,
                  factory: Callable[[], asyncio.Protocol] = SerialProtocol
                  ) -> Awaitable[Connection]:
    address = detect_device(device, id)
    protocol = factory()
    ser = serial.serial_for_url(address, baudrate=baudrate)
    transport = SerialTransport(asyncio.get_event_loop(), protocol, ser)
    transport.serial.rts = False
    return Connection(address, transport, protocol)


def all_ports() -> Iterable[PortType_]:
    return tuple(list_ports.comports())


def recognized_ports(
    allowed: Iterable[DeviceMatch] = KNOWN_DEVICES,
    serial_number: str = None
) -> Iterable[PortType_]:

    # Construct a regex OR'ing all allowed hardware ID matches
    # Example result: (?:HWID_REGEX_ONE|HWID_REGEX_TWO)
    matcher = f'(?:{"|".join([dev.hwid for dev in allowed])})'

    for port in list_ports.grep(matcher):
        if serial_number is None or serial_number == port.serial_number:
            yield port


def detect_device(device: str = None, serial_number: str = None) -> str:
    if device is None:
        try:
            port = next(recognized_ports(serial_number=serial_number))
            device = port.device
            LOGGER.info(f'Automatically detected {[v for v in port]}')
        except StopIteration:
            raise ConnectionError(
                f'Could not find recognized device. Known={[{v for v in p} for p in all_ports()]}')

    return device
