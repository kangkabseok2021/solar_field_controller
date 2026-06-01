"""Plot tracking accuracy, efficiency curve, and daily yield from a DAQ CSV."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt


def load_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["tracking_error"] = df["target_angle"] - df["actual_angle"]
    return df


def plot_tracking(df: pd.DataFrame, ax: plt.Axes) -> None:
    ax.plot(df["timestamp"], df["target_angle"],  label="Target angle (°)",  lw=1.5)
    ax.plot(df["timestamp"], df["actual_angle"],  label="Actual angle (°)",  lw=1.0, alpha=0.8)
    rms = math.sqrt((df["tracking_error"] ** 2).mean())
    ax.set_title(f"Tracking Accuracy — RMS error {rms:.3f}°")
    ax.set_ylabel("Angle (°)")
    ax.legend()
    ax.grid(alpha=0.3)


def plot_efficiency(df: pd.DataFrame, ax: plt.Axes,
                    collector_area_m2: float = 10.0,
                    fluid_flow_kgs: float = 0.5,
                    fluid_cp_jkg: float = 4182.0) -> None:
    """η = Q_useful / (A × DNI), Q_useful approximated from temperature rise."""
    # Without inlet/outlet split we use a simplified model: η ∝ 1 − |θ_i|/90
    theta_i = np.abs(np.radians(df["tracking_error"].values))
    eta = np.cos(theta_i)  # incidence-angle correction factor
    valid = df["dni"] > 10
    ax.scatter(df.loc[valid, "tracking_error"], eta[valid],
               s=8, alpha=0.5, c=df.loc[valid, "dni"], cmap="YlOrRd")
    ax.set_title("Collector Efficiency vs. Tracking Error")
    ax.set_xlabel("Tracking error (°)")
    ax.set_ylabel("η (incidence correction)")
    ax.grid(alpha=0.3)


def plot_daily_yield(df: pd.DataFrame, ax: plt.Axes) -> None:
    if "timestamp" not in df.columns:
        return
    df2 = df.set_index("timestamp").resample("h")["dni"].mean().dropna()
    ax.bar(df2.index.hour, df2.values, color="#f59e0b", alpha=0.8)
    ax.set_title("Mean Hourly DNI (W/m²)")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("DNI (W/m²)")
    ax.grid(axis="y", alpha=0.3)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Analyse solar field DAQ CSV")
    parser.add_argument("csv", help="Path to field_*.csv")
    parser.add_argument("--headless", action="store_true",
                        help="Save PNGs without opening display")
    args = parser.parse_args(argv)

    if args.headless:
        matplotlib.use("Agg")

    df = load_csv(args.csv)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    plot_tracking(df, axes[0])
    plot_efficiency(df, axes[1])
    plot_daily_yield(df, axes[2])
    plt.tight_layout()

    if args.headless:
        out = Path(args.csv).with_suffix(".png")
        fig.savefig(out, dpi=120)
        print(f"Saved: {out}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
