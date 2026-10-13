# Hasil G3 Run02 — USB listener langsung di Raspberry Pi 5

**Tanggal:** 13 Oktober 2026, sekitar 17.40–17.43 WIB
**Status:** **INCONCLUSIVE / NOT_STARTED menurut validator Pi**,
bukan keberhasilan lima siklus E2E.

## Prosedur yang benar-benar dilaksanakan

Operator meminta ulang satu kali G3 setelah patch framing.
Sebelum pengujian, source listener Pi dibandingkan dengan
Windows dan ditemukan **SHA256 identik**:

`878fa1bf50b131aeae8fcf4d6ab7a3de6451f154703b59e767037f7427fd861b`

Semua tes offline yang dijalankan pada Windows dan Pi
**PASS**: `test_stage7_pi_adapter.py`,
`test_stage7_bridge.py`,
`test_stage7_usb_readonly_probe.py`,
serta `test_stage8_offline_e2e.py`.
Port FT232R VID:PID `0403:6001`
serial `A10KMM3S` hadir sebagai
`/dev/ttyUSB0`; pemilik port sebelumnya
tidak terdeteksi dan `get_throttled=0x0`.

Proses berikut **benar-benar dijalankan** di Pi melalui
terminal SSH dengan host key terverifikasi dan
`HostKeyAlias=enose-pi5`:

```text
.venv/bin/python -u scripts/stage7_pi_adapter.py serial-readonly
--port /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0
--baud 115200 --duration 180
--acknowledgment I_APPROVE_USB_SERIAL_READONLY
--output results/pi_stage7/custom_pcb_usb_g3_nextion_run02.json
```

Port owner selama listener aktif adalah PID `2236`
proses `stage7_pi_adapter.py`, diverifikasi dengan
`fuser /dev/ttyUSB0`. Operator diminta **START AI TEST
satu kali melalui Nextion** saat proses berjalan.
Belum ada konfirmasi pasca-percobaan ini tentang
apakah tombol benar-benar ditekan dan bagaimana
perilaku lima siklus pada **run kedua**.

## Bukti asli Raspberry Pi

`/home/enose-v3/smart-coffee-stage7/results/pi_stage7/custom_pcb_usb_g3_nextion_run02.json`

SHA256:
`9a6733326df5f941110433dc888bb25dede37a10ec8df7db6070ea461a6dec20`

| Metrik | Nilai |
|---|---|
| `hardware_serial_opened` | `true` |
| `input_frames_read` | **203** baris lengkap |
| `serial_nonempty_chunks` | **303** |
| `serial_bytes_received` | **52.224 byte** |
| `complete_newline_frames` | **203** |
| `malformed_json_lines` | **14** |
| `other_json_lines` | **189** |
| `valid_sensor_frames_seen` | **0** |
| `wire_events_seen` | **{}** |
| `oversized_lines_discarded` | **0** |
| `partial_tail_bytes_discarded` | **0** |
| `terminal_event_count` | **0** |
| `final.quality` | **NOT_STARTED** |
| `final.reason` | **no_completed_session** |
| `final.status` | **N/A** |
| `model_promotion_allowed` | **false** |
| TX byte dari listener | **0** |

Proses selesai otomatis sesudah batas
180 detik (exit code `2` karena tidak
mencapai `COMPLETE_QA`). Setelah pengujian,
port telah ditutup, `fuser` kosong, dan
Pi masih melaporkan `throttled=0x0`.
Tidak ada upload firmware, perintah serial
dari Pi, atau aktuasi yang dipicu Pi.

## Interpretasi dan batas bukti

Perbaikan framing sebelumnya telah terpasang
di Pi dan menerima **203 baris newline lengkap**,
termasuk **189 JSON valid**. Tidak ada
`ACQ_START`, `ACQ_COMPLETE` atau sensor
yang cocok dengan `acquisition_schema.py`.
Oleh karena itu **fragmentasi read timeout
tidak lagi cukup menjelaskan hasil G3 kedua**.

Kemungkinan yang masih perlu dibedakan:
**(a)** mode AI TEST tidak dimulai pada jendela
listener yang kedua; **(b)** firmware aktual
menghasilkan skema field dan event berbeda dari
source `src/main.cpp`; atau **(c)** jenis pesan
yang diterima adalah diagnostik/telemetri lain.
Evidence berbentuk agregat **tidak menyimpan isi
189 JSON**, jadi key schema sebenarnya
belum diketahui. Jangan menyimpulkan bahwa
189 JSON adalah sampel akuisisi sah.

Langkah berikutnya: tanyakan apakah START AI TEST
benar-benar ditekan selama Run02 dan apakah
lima siklus terlihat selesai. Bila ya,
siapkan **diagnostik nama field JSON-only**
untuk membandingkan firmware aktual dengan
kontrak host, dengan izin baru sebelum
membuka USB atau mengulang sesi fisik.
**Tidak melakukan uji G3 ketiga otomatis.**
