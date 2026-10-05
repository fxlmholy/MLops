
import pandas as pd
import pytest

from src.features import build_features


def test_build_features_creates_required_columns():
    dates = pd.date_range("2025-01-01", periods=40, freq="D")
    history = pd.DataFrame({
        "date": dates,
        "article": ["A"] * 40,
        "qty": range(1, 41),
    })

    result = build_features(history, target_date="2025-02-09")

    required = {
        "lag_1",
        "lag_7",
        "lag_14",
        "rolling_mean_7",
        "rolling_mean_28",
        "rolling_std_7",
        "day_of_week",
        "month",
        "is_weekend",
        "is_holiday",
        "item_encoded",
    }
    assert required.issubset(result.columns)


def test_lag_and_rolling_use_past_values_only():
    history = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=10, freq="D"),
        "qty": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    })

    result = build_features(history)
    row = result.loc[result["date"] == pd.Timestamp("2025-01-08")].iloc[0]

    assert row["lag_1"] == 70
    assert row["lag_7"] == 10
    assert row["rolling_mean_7"] == pytest.approx(40)


def test_features_do_not_change_when_future_targets_change():
    history = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=10, freq="D"),
        "qty": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    })
    changed = history.copy()
    changed.loc[changed["date"] > "2025-01-08", "qty"] = 9999

    original_features = build_features(history, target_date="2025-01-08")
    changed_features = build_features(changed, target_date="2025-01-08")

    cols = [
        "lag_1",
        "lag_7",
        "lag_14",
        "rolling_mean_7",
        "rolling_mean_28",
        "rolling_std_7",
    ]
    pd.testing.assert_frame_equal(
        original_features[cols],
        changed_features[cols],
    )
