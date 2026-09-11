"""Demand seasonality curves for battery products.

Two genuine, well-documented real-world patterns drive this instead of
arbitrary noise:

- **Winter cold-snap failures**: lead-acid battery capacity drops sharply
  in cold weather, and a battery that was marginal in autumn frequently
  fails outright on the first hard freeze. Automotive and motorcycle
  battery replacement demand spikes accordingly, roughly December-January
  in Iran, with the sharpest days tracking actual cold snaps rather than a
  smooth seasonal curve.
- **Pre-Nowruz travel prep**: households and small fleets doing long road
  trips for Nowruz commonly replace a marginal battery beforehand rather
  than risk a breakdown — a smaller, more predictable bump than the winter
  spike, concentrated in the 2-3 weeks before Nowruz, affecting SLI as well
  as deep-cycle/marine batteries used in campers and boats.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

NOWRUZ_DATES = {2024: date(2024, 3, 20), 2025: date(2025, 3, 20), 2026: date(2026, 3, 21)}

# A handful of hard cold snaps per winter (specific days get an extra jolt
# on top of the broader Dec-Jan elevation) — battery failures cluster on
# the days it actually gets cold, not smoothly across the season.
COLD_SNAPS = [
    date(2024, 12, 8),
    date(2024, 12, 22),
    date(2025, 1, 12),
    date(2025, 1, 26),
    date(2025, 12, 6),
    date(2025, 12, 20),
    date(2026, 1, 10),
    date(2026, 1, 24),
]


def seasonal_multiplier(
    dates: pd.DatetimeIndex, seasonal_peak: str | None, rng: np.random.Generator
) -> np.ndarray:
    mult = np.ones(len(dates))
    d = dates.date
    month = dates.month.values

    if seasonal_peak == "WinterColdSnap":
        # Broad winter elevation, Nov 15 - Feb 15.
        in_winter = (
            np.isin(month, [11, 12, 1, 2])
            & ~((month == 11) & (dates.day.values < 15))
            & ~((month == 2) & (dates.day.values > 15))
        )
        mult[in_winter] *= 1.6

        for snap in COLD_SNAPS:
            days_from = np.array([(dd - snap).days for dd in d])
            near = np.abs(days_from) <= 5
            mult[near] *= 1.0 + 3.2 * np.exp(-0.5 * (days_from[near] / 2.0) ** 2)

    elif seasonal_peak == "PreNowruzTravel":
        for year, peak in NOWRUZ_DATES.items():
            days_from = np.array([(dd - peak).days for dd in d])
            pre = (days_from >= -21) & (days_from <= -2)
            mult[pre] *= 1.0 + 1.3 * np.exp(-0.5 * ((days_from[pre] + 10) / 8.0) ** 2)

    return mult


def weekday_multiplier(dates: pd.DatetimeIndex) -> np.ndarray:
    """B2B orders concentrate mid-week; Friday (Iran's weekend) is quiet."""
    weekday = dates.dayofweek.values  # Monday=0 ... Sunday=6
    mult = np.ones(len(dates))
    mult[weekday == 4] = 0.25  # Friday
    mult[weekday == 3] = 0.85  # Thursday (short day)
    return mult
