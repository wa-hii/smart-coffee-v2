"""Tes offline: merge antarbatch harus menjaga provenance, missing frames, dan raw."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import sys

import pandas as pd

from acquisition_schema import ADC_COLS, CSV_COLUMNS
from plot_cross_roast_b33_b36 import (
    TRACE_COLORS, generate, groups, normalize_first_purge, scan,
)


def make_csv(path: Path, level: str, code: str, batch: str,
             origin: str = "Arabika Sumatra Utara", broken: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    tick = 1
    for run in range(1, 6):
        for phase, count in (("purging", 25), ("collecting", 5)):
            for index in range(1, count + 1):
                row = dict(timestamp=tick * 1000, sample_id=f"{level}-{code}",
                           roast_level={"D": "dark", "M": "medium", "L": "light"}[level],
                           origin=origin, batch_id=batch, run_id=run, phase=phase,
                           sample_idx=(index + 1 if broken and run == 2 and phase == "purging" and index >= 8 else index),
                           temperature=25, humidity=40)
                row.update({s: 1500 + tick for s in ADC_COLS})
                rows.append(row)
                tick += 1
    pd.DataFrame(rows, columns=CSV_COLUMNS).to_csv(path, index=False)


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        raw = root / "raw"
        archive = raw / "irul_B36_B37"
        archive.mkdir(parents=True)
        manifest = root / "manifest.csv"
        for batch in ("B33", "B34", "B35"):
            for level in ("D", "M", "L"):
                make_csv(raw / f"{level}-MING_{batch}.csv", level, "MING", batch)
        make_csv(raw / "L-MING_B36.csv", "L", "MING", "B36")
        make_csv(archive / "M-MING_B36.csv", "M", "MING", "B36")
        make_csv(archive / "D-MING_B36.csv", "D", "MING", "B36", broken=True)
        # B36 L versi arsip yang tidak boleh mengganti source root.
        make_csv(archive / "L-MING_B36.csv", "L", "MING", "B36")
        make_csv(raw / "L-CAW_B33.csv", "L", "CAW", "B33", origin="CAW")
        make_csv(raw / "D-TEM_B33.csv", "D", "TEM", "B33", origin="Arabika Temanggung Mukidi")
        make_csv(raw / "M-TEM_B33.csv", "M", "TEM", "B33", origin="Arabika Temanggung")
        make_csv(raw / "L-TEM_B34.csv", "L", "TEM", "B34", origin="Arabika Temanggung")
        pd.DataFrame([
            dict(import_relative_path=f"data/raw/irul_B36_B37/{name}",
                 sha256=hashlib.sha256((archive / name).read_bytes()).hexdigest())
            for name in ("D-MING_B36.csv", "M-MING_B36.csv", "L-MING_B36.csv")
        ]).to_csv(manifest, index=False)
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.rglob("*.csv")}
        records, excluded = scan(raw, archive, manifest)
        ming = [r for r in records if r.origin_code == "MING"]
        assert len(ming) == 11
        assert any(r.batch == "B36" and r.level == "M" and r.source.parent == archive for r in ming)
        assert any(r.batch == "B36" and r.level == "L" and r.source.parent == raw for r in ming)
        assert any("D-MING_B36.csv" in row["file"] and "tidak kontigu" in row["reason"] for row in excluded)
        assert all(r.origin_code != "CAW" for r in records)
        assert len({r.origin_name for r in records if r.origin_code == "TEM"}) == 2
        assert len(groups(records)["MING", "Arabika Sumatra Utara"]) == 11
        assert len(set(TRACE_COLORS.values())) == 12  # semua kombinasi warna berbeda
        example = next(r for r in ming if r.batch == "B33" and r.level == "D")
        x, y, baseline, first_purge_count, anchor = normalize_first_purge(example.data, ADC_COLS[0])
        assert len(x) == len(example.data) == len(y) == 150
        assert first_purge_count == 25 and anchor == 24
        assert x[0] == -24 and x[anchor] == 0 and x[25] == 1
        assert y[anchor] == 0 and baseline == float(example.data.loc[anchor, ADC_COLS[0]])
        assert y[0] == -24 and y[25] == 1  # semua nilai asli dipertahankan sebagai delta

        out = root / "out"
        result = generate(out, records, excluded, sensors=[ADC_COLS[0]])
        assert result["origin_groups"] == 2
        assert result["plots"] == 4
        assert len(list(out.rglob("*.png"))) == 4
        diagnostics = pd.read_csv(out / "series_t0_diagnostics.csv")
        assert diagnostics.t0_delta_adc.eq(0).all()
        assert diagnostics.first_collect_x.eq(1).all()
        assert len(diagnostics) == 13  # 11 MING + 2 TEM metadata sesuai
        assert len(set(diagnostics.loc[diagnostics.origin_code == "MING", "color"])) == 11
        assert diagnostics.loc[diagnostics.origin_code == "MING", "first_purge_samples"].eq(25).all()
        series = pd.read_csv(out / "missing_series.csv")
        assert len(series.loc[(series.origin_code == "MING") & (series.batch == "B36") &
                              (series.roast == "dark")]) == 1
        assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.rglob("*.csv")}
        try:
            generate(out, records, excluded, sensors=[ADC_COLS[0]])
        except FileExistsError:
            pass
        else:
            raise AssertionError("Hasil grafik lama tidak boleh ditimpa")

        # File arsip yang berubah setelah freeze harus ditolak.
        with (archive / "M-MING_B36.csv").open("a", encoding="utf-8") as f:
            f.write("\n")
        other, hold = scan(raw, archive, manifest)
        assert not any(r.source.name == "M-MING_B36.csv" for r in other)
        assert any("mismatched_archive_manifest" in row["reason"] for row in hold)
    print("PLOT_CROSS_ROAST_B33_B36_TEST_PASS")


if __name__ == "__main__":
    sys.exit(main())
