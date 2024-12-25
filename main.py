"""
Progressively increases stepper acceleration until steps are lost
"""

import argparse
import math
import re
import sys
import time
from pathlib import Path
from serial_daemon import SerialDaemon


class StepperStressor:
    PASS_CRITERION = 3  # Consecutive successful movements
    FAIL_CRITERION = 20  # Skipped steps

    GCODE = """
M204 S10000
G28 X
SET_VELOCITY_LIMIT ACCEL={accel} ACCEL_TO_DECEL={accel}
M204 S{accel}
GET_POSITION
G1 X{x} F{feedrate:.0f}
M400
G4 P200
GET_POSITION
SET_VELOCITY_LIMIT ACCEL=1000 ACCEL_TO_DECEL=1000
M204 S1000
G28 X
GET_POSITION
M18
"""
    REGEX_MCU_STEPS = re.compile(
        r"// mcu: stepper_x:(-?\d+) stepper_y:-?\d+ stepper_z:-?\d+"
    )
    REGEX_POSITION = re.compile(
        r"// stepper: stepper_x:(-?\d+\.\d+) stepper_y:-?\d+\.\d+ stepper_z:-?\d+\.\d+"
    )

    ACCELS = [1000, 5000, 10000, 20000, 30000, 40000]

    def __init__(self, max_travel, max_velocity):
        self.max_travel = max_travel
        self.max_velocity = max_velocity
        self.accel_index = 0
        self.pass_count = 0
        self.fail_count = 0

        self.current_accel = self.ACCELS[0]
        self.min_accel = 0
        self.max_accel = None

        self.home_steps = None
        self.serial_write = None

    def set_serial_write(self, serial_write):
        self.serial_write = serial_write

    def iterate(self):
        if self.serial_write is None:
            print("self.serial_write is None", file=sys.stderr)
            sys.exit(1)

        if self.fail_count or self.pass_count >= self.PASS_CRITERION:
            if self.fail_count:
                self.max_accel = self.current_accel
            else:
                self.min_accel = self.current_accel

            self.pass_count = 0
            self.fail_count = 0

            # Iterate or calculate accel for this iteration
            if self.max_accel is None:
                self.accel_index += 1
                if self.accel_index >= len(self.ACCELS):
                    print("Max accel reached. Terminating.")
                    sys.exit()
                else:
                    self.current_accel = self.ACCELS[self.accel_index]
            else:
                if self.max_accel - self.min_accel <= 1000:
                    print(f"Converged. Min: {self.min_accel}, Max: {self.max_accel}")
                    sys.exit()
                else:
                    # Binary search
                    self.current_accel = 0.5 * (self.min_accel + self.max_accel)
                    # Round to nearest 500
                    self.current_accel = int(round(self.current_accel / 500) * 500)

        self.home_steps = None

        # Peak velocity is achieved at midpoint, unless max is reached
        peak_velocity = min(
            self.max_velocity,
            math.sqrt(self.current_accel * self.max_travel),
        )
        print(
            f"accel: {self.current_accel} mm/s^2, peak velocity: {peak_velocity:.0f} mm/s => ",
            end="",
            flush=True,
        )

        self.serial_write(
            self.GCODE.format(
                accel=self.current_accel,
                x=self.max_travel,
                feedrate=peak_velocity * 60,
            )
        )

    def handle_position(self, position, mcu_steps):
        if self.home_steps is None:
            if position <= 0.0:
                self.home_steps = mcu_steps
        else:
            if position <= 0.0:
                skipped_steps = mcu_steps - self.home_steps
                self.home_steps = mcu_steps
                if abs(skipped_steps) < self.FAIL_CRITERION:
                    self.pass_count += 1
                    print(f"PASSED #{self.pass_count}")
                else:
                    self.fail_count += 1
                    print(f"FAILED, skipped {skipped_steps} steps")
                self.iterate()

    def callback(self, bytes_raw: bytes):
        mcu_steps = None
        position = None
        strings = bytes_raw.decode().split("\n")
        for string in strings:
            match = self.REGEX_MCU_STEPS.match(string)
            if match:
                mcu_steps = int(match.group(1))
                continue
            match = self.REGEX_POSITION.match(string)
            if match:
                position = float(match.group(1))
                continue
        if position is not None and mcu_steps is not None:
            self.handle_position(position, mcu_steps)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress test stepper systems.")
    parser.add_argument(
        "--port_name",
        type=str,
        default=f"{Path.home()}/printer_data/comms/klippy.serial",
        help="Path to Klipper's psudo-serial port (default: ~/printer_data_comms/klippy.serial)",
    )
    parser.add_argument(
        "--max_travel",
        type=int,
        default=300,
        help="Maximum travel in mm (default: 300)",
    )
    parser.add_argument(
        "--max_velocity",
        type=int,
        default=1000,
        help="Maximum velocity in mm/s (default: 1000)",
    )
    args = parser.parse_args()

    stepper_stresser = StepperStressor(args.max_travel, args.max_velocity)

    serial_daemon = SerialDaemon(stepper_stresser.callback)
    serial_daemon.set_baudrate(230400)
    serial_daemon.set_port_name(args.port_name)
    serial_daemon.open_port()
    serial_daemon.start()
    while not serial_daemon.is_port_open():
        time.sleep(0.2)

    stepper_stresser.set_serial_write(serial_daemon.write_string)
    stepper_stresser.iterate()

    while True:
        if not serial_daemon.is_alive():
            serial_daemon.stop()
            break
        time.sleep(0.2)
