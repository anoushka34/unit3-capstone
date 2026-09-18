"""
generate_charts.py

Implements the Bronze requirement: "Generate at least 2 charts from your
Redshift data using matplotlib." Redshift itself has not been provisioned
(it is a paid, always-on cluster resource - see README for the same
cost-based reasoning that ruled out RDS). Charts are generated directly
from data.csv instead, which is the same underlying dataset Redshift would
have held. Documented as a substitute, not a claim that Redshift was used.

Install once:
    pip install matplotlib pandas --break-system-packages
"""

import pandas as pd
import matplotlib.pyplot as plt

CSV_PATH = "data/data.csv"
OUTPUT_DIR = "charts"

import os
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_data(csv_path: str = CSV_PATH) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Normalize numeric columns that may have formatting issues
    for col in ["total", "PkStreams", "wks", "t10", "pk"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def chart_top_artists_by_streams(df: pd.DataFrame, top_n: int = 10):
    """Bar chart: top N artists by total streams (summed across their tracks)."""
    grouped = df.groupby("artist name")["total"].sum().sort_values(ascending=False).head(top_n)

    plt.figure(figsize=(10, 6))
    grouped.plot(kind="bar", color="#1DB954")  # Spotify green, thematically fitting
    plt.title(f"Top {top_n} Artists by Total Streams")
    plt.xlabel("Artist")
    plt.ylabel("Total Streams")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "top_artists_by_streams.png")
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def chart_weeks_on_chart_distribution(df: pd.DataFrame):
    """Histogram: distribution of how many weeks songs stayed on the chart."""
    plt.figure(figsize=(10, 6))
    plt.hist(df["wks"].dropna(), bins=30, color="#1DB954", edgecolor="black")
    plt.title("Distribution of Weeks on Chart")
    plt.xlabel("Weeks on Chart")
    plt.ylabel("Number of Songs")
    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "weeks_on_chart_distribution.png")
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def chart_streams_vs_peak_streams(df: pd.DataFrame):
    """Bonus third chart: scatter of total streams vs peak-week streams, useful analytical view."""
    plt.figure(figsize=(10, 6))
    plt.scatter(df["PkStreams"], df["total"], alpha=0.6, color="#1DB954")
    plt.title("Total Streams vs. Peak-Week Streams")
    plt.xlabel("Peak-Week Streams")
    plt.ylabel("Total Streams")
    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "total_vs_peak_streams.png")
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    df = load_data()
    print(f"Loaded {len(df)} rows from {CSV_PATH}\n")

    chart_top_artists_by_streams(df)
    chart_weeks_on_chart_distribution(df)
    chart_streams_vs_peak_streams(df)

    print(f"\nAll charts saved to ./{OUTPUT_DIR}/")