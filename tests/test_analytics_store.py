"""Tests for analytics_store persistence."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

from mouse_jiggler import analytics_store


def _use_tmp_store(monkeypatch, tmp_path):
    path = tmp_path / "analytics.json"
    monkeypatch.setattr(analytics_store, "default_analytics_path", lambda: path)
    return path


def test_record_nudge_and_runtime_roundtrip(monkeypatch, tmp_path) -> None:
    _use_tmp_store(monkeypatch, tmp_path)
    # Use a recent day so the 120-day retention window never prunes it.
    day = date.today() - timedelta(days=1)

    analytics_store.record_nudge("circle", at=datetime.combine(day, time(14, 30)))
    analytics_store.record_nudge("natural", at=datetime.combine(day, time(15, 0)))
    analytics_store.add_runtime_seconds(42.5, on_date=day)

    days = analytics_store.load_days_copy()
    key = day.isoformat()
    assert key in days
    assert days[key]["hourly_nudges"][14] == 1
    assert days[key]["hourly_nudges"][15] == 1
    assert days[key]["pattern"]["circle"] == 1
    assert days[key]["pattern"]["natural"] == 1
    assert abs(days[key]["runtime_sec"] - 42.5) < 1e-6


def test_load_days_copy_does_not_rewrite_unchanged_file(monkeypatch, tmp_path) -> None:
    path = _use_tmp_store(monkeypatch, tmp_path)
    analytics_store.add_runtime_seconds(5.0)
    before = analytics_store.data_signature()
    assert before is not None

    saves: list[object] = []
    monkeypatch.setattr(analytics_store, "_save", lambda *a, **k: saves.append(a))
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


def test_save_is_atomic_and_leaves_no_temp_file(monkeypatch, tmp_path) -> None:
    path = _use_tmp_store(monkeypatch, tmp_path)
    analytics_store.record_nudge("square")

    assert path.is_file()
    assert not (tmp_path / "analytics.json.tmp").exists()
    json.loads(path.read_text(encoding="utf-8"))


def test_data_signature_changes_after_write(monkeypatch, tmp_path) -> None:
    _use_tmp_store(monkeypatch, tmp_path)
    assert analytics_store.data_signature() is None
    analytics_store.add_runtime_seconds(1.0)
    first = analytics_store.data_signature()
    # Change the file size too, so the check does not depend on mtime resolution.
    analytics_store.add_runtime_seconds(12345.678)
    assert first is not None
    assert analytics_store.data_signature() != first
