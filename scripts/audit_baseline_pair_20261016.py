"""Read-only comparison of the two physical 60-s Nextion baseline recordings.

Only creates result files in a new folder. Never opens COM ports, changes source
CSV/EEPROM, or declares clean-air provenance without operator evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from acquisition_schema import ADC_COLS
from baseline_quality import inspect_baseline

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "data/baseline/BASELINE_20261016_185310_e636759c6edb.csv",
    ROOT / "data/baseline/BASELINE_20261016_185522_126dd90194e8.csv",
]
OUT = ROOT / "results/baseline_60s_pair_qa_20261016"


def main():
    if OUT.exists():
        raise FileExistsError(f"Refusing overwrite: {OUT}")
    frames = [pd.read_csv(path) for path in FILES]
    reports = [inspect_baseline(path) for path in FILES]
    for path, frame, report in zip(FILES, frames, reports):
        qc = json.loads(path.with_suffix(".baseline_qc.json").read_text(encoding="utf-8"))
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        assert sha == report["sha256"] == qc["sha256"]
        assert len(frame) == report["sample_count"] == 60
        assert frame.isna().sum().sum() == 0
        assert list(frame.sample_idx) == list(range(1, 61))
        assert len(report["sensor_b0"]) == len(ADC_COLS) == 10
    OUT.mkdir(parents=True)
    plot_folder = OUT / "plots"
    plot_folder.mkdir()
    comparison = []
    for column, one, two in zip(ADC_COLS, reports[0]["sensor_b0"], reports[1]["sensor_b0"]):
        assert one["sensor"] == two["sensor"] == column
        b1, b2 = one["b0_last10_median_adc"], two["b0_last10_median_adc"]
        percent = 100 * (b2 - b1) / b1
        comparison.append({
            "sensor": column, "baseline_1_adc": b1, "baseline_2_adc": b2,
            "baseline_2_minus_1_adc": b2-b1,
            "baseline_2_vs_1_pct": round(percent, 4),
            "within_run_1_drift_pct": one["first_to_last_drift_pct"],
            "within_run_2_drift_pct": two["first_to_last_drift_pct"],
            "within_run_1_pass_1pct": one["stable_within_1pct_by_window_medians"],
            "within_run_2_pass_1pct": two["stable_within_1pct_by_window_medians"],
        })
        fig, ax = plt.subplots(figsize=(10, 4.7))
        for idx, (frame, b0) in enumerate(((frames[0], b1), (frames[1], b2)), 1):
            time_s = (frame["timestamp"] - frame["timestamp"].iloc[0]) / 1000
            line, = ax.plot(time_s, frame[column], linewidth=1.35, label=f"Baseline {idx} (60 samples)")
            ax.axhline(b0, linestyle=":", linewidth=1.0, color=line.get_color(),
                       label=f"B0-{idx} (last 10 median): {b0:g}")
        ax.set(xlabel="Detik relatif tiap sesi (dua akuisisi terpisah)",
               ylabel="ADC mentah",
               title=f"Nextion 60 s baseline comparison | {column}")
        ax.grid(alpha=.23)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(plot_folder / f"{column}_baseline_pair.png", dpi=150)
        plt.close(fig)
    df = pd.DataFrame(comparison)
    df.to_csv(OUT / "baseline_b0_comparison.csv", index=False)
    gaps = [frame.timestamp.diff().dropna() for frame in frames]
    summary = {
        "source_files": [path.name for path in FILES],
        "source_sha256": [report["sha256"] for report in reports],
        "both_capture_qc_valid": True,
        "sampling_per_recording": [60,60],
        "first_to_last_s": [round(report["duration_first_to_last_ms"]/1000, 3) for report in reports],
        "sampling_gaps_ms_min_max": [[int(g.min()), int(g.max())] for g in gaps],
        "missing_cells": [int(frame.isna().sum().sum()) for frame in frames],
        "within_run_1_percent_criterion_pass_sensors": int(df["within_run_1_pass_1pct"].sum()),
        "within_run_2_percent_criterion_pass_sensors": int(df["within_run_2_pass_1pct"].sum()),
        "max_inter_session_b0_absolute_pct": round(float(df.baseline_2_vs_1_pct.abs().max()), 4),
        "inter_session_b0_within_1pct_all_sensors": bool(df.baseline_2_vs_1_pct.abs().le(1.0).all()),
        "baseline_2_candidate_only": True,
        "physical_clean_air_verified_independently": False,
        "before_B41": False,
        "eeprom_r0_written_during_capture": False,
        "evaluation": "Second session meets exploratory 1% within-run and between-run criteria, but physical air cleanliness and sensor-specific stability not independently validated.",
        "plot_count":len(list(plot_folder.glob("*.png"))),
    }
    (OUT / "summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
