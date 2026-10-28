import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import analysis as an  # noqa: E402


@pytest.fixture
def synthetic(monkeypatch):
    """Two target slots on Jan 2; three forecast vintages for the first slot."""
    t = pd.Timestamp("2026-01-02 12:00", tz="UTC")
    actuals = pd.DataFrame({"startTime": [t, t + pd.Timedelta(minutes=30)], "generation": [1000.0, 1100.0]})
    fc = pd.DataFrame(
        {
            "startTime": [t, t, t, t + pd.Timedelta(minutes=30)],
            "publishTime": pd.to_datetime(
                ["2026-01-01 06:00", "2026-01-01 08:00", "2026-01-01 10:00", "2026-01-01 08:00"], utc=True
            ),
            "generation": [900.0, 950.0, 1050.0, 1000.0],
        }
    )
    for df, cols in ((actuals, ["startTime"]), (fc, ["startTime", "publishTime"])):
        for c in cols:
            df[c] = df[c].astype(an.UTC_NS)
    monkeypatch.setattr(an, "load_data", lambda: (actuals, fc))


def test_uses_latest_forecast_before_cutoff(synthetic):
    df = an.day_ahead_view(cutoff_hour=9)  # cutoff = Jan 1 09:00 -> 08:00 vintage wins, 10:00 is too late
    assert df.iloc[0]["forecast"] == 950.0
    assert df.iloc[0]["error"] == 50.0


def test_later_cutoff_sees_newer_forecast(synthetic):
    assert an.day_ahead_view(cutoff_hour=11).iloc[0]["forecast"] == 1050.0


def test_summary_metrics(synthetic):
    s = an.summarize(an.day_ahead_view(9))  # errors: +50, +100
    assert s["mae"] == 75.0
    assert s["bias"] == 75.0
    assert s["n"] == 2


def test_horizon_view(synthetic):
    # 24h before Jan 2 12:00 = Jan 1 12:00 -> latest vintage is the 10:00 one
    assert an.horizon_view(24).iloc[0]["forecast"] == 1050.0
