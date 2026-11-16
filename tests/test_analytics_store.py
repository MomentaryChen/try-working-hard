"""Tests for analytics_store persistence."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

import pytest

from mouse_jiggler import analytics_store


@pytest.fixture(autouse=True)
def _fresh_cache():
    analytics_store._reset_cache()
    yield
    analytics_store._reset_cache()


def _use_tmp_store(monkeypatch, tmp_path):
    path = tmp_path / "analytics.json"
    monkeypatch.setattr(analytics_store, "default_analytics_path", lambda: path)
    return path


def _use_fake_clock(monkeypatch, start: float = 1000.0) -> list[float]:
    clock = [start]
    monkeypatch.setattr(analytics_store, "_monotonic", lambda: clock[0])
    return clock


def test_record_nudge_and_runtime_roundtrip(monkeypatch, tmp_path) -> None:
    path = _use_tmp_store(monkeypatch, tmp_path)
    # Use a recent day so the 120-day retention window never prunes it.
    day = date.today() - timedelta(days=1)

    analytics_store.record_nudge("circle", at=datetime.combine(day, time(14, 30)))
    analytics_store.record_nudge("natural", at=datetime.combine(day, time(15, 0)))
    analytics_store.add_runtime_seconds(42.5, on_date=day)
    assert analytics_store.flush() is True

    # Reload from disk to prove the flushed file holds everything.
    analytics_store._reset_cache()
    days = analytics_store.load_days_copy()
    key = day.isoformat()
    assert key in days
    assert days[key]["hourly_nudges"][14] == 1
    assert days[key]["hourly_nudges"][15] == 1
    assert days[key]["pattern"]["circle"] == 1
    assert days[key]["pattern"]["natural"] == 1
    assert abs(days[key]["runtime_sec"] - 42.5) < 1e-6
    assert path.is_file()


def test_increments_are_batched_until_interval(monkeypatch, tmp_path) -> None:
    path = _use_tmp_store(monkeypatch, tmp_path)
    clock = _use_fake_clock(monkeypatch)
    saves: list[object] = []
    real_save = analytics_store._save

    def _counting_save(*a, **k):
        saves.append(a)
        return real_save(*a, **k)

    monkeypatch.setattr(analytics_store, "_save", _counting_save)

    for _ in range(5):
        analytics_store.record_nudge("square")
        analytics_store.add_runtime_seconds(1.0)
        clock[0] += 1.0
    assert saves == []
    assert not path.exists()

    clock[0] += analytics_store.FLUSH_INTERVAL_SEC
    analytics_store.record_nudge("square")
    assert len(saves) == 1
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    today = on_disk["days"][date.today().isoformat()]
    assert today["pattern"]["square"] == 6
    assert abs(today["runtime_sec"] - 5.0) < 1e-6


def test_load_days_copy_includes_pending_increments(monkeypatch, tmp_path) -> None:
    path = _use_tmp_store(monkeypatch, tmp_path)
    _use_fake_clock(monkeypatch)

    analytics_store.record_nudge("circle")
    analytics_store.add_runtime_seconds(7.0)

    assert not path.exists()
    days = analytics_store.load_days_copy()
    today = days[date.today().isoformat()]
    assert today["pattern"]["circle"] == 1
    assert abs(today["runtime_sec"] - 7.0) < 1e-6


def test_load_days_copy_returns_independent_copy(monkeypatch, tmp_path) -> None:
    _use_tmp_store(monkeypatch, tmp_path)
    analytics_store.record_nudge("circle")
    snapshot = analytics_store.load_days_copy()
    analytics_store.record_nudge("circle")
    key = date.today().isoformat()
    assert snapshot[key]["pattern"]["circle"] == 1
    assert analytics_store.load_days_copy()[key]["pattern"]["circle"] == 2


def test_flush_writes_pending_and_is_noop_when_clean(monkeypatch, tmp_path) -> None:
    path = _use_tmp_store(monkeypatch, tmp_path)
    _use_fake_clock(monkeypatch)
    analytics_store.add_runtime_seconds(3.0)
    assert not path.exists()

    assert analytics_store.flush() is True
    assert path.is_file()
    assert not (tmp_path / "analytics.json.tmp").exists()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert abs(on_disk["days"][date.today().isoformat()]["runtime_sec"] - 3.0) < 1e-6

    saves: list[object] = []
    monkeypatch.setattr(analytics_store, "_save", lambda *a, **k: saves.append(a) or True)
    assert analytics_store.flush() is True
    assert saves == []


def test_failed_flush_keeps_data_pending(monkeypatch, tmp_path) -> None:
    _use_tmp_store(monkeypatch, tmp_path)
    analytics_store.add_runtime_seconds(3.0)
    monkeypatch.setattr(analytics_store, "_save", lambda *a, **k: False)
    assert analytics_store.flush() is False

    saves: list[object] = []
    monkeypatch.setattr(analytics_store, "_save", lambda *a, **k: saves.append(a) or True)
    assert analytics_store.flush() is True
    assert len(saves) == 1


def test_load_days_copy_does_not_rewrite_unchanged_file(monkeypatch, tmp_path) -> None:
    path = _use_tmp_store(monkeypatch, tmp_path)
    analytics_store.add_runtime_seconds(5.0)
    analytics_store.flush()
    before = analytics_store.data_signature()

    saves: list[object] = []
    monkeypatch.setattr(analytics_store, "_save", lambda *a, **k: saves.append(a) or True)
    analytics_store.load_days_copy()
    analytics_store.load_days_copy()

    assert saves == []
    assert analytics_store.data_signature() == before
    assert path.is_file()


def test_load_days_copy_prunes_stale_days_and_persists(monkeypatch, tmp_path) -> None:
    path = _use_tmp_store(monkeypatch, tmp_path)
    stale = (date.today() - timedelta(days=400)).isoformat()
    fresh = date.today().isoformat()
    path.write_text(
        json.dumps({"version": 1, "days": {stale: {"runtime_sec": 1.0}, fresh: {"runtime_sec": 2.0}}}),
        encoding="utf-8",
    )

    days = analytics_store.load_days_copy()

    assert set(days) == {fresh}
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert set(on_disk["days"]) == {fresh}


def test_prune_runs_at_most_once_per_day(monkeypatch, tmp_path) -> None:
    _use_tmp_store(monkeypatch, tmp_path)
    today = [date(2026, 6, 1)]
    monkeypatch.setattr(analytics_store, "_today", lambda: today[0])
    calls: list[int] = []
    real_prune = analytics_store._prune

    def _counting_prune(days):
        calls.append(1)
        return real_prune(days)

    monkeypatch.setattr(analytics_store, "_prune", _counting_prune)

    for _ in range(3):
        analytics_store.add_runtime_seconds(1.0)
        analytics_store.load_days_copy()
    assert len(calls) == 1

    today[0] = date(2026, 6, 2)
    analytics_store.add_runtime_seconds(1.0)
    analytics_store.load_days_copy()
    assert len(calls) == 2


def test_data_signature_changes_on_pending_increment(monkeypatch, tmp_path) -> None:
    path = _use_tmp_store(monkeypatch, tmp_path)
    _use_fake_clock(monkeypatch)
    first = analytics_store.data_signature()
    assert analytics_store.data_signature() == first

    analytics_store.add_runtime_seconds(1.0)
    second = analytics_store.data_signature()
    assert second != first
    assert not path.exists()

    # Flushing writes the same data, so the signature must not change.
    analytics_store.flush()
    assert analytics_store.data_signature() == second
