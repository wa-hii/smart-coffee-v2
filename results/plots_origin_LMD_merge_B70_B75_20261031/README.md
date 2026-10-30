# Overlay Light–Medium–Dark berdasarkan origin, seluruh batch valid

Sumber: `D:\ENOSE\smart-coffee-v2-hardware\smart-coffee-v2-hardware\results\combined_30cycle_B70_B75_20261031\01_VALID_GABUNGAN`.
CSV diperiksa: **233**; rekaman digunakan: **196**; origin eligible: **6**.
PNG: **120** (RAW 60, T0 normalized 60).

## Kelayakan per origin

| Origin | Light (batch unik) | Medium | Dark | Eligible |
|---|---:|---:|---:|---|
| CAT | 11 | 11 | 12 | Ya |
| GAW | 11 | 10 | 13 | Ya |
| GAY | 11 | 0 | 0 | Tidak: TIDAK_LENGKAP_Medium:0/5,Dark:0/5 |
| GRB | 11 | 11 | 11 | Ya |
| MING | 10 | 11 | 11 | Ya |
| MUK | 0 | 12 | 0 | Tidak: TIDAK_LENGKAP_Light:0/5,Dark:0/5 |
| RAT | 0 | 0 | 12 | Tidak: TIDAK_LENGKAP_Light:0/5,Medium:0/5 |
| TEM | 11 | 10 | 11 | Ya |
| TOR | 10 | 10 | 11 | Ya |

## Methodology

- Overlay **all selected genuine CSV curves** per sensor/roast on one axis (not averaged curves).
- Tidak ada filter nomor batch: batch hanya label identitas rekaman; semua CSV valid dinilai menggunakan aturan yang sama. Setiap CSV 900 sampel dan 30 × (25s purging + 5s collecting).
- Minimum five **unique batch IDs** each roast. Canonical sample code filename is preferred if repeated valid recordings share a batch; see `duplicate_same_batch_qa.csv`.
- RAW ADC unchanged. ΔADC(t) = ADC(t) − ADC(t0) where t0=last purging measurement in cycle1 (sample_idx=25, at nominal t=24s). t26 is first collecting measurement.
- All 900 samples plotted; t0-normalized negative time interval retains first 24 purge samples.
- Light hijau (`#168A43`), Medium kuning keemasan (`#D4A400`), Dark merah (`#C62828`). Different batch runs within a roast have different dash patterns.
- Shaded collecting phases show 5s *nominal* windows, not independently logged actual valve movement.
- No smoothing, interpolation, resampling, filling missing points, or synthetic readings.

## Files

- `01_RAW_LMD_MERGED/ORIGIN/*.png`: 10 sensors × origin, raw.
- `02_T0_NORMALIZED_LMD_MERGED/ORIGIN/*.png`: 10 sensors × origin, normalized.
- `GALERI_LMD_MERGE.html`: filter origin, sensor, raw/t0.
- `plot_index.csv`: one row per graph and source list.
- `input_provenance.csv`: SHA256 and selection reason for **all audited** source CSV.
- `eligible_origins.csv`: seluruh origin yang ditemukan pada dataset dan pemeriksaan kelayakannya.
- `baseline_t0_per_sensor.csv`: anchor ADC for every selected record and sensor.
- `sensor_separation_diagnostics.csv`: per-origin/sensor descriptive ratios, ranks, baseline spread, drift and collection contrast.
- `duplicate_same_batch_qa.csv`: records excluded from the graph for sharing same roast+origin+batch without independent provenance.

## Interpretation limitations

Metrics are descriptive (ratios of between-roast to within-roast variation in *recording-level* features). They are **not classification accuracy, p-values, or evidence of independence**. Baseline at t0 is a within-run purge reference, not an external clean-air calibration. Physical instrument, temperature/humidity, chamber memory, specimen identity and temporal drift remain potential confounders.
