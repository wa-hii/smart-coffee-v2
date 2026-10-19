# Probook tiga alat: frame serial invalid — 19 Oktober 2026

## Bukti pengguna

- ALAT_1 `L-TOR_B61`: 758 sensor rows kemudian `ACQ INCOMPLETE`
  dengan alasan `serial frame corrupt or oversized`.
- ALAT_3 `L-CAT_B63`: 487 sensor rows kemudian `ACQ INCOMPLETE`
  dengan alasan sama.
- `L-CAT_B63`, `L-TOR_B64`, dan `L-GAW_B64` juga mengeluarkan `ACQ START`
  pada log lintas-proses, tetapi informasi tersebut saja **bukan bukti**
  bahwa masing-masing sesi kedua selesai ataupun gagal.

## Penyebab yang didukung audit kode

`serial_wire.py` menerima chunk USB 256 byte dan menggabungkannya hingga
newline. Batas satu frame valid dari `stage7_bridge.py` adalah **4096
byte**. Jika decode strict JSON gagal (`invalid_json_or_encoding`, NUL,
duplicate key, nonfinite number, objek bukan dictionary), parser mengirim
`TRANSPORT_ERROR reason=malformed_json`. Jika frame melebihi batas atau
newline hilang hingga buffer membengkak, parser mengirim
`TRANSPORT_ERROR reason=oversized_line`.

`lcd_acquisition_service.py` memindahkan sesi aktif ke `incomplete` segera
setelah salah satu event tersebut. Ini **sengaja fail-closed** untuk menjaga
validitas dataset; satu pesan rusak tidak boleh ditulis sebagai sensor
seolah valid. Tidak ada bukti pada log v5 apakah error spesifik berasal
dari parsing JSON atau oversized line, dan tidak cukup data untuk
menyimpulkan komponen fisik yang menyebabkan. Gangguan USB/hub/driver,
MCU reset, newline hilang, ataupun output angka nonfinite semuanya adalah
hipotesis yang harus dibuktikan dengan observasi lanjut.

## Perubahan diagnostik v7

- `serial_wire.py`: menyertakan `detail` dari FrameError dan panjang bytes
  malformed JSON, atau `limit_bytes=4096` pada oversized line. **Tidak
  merekam raw frame atau konten sensitif lain**.
- `lcd_acquisition_service.py`: log `SERIAL FRAME REJECTED reason=...`
  berikut detail dan jumlah rows diterima sebelum fail-closed. Sesi tetap
  incomplete; perangkat, firmware dan protokol tidak diubah.
- `scripts/test_serial_frame_diagnostics.py`: simulasi malformed JSON,
  duplicate keys, nonfinite value, >4096 byte, quarantining partial,
  dan kesiapan membuat sesi baru tanpa perangkat serial nyata.

## QA dan batasan

- PASS `test_serial_frame_diagnostics.py`.
- PASS `test_multi_device_receiver.py` (3 receiver paralel x 2 sesi).
- PASS `test_usb_autodetect.py`, `test_acquisition_integrity.py` dan
  `test_take30_contract.py`.
- PASS `test_receiver_bundle.py` (ZIP portable v7).
- **Tidak dilakukan:** membuka COM5/COM6/COM7, flash MCU, reset, atau
  tindakan hardware. Validasi serial fisik Probook belum dilakukan.

Jika insiden berulang setelah instal v7 saat semua alat IDLE, kumpulkan
perangkat dan timestamp `SERIAL FRAME REJECTED` yang spesifik serta cek
USB/catu daya/kabel. Jangan menghapus CSV incompletes ataupun mengganti
menjadi CSV final tanpa validasi.
