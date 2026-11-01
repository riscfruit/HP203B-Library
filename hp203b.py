"""
hp203b.py - MicroPython library for HP203B barometric pressure sensor.
Intended for use with Riscfruit Pico2 Expansion Card to control HP203B sensor module.

Licensed under GPL-3.0

Copyright (c) 2026, Riscfruit Laboratory
All rights reserved.
"""

import time
from machine import I2C, Pin

__version__ = "1.0.0"

# Oversampling (decimation) rates
OSR_4096 = 0
OSR_2048 = 1
OSR_1024 = 2
OSR_512 = 3
OSR_256 = 4
OSR_128 = 5

# Conversion channels
CH_PT = 0x00  # pressure + temperature
CH_T = 0x02   # temperature only

# Datasheet conversion times (T+P) in ms, plus ~10% margin, indexed by OSR_*
_CONV_MS = (145, 75, 38, 20, 11, 7)

# Commands
_CMD_SOFT_RST = 0x06
_CMD_ADC_CVT = 0x40
_CMD_READ_PT = 0x10
_CMD_READ_AT = 0x11
_CMD_READ_P = 0x30
_CMD_READ_A = 0x31
_CMD_READ_T = 0x32
_CMD_READ_REG = 0x80
_CMD_WRITE_REG = 0xC0



class HP203BError(OSError):
    # Raised when the sensor cannot be reached even after all recovery steps.


def _u20(b, o):
    return ((b[o] & 0x0F) << 16) | (b[o + 1] << 8) | b[o + 2]


def _s20(b, o):
    v = _u20(b, o)
    return v - 0x100000 if v & 0x80000 else v


class HP203B:
    def __init__(self, i2c=None, sda=None, scl=None, i2c_id=1, freq=100000,
                 addr=None, osr=OSR_4096, retries=5, timeout_us=100000,
                 reset=True):
        # Fill i2c (channel), sda, scl or it auto-detecs
        # addr=None auto-detects 0x76 (CSB low) or 0x77 (CSB high).
    
        self._sda = sda
        self._scl = scl
        self._id = i2c_id
        self._freq = freq
        self._timeout = timeout_us
        self._retries = max(1, retries)
        self._osr = osr
        self._rs = None  # None = unknown, True = repeated START works, False = use STOP
        self._can_recover = sda is not None and scl is not None
        self.i2c = i2c
        self.addr = addr

        if self.i2c is None:
            if not self._can_recover:
                raise ValueError("pass an i2c object or both sda and scl")
            self._bus_recover()  # also clears any junk left by a previous crashed run
        if self.addr is None:
            self.addr = self._detect()
        if reset:
            self.reset()

    # Bus handling
    def _open_i2c(self):
        if self.i2c is not None:
            try:
                self.i2c.deinit()
            except Exception:
                pass
        try:
            self.i2c = I2C(self._id, sda=Pin(self._sda), scl=Pin(self._scl),
                           freq=self._freq, timeout=self._timeout)
        except TypeError:  # port without a timeout argument
            self.i2c = I2C(self._id, sda=Pin(self._sda), scl=Pin(self._scl),
                           freq=self._freq)

    def _bus_recover(self):
        # Free a bus held by a half-finished transfer, then re-create the I2C object.
        if not self._can_recover:
            return
        if self.i2c is not None:
            try:
                self.i2c.deinit()
            except Exception:
                pass
        scl = Pin(self._scl, Pin.OPEN_DRAIN, Pin.PULL_UP, value=1)
        sda = Pin(self._sda, Pin.OPEN_DRAIN, Pin.PULL_UP, value=1)
        time.sleep_us(20)
        # Clock out up to 9 pulses until the slave releases SDA
        for _ in range(9):
            if sda.value():
                break
            scl.value(0)
            time.sleep_us(10)
            scl.value(1)
            time.sleep_us(10)
        # Manual STOP condition: SDA low -> high while SCL high
        sda.value(0)
        time.sleep_us(10)
        scl.value(1)
        time.sleep_us(10)
        sda.value(1)
        time.sleep_us(20)
        self._open_i2c()

    def _recover(self, attempt):
        # Escalating recovery used between retries.
        time.sleep_ms(min(2 << attempt, 50))
        if attempt >= 1:
            self._bus_recover()
        if attempt >= 2:
            try:
                self.i2c.writeto(self.addr, bytes([_CMD_SOFT_RST]))
                time.sleep_ms(20)
            except OSError:
                pass

    def _retry(self, fn):
        last = None
        for attempt in range(self._retries):
            try:
                return fn()
            except OSError as e:
                last = e
                self._recover(attempt)
        raise HP203BError(
            "HP203B not responding after %d tries (last error: %r). Check wiring, "
            "3.3V, pull-ups (4.7k), CSB/address, and pin numbers." % (self._retries, last))

    def _detect(self):
        def go():
            found = self.i2c.scan()
            for a in (0x76, 0x77):
                if a in found:
                    return a
            raise OSError(19)  # ENODEV -> triggers recovery/retry
        return self._retry(go)

    # Raw transactions (single attempt, no recovery)
    def _read_cmd_once(self, cmd, n):
        order = (True, False) if (self._rs is None or self._rs) else (False, True)
        last = None
        for style in order:
            try:
                if style:
                    self.i2c.writeto(self.addr, bytes([cmd]), False)  # repeated START
                else:
                    self.i2c.writeto(self.addr, bytes([cmd]))         # STOP, then START
                data = self.i2c.readfrom(self.addr, n)
                self._rs = style
                return data
            except OSError as e:
                last = e
        raise last

    def _read_cmd(self, cmd, n, polls=4):
        # Write a read-command and fetch n bytes; polls briefly in case the chip is busy.
        last = None
        for _ in range(polls):
            try:
                return self._read_cmd_once(cmd, n)
            except OSError as e:
                last = e
                time.sleep_ms(2)
        raise last

    # Registers / reset
    def read_reg(self, reg):
        return self._retry(lambda: self._read_cmd(_CMD_READ_REG | reg, 1)[0])

    def write_reg(self, reg, value):
        self._retry(lambda: self.i2c.writeto(self.addr, bytes([_CMD_WRITE_REG | reg, value])))

    def reset(self):
        # Soft reset, then wait a fixed time.
        self._retry(lambda: self.i2c.writeto(self.addr, bytes([_CMD_SOFT_RST])))
        time.sleep_ms(50)

    # Measurements
    @property
    def osr(self):
        return self._osr

    @osr.setter
    def osr(self, value):
        if not 0 <= value <= 5:
            raise ValueError("osr must be OSR_4096 .. OSR_128 (0..5)")
        self._osr = value

    def _measure(self, chnl, read_cmd, n):
        cvt = _CMD_ADC_CVT | (self._osr << 2) | chnl

        def go():
            self.i2c.writeto(self.addr, bytes([cvt]))
            time.sleep_ms(_CONV_MS[self._osr])
            return self._read_cmd(read_cmd, n)

        # The whole convert+read sequence is retried together, so a recovery
        # (which may reset the chip) never leaves us reading a lost conversion.
        return self._retry(go)

    def temperature(self):
        # Temperature in degrees Celsius."""
        d = self._measure(CH_T, _CMD_READ_T, 3)
        return _s20(d, 0) / 100.0

    def pressure(self):
        # Pressure in hPa (mbar).
        d = self._measure(CH_PT, _CMD_READ_P, 3)
        return _u20(d, 0) / 100.0

    def read(self):
        # One conversion, returns (temperature_C, pressure_hPa).
        d = self._measure(CH_PT, _CMD_READ_PT, 6)
        return _s20(d, 0) / 100.0, _u20(d, 3) / 100.0

    def altitude(self, sea_level_hpa=1013.25):
        # Altitude in metres from pressure, using the standard barometric formula.
        # Pass your local sea-level pressure for better accuracy.
        p = self.pressure()
        return 44330.0 * (1.0 - (p / sea_level_hpa) ** 0.1903)

    def read_all(self, sea_level_hpa=1013.25):
        # One conversion, returns (temperature_C, pressure_hPa, altitude_m).
        t, p = self.read()
        return t, p, 44330.0 * (1.0 - (p / sea_level_hpa) ** 0.1903)

    def device_altitude(self):
        # Altitude in metres as computed by the chip itself (fixed 1013.25 hPa reference).
        d = self._measure(CH_PT, _CMD_READ_AT, 6)
        return _s20(d, 3) / 100.0

    def deinit(self):
        try:
            self.i2c.deinit()
        except Exception:
            pass


def diagnose(sda=26, scl=27, i2c_id=1, freq=100000):
    # Print a quick health report for the bus. Run this when nothing works.
    s = Pin(sda, Pin.IN, Pin.PULL_UP)
    c = Pin(scl, Pin.IN, Pin.PULL_UP)
    time.sleep_ms(5)
    print("Idle levels  SDA=%d SCL=%d  (both should be 1; 0 = stuck/shorted line)"
          % (s.value(), c.value()))
    try:
        dev = HP203B(sda=sda, scl=scl, i2c_id=i2c_id, freq=freq, reset=False, retries=2)
    except OSError as e:
        print("No sensor found")
        return
    print("Found HP203B at 0x%02X" % dev.addr)
    try:
        dev.reset()
        t, p = dev.read()
        print("Read OK: %.2f C, %.2f hPa (read style: %s)"
              % (t, p, "repeated START" if dev._rs else "STOP+START"))
    except OSError as e:
        print("Sensor is on the bus but measurement failed:", e)
