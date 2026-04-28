"""Tests for analytics_store persistence."""

from __future__ import annotations

from datetime import date, datetime

from mouse_jiggler import analytics_store


def test_record_nudge_and_runtime_roundtrip(monkeypatch, tmp_path) -> None:
    def _path() -> object:
        return tmp_path / "analytics.json"

    monkeypatch.setattr(analytics_store, "default_analytics_path", _path)

    analytics_store.record_nudge("circle", at=datetime(2026, 4, 28, 14, 30, 0))
    analytics_store.add_runtime_seconds(42.5, on_date=date(2026, 4, 28))

    days = analytics_store.load_days_copy()
    key = "2026-04-28"
    assert key in days
    assert days[key]["hourly_nudges"][14] == 1
    assert days[key]["pattern"]["circle"] == 1
    assert abs(days[key]["runtime_sec"] - 42.5) < 1e-6
