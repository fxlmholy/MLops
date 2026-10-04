
"""P3 (M3) - Feature engineering shared by training and serving."""

import pandas as pd


def build_features(
    history_df: pd.DataFrame,
    target_date=None,
    lags=(1, 7, 14),
    windows=(7, 28),
) -> pd.DataFrame:
    """สร้างฟีเจอร์จากข้อมูลย้อนหลัง โดยไม่ใช้ยอดขายในอนาคต."""

    if not isinstance(history_df, pd.DataFrame):
        raise TypeError("history_df must be a pandas DataFrame")

    df = history_df.copy()
    if df.empty:
        return df

    # รองรับรูปแบบคอลัมน์วันที่และยอดขายของโปรเจกต์
    date_col = next(
        (c for c in ("date", "datetime", "ds", "Date", "Datetime")
         if c in df.columns),
        None,
    )
    if date_col is None:
        if isinstance(df.index, pd.DatetimeIndex):
            df["_feature_date"] = df.index
            date_col = "_feature_date"
        else:
            raise ValueError("history_df must contain a date column")

    target_col = next(
        (c for c in ("qty", "sales", "y", "target", "demand")
         if c in df.columns),
        None,
    )
    if target_col is None:
        raise ValueError("history_df must contain a target column such as qty")

    item_col = next(
        (c for c in ("article", "item", "item_id", "product", "product_id")
         if c in df.columns),
        None,
    )

    df[date_col] = pd.to_datetime(df[date_col], errors="raise")
    df = df.sort_values(
        ([item_col] if item_col else []) + [date_col],
        kind="stable",
    ).reset_index(drop=True)

    dates = df[date_col]
    df["day_of_week"] = dates.dt.dayofweek
    df["month"] = dates.dt.month
    df["is_weekend"] = (dates.dt.dayofweek >= 5).astype("int8")

    try:
        import holidays
    except ImportError as exc:
        raise ImportError(
            "Install project dependencies to calculate French holidays."
        ) from exc

    holiday_dates = holidays.country_holidays(
        "FR", years=sorted(dates.dt.year.unique().tolist())
    )
    df["is_holiday"] = dates.dt.date.map(
        lambda day: int(day in holiday_dates)
    ).astype("int8")

    # รหัสสินค้าแบบ deterministic ภายในข้อมูลที่ได้รับ
    if item_col:
        item_values = df[item_col].astype("string").fillna("<missing>")
        df["item_encoded"] = pd.factorize(item_values, sort=True)[0].astype(
            "int32"
        )

    groups = df.groupby(item_col, sort=False)[target_col] if item_col else None

    for lag in lags:
        if lag < 1:
            raise ValueError("lag values must be >= 1")
        df[f"lag_{lag}"] = (
            groups.shift(lag) if groups is not None
            else df[target_col].shift(lag)
        )

    # shift(1) ทำให้ rolling ใช้ข้อมูลก่อนวันเป้าหมายเท่านั้น
    shifted = (
        df.groupby(item_col, sort=False)[target_col].shift(1)
        if item_col else df[target_col].shift(1)
    )
    for window in windows:
        if window < 1:
            raise ValueError("window values must be >= 1")
        if item_col:
            rolling = shifted.groupby(df[item_col], sort=False).rolling(
                window=window, min_periods=1
            )
            df[f"rolling_mean_{window}"] = (
                rolling.mean().reset_index(level=0, drop=True)
            )
        else:
            df[f"rolling_mean_{window}"] = shifted.rolling(
                window=window, min_periods=1
            ).mean()

    if item_col:
        rolling_std = shifted.groupby(df[item_col], sort=False).rolling(
            window=7, min_periods=2
        ).std()
        df["rolling_std_7"] = rolling_std.reset_index(
            level=0, drop=True
        )
    else:
        df["rolling_std_7"] = shifted.rolling(
            window=7, min_periods=2
        ).std()

    # จำกัดผลลัพธ์ถึง target_date หากระบุ
    if target_date is not None:
        cutoff = pd.to_datetime(target_date)
        df = df.loc[df[date_col] <= cutoff].copy()

    if "_feature_date" in df.columns:
        df = df.drop(columns=["_feature_date"])

    return df
