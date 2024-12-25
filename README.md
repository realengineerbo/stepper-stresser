# Stepper Stresser

## Introduction

The stepper stresser script works with [Klipper](https://www.klipper3d.org/) to determine the maximum acceleration and velocity of a stepper system.

See [this video](https://youtu.be/ecmG-Qz5V3g?si=bg65TfaQ9zB4BXiS) for an example application of this script.

The script pipes gcode to Klipper via the pseudo-serial port, commanding the x-axis to home, move and home again. At each stage, the `GET_POSITION` gcode is used to obtain the current position and MCU step count.

The acceleration (and velocity) of the moves progressively get faster, with the intentional of inducing a failure.

The difference in MCU step counts after the first and second homing is then used to determine if the stepper has skipped sufficient steps to qualify as a failure.

Once a failure is detected, a binary search is performed to find the maximum "safe" acceleration and velocity values.

## Setup

Ensure Klipper and your motion system is configured. At minimum, you need:

* x-axis with endstop at the 0 position
* Configured the acceleration and velocity limits greater than test intended test values

[`venv`](https://docs.python.org/3/library/venv.html) is recommended, but not necessary.

After setting up and activating `venv`, install the dependencies:

```shell
pip install -r requirements.txt
```

## Usage

The main script accepts three optional arguments:

* `--port_name`: Path to Klipper's psudo-serial port (default: ~/printer_data_comms/klippy.serial)
* `--max_travel`: Maximum travel in mm (default: 300)
* `--max_velocity`: Maximum velocity in mm/s (default: 1000)

Examples:

```shell
python main.py # Run with default port name, 300mm max. travel, 1000mm/s max. velocity
python main.py --max_travel 50 --max_velocity 2000 # Run with default port name, 50mm max. travel, 2000mm/s max. velocity
```