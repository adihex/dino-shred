"""Obstacle spawner: schedules obstacles onto future beats (spec 3.7).

Difficulty ramps by density — every 4th beat, then every 2nd, then every beat.
Spawning looks `horizon_s` ahead so obstacles enter from off-screen right.
"""

import random

from dino_shred.game.objects import Obstacle
from dino_shred.rhythm.conductor import Conductor


class Spawner:
    def __init__(
        self,
        conductor: Conductor,
        first_beat: int,
        horizon_s: float = 3.0,
        seed: int | None = None,
    ) -> None:
        self.conductor = conductor
        self.first_beat = first_beat
        self.horizon_s = horizon_s
        self._rng = random.Random(seed)
        self._next_beat = first_beat

    def density(self, beat_n: int) -> int:
        played = beat_n - self.first_beat
        if played < 16:
            return 4
        if played < 48:
            return 2
        return 1

    def update(self, t: float) -> list[Obstacle]:
        spawned: list[Obstacle] = []
        while self.conductor.beat_time(self._next_beat) < t + self.horizon_s:
            n = self._next_beat
            self._next_beat += 1
            if (n - self.first_beat) % self.density(n) == 0:
                spawned.append(Obstacle(n, self.conductor, self._rng.randint(0, 1)))
        return spawned


__all__ = ["Spawner"]
