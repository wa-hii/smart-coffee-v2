# Independent audit & QA/QC — Smart Coffee E-Nose v2

Date: 2026-10-08. Branch: `wahyu`; starting HEAD: `54d3321`.
Review scope: firmware/static design, Nextion HMI contract, CSV listener,
raw B32–B35 quality, prior ML artifacts and Raspberry Pi 5 design. No COM5,
EEPROM, physical acquisition, flashing, or model training was performed.

## Executive finding

The active sensor acquisition data are **structurally usable for research**
but no batch-independent AI model is yet validated. The former MQ9/long-run
feature pipeline is incompatible with the active MQ3/5-second contract. Device
integration is neither completed nor demonstrated by firmware builds.

## Evidence-based findings

| Severity | Finding | Evidence | Action/status |
|---|---|---|---|
| P0 | PHASE_CHANGE metadata row previously written into CSV | historical B33–B35 contain 612 such records; prior fix `54d3321` | Current schema regression rechecked; read-time metadata excluded |
| P0 | JSON non-null ADC check accepted strings/out-of-range | previous `acquisition_schema.py` used `is not None` | Integer/range checks and negative tests added |
| P0 | Duplicate `run_id/phase/sample_idx` previously undetected | validator lacked duplicate-key check | Validator + synthetic regression |
| P0 | Autosave output could collide within a second/overwrite | unique timestamp suffix + `os.replace` | unique numbered suffix, UUID staging and no-clobber atomic publication |
| P0 | Old extractor uses MQ9 and at least 10 collecting rows | `scripts/8_extract_features.py` | Explicit fail-closed guard; separate MQ3 feature candidate |
| P0 | Historical ML validation not comparable with B32+ | B01–B05 results, RF 57.5% and 55%; intra-train StratifiedKFold over correlated runs | Promotion blocked; group-aware evaluation specified |
| P1 | Phase boundary sample attribution risk | `adsCallback` reads sensor before state transition but prints post-transition phase | Documented, **not changed** pending controlled timing test |
| P1 | Origin and confidence currently unavailable | `USE_ON_DEVICE_INFERENCE=0` by default; `pResult` N/A fields | Hybrid host inference proposed, not implemented |
| P1 | Session identity and physical specimen metadata absent | `sample_id` and `batch_id` identify label/repeated batch, `millis()` is uptime | UID + host timestamp + specimen provenance contract planned |
| P2 | Nextion offline contract checker uses deprecated Pillow `.getdata()` | offline verifier warning | Non-blocking tool maintenance candidate |

## Initial dataset QA (real local files, no modifications)

| Metric | Value |
|---|---:|
| B32 / B33 / B34 / B35 files | 18 / 20 / 22 / 26 |
| Total files | 86 |
| Complete sensor rows | 13,003 |
| Metadata-only rows | 612 |
| Partial sensor rows | 0 |
| Sensor rows purging / collecting | 10,756 / 2,247 |
| Missing SHT30 temperature/humidity rows | 0 / 0 |
| Observed raw ADC zeros / 32767 saturation values | 0 / 0 |
| Roasting labels light/medium/dark (file counts) | 30 / 28 / 28 |
| Unique sample code (roast × origin) | 23 |
| Validator PASS | 86/86 |
| Candidate features per acquisition | 62 |

These counts do not certify the validity of roast ground truth, calibration,
sensor drift resilience, nor 86 **independent physical specimens**.

## Reproducible offline tests

```powershell
pio run -e mega2560 -e nextion_test
python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py
python scripts/test_acquisition_suite.py
python scripts/test_feature_pipeline.py
python scripts/audit_b32_dataset.py
python scripts/validate_b32_acquisition.py
# Explicit and separately versioned candidate output; does NOT train AI:
python scripts/extract_b32_features.py --output data/processed/b32_b35_features_candidate.csv
```

Evidence established during this audit:

- PlatformIO release builds PASS on `mega2560` and `nextion_test`.
  Main firmware: static RAM 3,720/8,192 bytes, flash 35,854/253,952 bytes;
  test firmware RAM 541/8,192, flash 5,062/253,952 bytes.
- HMI verifier PASS for 12 locked Figma assets, 12 HMI pages, 23 mapped
  events, `Serial2` 9600, pDataRun controls. No Nextion Editor/live results.
- Acquisition payload, synthetic CSV integrity, 86-file validator, and
  62-feature candidate regressions all PASS in this environment.
- Full B32–B35 inventory command reports 13,615 total CSV rows and validates
  file-level observations. Re-running extractor requires a fresh output path,
  intentionally refusing to overwrite earlier candidate artifacts.

## Residual risks and independent gates

1. **No hardware evidence:** verify phase attribution, SHT30 & ADS mapping,
   pump/valve timing, warm-up/clean-air calibration, COM5/LCD and real TFT.
2. **No model benchmark on current data:** no valid B32–B35 accuracy, origin
   classifier, calibration, unknown detection or Pi inference result yet.
3. **No prospective proof:** new blind session/specimen test and independent
   holdout must follow a frozen protocol. 4 batches are exploratory only.
4. **Dataset taxonomy:** resolve different labels for code TEM/MUK and record
   whether each code is an origin, cultivar, processing method or vendor.
5. **Approval required:** firmware flash, TFT upload, calibration/EEPROM,
   actual COM5 access, Raspberry Pi live deployment, motor/pump actuation.

## QA disposition

Offline build/HMI acquisition-CSV gate: **PASS** within documented limits.
Scientific AI generalization gate: **NOT ASSESSED / BLOCKED**.
Pi/device physical E2E gate: **NOT TESTED / BLOCKED**.

Authority for next steps: `01_MASTER_E2E_ROADMAP.md`. Do not claim full
device readiness until both remaining gates are independently closed.
