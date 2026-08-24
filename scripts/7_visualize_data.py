"""
7_visualize_data.py
Visualisasi dan analisis deskriptif RAW CSV E-NOSE.

Script ini TIDAK melakukan machine learning atau training model.
Raw CSV hanya dibaca; tidak ada file sumber yang ditulis ulang.

Jalankan dari root proyek:
    python scripts/7_visualize_data.py

Output:
    plots/raw/         Grafik setiap sensor untuk setiap run
    plots/per_sample/  Semua run dan rata-rata per sample
    plots/per_roast/   Perbandingan Light/Medium/Dark
    plots/per_batch/   Perbandingan antar batch
    plots/analysis_summary.md
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
VALIDATION_REPORT = BASE_DIR / "data_analysis" / "validation_report.csv"
PLOTS_DIR = BASE_DIR / "plots"

SENSORS = [
    "adc_tgs822", "adc_mq135", "adc_mq9", "adc_tgs2611", "adc_tgs2620",
    "adc_tgs2600", "adc_tgs2602", "adc_mq8", "adc_tgs813", "adc_tgs816",
]
EXPECTED_SAMPLES = {
    "L-MAN": "light", "L-RAT": "light", "L-GAY": "light", "L-MER": "light",
    "M-MAN": "medium", "M-RAT": "medium", "M-TEM": "medium", "M-TIM": "medium",
    "D-MAN": "dark", "D-RAT": "dark", "D-GAY": "dark",
}
ROAST_ORDER = ["light", "medium", "dark"]
COLORS = {"light": "#E6A23C", "medium": "#5B8FF9", "dark": "#593A2E"}


def safe_name(value: object) -> str:
    text = str(value) if value is not None else "UNKNOWN"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "UNKNOWN"


def infer_metadata(df: pd.DataFrame, filename: str) -> pd.DataFrame:
    """Support both current metadata and older label/cycle CSV formats."""
    df = df.copy()
    if "roast_level" not in df.columns and "label" in df.columns:
        df["roast_level"] = df["label"]
    if "run_id" not in df.columns and "cycle" in df.columns:
        df["run_id"] = df["cycle"]
    if "sample_id" not in df.columns:
        match = re.match(r"([LMD]-[A-Z]+)_", filename.upper())
        df["sample_id"] = match.group(1) if match else "UNKNOWN"
    if "batch_id" not in df.columns:
        match = re.search(r"_(B\d+)", filename.upper())
        df["batch_id"] = match.group(1) if match else "UNKNOWN"
    if "origin" not in df.columns:
        df["origin"] = "UNKNOWN"
    if "roast_level" not in df.columns:
        lower_name = filename.lower()
        df["roast_level"] = next(
            (roast for roast in ROAST_ORDER if lower_name.startswith(roast + "_")),
            "unknown",
        )
    if "run_id" not in df.columns:
        df["run_id"] = 1
    if "phase" not in df.columns:
        df["phase"] = "collecting"
    for column in ["sample_id", "batch_id", "origin", "roast_level", "phase"]:
        df[column] = df[column].fillna("UNKNOWN").astype(str).str.strip()
    df["roast_level"] = df["roast_level"].str.lower()
    return df


def load_raw_data() -> tuple[pd.DataFrame, list[str], list[str]]:
    """Load raw CSVs, excluding only files with ERROR in validation report."""
    error_files: set[str] = set()
    if VALIDATION_REPORT.exists():
        report = pd.read_csv(VALIDATION_REPORT)
        if {"filename", "status"}.issubset(report.columns):
            error_files = set(report.loc[report["status"] == "ERROR", "filename"].astype(str))

    frames: list[pd.DataFrame] = []
    skipped: list[str] = []
    for path in sorted(DATA_DIR.glob("*.csv")):
        if path.name.startswith("dataset_fitur") or path.name in error_files:
            continue
        try:
            frame = pd.read_csv(path)
        except Exception as exc:
            skipped.append(f"{path.name}: gagal dibaca ({exc})")
            continue
        frame = infer_metadata(frame, path.name)
        available = [sensor for sensor in SENSORS if sensor in frame.columns]
        if not available:
            skipped.append(f"{path.name}: tidak memiliki kolom sensor adc_*")
            continue
        for sensor in available:
            frame[sensor] = pd.to_numeric(frame[sensor], errors="coerce")
        frame["source_file"] = path.name
        frames.append(frame)

    if not frames:
        raise RuntimeError("Tidak ada raw CSV yang dapat divisualisasikan di data/.")
    return pd.concat(frames, ignore_index=True), skipped, sorted(error_files)


def sensor_columns(df: pd.DataFrame) -> list[str]:
    return [sensor for sensor in SENSORS if sensor in df.columns]


def time_seconds(frame: pd.DataFrame) -> np.ndarray:
    if "timestamp" in frame.columns:
        values = pd.to_numeric(frame["timestamp"], errors="coerce").to_numpy(dtype=float)
        if np.isfinite(values).sum() > 1:
            first = values[np.isfinite(values)][0]
            return (values - first) / 1000.0
    if "sample_idx" in frame.columns:
        values = pd.to_numeric(frame["sample_idx"], errors="coerce").to_numpy(dtype=float)
        if np.isfinite(values).sum() > 1:
            first = values[np.isfinite(values)][0]
            return values - first
    return np.arange(len(frame), dtype=float)


def phase_ranges(frame: pd.DataFrame, x: np.ndarray) -> list[tuple[str, float, float]]:
    ranges = []
    if "phase" not in frame.columns or len(frame) == 0:
        return ranges
    phases = frame["phase"].astype(str).str.lower().to_numpy()
    start = 0
    for index in range(1, len(phases) + 1):
        if index == len(phases) or phases[index] != phases[start]:
            ranges.append((phases[start], float(x[start]), float(x[index - 1])))
            start = index
    return ranges


def style_axis(ax: plt.Axes, title: str, sensor: str) -> None:
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Waktu sejak awal run (detik)")
    ax.set_ylabel("Nilai ADC")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, loc="best")


def plot_raw_runs(df: pd.DataFrame, sensors: list[str], output: Path) -> int:
    count = 0
    for source, source_df in df.groupby("source_file", dropna=False):
        folder = output / "raw" / safe_name(Path(str(source)).stem)
        folder.mkdir(parents=True, exist_ok=True)
        fig, axes = plt.subplots(2, 5, figsize=(16, 7), sharex=False)
        axes = axes.flatten()
        for index, sensor in enumerate(sensors):
            ax = axes[index]
            for run_id, run in source_df.groupby("run_id", dropna=False):
                run = run.sort_values("timestamp" if "timestamp" in run.columns else "sample_idx")
                x = time_seconds(run)
                values = pd.to_numeric(run[sensor], errors="coerce").to_numpy(dtype=float)
                valid = np.isfinite(values) & np.isfinite(x)
                if valid.any():
                    ax.plot(x[valid], values[valid], linewidth=0.7, alpha=0.55, label=f"R{run_id}")
            ax.set_title(sensor, fontsize=9)
            ax.set_xlabel("detik", fontsize=8)
            ax.set_ylabel("ADC", fontsize=8)
            ax.grid(True, alpha=0.22)
            if index == 0:
                ax.legend(fontsize=6, ncol=2, loc="best")
        for ax in axes[len(sensors):]:
            ax.set_visible(False)
        fig.suptitle(f"{source} | seluruh run per sensor | Purging dan Collecting", fontsize=13)
        fig.tight_layout()
        fig.savefig(folder / "all_runs_all_sensors.png", dpi=90)
        plt.close(fig)
        count += 1
    return count


def plot_sample_views(df: pd.DataFrame, sensors: list[str], output: Path) -> int:
    count = 0
    for sample, sample_df in df.groupby("sample_id", dropna=False):
        sample_folder = output / "per_sample" / safe_name(sample)
        sample_folder.mkdir(parents=True, exist_ok=True)
        for sensor in sensors:
            fig, axes = plt.subplots(1, 2, figsize=(14, 4.2), sharey=True)
            for run_id, run in sample_df.groupby("run_id", dropna=False):
                run = run.sort_values("timestamp" if "timestamp" in run.columns else "sample_idx")
                x = time_seconds(run)
                values = pd.to_numeric(run[sensor], errors="coerce").to_numpy(dtype=float)
                valid = np.isfinite(values) & np.isfinite(x)
                if valid.any():
                    axes[0].plot(x[valid], values[valid], linewidth=0.8, alpha=0.55, label=f"Run {run_id}")
            axes[0].set_title(f"{sample} | {sensor} | seluruh run")
            axes[0].set_xlabel("Waktu (detik)"); axes[0].set_ylabel("Nilai ADC")
            axes[0].grid(True, alpha=0.25); axes[0].legend(fontsize=6, ncol=2)

            collecting = sample_df[sample_df["phase"].str.lower() == "collecting"]
            grouped = collecting.groupby("run_id", dropna=False)[sensor]
            run_means = grouped.mean()
            run_stds = grouped.std().fillna(0)
            axes[1].errorbar(run_means.index.astype(str), run_means.values,
                             yerr=run_stds.values, fmt="o-", color="#D1495B", capsize=3)
            axes[1].set_title(f"{sample} | {sensor} | rata-rata collecting")
            axes[1].set_xlabel("Run"); axes[1].set_ylabel("Mean ADC +/- SD")
            axes[1].grid(True, alpha=0.25)
            fig.tight_layout()
            fig.savefig(sample_folder / f"{sensor}_runs_and_average.png", dpi=120)
            plt.close(fig)
            count += 1
    return count


def plot_roast_views(df: pd.DataFrame, sensors: list[str], output: Path) -> int:
    count = 0
    collecting = df[df["phase"].str.lower() == "collecting"]
    folder = output / "per_roast"
    folder.mkdir(parents=True, exist_ok=True)
    for sensor in sensors:
        fig, axes = plt.subplots(1, 2, figsize=(14, 4.2))
        for roast in ROAST_ORDER:
            roast_df = collecting[collecting["roast_level"] == roast]
            if roast_df.empty:
                continue
            by_run = roast_df.groupby(["source_file", "run_id"])[sensor].mean()
            axes[0].plot(np.arange(len(by_run)), by_run.values, "o-", alpha=0.55,
                         color=COLORS[roast], label=roast.title())
            axes[1].boxplot(roast_df[sensor].dropna().values, positions=[ROAST_ORDER.index(roast)],
                            widths=0.55, patch_artist=True,
                            boxprops={"facecolor": COLORS[roast], "alpha": 0.65})
        axes[0].set_title(f"{sensor} | mean collecting per run")
        axes[0].set_xlabel("Urutan run"); axes[0].set_ylabel("Mean ADC")
        axes[0].grid(True, alpha=0.25); axes[0].legend()
        axes[1].set_title(f"{sensor} | distribusi collecting")
        axes[1].set_xticks(range(len(ROAST_ORDER))); axes[1].set_xticklabels([r.title() for r in ROAST_ORDER])
        axes[1].set_ylabel("ADC"); axes[1].grid(True, alpha=0.25, axis="y")
        fig.tight_layout(); fig.savefig(folder / f"{sensor}_roast_comparison.png", dpi=120)
        plt.close(fig); count += 1
    return count


def plot_batch_views(df: pd.DataFrame, sensors: list[str], output: Path) -> int:
    count = 0
    collecting = df[df["phase"].str.lower() == "collecting"]
    folder = output / "per_batch"
    folder.mkdir(parents=True, exist_ok=True)
    for sensor in sensors:
        grouped = collecting.groupby(["batch_id", "roast_level"])[sensor].mean().unstack(fill_value=np.nan)
        if grouped.empty:
            continue
        fig, ax = plt.subplots(figsize=(10, 4.5))
        grouped.reindex(columns=ROAST_ORDER).plot(kind="bar", ax=ax, color=[COLORS[r] for r in ROAST_ORDER])
        ax.set_title(f"{sensor} | perbandingan batch dan roast level")
        ax.set_xlabel("Batch"); ax.set_ylabel("Mean ADC collecting")
        ax.grid(True, alpha=0.25, axis="y"); ax.legend(title="Roast")
        fig.tight_layout(); fig.savefig(folder / f"{sensor}_batch_comparison.png", dpi=120)
        plt.close(fig); count += 1
    return count


def descriptive_analysis(df: pd.DataFrame, sensors: list[str], skipped: list[str], excluded: list[str]) -> str:
    collecting = df[df["phase"].str.lower() == "collecting"].copy()
    lines = [
        "# Analisis Deskriptif Visualisasi E-NOSE",
        "",
        "Dokumen ini dibuat dari RAW CSV secara deskriptif. Tidak ada machine learning, Random Forest, atau training model.",
        "Raw CSV tidak diubah.",
        "",
        "## Cakupan Data",
        f"- CSV terbaca: {df['source_file'].nunique()}",
        f"- Sample terdeteksi: {df['sample_id'].nunique()} ({', '.join(sorted(df['sample_id'].unique()))})",
        f"- Batch terdeteksi: {df['batch_id'].nunique()} ({', '.join(sorted(df['batch_id'].unique()))})",
        f"- Sensor divisualisasikan: {len(sensors)}",
        f"- Baris collecting: {len(collecting):,}",
        "",
        "## Ringkasan Respons Sensor",
        "",
        "| Sensor | Mean ADC | SD | CV (%) | Range | Slope indikatif |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    metrics = []
    for sensor in sensors:
        values = collecting[sensor].dropna().to_numpy(dtype=float)
        if len(values) == 0:
            continue
        mean = float(np.mean(values)); std = float(np.std(values)); value_range = float(np.ptp(values))
        cv = abs(std / mean * 100) if mean else float("inf")
        ordered = collecting[["timestamp", sensor]].dropna().copy()
        ordered["timestamp"] = pd.to_numeric(ordered["timestamp"], errors="coerce")
        ordered = ordered.dropna().sort_values("timestamp")
        slope = float(np.polyfit(np.arange(len(ordered)), ordered[sensor], 1)[0]) if len(ordered) > 1 else 0.0
        metrics.append((sensor, mean, std, cv, value_range, slope))
        lines.append(f"| {sensor} | {mean:.2f} | {std:.2f} | {cv:.2f} | {value_range:.2f} | {slope:.4f} |")

    if metrics:
        strongest = max(metrics, key=lambda item: item[4])
        noisiest = max(metrics, key=lambda item: item[3])
        stable = min(metrics, key=lambda item: item[3])
        drift = max(metrics, key=lambda item: abs(item[5]))
        lines.extend([
            "",
            "## Temuan Indikatif",
            "",
            f"- **Respons kuat:** {strongest[0]} memiliki rentang ADC terbesar. Ini merupakan indikasi respons amplitudo yang lebih besar pada data ini, bukan bukti bahwa sensor pasti paling penting.",
            f"- **Noise relatif tinggi:** {noisiest[0]} memiliki CV relatif tertinggi. Kemungkinan variasinya dipengaruhi noise, perubahan aroma, atau baseline; perlu dianalisis lebih lanjut.",
            f"- **Respons relatif stabil:** {stable[0]} memiliki CV relatif terendah. Stabilitas ini tidak otomatis berarti responsnya informatif.",
            f"- **Drift:** {drift[0]} memiliki kemiringan waktu absolut terbesar pada penggabungan collecting. Ini adalah indikasi drift dan perlu dibandingkan per run serta setelah baseline purging.",
        ])

    roast_means = collecting.groupby("roast_level")[sensors].mean()
    if not roast_means.empty:
        lines.extend(["", "## Perbedaan Roast Level", ""])
        for sensor in sensors:
            available = roast_means[sensor].dropna()
            if len(available) >= 2:
                high = available.idxmax(); low = available.idxmin()
                lines.append(f"- {sensor}: mean tertinggi pada **{high}** dan terendah pada **{low}**. Ini hanya indikasi perbedaan visual/deskriptif.")

    batch_means = collecting.groupby("batch_id")[sensors].mean()
    if len(batch_means) > 1:
        lines.extend(["", "## Perbedaan Batch", ""])
        batch_spread = (batch_means.max() - batch_means.min()).sort_values(ascending=False)
        for sensor in batch_spread.head(5).index:
            lines.append(f"- {sensor}: memiliki selisih mean antar batch relatif besar ({batch_spread[sensor]:.2f} ADC); kemungkinan ada efek batch atau kondisi akuisisi.")

    outlier_notes = []
    for sensor in sensors:
        values = collecting[sensor].dropna()
        if len(values) < 4:
            continue
        q1, q3 = values.quantile([0.25, 0.75]); iqr = q3 - q1
        outliers = int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum())
        if outliers:
            outlier_notes.append(f"{sensor} ({outliers} titik menurut aturan IQR)")
    lines.extend(["", "## Outlier dan Keterbatasan", ""])
    lines.append("- Kandidat outlier: " + (", ".join(outlier_notes) if outlier_notes else "tidak terdeteksi dengan aturan IQR global."))
    lines.append("- Data purging tetap divisualisasikan bila tersedia; analisis respons roast level memakai fase collecting.")
    lines.append("- File dengan metadata tidak lengkap diberi label UNKNOWN. Perbandingan antar sample untuk file tersebut perlu dianalisis lebih lanjut.")
    if skipped:
        lines.append("- File yang dilewati: " + "; ".join(skipped))
    if excluded:
        lines.append("- File dengan status ERROR dari validation report tidak diplot: " + ", ".join(excluded))
    lines.append("- Kesimpulan visual bersifat indikatif dan tidak membuktikan kepentingan sensor tanpa analisis statistik lanjutan.")
    return "\n".join(lines) + "\n"


def main() -> None:
    df, skipped, excluded = load_raw_data()
    sensors = sensor_columns(df)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    raw_count = plot_raw_runs(df, sensors, PLOTS_DIR)
    sample_count = plot_sample_views(df, sensors, PLOTS_DIR)
    roast_count = plot_roast_views(df, sensors, PLOTS_DIR)
    batch_count = plot_batch_views(df, sensors, PLOTS_DIR)
    summary = descriptive_analysis(df, sensors, skipped, excluded)
    summary_path = PLOTS_DIR / "analysis_summary.md"
    summary_path.write_text(summary, encoding="utf-8")
    print(f"CSV terbaca: {df['source_file'].nunique()}")
    print(f"Sensor: {len(sensors)}")
    print(f"Grafik raw: {raw_count}")
    print(f"Grafik per sample: {sample_count}")
    print(f"Grafik per roast: {roast_count}")
    print(f"Grafik per batch: {batch_count}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
