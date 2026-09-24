import numpy as np

from dino_shred.audio.detect import EnergyGate, OnsetEvent

SR, HOP = 48000, 256


def synth_plucks(onsets_s: list[float], dur_s: float = 2.0, amp: float = 0.5) -> np.ndarray:
    """Decaying 110 Hz bursts at given onset times — a crude palm-muted chug."""
    sig = np.zeros(int(SR * dur_s), dtype=np.float32)
    t = np.arange(int(SR * 0.30), dtype=np.float32) / SR
    burst = (amp * np.sin(2 * np.pi * 110.0 * t) * np.exp(-t / 0.05)).astype(np.float32)
    for on in onsets_s:
        i = int(on * SR)
        sig[i : i + len(burst)] += burst[: len(sig) - i]
    return sig


def run_detector(gate: EnergyGate, sig: np.ndarray) -> list[OnsetEvent]:
    events = []
    for i in range(0, len(sig) - HOP + 1, HOP):
        ev = gate.process(sig[i : i + HOP], i / SR)
        if ev is not None:
            events.append(ev)
    return events


def test_silence_yields_nothing() -> None:
    gate = EnergyGate()
    assert run_detector(gate, np.zeros(SR, dtype=np.float32)) == []


def test_detects_each_pluck_once_within_two_hops() -> None:
    truth = [0.25, 0.75, 1.25, 1.75]
    events = run_detector(EnergyGate(), synth_plucks(truth))
    assert len(events) == 4
    for ev, expected in zip(events, truth, strict=True):
        assert abs(ev.t - expected) <= 2 * HOP / SR
        assert ev.strength > 0
        assert ev.detector == "energy"


def test_hysteresis_blocks_retrigger_during_decay() -> None:
    # One pluck with a slow decay must produce exactly one event.
    events = run_detector(EnergyGate(), synth_plucks([0.5], dur_s=1.5))
    assert len(events) == 1


def test_refractory_merges_double_hit() -> None:
    # Two hits 40 ms apart (< 80 ms refractory) -> one event.
    events = run_detector(EnergyGate(), synth_plucks([0.5, 0.54]))
    assert len(events) == 1
