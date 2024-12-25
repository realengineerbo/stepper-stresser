"""
Daemon thread for reading and writing to serial port
"""

import time
from threading import Thread, Event
from typing import Callable
from serial import Serial, SerialException
from serial.tools import list_ports


class SerialDaemon(Thread):
    def __init__(self, callback: Callable[[bytes], None]):
        Thread.__init__(self)
        self.callback = callback
        self.daemon = True
        self.port_name = ""
        self.serial = Serial()
        self.open_port_event = Event()
        self.close_port_event = Event()
        self.stop_event = Event()

    @staticmethod
    def get_ports():
        return list_ports.comports()

    def set_baudrate(self, baudrate: int):
        self.serial.baudrate = baudrate

    def set_port_name(self, port_name: str):
        if self.port_name != port_name:
            self.port_name = port_name

    def is_port_open(self):
        return self.serial.is_open

    def open_port(self):
        if self.port_name:
            self.open_port_event.set()

    def close_port(self):
        self.close_port_event.set()

    def read_bytes(self):
        if self.serial.is_open:
            try:
                raw_bytes: bytes = b""
                while True:
                    # read() blocks to prevent unnecessary looping
                    raw_bytes += self.serial.read()
                    raw_bytes += self.serial.read(self.serial.in_waiting)
                    return raw_bytes
            except SerialException:
                self.close_port()

        time.sleep(0.5)
        return None

    def write_bytes(self, bytes_raw: bytes):
        if self.serial.is_open:
            array = bytearray(bytes_raw)
            array.append(0)
            # print(f"Writing {len(array)} bytes: {array}")
            self.serial.write(array)
        else:
            print("No port open")

    def write_string(self, string: str):
        self.write_bytes(string.encode())

    def run(self):
        while not self.stop_event.is_set():
            if self.open_port_event.is_set():
                self.open_port_event.clear()

                ports = SerialDaemon.get_ports()
                if not any(port.device == self.port_name for port in ports):
                    print(f"Port {self.port_name} not found, opening anyway")

                self.serial.port = self.port_name
                try:
                    self.serial.open()
                except SerialException:
                    pass
                else:
                    if self.serial.is_open:
                        print(f"Opened {self.port_name}")

            if self.close_port_event.is_set():
                self.close_port_event.clear()
                if self.serial.is_open:
                    self.serial.close()
                    print(f"Closed {self.port_name}")

            bytes_raw: bytes = self.read_bytes()
            if bytes_raw is not None:
                self.callback(bytes_raw)

    def stop(self):
        self.stop_event.set()
