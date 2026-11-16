from __future__ import annotations

import os
import sys

import pytest

from mouse_jiggler import single_instance


@pytest.mark.skipif(sys.platform != "win32", reason="Windows named kernel objects")
def test_second_acquire_signals_first_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    # Unique names so the test never talks to a real running app.
    suffix = f"{os.getpid()}-{id(monkeypatch)}"
    monkeypatch.setattr(single_instance, "MUTEX_NAME", f"Local\\twh-test-mutex-{suffix}")
    monkeypatch.setattr(single_instance, "SHOW_EVENT_NAME", f"Local\\twh-test-event-{suffix}")

    first = single_instance.acquire()
    assert first is not None
    assert first.show_requested() is False

    assert single_instance.acquire() is None
    assert first.show_requested() is True
    # Auto-reset: one request is reported once.
    assert first.show_requested() is False


def test_empty_guard_never_requests_show() -> None:
    assert single_instance.InstanceGuard().show_requested() is False
