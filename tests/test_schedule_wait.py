"""Tests for the worker's schedule wait (``RunnerMixin._wait_for_schedule_if_needed``)."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from mouse_jiggler import ui_runner
from mouse_jiggler.ui_runner import RunnerMixin

_VALID = object()


@pytest.fixture
def stub(monkeypatch):
    """A minimal app stand-in whose schedule is outside the window until told otherwise."""
    state = SimpleNamespace(in_window=False, spec=_VALID, exited=0, waits_begun=0)
    fake_schedule = SimpleNamespace(
        is_within_schedule=lambda _now, _spec: state.in_window,
        next_schedule_start=lambda now, _spec: now + timedelta(hours=8),
    )
    monkeypatch.setattr(ui_runner, "schedule_window", fake_schedule)

    def _exit_wait() -> None:
        state.exited += 1

    def _wait_begin(_resume_at: datetime) -> None:
        state.waits_begun += 1

    app = SimpleNamespace(
        _run_schedule_window=True,
        _stop=threading.Event(),
        _schedule_changed=threading.Event(),
        _build_schedule_spec=lambda: state.spec,
        _ui_invoke=lambda fn: fn(),
        _ui_schedule_wait_begin=_wait_begin,
        _ui_exit_schedule_wait=_exit_wait,
        _log=lambda _msg: None,
        _t=lambda key, **_kw: key,
    )
    return app, state


def _start_wait(app) -> tuple[threading.Thread, list[bool]]:
    result: list[bool] = []
    t = threading.Thread(
        target=lambda: result.append(RunnerMixin._wait_for_schedule_if_needed(app)),
        daemon=True,
    )
    t.start()
    return t, result


def _wait_until(cond, timeout: float = 2.0) -> None:
    end = time.monotonic() + timeout
    while not cond():
        assert time.monotonic() < end, "condition not reached in time"
        time.sleep(0.01)


def test_schedule_change_wakes_wait_immediately(stub) -> None:
    app, state = stub
    t, result = _start_wait(app)
    _wait_until(lambda: state.waits_begun == 1)

    state.in_window = True
    app._schedule_changed.set()
    t.join(timeout=1.0)

    assert not t.is_alive()
    assert result == [True]
    assert state.exited == 1


def test_stop_wakes_wait_immediately(stub) -> None:
    app, state = stub
    t, result = _start_wait(app)
    _wait_until(lambda: state.waits_begun == 1)

    app._stop.set()
    app._schedule_changed.set()
    t.join(timeout=1.0)

    assert not t.is_alive()
    assert result == [False]


def test_invalid_schedule_mid_wait_keeps_waiting(stub) -> None:
    app, state = stub
    t, result = _start_wait(app)
    _wait_until(lambda: state.waits_begun == 1)

    state.spec = None
    app._schedule_changed.set()
    time.sleep(0.1)
    assert t.is_alive()
    assert result == []

    state.spec = _VALID
    state.in_window = True
    app._schedule_changed.set()
    t.join(timeout=1.0)

    assert not t.is_alive()
    assert result == [True]


def test_switching_schedule_off_ends_wait(stub) -> None:
    app, state = stub
    t, result = _start_wait(app)
    _wait_until(lambda: state.waits_begun == 1)

    app._run_schedule_window = False
    app._schedule_changed.set()
    t.join(timeout=1.0)

    assert not t.is_alive()
    assert result == [True]
    assert state.exited == 1


def test_invalid_schedule_at_start_returns_false(stub) -> None:
    app, state = stub
    state.spec = None
    assert RunnerMixin._wait_for_schedule_if_needed(app) is False
