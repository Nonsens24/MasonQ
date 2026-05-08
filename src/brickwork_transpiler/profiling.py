"""Small profiling helpers for scientific workflows."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class TimedResult(Generic[T]):
    value: T
    seconds: float


def timed(call: Callable[[], T]) -> TimedResult[T]:
    start = perf_counter()
    value = call()
    return TimedResult(value=value, seconds=perf_counter() - start)

