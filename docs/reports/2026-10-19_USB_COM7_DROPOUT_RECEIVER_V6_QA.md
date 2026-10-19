# Incident: Probook COM7 dropout, sequential dataset follow-up — 19 Oct 2026

## Observasi dari log pengguna (laptop Probook)

Tiga perangkat USB FTDI terdeteksi dan CONNECTED pada receiver v5:

| Physical label | USB port / serial | Run | Final status |
|---|---|---|---|
| ALAT_1 | COM5 / A10KMM3SA | M-GRB_B61 | ACQ COMPLETE, 900 rows, QA PASS |
| ALAT_2 | COM6 / A10KN6X9A | L-MING_B51 | ACQ COMPLETE, 900 rows, QA PASS |
| ALAT_3 | COM7 / A10KMZQJA | L-MING_B52 | disconnected, 597 rows quarantined |
| ALAT_1 | COM5 / A10KMM3SA | M-GRB_B62 | ACQ START only in provided excerpt |

COM7 error: `serial.serialutil.SerialException: ClearCommError failed
(PermissionError(13, 'Access is denied.', None, 5))`, later `USB waiting:
usb_not_found`. The `L-MING_B52` file is kept as incomplete under
`data/raw/devices/ALAT_3/incomplete` rather than promoted to final.
The subsequent `M-GRB_B62` was NOT shown to fail or succeed in the supplied
excerpt; need newer timestamped ALAT_1 log.

## Code review

`AcquisitionService.handle_event` accepts repeated `ACQ_START` after a
completed session (session is set to `None` after `complete()`). Each run
gets a fresh temporary file, validates 30 cycles, and reserves a unique
CSV destination. Multi-device isolation happens before the worker starts.
Disconnected serial streams preserve incomplete CSV and return to USB
auto-discovery; missing samples are never fabricated/reconstructed.

v6 diagnostic improvements:

- `scripts/diagnose_three_receivers.py` reads statuses, USB enumeration,
  completed CSV names, incomplete and `.incoming` files, and per-device log
  highlights. No COM opens or writes by default. Optional explicit JSON
  report output via `--output`.
- `scripts/lcd_acquisition_service.py` annotates console logs with ALAT ID,
  records ignored `ACQ_COMPLETE` with no active labeled session, and logs
  firmware/receiver sample-count mismatch explicitly. Default single-device
  receiver remains backward-compatible.
- Simulator verifies 2 sequential complete sessions (B99, B100) on each of
  3 concurrent isolated workers, total **6 valid files** at 900 rows each.
- Portable ZIP v6 is build-only; source raw CSV and legacy packages retained.

## Offline QA results

- `test_diagnose_three_receivers.py`: PASS (complete, missing, disconnected).
- `test_multi_device_receiver.py`: PASS (three workers × two sessions,
  900 rows per session, distinct files).
- `test_acquisition_integrity.py`: PASS.
- `test_usb_autodetect.py`: PASS.
- `test_receiver_host_instance_lock.py`: PASS.
- `test_take30_contract.py`: PASS.
- `test_recover_receiver_completed_csv.py`: PASS.
- `test_receiver_bundle.py`: PASS (28 bundle files, extraction/import/preflight).

**Limits:** no access to laptop Probook filesystem or physical COM5/6/7 from
the DevSpace host; physical USB disconnection root cause and success of
M-GRB_B62 remain unverified. Hardware remediation requires operator during
IDLE. Avoid opening Serial Monitor, uploading firmware, or changing USB
power/driver settings while acquiring.
