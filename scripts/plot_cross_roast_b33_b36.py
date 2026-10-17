"""Bandingkan dark/medium/light satu origin B33--B36, dinormalisasi pada t0.

Dua bentuk plot per kanal: overlay akuisisi lima siklus per batch dan
penggabungan visual B33 -> B36 berdampingan per tingkat roasting.
Setiap file memakai t0 = sampel sensor TERAKHIR purging siklus pertama,
sebelum collecting pertama: x = indeks sampel relatif t0;
y = ADC(sensor) - ADC(sensor pada t0).
Tidak melakukan interpolasi, smoothing, pengubahan CSV, atau validasi label
spesimen fisik. Berkas HOLD tidak masuk kurva seolah datanya lengkap.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

from acquisition_schema import ADC_COLS
from validate_acquisition import classify_rows, validate_file

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
ARCHIVE = RAW / "irul_B36_B37"
ARCHIVE_MANIFEST = ROOT / "data" / "analysis" / "irul_B36_B37_import_manifest.csv"
OUT = ROOT / "results" / "plots_cross_roast_B33_B36_t0norm_multicolor_20261018"
BATCHES = ("B33", "B34", "B35", "B36")
ROAST = {"D": "dark", "M": "medium", "L": "light"}
# 12 warna berbeda: kelompok rona merepresentasikan roast, nuansa dalam
# kelompok mewakili batch. Pola garis tambahan agar tetap bisa dibedakan
# apabila dicetak grayscale atau tampilan tidak mampu membedakan warna.
TRACE_COLORS = {
    ("D", "B33"): "#174A93", ("D", "B34"): "#1688C6",
    ("D", "B35"): "#7254B2", ("D", "B36"): "#4FA8DA",
    ("M", "B33"): "#C53A30", ("M", "B34"): "#EE7229",
    ("M", "B35"): "#D19A1A", ("M", "B36"): "#A73870",
    ("L", "B33"): "#087E54", ("L", "B34"): "#48A537",
    ("L", "B35"): "#16A29C", ("L", "B36"): "#8BAE32",
}
BATCH_STYLES = {"B33": "-", "B34": "--", "B35": ":", "B36": "-."}
NAME = re.compile(r"^([DML])-([A-Z0-9]+)_(B3[3-6])\.csv$")


@dataclass
class Record:
    source: Path
    level: str
    origin_code: str
    origin_name: str
    batch: str
    data: pd.DataFrame
    sha256: str


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def manifest_hashes(manifest: Path) -> dict[str, str]:
    if not manifest.is_file():
        return {}
    df = pd.read_csv(manifest, dtype=str).fillna("")
    expected = {"import_relative_path", "sha256"}
    if not expected.issubset(df.columns):
        raise ValueError("Manifest arsip tidak memiliki kolom SHA256 yang wajib")
    result = {}
    for row in df.itertuples(index=False):
        name = Path(row.import_relative_path.replace("\\", "/")).name
        if name in result:
            raise ValueError(f"Nama duplikat di manifest arsip: {name}")
        result[name] = row.sha256.lower()
    return result


def scan(raw: Path = RAW, archive: Path = ARCHIVE,
         manifest: Path = ARCHIVE_MANIFEST) -> tuple[list[Record], list[dict]]:
    """Utamakan root raw; fallback arsip HANYA bila B36 root tidak ada.

    Fallback arsip wajib diverifikasi terhadap manifest impor. Jika root ada
    tapi gagal validasi, tidak boleh ditukar diam-diam dengan arsip lain.
    """
    hashes = manifest_hashes(manifest)
    selected: dict[str, Path] = {}
    for batch in BATCHES:
        for path in sorted(raw.glob(f"*-*_{batch}.csv")):
            if NAME.fullmatch(path.name) and path.name.split("-", 1)[1].split("_", 1)[0] != "CAW":
                selected[path.name] = path
    # Arsip B36 mengisi berkas yang belum ada di root saja.
    for path in sorted(archive.glob("*-*_B36.csv")):
        if NAME.fullmatch(path.name) and "-CAW_" not in path.name:
            selected.setdefault(path.name, path)

    records, excluded = [], []
    for name, path in sorted(selected.items()):
        level, code, batch = NAME.fullmatch(name).groups()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.parent == archive and hashes.get(name) != digest:
            excluded.append(dict(file=relative(path), origin=code, batch=batch,
                                 roast=level, reason="missing_or_mismatched_archive_manifest_sha256"))
            continue
        issues = validate_file(path, expected_cycles=5)
        if issues:
            excluded.append(dict(file=relative(path), origin=code, batch=batch,
                                 roast=level, reason=" | ".join(issues)))
            continue
        df = pd.read_csv(path, low_memory=False)
        sensors, _, partial = classify_rows(df)
        if partial.any():
            excluded.append(dict(file=relative(path), origin=code, batch=batch,
                                 roast=level, reason="partial_sensor_rows"))
            continue
        df = df.loc[sensors].reset_index(drop=True)
        expected_id = f"{level}-{code}"
        if (not df.sample_id.eq(expected_id).all() or not df.batch_id.eq(batch).all()
                or not df.roast_level.astype(str).str.lower().eq(ROAST[level]).all()
                or df.origin.isna().any() or df.origin.astype(str).str.strip().eq("").any()
                or df.origin.nunique() != 1):
            excluded.append(dict(file=relative(path), origin=code, batch=batch,
                                 roast=level, reason="filename_and_metadata_mismatch"))
            continue
        records.append(Record(path, level, code, str(df.origin.iloc[0]), batch, df, digest))
    return records, excluded


def groups(records: list[Record]) -> dict[tuple[str, str], list[Record]]:
    result = defaultdict(list)
    for record in records:
        result[record.origin_code, record.origin_name].append(record)
    # Origin benar-benar sama berdasarkan kode DAN metadata teks. Jangan
    # diam-diam gabungkan TEM = Temanggung dengan TEM = Temanggung Mukidi.
    return {k: sorted(v, key=lambda r: (r.batch, r.level))
            for k, v in sorted(result.items())
            if len({r.level for r in v}) >= 2 and len({r.batch for r in v}) >= 2}


def safe_slug(code: str, name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")[:64]
    return f"{code}_{clean}"


def normalize_first_purge(data: pd.DataFrame, sensor: str):
    """Return (x_rel, delta_adc, anchor_adc, n_purge, anchor_idx).

    Sampel purging pra-t0 dipertahankan (x negatif). Sampel collecting pertama
    berada di x=1 jika pengurutan akuisisi benar. Tidak ada resampling.
    """
    purge = data.loc[(data.run_id == 1) & (data.phase == "purging")]
    collect = data.loc[(data.run_id == 1) & (data.phase == "collecting")]
    if purge.empty or collect.empty or not purge.index.max() < collect.index.min():
        raise ValueError("Fase awal harus purging sebelum collecting")
    anchor_idx = int(purge.index[-1])
    x = np.arange(len(data), dtype=int) - anchor_idx
    anchor_adc = float(data.loc[anchor_idx, sensor])
    y = data[sensor].to_numpy(dtype=float) - anchor_adc
    if not np.all(np.isfinite(y)) or x[anchor_idx] != 0 or y[anchor_idx] != 0:
        raise ValueError("Normalisasi t0 gagal")
    if x[int(collect.index[0])] != 1:
        raise ValueError("Collecting pertama tidak tepat setelah t0")
    return x, y, anchor_adc, len(purge), anchor_idx


def draw_overlay(items: list[Record], sensor: str, label: str, target: Path):
    fig, ax = plt.subplots(figsize=(14, 5.8))
    for record in sorted(items, key=lambda r: (r.level, r.batch)):
        x, y, _, _, _ = normalize_first_purge(record.data, sensor)
        ax.plot(x, y,
                linestyle=BATCH_STYLES[record.batch],
                color=TRACE_COLORS[record.level, record.batch],
                linewidth=1.35, alpha=.92,
                label=f"{ROAST[record.level].title()} · {record.batch}")
    ax.axhline(0, color="#444444", linestyle=":", lw=1, alpha=.7)
    ax.axvline(0, color="#444444", linestyle="--", lw=1, alpha=.7)
    ax.set(title=f"{label} | {sensor} | Overlay B33–B36 · normalisasi t0",
           xlabel="Indeks sampel relatif t0 (akhir purging pertama, bukan detik)",
           ylabel="ΔADC = ADC - ADC(t0)")
    ax.grid(alpha=.22)
    ax.legend(title="Roasting · Batch", loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    fig.subplots_adjust(right=.79, bottom=.15)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=155, facecolor="white")
    plt.close(fig)


def draw_merged(items: list[Record], sensor: str, label: str, target: Path):
    """Susun batch per roast tanpa menyambung akhir satu CSV ke awal CSV lain."""
    width = max(175, max(len(record.data) for record in items) + 22)
    anchor_position = 32
    fig, ax = plt.subplots(figsize=(15, 5.7))
    for record in sorted(items, key=lambda r: (r.level, r.batch)):
        idx = BATCHES.index(record.batch)
        x_relative, y, _, _, _ = normalize_first_purge(record.data, sensor)
        x = idx * width + anchor_position + x_relative
        ax.plot(x, y, color=TRACE_COLORS[record.level, record.batch],
                linestyle=BATCH_STYLES[record.batch], linewidth=1.2, alpha=.92)
    for i in range(1, len(BATCHES)):
        ax.axvline(i * width, color="grey", linewidth=.8, linestyle="--", alpha=.55)
    for i in range(len(BATCHES)):
        ax.axvline(i * width + anchor_position, color="grey", linewidth=.7,
                   linestyle=":", alpha=.45)
    ax.axhline(0, color="#444444", linestyle=":", lw=1, alpha=.7)
    ax.set_xticks([i * width + anchor_position for i in range(len(BATCHES))],
                  [f"{b}\nt0" for b in BATCHES])
    ax.set_xlim(0, len(BATCHES) * width)
    ax.set(title=f"{label} | {sensor} | B33–B36 · t0 normalisasi per file",
           xlabel="Batch terpisah | titik t0 = akhir purging pertama (bukan waktu kontinu)",
           ylabel="ΔADC = ADC - ADC(t0)")
    ax.grid(alpha=.2)
    handles = [Line2D([0], [0], color=TRACE_COLORS[r.level, r.batch],
                      linestyle=BATCH_STYLES[r.batch], lw=2,
                      label=f"{ROAST[r.level].title()} · {r.batch}")
               for r in sorted(items, key=lambda r: (r.level, r.batch))]
    ax.legend(handles=handles, title="Roasting · Batch", loc="upper left",
              bbox_to_anchor=(1.01, 1), fontsize=8)
    fig.subplots_adjust(right=.80, bottom=.17)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=155, facecolor="white")
    plt.close(fig)


def generate(output: Path, records: list[Record], excluded: list[dict],
             sensors=ADC_COLS) -> dict:
    if output.exists():
        raise FileExistsError(f"Menolak menimpa output lama: {output}")
    if output == RAW or RAW in output.parents:
        raise ValueError("Output tidak boleh disimpan ke dalam data/raw")
    if len(set(TRACE_COLORS.values())) != len(TRACE_COLORS):
        raise ValueError("Setiap batch + roasting wajib memakai warna unik")
    plot_groups = groups(records)
    if not plot_groups:
        raise ValueError("Tidak ada origin dengan >=2 level roasting dan >=2 batch valid")
    output.mkdir(parents=True)
    index = []
    diagnostics = []
    for (code, name), items in plot_groups.items():
        stem = safe_slug(code, name)
        for sensor in sensors:
            for r in items:
                x, y, base, n_purge, anchor_idx = normalize_first_purge(r.data, sensor)
                diagnostics.append(dict(file=relative(r.source), sha256=r.sha256,
                                        origin_code=code, origin_name=name,
                                        batch=r.batch, roast=ROAST[r.level], sensor=sensor,
                                        t0_anchor_adc=base, first_purge_samples=n_purge,
                                        t0_row_zero_based=anchor_idx, first_collect_x=1,
                                        t0_delta_adc=float(y[anchor_idx]),
                                        min_delta_adc=float(y.min()), max_delta_adc=float(y.max()),
                                        plotted_samples=len(x), color=TRACE_COLORS[r.level, r.batch],
                                        linestyle=BATCH_STYLES[r.batch]))
            for family, draw in (("01_overlay", draw_overlay), ("02_merge_per_roasting", draw_merged)):
                path = output / family / stem / f"{stem}_{sensor}.png"
                draw(items, sensor, f"{code}: {name}", path)
                index.append(dict(family=family, path=relative(path), origin_code=code,
                                  origin_name=name, sensor=sensor,
                                  source_files=";".join(relative(r.source) for r in items),
                                  number_of_traces=len(items)))

    for filename, rows, fields in (
        ("series_t0_diagnostics.csv", diagnostics,
         ["file", "sha256", "origin_code", "origin_name", "batch", "roast", "sensor",
          "t0_anchor_adc", "first_purge_samples", "t0_row_zero_based", "first_collect_x",
          "t0_delta_adc", "min_delta_adc", "max_delta_adc", "plotted_samples", "color", "linestyle"]),
        ("plot_index.csv", index,
         ["family", "path", "origin_code", "origin_name", "sensor", "source_files", "number_of_traces"]),
        ("excluded.csv", excluded, ["file", "origin", "batch", "roast", "reason"]),
        ("source_manifest.csv", [dict(file=relative(r.source), sha256=r.sha256,
                                     origin_code=r.origin_code, origin_name=r.origin_name,
                                     batch=r.batch, roast=ROAST[r.level],
                                     rows=len(r.data), cycles=r.data.run_id.nunique()) for r in records],
         ["file", "sha256", "origin_code", "origin_name", "batch", "roast", "rows", "cycles"]),
    ):
        with (output / filename).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    missing = []
    for (code, name), items in plot_groups.items():
        available = {(r.batch, r.level) for r in items}
        for batch in BATCHES:
            for level in ROAST:
                if (batch, level) not in available:
                    missing.append(dict(origin_code=code, origin_name=name,
                                        batch=batch, roast=ROAST[level], status="tidak_ada_kurva_lolos_QC"))
    with (output / "missing_series.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["origin_code", "origin_name", "batch", "roast", "status"])
        writer.writeheader()
        writer.writerows(missing)
    summary = dict(plots=len(index), origin_groups=len(plot_groups),
                   valid_csv=len(records), excluded_csv=len(excluded),
                   batches=list(BATCHES), missing_series=len(missing),
                   normalized_series=len(diagnostics),
                   plot_families=["01_overlay", "02_merge_per_roasting"],
                   normalization="each CSV/channel: t0 is last first-cycle purging sample; x = sensor row index - t0 index; y = ADC - ADC(t0); first collecting x=1",
                   colors="unique for every roast+batch series; dashed styles distinguish batches",
                   sampling="ordinal sensor rows, no interpolation, no continuous elapsed time",
                   source_policy="root data/raw preferred, missing B36 taken from irul archive only with SHA256 manifest verification",
                   origin_policy="exact origin metadata AND origin code must match",
                   archive_hold_policy="invalid/noncontiguous index excluded from plotting",
                   physical_specimen_ground_truth_verified=False,
                   raw_modified=False, previous_plots_overwritten=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    records, excluded = scan()
    summary = generate(args.output_dir.resolve(), records, excluded)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
