import numpy as np
import pytest

from dino_shred.audio.clicks import ClickScheduler
from dino_shred.audio.detect import EnergyGate
from dino_shred.audio.engine import AudioEngine, DeviceNotFoundError, find_device
from dino_shred.rhythm.conductor import Conductor

SR, BS = 48000, 256


def make_engine() -> AudioEngine:
    cond = Conductor(t0=10.0, bpm=120.0)
    return AudioEngine(
        detector=EnergyGate(), scheduler=ClickScheduler(cond, sr=SR), input_channel=2
    )


def blocks(sig: np.ndarray) -> list[np.ndarray]:
    """Split mono signal into (BS, 2) stereo blocks with guitar on column 1."""
    out = []
    for i in range(0, len(sig) - BS + 1, BS):
        b = np.zeros((BS, 2), dtype=np.float32)
        b[:, 1] = sig[i : i + BS]
        out.append(b)
    return out


def test_onset_events_carry_adc_timestamps() -> None:
    eng = make_engine()
    sig = np.zeros(SR, dtype=np.float32)
    sig[24000 : 24000 + 2400] = 0.5  # step onset at +0.5 s
    outdata = np.zeros((BS, 2), dtype=np.float32)
    for i, block in enumerate(blocks(sig)):
        adc = 50.0 + i * BS / SR  # stream clock starts at 50.0
        eng._process(block, outdata, adc_time=adc, dac_time=adc + 0.01)
    events = eng.get_events()
    assert len(events) == 1
    assert abs(events[0].t - 50.5) <= 2 * BS / SR


def test_clicks_rendered_into_both_output_channels() -> None:
    eng = make_engine()
    indata = np.zeros((BS, 2), dtype=np.float32)
    outdata = np.ones((BS, 2), dtype=np.float32)  # uninitialized memory simulation
    # dac window [10.0, 10.0053) contains beat 0 of the conductor (t0=10.0)
    eng._process(indata, outdata, adc_time=9.99, dac_time=10.0)
    assert np.abs(outdata[:, 0]).max() > 0
    np.testing.assert_array_equal(outdata[:, 0], outdata[:, 1])
    assert outdata[0, 0] != 1.0  # buffer was cleared, not accumulated onto


def test_queue_overflow_drops_and_counts() -> None:
    eng = make_engine()
    eng.events.maxsize = 2
    sig_on = np.full(BS, 0.5, dtype=np.float32)
    sig_off = np.zeros(BS, dtype=np.float32)
    outdata = np.zeros((BS, 2), dtype=np.float32)
    t = 0.0
    for _ in range(5):  # 5 distinct onsets, queue holds 2
        # 1 hot block + 19 silent blocks = bursts ~107 ms apart (> 80 ms refractory),
        # with full re-arm (silence) between them -> exactly one event per burst.
        for sig in (sig_on,) + (sig_off,) * 19:
            block = np.zeros((BS, 2), dtype=np.float32)
            block[:, 1] = sig
            eng._process(block, outdata, adc_time=t, dac_time=t + 0.01)
            t += BS / SR
    assert eng.status.queue_drops == 3
    assert len(eng.get_events()) == 2


def test_peak_hold_take_and_reset() -> None:
    eng = make_engine()
    outdata = np.zeros((BS, 2), dtype=np.float32)
    block = np.zeros((BS, 2), dtype=np.float32)
    block[:, 1] = 0.25
    eng._process(block, outdata, adc_time=0.0, dac_time=0.01)
    assert eng.take_peak() == pytest.approx(0.25)
    assert eng.take_peak() == 0.0  # reset after read (silence watchdog polls this)


def test_find_device_raises_with_device_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    import dino_shred.audio.engine as engine_mod

    monkeypatch.setattr(
        engine_mod.sd,
        "query_devices",
        lambda: [{"name": "MacBook Pro Microphone", "max_input_channels": 1}],
    )
    with pytest.raises(DeviceNotFoundError, match="MacBook Pro Microphone"):
        find_device("M-Track")
