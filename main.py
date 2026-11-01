import time
from hp203b import HP203B, OSR_1024
# from hp203b import diagnose; diagnose(26, 27, 1)   # uncomment if nothing responds

sensor = HP203B(sda=26, scl=27, i2c_id=1, freq=100000, osr=OSR_1024)
print("HP203B at 0x%02X" % sensor.addr)

while True:
    t, p, alt = sensor.read_all()  # sea_level_hpa=... for local calibration
    print("Temp: %.2f C   Pressure: %.2f hPa   Altitude: %.1f m" % (t, p, alt))
    time.sleep(1)
