# Nextion ↔ ATmega2560 ↔ Raspberry Pi 5 E2E contract (proposed)

**Design document only. No live Pi/USB protocol modifications have been made.**

## Current vs target

Current: ten analog gas channels → four ADS1115 → ATmega2560; SHT30 is
**direct I2C** on the shared bus (it does not pass through an ADS1115).
ATmega directly drives pump/valve and Nextion (Serial2 at 9600 baud); USB
Serial at 115200 baud streams JSON events/readings to a host. The local
TinyML option is disabled by default; origin/confidence are N/A.

Target (preferred hybrid):

`Nextion START TEST → ATmega control/acquisition → USB JSON → Raspberry Pi 5
→ stream validator → feature contract → AI pipeline → result+abstention
→ USB result/ACK → ATmega → Nextion pResult`

No inference should block pump/valve safety state transitions. Host is an
optional intelligence layer: USB disconnection, missing model, timeout or
unrecognized sample must yield a truthful N/A/error rather than guess.

## Responsibility map

| Component | Owns | Explicitly does not own |
|---|---|---|
| ATmega2560 | ADC/SHT30, actuators, state-machine time, MCU safety, event tags, Nextion serial | Model training, dataset fitting, large file/history storage |
| Nextion | UI interactions, settings, progress, N/A/error screen | Ground truth for AI_TEST, raw acquisition metadata reconciliation |
| Raspberry Pi 5 | Reception, loss detection, valid run assembly, 5-cycle feature extraction, validated model/pipeline, result/unknown, persistent audit logs | Direct safety-critical valve/pump commands |
| Offline training PC | Provenance, group CV, model selection, model-card/versioned deployment export | On-line hyperparameter fitting from test data |

## Proposed USB protocol v1 — NOT YET IMPLEMENTED

Represent each message as newline-delimited UTF-8 JSON with `version=1`,
`type`, `session_id` (UUID), `message_seq` (monotonic within session),
`device_id`, `emitted_uptime_ms`, and `mode`. Types:

- `ACQ_START`: mode `labeled_data` or `ai_test`; config cycles/purge/collect,
  firmware schema; labels only for `labeled_data`.
- `SENSOR_SAMPLE`: cycle, phase, sample_idx, ordered ADC data (all ten),
  temperature/humidity nullable with a quality code.
- `PHASE_CHANGE`, `ACQ_PAUSE`, `ACQ_RESUME`, `ACQ_STOP`, `ACQ_COMPLETE`: status
  with counts; control events must **never** become sample records.
- `INFERENCE_REQUEST`: emitted only after valid 5-cycle AI_TEST acquisition.
- `INFERENCE_RESULT`: echoes session_id, model_version, prediction or unknown,
  calibrated probabilities only if available and validated, quality flags,
  artifact hash; origin may be unknown independently of roast.
- `INFERENCE_ERROR`: no device, invalid acquisition, incomplete session,
  unsupported model/schema or timeout. MCU displays N/A with a reason.
- `ACK` / `NACK`: sequence/session correlation; retransmission only for
  idempotent commands/results (never implicitly repeat physical START).

Payload examples above are proposed semantic fields, **not evidence of
currently emitted firmware messages**. Distinguish `run_id` (cycle 1..5) from
`session_id` (unique acquisition), `sample_id` (label) and physical specimen
UID (multiple acquisitions may use the same coffee specimen).

## Reliability and UX acceptance tests

1. Offline replay valid 5-cycle AI_TEST → exactly one inference result; no
   roast/origin training labels are fed to the model.
2. Missing ADC, wrong order/shape, duplicate seq, corrupt JSON, out-of-order
   cycle, impossible environmental values → reject or quality-flag as designed.
3. MCU reboot or Nextion reboot mid-run → never claim completed capture;
   display correct recovery/unknown state.
4. Pi offline or model missing → bounded inference timeout and N/A, while
   ATmega actuators remain in defined safe state.
5. Complete labeled capture → atomic CSV, host provenance, no class inference;
   partial file remains quarantined with reason, not silently deleted.
6. Verify latency and serial throughput on actual Raspberry Pi 5. Record
   percentile latency, resource usage, model footprint and error recovery.
7. Only after consent/maintenance window: live test of each UI button,
   pumping/valve timing, SHT30 failure, serial reconnect and power failure.

## Platform selection

- **Hybrid Pi5+ATmega — recommended** because four ADS1115/actuation already
  belong to MCU, while Pi5 can run ordinary sklearn models, store provenance
  and support replaceable model artifacts. Still pending device benchmark.
- ATmega-only inference — preserve as historical fallback experiment, not
  default. SRAM 8 KB, current feature parity and class mapping must be proven;
  existing model header cannot be assumed compatible with MQ3/62 features.
- Pi-only hardware control — not recommended; introduces unnecessary safety
  coupling and bypasses established MCU timing.

Hardware evidence and physical approval remain separate from offline builds.
Do not touch COM5 while the listener owns it, upload TFT, flash MCU or restart
live services during offline QA.
