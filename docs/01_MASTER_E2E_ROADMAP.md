# MASTER SMART COFFEE E-NOSE AI RESEARCH AND IMPLEMENTATION ROADMAP

**Authority v1 / 2026-10-08.** Scope: Smart Coffee E-Nose v2 / RoastSense,
ATmega2560 + Nextion + host/Raspberry Pi 5. Existing hardware acquisition
must remain stable; **do not auto-implement future phases**. Current evidence:
`00_CURRENT_STATE.md`, `06_INDEPENDENT_AUDIT_QA_QC.md`.

## Non-negotiable engineering rules

- Source code, Git status, real raw files and reproducible tests outrank old
  documentation. Label proposed interfaces distinctly from current firmware.
- Preserve raw MQ9 legacy, raw MQ3 B32+, HMI and final Figma assets. No
  irreversible rewrite, COM5 contention, EEPROM calibration, live upload or
  physical acquisition without separate approval.
- Distinguish a CSV file/acquisition, five cycles, batch/day/session, physical
  coffee specimen, and origin/roast labels. **Avoid training/test leakage**.
- Track three gates separately: **software offline**, **hardware bench**, and
  **prospective inference**. No automatic DONE across gates.
- Every phase uses the loop: inspect → reproduce → fix → targeted test →
  independent QA → documented evidence → go/no-go. Include failure fixtures.
- Priority: P0 correctness and valid data; P1 model evaluation/architecture;
  P2 enhancements. Evidence artifacts must be reproducible by CLI/Git hash.

## Snapshot and dependency graph

| Phase | Status | Priority | Main predecessor | Hardware needed? |
|---|---|---|---|---|
| 0 Current state and methodology | PARTIAL | P0 | None | No |
| 1 Firmware/Nextion/acquisition quality | PARTIAL | P0 | 0 | For final physical sign-off |
| 2 Dataset catalog/quality | PARTIAL | P0 | 0–1 | Not for existing files; yes for new specimens |
| 3 Reproducible preprocessing/features | PARTIAL candidate | P0 | 2 | No |
| 4 Baselines/challengers | PLANNED | P1 | 3 | No |
| 5 Cross-batch evaluation/unknown | PLANNED | P0 | 3–4 | New specimens for final sign-off |
| 6 Model selection/runtime artifact | BLOCKED by 5 | P1 | 5 | Device for latency |
| 7 Pi/ATmega integration design | PARTIAL design | P1 | 1, 6 | Required for integration |
| 8 Full offline E2E mock replay | PLANNED | P1 | 6–7 | No |
| 9 Hardware integration | BLOCKED approval | P1 | 8 | Yes |
| 10 Prospective validation/promotion | BLOCKED | P0 release gate | 5, 9 | Yes |

Dependencies follow quality gates, not a commitment to execute work in one
session. 0–3 can substantially advance offline. 4–6 depend on scientific
validity; 9–10 cannot be simulated as completed physical evidence.

## Phase 0 — Current-state and methodology closure

- **Objective / status / priority:** freeze actual architecture, scope,
  repository authority; PARTIAL, P0; independent audit baseline established.
- **Dependencies / design:** branch inventory, active hardware ownership,
  labeled vs AI_TEST semantics, schema versions; no hardware required.
- **Tasks:** reconcile Git history/docs/source; map ADC order, phase machine,
  12 Nextion pages, uploader, active HMI; resolve source-of-truth conflicts,
  outdated comments and origin taxonomy; define unique sample/session UID.
- **Files:** README, platformio.ini, src/, nextion/, scripts/, docs/00.
- **Tests / negative:** `git status --short --branch`, offline PlatformIO
  builds, Nextion verifier; detect mismatched labels, stale TFT, differing
  USART/baud and unwanted local change overwrites.
- **Outputs / evidence:** current-state document, architecture map, source
  schema, Git/diff/test logs; B32+ 86-file inventory as reference.
- **Acceptance / go-no-go:** every subsystem has named current authority,
  provenance and evidence status; unresolved conflicts explicitly BLOCKED.
- **Risks / mitigation / done:** old documentation drift; source/tests outrank
  prose. DONE after full inventory reconciliation and reviewed sign-off.

## Phase 1 — Hardware/firmware/data-acquisition quality closure

- **Objective / status / priority:** no mislabeled phase or lost/corrupt data;
  PARTIAL P0; listener/schema/validator fixes tested offline.
- **Dependencies / design:** phase timing, 10 ADC channels + shared SHT30 I2C,
  actuator failsafe, Nextion 9600, USB 115200; MCU owns physical state.
- **Tasks:** inspect ADC gain/saturation, warm-up/R0/RL/EEPROM, retry/failure
  handling, sample_idx and millis rollover, phase-boundary attribution,
  pump/valve timing, pause/resume, user commands and missing sensor path.
- **Files:** src/main.cpp, sensor.*, actuator.*, sht30.*, nextion_transport.*,
  acquisition_schema.py, collectors, LCD autosave and validators.
- **Tests / negative:** `pio run -e mega2560 -e nextion_test`,
  `python scripts/test_acquisition_suite.py`, offline HMI verifier; malformed
  ADC, duplicate idx, metadata-only event, disconnected serial, same-second
  filename collision, Nextion reboot, cancellation and idle/safe actuator.
- **Outputs / evidence:** annotated transition trace/oscilloscope or logged
  boundary run, stable raw CSV and regression suite; no raw rewrite.
- **Acceptance / go-no-go:** all required sensor frames typed/ranged; zero
  silent sensor/event confusion, duplicate output overwrite or unsafe actuator
  recovery; 25+5 s timing objectively bench measured before firmware change.
- **Risks / mitigation / done:** timing refactor could change dataset
  semantics; use offline simulation then approved physical regression. Final
  DONE requires bench tests, so currently NO-GO for hardware claims.

## Phase 2 — Dataset catalog and quality assessment

- **Objective / status / priority:** auditable independent measurement units;
  PARTIAL P0. Current 86-file inventory/validator DONE; scientific audit pending.
- **Dependencies / design:** Phase 1 stable schema and provenance fields,
  historical MQ9 isolated from current MQ3; existing files offline only.
- **Tasks:** immutable hashes, file/batch/roast/origin/cycle distributions,
  repeat specimens, unknown metadata, missing env, drift, baseline return,
  carryover, confounds from order/day/coffee mass; check B32–B35 plots.
- **Files:** data/raw/, `scripts/audit_b32_dataset.py`,
  `validate_acquisition.py`, plot_sensor_pattern.py, data/analysis/.
- **Tests / negative:** `python scripts/audit_b32_dataset.py`; swapped MQ9,
  phase-only rows, invalid timestamp, duplicate samples and inconsistent
  origin codes; compare plots with raw and per-run phase boundaries.
- **Outputs / evidence:** dataset manifest and missing-provenance report,
  class coverage map, invalid vs usable cohorts, signal/temperature drift.
- **Acceptance / go-no-go:** every training file tied to raw hash, batch,
  source schema and an explicit independence assumption; reject incomplete
  input from ML. Dataset validity != physical generalization readiness.
- **Risks / mitigation / done:** four batches can hide session correlation;
  collect independent days/specimens. DONE after provenance is complete.

## Phase 3 — Reproducible preprocessing/feature pipeline

- **Objective / status / priority:** identical feature vector for fit and Pi
  inference; PARTIAL candidate P0; 62 numeric features/86 rows exported.
- **Dependencies / design:** Phase 2 valid MQ3 measurements; one file = one
  observation, five internal cycles aggregated, no fitted transform globally.
- **Tasks:** baseline-relative response, slope, SD, sensors/temperature
  handling; stable ordered schema; dimensionality/stability ablation; decide
  if using purge trailing points is physically reliable.
- **Files:** `scripts/extract_b32_features.py`,
  `data/processed/b32_b35_features_candidate.csv` and `.schema.json`.
- **Tests / negative:** run explicit `--output` in new location; replay same
  file twice identical, invert phase/missing ADC/non-monotonic timestamp fail,
  collision/legacy inputs denied; no train data fit before splitting.
- **Outputs / evidence:** hash-addressed schema, deterministic sample-level
  features and independent Python test; model input whitelist `f_*`.
- **Acceptance / go-no-go:** no data loss or NaN/inf, exact order, one row/file,
  strict invalid-file rejection, cross-machine parity verified; CANDIDATE
  remains NO-GO for deployment until ablation and training-serving parity.
- **Risks / mitigation / done:** 62 features for 86 observations invites
  overfit; use compact subsets, regularization and fold-contained selection.

## Phase 4 — Baseline and challenger model research

- **Objective / status / priority:** compare classical models fairly;
  PLANNED P1. Historical MQ9 RF not an active baseline.
- **Dependencies / design:** 3, evaluation folds frozen before tuning;
  labels for roast-only, known-origin, joint only if supported.
- **Tasks:** dummy/majority, LogisticRegression, shrinkage LDA, linear/RBF
  SVM, RF/ExtraTrees, PLS-DA, kNN; optional boosting; defer temporal CNN/
  ROCKET unless new sequences/data justify them.
- **Files:** new versioned experiments under scripts/ or research/, model
  registry outside legacy `models/random_forest_final.joblib`.
- **Tests / negative:** grouped CV, training-fold-only scaler/selector, seeded
  reproducible runs, shuffled-label sanity check; reject folds lacking a class
  for claims about that class.
- **Outputs / evidence:** per-fold macro F1/balanced accuracy, latency, byte
  size, confusion matrices, manifest, exact config and reproducibility logs.
- **Acceptance / go-no-go:** baseline with all relevant folds and no leakage;
  no test-set tuning. No model promotion based on 86 correlated files alone.
- **Risks / mitigation / done:** tiny class/sample sizes; regularize, limit
  hyperparameters, report uncertainty, acquire new independent samples.

## Phase 5 — Cross-batch generalization, drift and unknown rejection

- **Objective / status / priority:** prove robust unseen acquisition accuracy;
  PLANNED P0 release prerequisite.
- **Dependencies / design:** 2–4 and frozen thresholds; batch-group LOBO as
  stress test, then prospective new specimen/day/instrument holdout.
- **Tasks:** 4 batch-held-out folds, class-coverage diagnostics, group-aware
  nested tune only when defensible, per-origin/roast results, prediction
  calibration, unknown/unseen origin policy, drift/humidity sensitivity,
  false-confident errors and early-cycle ablation.
- **Files:** immutable evaluation manifest, results/ grouped reports,
  sklearn Pipeline artifact for each training split.
- **Tests / negative:** inspect group overlap (must be zero); unseen
  roast-origin combination, unknown origin, intentionally corrupted sensor,
  drift/temperature perturbations, ill-defined labels and repeated tests.
- **Outputs / evidence:** held-out fold reports plus prospective signed-off
  dataset independent of development data; risk/coverage curve.
- **Acceptance / go-no-go:** no fold leakage, bounded false-confident outputs,
  score intervals and per-class coverage documented; minimum score/abstain
  thresholds **pre-agreed before seeing prospective set**.
- **Risks / mitigation / done:** missing classes in small folds make multiclass
  metrics unstable. Report N/A rather than average-away failures; final DONE
  requires new specimen validation.

## Phase 6 — Model selection and inference artifact contract

- **Objective / status / priority:** choose a deployable frozen pipeline;
  BLOCKED by 5, P1.
- **Dependencies / design:** promotion after performance, calibration and
  prospective validation; single model registry and immutable model card.
- **Tasks:** select roast model, origin policy, unknown/abstain calibration,
  stable class ordering, `f_*` feature checksum/order, sensor version mapping,
  model size and speed/DRAM limit, latency-budget agreement.
- **Files:** models/ registry proposal, frozen sklearn Pipeline, feature
  schema JSON, docs/03, replay/inference tests.
- **Tests / negative:** mismatch schema/feature dimension or order, unknown
  origin, absent model, corrupt artifact, library incompatibility, serial
  timeout; must return explicit error/N/A, never a guessed class.
- **Outputs / evidence:** model card with training/validation provenance,
  artifact SHA, exact environment and CPU benchmark.
- **Acceptance / go-no-go:** model scores meet pre-registered quality gates
  on held-out data; fit/serve parity; no confidence without calibration;
  otherwise NO-GO and continue collecting data.
- **Risks / mitigation / done:** accidental leakage from old RF model headers;
  do not reuse legacy model_rf.h or auto-activate AVR TinyML.

## Phase 7 — Raspberry Pi 5 / ATmega integration preparation

- **Objective / status / priority:** explicit interoperable protocol; PARTIAL
  design only P1; proposal in `04_NEXTION_ATMEGA_RASPI_ARCHITECTURE.md`.
- **Dependencies / design:** phases 1 and 6; ATmega remains sole owner of
  valve, pump, timing and safety; Pi model host is optional.
- **Tasks:** versioned NDJSON `session_id`/`message_seq`/ACK/error, host process
  isolation, USB reconnect/deduplication, label-free AI_TEST, result to ATmega
  then Nextion; session and error log; prohibit two COM owners.
- **Files:** new host adapter (future), src/main.cpp (only approved change),
  src/nextion_* and docs/04.
- **Tests / negative:** packet loss/dup/out-of-order, Pi unresponsive, MCU or
  display reboot, timeout, malformed sample, hostile filename; no actuator
  change from host, no fabricated origin/confidence.
- **Outputs / evidence:** protocol fixture suite, interface diagram, Pi
  deployment instructions, test matrix and rollback recipe.
- **Acceptance / go-no-go:** deterministic recovery, one result per session,
  clear N/A mode, no COM conflict, measured resource/timeout limits.
- **Risks / mitigation / done:** live protocol upgrades require dual-version
  compatibility; mock first, bench only with authorization.

## Phase 8 — Full E2E offline integration/replay

- **Objective / status / priority:** simulate button-to-prediction path
  without touching hardware; PLANNED P1.
- **Dependencies / design:** phases 6–7; mock Nextion events, MCU trace,
  validator, feature generator, runtime, message ACK/error.
- **Tasks:** replay B32+ labeled mode to autosave mock, AI_TEST mode to
  model+decision mock, N/A and unknown screens; reject label leakage.
- **Files:** simulation fixtures and CLI tests (new), schema/model cards,
  docs/07 when implemented; keep production `Serial2` protocol unchanged.
- **Tests / negative:** corrupt/duplicate event, stop/pause, incomplete run,
  missing model, low-confidence class, stale session and simulated disconnect.
- **Outputs / evidence:** deterministic replay outputs, JSON trace, pass/fail
  E2E report, no input/raw mutation.
- **Acceptance / go-no-go:** all positive/negative fixtures pass on a clean
  environment with reproducible hashes; final hardware test still pending.
- **Risks / mitigation / done:** mock cannot prove ADC/wiring/timing; only
  label software-level E2E as DONE.

## Phase 9 — Physical hardware integration and validation

- **Objective / status / priority:** prove real 3-device communication;
  BLOCKED approval P1.
- **Dependencies / design:** Phase 8 PASS; bench-safe maintenance window,
  exclusive COM owner, known firmware/HMI backup, observer and rollback.
- **Tasks:** verify actual ADS addresses/channel mapping, SHT30, power and
  gas warm-up, pump/valve trace, Serial2 pin 8/9 physical IC, compiled TFT,
  Nextion 12-page navigation, USB/Pi reconnect, end-to-end result latency.
- **Files:** deployment log, firmware build hashes, actual Nextion-compiled
  TFT, instrument logs and measured timings.
- **Tests / negative:** unplug I2C/USB, partial run, MCU/LCD/Pi reboot,
  pause/resume, valve fault, unknown coffee, aborted calibration.
- **Outputs / evidence:** measured sensor/actuator timing and recovery,
  release notes/photos/traces, comparison to recorded offline fixtures.
- **Acceptance / go-no-go:** bench acceptance sign-off, no unsafe actuator
  motion; failure causes accurate N/A and safe state; no unapproved flashes.
- **Risks / mitigation / done:** hardware operation may contaminate samples;
  follow SOP, segregate test data, restore last known-good revision.

## Phase 10 — Prospective validation and production promotion

- **Objective / status / priority:** validate unseen real coffee and promote
  model without misleading confidence; BLOCKED, P0 release gate.
- **Dependencies / design:** phases 5, 6, 9; frozen candidate with no leakage
  and preregistered metrics/acceptance thresholds.
- **Tasks:** acquire blinded independent specimens across roast/origin/day,
  fixed warm-up/purge/collect SOP, measure repeatability, sensor drift,
  nuisance factors, false unknown/false accept and operational latency;
  freeze model registry and documented rollback.
- **Files:** locked test manifest, evidence in results/, approved model card,
  tested host deployment and rollback instructions.
- **Tests / negative:** unseen origin/out-of-distribution coffee, missing
  channel, unusual humidity, changed sensor calibration, cycle count mismatch,
  corrupted model and loss of USB during inference.
- **Outputs / evidence:** prospective confusion matrix/per-class F1, error
  analysis, abstention coverage, uptime/failure counts, acceptance signatures.
- **Acceptance / go-no-go:** thresholds set *before* study are met; unknown
  class and error handling reliable; representative hardware trials completed.
  Otherwise NO-GO, keep legacy read-only and iterate data/model design.
- **Risks / mitigation / done:** four historical batches do not establish
  field validity; only real blinded, instrument-verified samples can close it.

## Immediate execution order and approval boundaries

1. **P0 offline now:** finish structural QA regression, document phase boundary
   issue, preserve original MQ9 processed artifacts, catalog B32–B35, validate
   one-row-per-acquisition feature candidate, record Git diff/test evidence.
2. **P0 next experiment:** add **physical specimen UID**, wall-clock/session
   identity, firmware/hardware versions, warm-up and coffee mass/preparation
   metadata on newly collected samples; decide origin taxonomy.
3. **P1 offline next:** train cheap, reproducible grouped baselines with
   correct feature contracts, report *per-batch* errors and unknown handling.
4. **P1 architecture:** complete host/Pi communication proposal, mock replay,
   loss/reconnect tests before bench.
5. **Hardware approval required:** live COM access, instrument measurements,
   firmware flashing, Nextion compilation/upload, valve/pump tests, calibration
   or EEPROM write, Raspberry Pi live deployment.

**Readiness now:** offline firmware + HMI contract + CSV structural QA are
supported; AI validation, Pi result loop and real device E2E remain NOT DONE.
Review roadmap after every new dataset batch, model promotion candidate or
physical bench evidence. Do not infer success from plots or training accuracy.
