"""The audio engine: ONE full-duplex stream, the master clock of the game (ADR 0002).

The PortAudio callback runs on a real-time thread. Rules inside _process:
no locks, no I/O, no prints, no unbounded work. Small numpy temporaries are
accepted pragmatically (Python-level, bounded by blocksize); events cross to
the game thread through a bounded non-blocking queue.

PortAudio swallows callback exceptions, so liveness is exposed via
EngineStatus.last_callback_time (the game shows an "audio dead" banner if
it goes stale) and silent input is detected by polling take_peak().
"""

import queue
import sys
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import sounddevice as sd

from dino_shred.audio.clicks import ClickScheduler
from dino_shred.audio.detect import EnergyGate, OnsetEvent


class DeviceNotFoundError(RuntimeError):
    pass


def find_device(name_substring: str = "M-Track") -> int:
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if (
            name_substring.lower() in dev["name"].lower()
            and dev["max_input_channels"] >= 2
        ):
            return i
    listing = "\n".join(f"  [{i}] {d['name']}" for i, d in enumerate(devices))
    raise DeviceNotFoundError(
        f"No input device matching {name_substring!r}. Available devices:\n{listing}\n"
        "Plug in the interface, or pass --device <index> / --keyboard-only."
    )


@dataclass
class EngineStatus:
    callbacks: int = 0
    xruns: int = 0
    queue_drops: int = 0
    last_callback_time: float = 0.0
    peak_hold: float = field(default=0.0)


class AudioEngine:
    def __init__(
        self,
        detector: EnergyGate,
        scheduler: ClickScheduler | None,
        device: int | None = None,
        input_channel: int = 2,
        samplerate: int = 48000,
        blocksize: int = 256,
    ) -> None:
        self.detector = detector
        self.scheduler = scheduler
        self.device = device
        self.input_channel = input_channel  # 1-based; M-Track instrument input is 2
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.events: queue.Queue[OnsetEvent] = queue.Queue(maxsize=64)
        self.status = EngineStatus()
        self._mono_out = np.zeros(blocksize, dtype=np.float32)
        self._stream: sd.Stream | None = None

    # -- callback core (hardware-free testable) --------------------------------

    def _process(
        self,
        indata: np.ndarray,
        outdata: np.ndarray,
        adc_time: float,
        dac_time: float,
    ) -> None:
        outdata[:] = 0.0  # duplex outdata is uninitialized memory: always clear
        if self.scheduler is not None:
            self._mono_out[:] = 0.0
            self.scheduler.render(dac_time, self._mono_out)
            outdata[:, 0] = self._mono_out
            outdata[:, 1] = self._mono_out

        frame = indata[:, self.input_channel - 1]
        peak = float(np.abs(frame).max()) if len(frame) else 0.0
        self.status.peak_hold = max(self.status.peak_hold, peak)

        event = self.detector.process(frame, adc_time)
        if event is not None:
            try:
                self.events.put_nowait(event)
            except queue.Full:
                self.status.queue_drops += 1

        self.status.callbacks += 1
        self.status.last_callback_time = dac_time

    def _callback(
        self,
        indata: np.ndarray,
        outdata: np.ndarray,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        if status:
            self.status.xruns += 1
        self._process(
            indata,
            outdata,
            time_info.inputBufferAdcTime,
            time_info.outputBufferDacTime,
        )

    # -- lifecycle --------------------------------------------------------------

    def start(self) -> None:
        device = self.device if self.device is not None else find_device()
        extra = (
            sd.CoreAudioSettings(change_device_parameters=True)
            if sys.platform == "darwin"
            else None
        )
        self._stream = sd.Stream(
            device=(device, device),
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            dtype="float32",
            channels=(2, 2),
            latency="low",
            extra_settings=extra,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    @property
    def time(self) -> float:
        if self._stream is None:
            raise RuntimeError("engine not started")
        return self._stream.time

    # -- game-thread helpers ------------------------------------------------------

    def get_events(self) -> list[OnsetEvent]:
        out: list[OnsetEvent] = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                return out

    def take_peak(self) -> float:
        """Return and reset the peak input level (silence-watchdog poll)."""
        peak = self.status.peak_hold
        self.status.peak_hold = 0.0
        return peak


__all__ = ["AudioEngine", "DeviceNotFoundError", "EngineStatus", "find_device"]
