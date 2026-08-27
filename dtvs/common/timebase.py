from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Rational:
    num: int
    den: int

    def __post_init__(self) -> None:
        if self.den <= 0:
            raise ValueError("denominator must be positive")
        if self.num < 0:
            raise ValueError("numerator must be non-negative")

    def as_fraction(self) -> Fraction:
        return Fraction(self.num, self.den)


def frames_for_seconds(seconds: int, fps_num: int, fps_den: int) -> int:
    frames = Fraction(seconds * fps_num, fps_den)
    if frames.denominator != 1:
        raise ValueError("duration does not resolve to an integer frame count")
    return frames.numerator

