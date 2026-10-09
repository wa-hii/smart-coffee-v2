"""Auto-generate E-NOSE sensor plots from active raw CSV acquisitions.

Default behavior:
- scan active CSV files in data/raw only;
- skip legacy_mq9 and runtime/incomplete data;
- generate only missing or stale per-sample plots;
- generate light/medium/dark comparisons per coffee origin for compatible
  five-run acquisitions;
- generate one multi-panel overview per sensor, grouped by origin.

The script never runs preprocessing or model training.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

from acquisition_schema import ADC_COLS
from stage2_dataset_audit import read_exclusions


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "results" / "sensor-plots"
ORIGIN_OUTPUT_DIR = OUTPUT_DIR / "by-origin"
EXCLUSION_MANIFEST = ROOT / "data" / "analysis" / "bench_only_exclusions.csv"

SENSORS = ADC_COLS + ["temperature", "humidity"]

ROAST_ORDER = ("light", "medium", "dark")
ROAST_COLORS = {
    "light": "red",
    "medium": "green",
    "dark": "blue",
}

AGGREGATE_RUNS = (1, 2, 3, 4, 5)
AGGREGATE_POINTS_PER_RUN = 32
MEAN_CYCLE_POINTS = 180


@dataclass(frozen=True)
class SourceRecord:
    path: Path
    sample_id: str
    roast: str
    origin: str
    batch_id: str
    sensors: frozenset[str]


def safe_name(text: str) -> str:
    value = str(text).strip()
    cleaned = "".join(
        char if char.isalnum() or char in "-_." else "_"
        for char in value
    )
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("._") or "unknown"


def first_value(df: pd.DataFrame, column: str, default: str = "-") -> str:
    if column not in df.columns:
        return default
    values = df[column].dropna()
    if values.empty:
        return default
    value = str(values.iloc[0]).strip()
    return value or default


def display_origin(origin: str) -> str:
    value = str(origin).strip()
    if value.lower().startswith("arabika "):
        return value[8:]
    return value


def pretty_sensor(sensor: str) -> str:
    if sensor == "temperature":
        return "Temperature"
    if sensor == "humidity":
        return "Humidity"
    return sensor.replace("adc_", "").upper()


def sensor_ylabel(sensor: str) -> str:
    if sensor == "temperature":
        return "Suhu (°C)"
    if sensor == "humidity":
        return "Kelembapan relatif (%RH)"
    return f"{sensor} (nilai ADC mentah)"


def get_csv_files(recursive: bool = False) -> list[Path]:
    # Jangan gabungkan data bench udara bersih berlabel kopi dengan chart
    # per-origin / per-roasting. File B36+ lainnya ditahan hingga provenance
    # diverifikasi; tidak boleh otomatis dianggap kelas kopi terverifikasi.
    exclusions = read_exclusions(EXCLUSION_MANIFEST)
    candidates = DATA_DIR.rglob("*.csv") if recursive else DATA_DIR.glob("*.csv")
    files: list[Path] = []
    for path in candidates:
        parts = {part.lower() for part in path.relative_to(DATA_DIR).parts}
        if "legacy_mq9" in parts:
            continue
        if "incomplete" in parts or ".incoming" in parts:
            continue
        if path.name in exclusions:
            if hashlib.sha256(path.read_bytes()).hexdigest() != exclusions[path.name]:
                raise ValueError(
                    f"Hash data bench tidak sesuai daftar pengecualian: {path.name}"
                )
            continue
        batch = re.search(r"_B(\d{2})(?:_|\.csv$)", path.name)
        if batch and int(batch.group(1)) >= 36:
            continue
        files.append(path)
    return sorted(files)


def read_header(file_path: Path) -> list[str]:
    return list(pd.read_csv(file_path, nrows=0).columns)


def load_data(file_path: Path) -> pd.DataFrame:
    df = pd.read_csv(file_path)
    missing = [
        column for column in ("run_id", "phase")
        if column not in df.columns
    ]
    if missing:
        raise ValueError(
            f"{file_path.name}: kolom wajib tidak ada: {', '.join(missing)}"
        )

    for sensor in SENSORS:
        if sensor in df.columns:
            df[sensor] = pd.to_numeric(df[sensor], errors="coerce")

    for column in ("run_id", "sample_idx", "timestamp"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    # Historical LCD acquisitions (B33-B35) may contain metadata-only rows
    # emitted from PHASE_CHANGE events.  Preserve the raw CSV unchanged, but
    # remove those rows in-memory before plotting so they cannot create NaN
    # gaps / broken lines in normalized plots.
    sensor_frame_cols = [
        column
        for column in ["timestamp", "sample_idx"] + ADC_COLS
        if column in df.columns
    ]
    if sensor_frame_cols:
        metadata_only = df[sensor_frame_cols].isna().all(axis=1)
        df = df.loc[~metadata_only].copy()

    df = df.dropna(subset=["run_id"]).copy()
    df["run_id"] = df["run_id"].astype(int)
    df["phase"] = df["phase"].astype(str).str.lower().str.strip()
    return df


def make_sample_label(df: pd.DataFrame, filename: str) -> str:
    return " | ".join(
        [
            first_value(df, "sample_id", filename),
            first_value(df, "roast_level"),
            first_value(df, "origin"),
            first_value(df, "batch_id"),
        ]
    )


def output_is_current(output: Path, sources: Iterable[Path]) -> bool:
    if not output.exists() or output.stat().st_size == 0:
        return False
    source_list = list(sources)
    if not source_list:
        return True
    newest_source = max(path.stat().st_mtime for path in source_list)
    return output.stat().st_mtime >= newest_source


def sample_output_is_current(output: Path, source_csv: Path) -> bool:
    """Freshness rule for per-sample plots.

    The normalized overview previously kept metadata-only PHASE_CHANGE rows,
    which could introduce NaN gaps.  Treat this generator file as an
    additional dependency for that output so the fixed implementation is
    regenerated once after a plotting-code update.  Other per-sensor plots
    already filtered NaNs and only depend on the source CSV.
    """
    sources = [source_csv]
    if output.name == "all_sensors_normalized.png":
        sources.append(Path(__file__).resolve())
    return output_is_current(output, sources)


def valid_sensor_rows(df: pd.DataFrame, sensor: str) -> pd.DataFrame:
    if sensor not in df.columns:
        return df.iloc[0:0].copy()
    return df[df[sensor].notna()].copy()


def infer_phase_boundary(df: pd.DataFrame, sensor: str) -> float | None:
    fractions: list[float] = []
    for run_id in sorted(df["run_id"].unique()):
        run = valid_sensor_rows(df[df["run_id"] == run_id], sensor)
        if len(run) < 2:
            continue
        purging = int((run["phase"] == "purging").sum())
        collecting = int((run["phase"] == "collecting").sum())
        total = purging + collecting
        if purging > 0 and collecting > 0 and total > 0:
            fractions.append(purging / total)
    if not fractions:
        return None
    return float(np.median(fractions))


def save_figure(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_raw_signal(
    df: pd.DataFrame,
    sensor: str,
    output_path: Path,
    title: str,
) -> bool:
    data = valid_sensor_rows(df, sensor)
    if data.empty:
        return False

    x = np.arange(len(data))
    plt.figure(figsize=(15, 5))
    plt.plot(x, data[sensor].to_numpy(), linewidth=1)

    run_changes = data["run_id"].ne(data["run_id"].shift())
    for position in np.where(run_changes.to_numpy())[0]:
        if position > 0:
            plt.axvline(
                position,
                linestyle="--",
                linewidth=0.6,
                alpha=0.35,
            )

    plt.title(f"Raw Signal\n{title}\n{pretty_sensor(sensor)}")
    plt.xlabel("Urutan sampel sensor valid")
    plt.ylabel(sensor_ylabel(sensor))
    plt.grid(alpha=0.25)
    save_figure(output_path)
    return True


def plot_cycle_overlay(
    df: pd.DataFrame,
    sensor: str,
    output_path: Path,
    title: str,
) -> bool:
    plt.figure(figsize=(12, 6))
    valid_runs = 0

    for run_id in sorted(df["run_id"].unique()):
        run = valid_sensor_rows(df[df["run_id"] == run_id], sensor)
        if len(run) < 2:
            continue
        x = np.linspace(0.0, 1.0, len(run))
        plt.plot(x, run[sensor].to_numpy(), alpha=0.30, linewidth=1)
        valid_runs += 1

    if valid_runs == 0:
        plt.close()
        return False

    boundary = infer_phase_boundary(df, sensor)
    if boundary is not None:
        plt.axvline(
            boundary,
            linestyle="--",
            linewidth=1.5,
            label="Purging → Collecting",
        )

    plt.title(
        f"Overlay Siklus ({valid_runs} run)\n"
        f"{title}\n{pretty_sensor(sensor)}"
    )
    plt.xlabel("Posisi relatif dalam 1 siklus (0–1)")
    plt.ylabel(sensor_ylabel(sensor))
    if boundary is not None:
        plt.legend()
    plt.grid(alpha=0.25)
    save_figure(output_path)
    return True


def plot_mean_cycle(
    df: pd.DataFrame,
    sensor: str,
    output_path: Path,
    title: str,
) -> bool:
    sequences: list[np.ndarray] = []
    for run_id in sorted(df["run_id"].unique()):
        run = valid_sensor_rows(df[df["run_id"] == run_id], sensor)
        values = run[sensor].to_numpy(dtype=float)
        if len(values) < 2:
            continue
        old_x = np.linspace(0.0, 1.0, len(values))
        new_x = np.linspace(0.0, 1.0, MEAN_CYCLE_POINTS)
        sequences.append(np.interp(new_x, old_x, values))

    if not sequences:
        return False

    matrix = np.vstack(sequences)
    mean_signal = np.mean(matrix, axis=0)
    std_signal = np.std(matrix, axis=0)
    x = np.linspace(0.0, 1.0, MEAN_CYCLE_POINTS)

    plt.figure(figsize=(12, 6))
    plt.plot(x, mean_signal, linewidth=2, label="Mean")
    plt.fill_between(
        x,
        mean_signal - std_signal,
        mean_signal + std_signal,
        alpha=0.20,
        label="±1 SD",
    )

    boundary = infer_phase_boundary(df, sensor)
    if boundary is not None:
        plt.axvline(
            boundary,
            linestyle="--",
            linewidth=1.5,
            label="Purging → Collecting",
        )

    plt.title(
        f"Rata-rata Pola Siklus ({len(sequences)} run)\n"
        f"{title}\n{pretty_sensor(sensor)}"
    )
    plt.xlabel("Posisi relatif dalam 1 siklus (0–1)")
    plt.ylabel(sensor_ylabel(sensor))
    plt.grid(alpha=0.25)
    plt.legend()
    save_figure(output_path)
    return True


def plot_all_sensors_normalized(
    df: pd.DataFrame,
    output_path: Path,
    title: str,
) -> bool:
    plotted = 0
    plt.figure(figsize=(15, 7))

    for sensor in SENSORS:
        if sensor not in df.columns:
            continue
        values = pd.to_numeric(df[sensor], errors="coerce")
        minimum = values.min(skipna=True)
        maximum = values.max(skipna=True)
        if pd.isna(minimum) or pd.isna(maximum) or maximum == minimum:
            continue
        normalized = (values - minimum) / (maximum - minimum)
        plt.plot(
            np.arange(len(normalized)),
            normalized,
            linewidth=1,
            label=pretty_sensor(sensor),
        )
        plotted += 1

    if plotted == 0:
        plt.close()
        return False

    plt.title(f"Perbandingan Semua Sensor - Normalisasi Min-Max\n{title}")
    plt.xlabel("Urutan baris raw acquisition")
    plt.ylabel("Nilai ternormalisasi (0–1)")
    plt.legend(ncol=3, fontsize=8)
    plt.grid(alpha=0.25)
    save_figure(output_path)
    return True


def sample_expected_outputs(
    header: Iterable[str],
    output_folder: Path,
) -> list[Path]:
    header_set = set(header)
    available = [sensor for sensor in SENSORS if sensor in header_set]
    outputs: list[Path] = []
    for sensor in available:
        outputs.extend(
            [
                output_folder / f"raw_{sensor}.png",
                output_folder / f"overlay_{sensor}.png",
                output_folder / f"mean_{sensor}.png",
            ]
        )
    if available:
        outputs.append(output_folder / "all_sensors_normalized.png")
    return outputs


def process_file(
    file_path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[int, int]:
    try:
        header = read_header(file_path)
    except Exception as exc:
        print(f"[FAIL] {file_path.name}: header: {exc}")
        return 0, 0

    if "adc_mq9" in header and "adc_mq3" not in header:
        print(f"[SKIP legacy MQ9] {file_path.name}")
        return 0, 1

    output_folder = OUTPUT_DIR / safe_name(file_path.stem)
    expected_from_header = sample_expected_outputs(header, output_folder)

    if (
        not force
        and expected_from_header
        and all(
            sample_output_is_current(path, file_path)
            for path in expected_from_header
        )
    ):
        print(f"[SKIP lengkap] {file_path.name}")
        return 0, len(expected_from_header)

    # Only files that appear incomplete reach this point. Load them once so
    # columns that exist but contain no usable values (for example historical
    # temperature/humidity placeholders) are not treated as missing plots
    # forever.
    try:
        df = load_data(file_path)
    except Exception as exc:
        print(f"[FAIL] {file_path.name}: {exc}")
        return 0, 0

    available_sensors = [
        sensor
        for sensor in SENSORS
        if sensor in df.columns and df[sensor].notna().sum() >= 2
    ]
    expected = sample_expected_outputs(available_sensors, output_folder)

    if (
        not force
        and expected
        and all(
            sample_output_is_current(path, file_path)
            for path in expected
        )
    ):
        print(f"[SKIP lengkap] {file_path.name}")
        return 0, len(expected)

    if dry_run:
        pending = [
            path
            for path in expected
            if force or not sample_output_is_current(path, file_path)
        ]
        print(f"[DRY SAMPLE] {file_path.name}: pending={len(pending)}")
        return len(pending), len(expected) - len(pending)

    output_folder.mkdir(parents=True, exist_ok=True)
    title = make_sample_label(df, file_path.stem)
    generated = 0
    skipped = 0

    for sensor in SENSORS:
        if sensor not in df.columns or df[sensor].notna().sum() < 2:
            continue

        tasks = (
            (output_folder / f"raw_{sensor}.png", plot_raw_signal),
            (output_folder / f"overlay_{sensor}.png", plot_cycle_overlay),
            (output_folder / f"mean_{sensor}.png", plot_mean_cycle),
        )
        for output_path, plotter in tasks:
            if not force and sample_output_is_current(output_path, file_path):
                skipped += 1
                continue
            if plotter(df, sensor, output_path, title):
                generated += 1

    normalized_path = output_folder / "all_sensors_normalized.png"
    if not force and sample_output_is_current(normalized_path, file_path):
        skipped += 1
    elif plot_all_sensors_normalized(df, normalized_path, title):
        generated += 1

    print(
        f"[SAMPLE] {file_path.name}: generated={generated}, "
        f"skipped={skipped}"
    )
    return generated, skipped


def inspect_five_run_source(file_path: Path) -> SourceRecord | None:
    try:
        header = read_header(file_path)
    except Exception:
        return None

    header_set = set(header)
    if "adc_mq3" not in header_set or "adc_mq9" in header_set:
        return None

    required = {"run_id", "sample_id", "roast_level", "origin", "batch_id"}
    if not required <= header_set:
        return None

    try:
        probe = pd.read_csv(
            file_path,
            usecols=[
                "run_id",
                "sample_id",
                "roast_level",
                "origin",
                "batch_id",
            ],
        )
    except Exception:
        return None

    runs = sorted(
        pd.to_numeric(probe["run_id"], errors="coerce")
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )
    if runs != list(AGGREGATE_RUNS):
        return None

    roast = first_value(probe, "roast_level", "").lower()
    origin = first_value(probe, "origin", "")
    sample_id = first_value(probe, "sample_id", "")
    batch_id = first_value(probe, "batch_id", "")
    if roast not in ROAST_ORDER or not origin or origin == "-":
        return None

    return SourceRecord(
        path=file_path,
        sample_id=sample_id,
        roast=roast,
        origin=origin,
        batch_id=batch_id,
        sensors=frozenset(
            sensor for sensor in SENSORS if sensor in header_set
        ),
    )


def build_origin_index(
    files: Iterable[Path],
) -> dict[str, list[SourceRecord]]:
    grouped: dict[str, list[SourceRecord]] = {}
    for file_path in files:
        record = inspect_five_run_source(file_path)
        if record is None:
            continue
        grouped.setdefault(record.origin, []).append(record)

    for records in grouped.values():
        records.sort(
            key=lambda item: (item.roast, item.batch_id, item.path.name)
        )
    return dict(sorted(grouped.items(), key=lambda item: item[0].lower()))


def resampled_session_trace(
    df: pd.DataFrame,
    sensor: str,
) -> np.ndarray | None:
    parts: list[np.ndarray] = []
    for run_id in AGGREGATE_RUNS:
        run = valid_sensor_rows(df[df["run_id"] == run_id], sensor)
        values = run[sensor].to_numpy(dtype=float)
        if len(values) < 2:
            return None
        old_x = np.linspace(0.0, 1.0, len(values))
        new_x = np.linspace(0.0, 1.0, AGGREGATE_POINTS_PER_RUN)
        parts.append(np.interp(new_x, old_x, values))
    return np.concatenate(parts)


def aggregate_origin_sensor(
    sensor: str,
    records: list[SourceRecord],
    df_cache: dict[Path, pd.DataFrame],
) -> tuple[dict[str, np.ndarray], dict[str, int], list[Path]]:
    traces: dict[str, list[np.ndarray]] = {
        roast: [] for roast in ROAST_ORDER
    }
    sources: list[Path] = []

    for record in records:
        if sensor not in record.sensors:
            continue
        if record.path not in df_cache:
            try:
                df_cache[record.path] = load_data(record.path)
            except Exception as exc:
                print(f"[WARN] {record.path.name}: {exc}")
                continue

        trace = resampled_session_trace(df_cache[record.path], sensor)
        if trace is None:
            continue
        traces[record.roast].append(trace)
        sources.append(record.path)

    means: dict[str, np.ndarray] = {}
    counts: dict[str, int] = {}
    for roast in ROAST_ORDER:
        if not traces[roast]:
            continue
        matrix = np.vstack(traces[roast])
        means[roast] = np.mean(matrix, axis=0)
        counts[roast] = len(traces[roast])
    return means, counts, sources


def draw_cycle_markers(axis) -> None:
    for run_index in range(1, len(AGGREGATE_RUNS)):
        axis.axvline(
            run_index * AGGREGATE_POINTS_PER_RUN,
            linestyle="--",
            linewidth=0.6,
            alpha=0.25,
        )


def plot_origin_roast_comparison(
    origin: str,
    sensor: str,
    means: dict[str, np.ndarray],
    counts: dict[str, int],
    output_path: Path,
) -> bool:
    if not means:
        return False

    x = np.arange(len(next(iter(means.values()))))
    fig, axis = plt.subplots(figsize=(12, 6))
    for roast in ROAST_ORDER:
        if roast not in means:
            continue
        axis.plot(
            x,
            means[roast],
            color=ROAST_COLORS[roast],
            linewidth=1.8,
            label=f"{roast} (n={counts[roast]})",
        )

    draw_cycle_markers(axis)
    axis.set_title(
        f"{display_origin(origin)} - {pretty_sensor(sensor)}\n"
        "Light / Medium / Dark - rata-rata seluruh batch 5-run"
    )
    axis.set_xlabel("Urutan titik (5 siklus; dinormalisasi per siklus)")
    axis.set_ylabel(sensor_ylabel(sensor))
    axis.grid(alpha=0.20)
    axis.legend(loc="best")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return True


def plot_sensor_origin_overview(
    sensor: str,
    origin_data: list[
        tuple[str, dict[str, np.ndarray], dict[str, int]]
    ],
    output_path: Path,
) -> bool:
    if not origin_data:
        return False

    columns = 2 if len(origin_data) > 1 else 1
    rows = math.ceil(len(origin_data) / columns)
    fig, axes = plt.subplots(
        rows,
        columns,
        figsize=(15, max(4.2 * rows, 5.0)),
        squeeze=False,
    )
    flat_axes = axes.ravel()

    for index, (origin, means, _counts) in enumerate(origin_data):
        axis = flat_axes[index]
        x = np.arange(len(next(iter(means.values()))))
        for roast in ROAST_ORDER:
            if roast not in means:
                continue
            axis.plot(
                x,
                means[roast],
                color=ROAST_COLORS[roast],
                linewidth=1.5,
                label=roast,
            )
        draw_cycle_markers(axis)
        axis.set_title(display_origin(origin))
        axis.set_xlabel("Urutan titik (seluruh 5 siklus)")
        axis.set_ylabel(sensor_ylabel(sensor))
        axis.grid(alpha=0.18)

    for axis in flat_axes[len(origin_data):]:
        axis.set_visible(False)

    available_roasts = [
        roast
        for roast in ROAST_ORDER
        if any(roast in means for _origin, means, _counts in origin_data)
    ]
    handles = [
        Line2D(
            [0],
            [0],
            color=ROAST_COLORS[roast],
            lw=2,
            label=roast,
        )
        for roast in available_roasts
    ]
    if handles:
        fig.legend(
            handles=handles,
            loc="upper center",
            ncol=len(handles),
            bbox_to_anchor=(0.5, 0.97),
        )

    fig.suptitle(
        f"Data E-NOSE - dipisah per origin - {pretty_sensor(sensor)}",
        fontsize=15,
        y=0.995,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return True


def generate_origin_plots(
    files: list[Path],
    *,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[int, int]:
    grouped = build_origin_index(files)
    if not grouped:
        print("[ORIGIN] tidak ada acquisition 5-run yang kompatibel")
        return 0, 0

    print(
        f"[ORIGIN] {len(grouped)} origin dari "
        f"{sum(len(records) for records in grouped.values())} file 5-run"
    )

    df_cache: dict[Path, pd.DataFrame] = {}
    aggregate_cache: dict[
        tuple[str, str],
        tuple[dict[str, np.ndarray], dict[str, int], list[Path]],
    ] = {}

    def get_aggregate(
        origin: str,
        sensor: str,
    ) -> tuple[dict[str, np.ndarray], dict[str, int], list[Path]]:
        key = (origin, sensor)
        if key not in aggregate_cache:
            aggregate_cache[key] = aggregate_origin_sensor(
                sensor,
                grouped[origin],
                df_cache,
            )
        return aggregate_cache[key]

    generated = 0
    skipped = 0

    for origin, records in grouped.items():
        output_folder = ORIGIN_OUTPUT_DIR / safe_name(origin)
        for sensor in SENSORS:
            candidate_sources = [
                record.path
                for record in records
                if sensor in record.sensors
            ]
            if not candidate_sources:
                continue

            output_path = (
                output_folder / f"roast_comparison_{sensor}.png"
            )
            if (
                not force
                and output_is_current(
                    output_path,
                    candidate_sources + [Path(__file__), EXCLUSION_MANIFEST],
                )
            ):
                skipped += 1
                continue

            if dry_run:
                print(
                    f"[DRY ORIGIN] {display_origin(origin)} / {sensor}"
                )
                generated += 1
                continue

            means, counts, sources = get_aggregate(origin, sensor)
            if means and sources and plot_origin_roast_comparison(
                origin,
                sensor,
                means,
                counts,
                output_path,
            ):
                generated += 1

    overview_folder = ORIGIN_OUTPUT_DIR / "_overview"
    for sensor in SENSORS:
        source_paths = [
            record.path
            for records in grouped.values()
            for record in records
            if sensor in record.sensors
        ]
        if not source_paths:
            continue

        output_path = overview_folder / f"roast_comparison_{sensor}.png"
        if not force and output_is_current(
            output_path, source_paths + [Path(__file__), EXCLUSION_MANIFEST]
        ):
            skipped += 1
            continue

        if dry_run:
            print(f"[DRY OVERVIEW] {sensor}")
            generated += 1
            continue

        origin_data = []
        for origin in grouped:
            means, counts, sources = get_aggregate(origin, sensor)
            if means and sources:
                origin_data.append((origin, means, counts))

        if plot_sensor_origin_overview(
            sensor,
            origin_data,
            output_path,
        ):
            generated += 1

    print(f"[ORIGIN] generated={generated}, skipped={skipped}")
    return generated, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate missing/stale sensor plots and roast comparisons "
            "per coffee origin."
        )
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate output walaupun masih current.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help=(
            "Scan subfolder data/raw juga; legacy/incomplete tetap di-skip."
        ),
    )
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="Hanya plot detail per CSV.",
    )
    parser.add_argument(
        "--origin-only",
        action="store_true",
        help="Hanya plot per origin dan overview.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Tampilkan pekerjaan tanpa menulis PNG.",
    )
    args = parser.parse_args()
    if args.sample_only and args.origin_only:
        parser.error("--sample-only dan --origin-only tidak boleh bersamaan")
    return args


def main() -> int:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = get_csv_files(recursive=args.recursive)
    if not files:
        print(f"Tidak ada CSV aktif di {DATA_DIR}")
        return 1

    print("=" * 78)
    print("SMART COFFEE E-NOSE - SENSOR PLOT AUTO GENERATOR")
    print("=" * 78)
    print(f"Data dir    : {DATA_DIR}")
    print(f"Output dir  : {OUTPUT_DIR}")
    print(f"CSV aktif   : {len(files)}")
    print(
        f"Mode        : {'dry-run' if args.dry_run else 'write'}"
        f"{' + force' if args.force else ''}"
    )

    total_generated = 0
    total_skipped = 0

    if not args.origin_only:
        for file_path in files:
            generated, skipped = process_file(
                file_path,
                force=args.force,
                dry_run=args.dry_run,
            )
            total_generated += generated
            total_skipped += skipped

    if not args.sample_only:
        generated, skipped = generate_origin_plots(
            files,
            force=args.force,
            dry_run=args.dry_run,
        )
        total_generated += generated
        total_skipped += skipped

    print("=" * 78)
    print(f"Generated : {total_generated}")
    print(f"Skipped   : {total_skipped}")
    if args.dry_run:
        print("Dry-run selesai; tidak ada PNG yang ditulis.")
    else:
        print(f"Hasil     : {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
