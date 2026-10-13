# Hasil G3 Run02 — USB listener langsung di Raspberry Pi 5

**Tanggal:** 13 Oktober 2026, sekitar 17.40–17.43 WIB
**Status:** **INCONCLUSIVE / NOT_STARTED menurut validator Pi**,
bukan keberhasilan lima siklus E2E.

## Addendum konfirmasi operator dan audit kontrak (13 Oktober, malam)

Operator **mengonfirmasi secara eksplisit** bahwa pada
**Run02** beliau **menekan START AI TEST di LCD Nextion**
dan **melihat kelima siklus berjalan sampai selesai**.
Dengan demikian, hipotesis "START tidak ditekan"
**tidak sesuai dengan observasi operator**. Status
host tetap `NOT_STARTED` karena bukti elektronik
tidak mengenali event atau payload sensor.
Keberhasilan HMI **berdasarkan observasi operator**
tidak mengubah ketidaklulusan validasi E2E Pi.

Audit `src/main.cpp` dan `src/sensor.cpp`:
`startAcquisition()` pada **source repo**
menulis `ACQ_START`, `processAcquisitionState()`
menulis `PHASE_CHANGE` dan `ACQ_COMPLETE`,
sementara `printJsonData()` menulis
`phase`, `cycle`, `sample_idx`, `timestamp`,
10 key `adc_*`, `temperature_c`, dan
`humidity_rh`. Jika source ini identik dengan
firmware yang terpasang dan USB UART yang dipantau,
event dan frame sensor seharusnya dapat dikenali.
**Belum ada bukti bahwa firmware terpasang sama
dengan source checkout.**

File bukti `run02.json` **hanya berisi agregat**,
sehingga 189 JSON tersebut tidak bisa ditafsirkan
ulang menjadi event maupun sampel tanpa merekam
struktur aktual. Klaim bahwa firmware pasti berbeda
masih berupa **hipotesis**, bukan hasil verifikasi.

Untuk diagnosis berikutnya, `stage7_pi_adapter.py`
telah ditambah diagnostik **`other_json_key_signatures`**:
hanya **nama field tingkat atas dan satu tingkat nested**
serta jumlah kemunculannya, maksimal 8 pola dan 32
nama per pola. **Nilai ADC, identitas sampel, label
kopi, dan isi payload mentah tidak disimpan**.
Regresi privacy/no-values, batas ukuran, framing,
dan replay telah **PASS offline** di Windows,
kemudian source dan tesnya **disalin ke Pi
dan regresi Pi juga PASS**. SHA256 Pi:
`stage7_pi_adapter.py`:
`5628304575b3d28d2234106b5f198e8670614b82301174206429df2b`;
`test_stage7_pi_adapter.py`:
`a0694d84a30397e9b35ea9e87d480b79b99858619a5e5b6ae64222a04c946dec`.
Pengujian `test_stage7_bridge.py` di Pi juga PASS
dan tidak ada pemilik `ttyUSB0` yang terdeteksi
sesudah deployment. Penambahan ini
**tidak berlaku surut** ke file Run02 dan
tidak membuka serial otomatis. Pembacaan baru
tetap memerlukan izin pengguna.

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
Saat laporan pertama dibuat belum ada konfirmasi
pasca-percobaan; **lihat addendum di atas** untuk
konfirmasi Run02 yang diterima kemudian.

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

Langkah berikutnya: setelah konfirmasi START
dan lima siklus selesai dari operator,
gunakan **diagnostik nama field JSON-only**
untuk membandingkan firmware aktual dengan
kontrak host, dengan izin baru sebelum
membuka USB atau mengulang sesi fisik.
**Tidak melakukan uji G3 ketiga otomatis.**
