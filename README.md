# HP203B-Library
MicroPython library for HP203B barometric pressure sensor. Written to be used on [Riscfruit Pico2 Expansion Card](https://github.com/riscfruit/Pico2-Expansion-Card) to control [HP203B Sensor Module](https://github.com/riscfruit/HP203B-I2C-Sensor).

### Installation
Install via pip inside your project directory:
```python
pip install hp203b-library
```

You can easily upload the library to your RP2040/RP2350 based embedded device (Riscfruit Pico2 Expansion Card, Raspberry Pi Pico, etc) by creating a lib directory inside and copying it there.

### Usage
Import the library and initialize sensor and read all values:

```python
from hp203b import HP203B, OSR_1024

sensor = HP203B(sda=26, scl=27, i2c_id=1, freq=100000, osr=OSR_1024)
t, p, alt = sensor.read_all()
```

See [hp203b-sensor-reading.py](examples/hp203b-sensor-reading.py) for a loop sensor reading example.

### Licensing
Copyright (c) 2026, Riscfruit Laboratory. This software is developed and distributed with [GPL 3.0](LICENSE).
