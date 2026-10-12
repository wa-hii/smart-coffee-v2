# Bukti E2E software Tahap 8 — CSV ATmega asli

Skrip: `scripts/stage8_offline_e2e.py`
dan uji `scripts/test_stage8_offline_e2e.py`.

CSV asli `D-GAW_B33.csv` 151 sensor samples,
SHA256 `d5e690f538a3967e2d07ded64903d284a348c1988bcc331a380dd50b0a8be819`.

**11 scenario kontrak**: dua jalur positif
(AI_TEST dengan pResult mock N/A, serta
AMBIL DATA labeled autosave mock in-memory
151/151 baris sama dengan sumber),
dan sembilan negatif fail-closed.

`pi_remote_evidence.json` adalah hasil
program yang **dijalankan langsung pada
Raspberry Pi** dalam isolated venv Python.
Hasil `evidence_v3.json` adalah keluaran Windows.
Keduanya identik, termasuk hash input dan hasil QA.

**Tegas: bukan hardware E2E.** Semua event Nextion,
transport serial, dan pResult masih mock;
tidak ada data dikirim ke MCU, tidak ada
model dipanggil, tidak ada aksi aktuator.
Status rilis model tetap NO-GO.

Laporan sumber, metodologi dan matriks risiko:
`docs/reports/2026-10-12_RISET_USB_PI5_DAN_E2E_TAHAP8.md`.
