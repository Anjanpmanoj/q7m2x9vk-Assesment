"""Download January 2026 wind actuals (FUELHH) and forecasts (WINDFOR) from Elexon into backend/data/.

Run:  python scripts/fetch_data.py
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
OUT = Path(__file__).resolve().parent.parent / "backend" / "data"
JAN_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
JAN_END = datetime(2026, 2, 1, tzinfo=timezone.utc)


def fetch(dataset: str, params: dict) -> list[dict]:
    r = requests.get(f"{BASE}/{dataset}/stream", params={**params, "format": "json"}, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body["data"] if isinstance(body, dict) else body


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%MZ")


def fetch_actuals() -> pd.DataFrame:
    rows, day = [], JAN_START
    while day < JAN_END:
        end = min(day + timedelta(days=7), JAN_END) - timedelta(days=1)
        rows += fetch("FUELHH", {
            "settlementDateFrom": day.date().isoformat(),
            "settlementDateTo": end.date().isoformat(),
            "fuelType": "WIND",
        })
        day += timedelta(days=7)
    df = pd.DataFrame(rows)
    df = df[df["fuelType"] == "WIND"][["startTime", "generation"]]
    return df.drop_duplicates("startTime").sort_values("startTime")


def fetch_forecasts() -> pd.DataFrame:
    # Forecasts for January targets can be published a few days earlier, so start in late December.
    rows, t = [], datetime(2025, 12, 28, tzinfo=timezone.utc)
    while t < JAN_END:
        end = min(t + timedelta(days=2), JAN_END)
        rows += fetch("WINDFOR", {"publishDateTimeFrom": iso(t), "publishDateTimeTo": iso(end)})
        t = end
    df = pd.DataFrame(rows)[["startTime", "publishTime", "generation"]]
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df = df[(df["startTime"] >= JAN_START) & (df["startTime"] < JAN_END)]
    return df.drop_duplicates(["startTime", "publishTime"]).sort_values(["startTime", "publishTime"])


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    a, f = fetch_actuals(), fetch_forecasts()
    a.to_csv(OUT / "actuals.csv", index=False)
    f.to_csv(OUT / "forecasts.csv", index=False)
    print(f"actuals: {len(a)} rows, forecasts: {len(f)} rows -> {OUT}")
