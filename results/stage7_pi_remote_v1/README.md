# Hasil Tahap 7 yang dijalankan langsung di Raspberry Pi 5

Uji pada 11 Oktober 2026 melalui Tailscale SSH
`enose-v3@enose-pi5` (Raspberry Pi 5 Model B Rev 1.1,
Debian 13, Python 3.13.5). File JSON replay asli
disalin kembali dari Pi ke repo untuk audit.

- `replay_d_gaw_b33.json`: replay pada **Pi nyata**, input
  `D-GAW_B33.csv` dari rekaman ATmega sebelumnya.
  Sumber CSV SHA256
  `d5e690f538a3967e2d07ded64903d284a348c1988bcc331a380dd50b0a8be819`
  sama di host dan Pi.
- Keluaran replay yang terukur: **151** sampel,
  `COMPLETE_QA`, `AI_TEST=N/A`,
  `hardware_serial_opened=false`,
  `sent_to_atmega=false`,
  `actuator_commands_sent=0`. Nominal 150 frame
  **tidak dipenuhi**, tetapi diterima oleh toleransi
  QA fase saat ini. CSV mentah tidak diedit.
- Paket venv: `pyserial==3.5`; pengujian
  `test_stage7_bridge.py`,
  `test_stage7_pi_adapter.py`,
  `test_stage7_pi_preflight.py` PASS di Pi.
- **NOT TESTED:** serial device `/dev/ttyACM*` atau
  `/dev/ttyUSB*` (ATmega belum dipasang), komunikasi
  fisik dua arah, Nextion/UI, aktuator atau inferensi.

Laporan utama:
`docs/reports/2026-10-11_TAHAP7_PI_VENV_OFFLINE_REPLAY.md`.
