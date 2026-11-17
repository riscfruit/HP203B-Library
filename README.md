# HP203B-Library
MicroPython library for HP203B barometric pressure sensor. Written to be used on [Riscfruit Pico2 Expansion Card](https://github.com/riscfruit/Pico2-Expansion-Card) to control [HP203B Sensor Module](https://github.com/riscfruit/HP203B-I2C-Sensor).

### Installation
Install via pip inside your project directory:
```bash
pip install hp203b-library
```

You can easily upload the library to your RP2040/RP2350 based embedded device (Riscfruit Pico2 Expansion Card, Raspberry Pi Pico, etc) by creating a lib directory inside and copying it there.

### Usage
Import the library and initialize sensor and read all values:

```python
import time
from hp203b import HP203B, OSR_1024

sensor = HP203B(sda=16, scl=17, i2c_id=0, freq=100000, osr=OSR_1024)
print("HP203B at 0x%02X" % sensor.addr)

while True:
    t, p, alt = sensor.read_all()  # sea_level_hpa=... for local calibration
    print("Temp: %.2f C   Pressure: %.2f hPa   Altitude: %.1f m" % (t, p, alt))
    time.sleep(1)
```

For diagnosis, run the following:
```python
from hp203b import diagnose; diagnose(16, 17, 0)
```

See [hp203b-sensor-reading.py](examples/hp203b-sensor-reading.py) for loop sensor reading example.

### Licensing
Copyright (c) 2026, Riscfruit Laboratory. This software is developed and distributed with [GPL 3.0](LICENSE).
