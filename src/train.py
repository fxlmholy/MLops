
"""P3 (M3): Feature engineering, model training, and MLflow tracking."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
import shap
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import load_config
from src.features import build_features
from src.split import time_split

ROOT = Path(__file__).resolve().parents[1]

FEATURE_COLUMNS = [
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
]


def git_commit() -> str:
    """Return the current Git commit."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def file_sha256(path: Path) -> str:
    """Calculate a file's SHA256 checksum."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wape(y_true, y_pred) -> float:
    """Calculate Weighted Absolute Percentage Error."""
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    denominator = np.abs(actual).sum()

    return (
        float(np.abs(actual - predicted).sum() / denominator)
        if denominator
        else 0.0
    )


def evaluate(y_true, y_pred, quantile=0.6) -> dict:
    """Calculate demand forecast metrics."""
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    error = actual - predicted

    return {
        "wape": wape(actual, predicted),
        "mae": float(mean_absolute_error(actual, predicted)),
        "pinball_loss": float(
            np.maximum(
                quantile * error,
                (quantile - 1) * error,
            ).mean()
        ),
        "stockout_proxy": float(np.maximum(error, 0).mean()),
        "waste_proxy": float(np.maximum(-error, 0).mean()),
    }


def save_prediction_plot(
    y_true,
    y_pred,
    model_name: str,
    split_name: str,
) -> Path:
    """Save an actual-versus-predicted plot."""
    fig, ax = plt.subplots(figsize=(8, 6))

    ax.scatter(y_true, y_pred, alpha=0.35)
    ax.set_xlabel("Actual demand")
    ax.set_ylabel("Predicted demand")
    ax.set_title(f"{split_name.title()} Actual vs Predicted: {model_name}")
    fig.tight_layout()

    plot_path = ROOT / (
        f"{model_name}_{split_name}_actual_vs_predicted.png"
    )

    try:
        fig.savefig(plot_path, dpi=150)
    finally:
        plt.close(fig)

    return plot_path


def log_shap_artifacts(model, X_test, model_name: str) -> None:
    """Log SHAP feature importance for tree-based models."""
    sample = X_test.sample(
        n=min(1000, len(X_test)),
        random_state=42,
    )

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(sample)

    shap.summary_plot(
        shap_values,
        sample,
        show=False,
        max_display=len(FEATURE_COLUMNS),
    )

    summary_path = ROOT / f"{model_name}_shap_summary.png"

    try:
        plt.gcf().savefig(
            summary_path,
            dpi=150,
            bbox_inches="tight",
        )
        mlflow.log_artifact(
            str(summary_path),
            artifact_path="shap",
        )
    finally:
        plt.close("all")
        summary_path.unlink(missing_ok=True)

    values = np.asarray(shap_values)

    if values.ndim == 3:
        values = values[:, :, 0]

    importance = pd.DataFrame(
        {
            "feature": sample.columns,
            "mean_abs_shap": np.abs(values).mean(axis=0),
        }
    ).sort_values("mean_abs_shap", ascending=False)

    importance_path = ROOT / f"{model_name}_shap_importance.csv"

    try:
        importance.to_csv(importance_path, index=False)
        mlflow.log_artifact(
            str(importance_path),
            artifact_path="shap",
        )
    finally:
        importance_path.unlink(missing_ok=True)


def main() -> None:
    """Train four models using M2 processed data and track with MLflow."""
    config = load_config()

    # Load the processed dataset created by M2.
    processed_path = ROOT / config["paths"]["processed"]

    if not processed_path.exists():
        raise FileNotFoundError(
            f"Processed dataset not found: {processed_path}. "
            "Run the M2 ingestion pipeline first."
        )

    daily = pd.read_parquet(processed_path)

    required_columns = {"date", "article", "qty"}
    missing_columns = required_columns - set(daily.columns)

    if missing_columns:
        raise ValueError(
            "Processed dataset is missing columns: "
            f"{sorted(missing_columns)}"
        )

    if daily.empty:
        raise ValueError("Processed dataset is empty.")

    daily["date"] = pd.to_datetime(daily["date"], errors="raise")
    daily["qty"] = pd.to_numeric(daily["qty"], errors="raise")

    # Do not reprocess or overwrite M2's Parquet file.
    featured = build_features(daily)
    featured = featured.replace([np.inf, -np.inf], np.nan)
    featured = featured.dropna(
        subset=FEATURE_COLUMNS + ["qty"]
    )

    train, val, test = time_split(
        featured,
        config["split"]["train_end"],
        config["split"]["val_end"],
    )

    if train.empty or val.empty or test.empty:
        raise ValueError(
            "Train, validation, or test is empty. "
            "Check the date ranges in configs/config.yaml."
        )

    X_train = train[FEATURE_COLUMNS]
    y_train = train["qty"]

    X_val = val[FEATURE_COLUMNS]
    y_val = val["qty"]

    X_test = test[FEATURE_COLUMNS]
    y_test = test["qty"]

    quantile = config.get("model", {}).get(
        "quantile_default",
        0.6,
    )

    from lightgbm import LGBMRegressor

    models = {
        "seasonal_naive": None,
        "linear_regression": make_pipeline(
            StandardScaler(),
            LinearRegression(),
        ),
        "lightgbm_default": LGBMRegressor(
            random_state=config.get("seed", 42),
            verbosity=-1,
        ),
        "lightgbm_tuned_holiday": LGBMRegressor(
            objective="quantile",
            alpha=quantile,
            n_estimators=300,
            learning_rate=0.03,
            num_leaves=31,
            random_state=config.get("seed", 42),
            verbosity=-1,
        ),
    }

    mlflow_cfg = config.get("mlflow", {})
    mlflow.set_tracking_uri(
        mlflow_cfg.get("tracking_uri", "mlruns")
    )
    mlflow.set_experiment(
        mlflow_cfg.get("experiment", "bakery-demand")
    )

    requirements_path = ROOT / "requirements.txt"
    results = []

    for name, model in models.items():
        with mlflow.start_run(run_name=name):
            mlflow.set_tags(
                {
                    "git_commit": git_commit(),
                    "data_sha256": file_sha256(processed_path),
                    "python_version": sys.version.split()[0],
                    "data_path": str(processed_path.relative_to(ROOT)),
                }
            )

            mlflow.log_params(
                {
                    "model_name": name,
                    "train_rows": len(train),
                    "validation_rows": len(val),
                    "test_rows": len(test),
                    "quantile": quantile,
                }
            )

            # Log environment and feature list.
            if requirements_path.exists():
                mlflow.log_artifact(
                    str(requirements_path),
                    artifact_path="environment",
                )

            mlflow.log_text(
                json.dumps(FEATURE_COLUMNS, indent=2),
                "feature_list.json",
            )

            # Fit and predict on validation and test sets.
            if model is None:
                val_predictions = val["lag_7"].to_numpy(dtype=float)
                test_predictions = test["lag_7"].to_numpy(dtype=float)
                mlflow.log_param("strategy", "lag_7")
            else:
                model.fit(X_train, y_train)

                val_predictions = model.predict(X_val)
                test_predictions = model.predict(X_test)

                params = {
                    key: value
                    for key, value in model.get_params().items()
                    if isinstance(
                        value,
                        (str, int, float, bool),
                    )
                    or value is None
                }
                mlflow.log_params(params)

                if name.startswith("lightgbm"):
                    mlflow.lightgbm.log_model(
                        model,
                        artifact_path="model",
                    )
                else:
                    mlflow.sklearn.log_model(
                        model,
                        artifact_path="model",
                    )

            # Validation metrics.
            val_metrics = evaluate(
                y_val,
                val_predictions,
                quantile,
            )
            mlflow.log_metrics(val_metrics)

            # Test metrics.
            test_metrics = evaluate(
                y_test,
                test_predictions,
                quantile,
            )
            mlflow.log_metrics(
                {
                    f"test_{key}": value
                    for key, value in test_metrics.items()
                }
            )

            # Actual-versus-predicted plots.
            for split_name, actual, predicted in [
                ("validation", y_val, val_predictions),
                ("test", y_test, test_predictions),
            ]:
                plot_path = save_prediction_plot(
                    actual,
                    predicted,
                    name,
                    split_name,
                )

                try:
                    mlflow.log_artifact(
                        str(plot_path),
                        artifact_path="plots",
                    )
                finally:
                    plot_path.unlink(missing_ok=True)

            # SHAP explanations for LightGBM models.
            if name.startswith("lightgbm"):
                log_shap_artifacts(
                    model,
                    X_test,
                    name,
                )

            results.append(
                {
                    "model": name,
                    **{f"val_{k}": v for k, v in val_metrics.items()},
                    **{f"test_{k}": v for k, v in test_metrics.items()},
                }
            )

    results_df = pd.DataFrame(results).sort_values("val_wape")

    print("\nValidation and test results:")
    print(results_df.to_string(index=False))
    print(f"\nProcessed data: {processed_path}")
    print("Use validation metrics for model selection.")
    print("Use test metrics for final evaluation only.")


if __name__ == "__main__":
    main()
