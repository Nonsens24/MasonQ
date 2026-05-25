"""Small progress-reporting helper for long MasonQ operations."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from time import perf_counter
from typing import Union

ProgressSink = Union[bool, Callable[[str], None], None]


class ProgressReporter:
    """Emit concise progress messages to stdout or a user-supplied callback."""

    def __init__(self, sink: ProgressSink = False) -> None:
        self._sink = sink

    @property
    def enabled(self) -> bool:
        return bool(self._sink)

    def emit(self, message: str) -> None:
        if not self._sink:
            return
        text = f"[MasonQ] {message}"
        if callable(self._sink):
            self._sink(text)
        else:
            print(text, flush=True)

    @contextmanager
    def step(self, message: str, done: str = "done"):
        self.emit(message)
        start = perf_counter()
        try:
            yield
        except Exception:
            elapsed = perf_counter() - start
            self.emit(f"{message} failed after {elapsed:.2f}s")
            raise
        else:
            elapsed = perf_counter() - start
            self.emit(f"{done} ({elapsed:.2f}s)")
