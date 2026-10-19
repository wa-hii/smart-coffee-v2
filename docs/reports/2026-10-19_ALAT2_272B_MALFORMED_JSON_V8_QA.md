# Insiden ALAT_2 (COM6) — malformed JSON 272 bytes, 19 Okt 2026

## Fakta dari operator laptop Probook

- ALAT_2/COM6, USB FTDI serial `A10KN6X9A` pada pemetaan sebelumnya.
- Pengambilan `L-MING_B60`, `accepted_rows=351`.
- `SERIAL FRAME REJECTED reason=malformed_json
  detail=invalid_json_or_encoding frame_bytes=272`.
- Hasil `L-MING_B60` dikarantina ke folder `incomplete`; bukan CSV 900 sampel.
- ALAT_1 `M-GRB_B62` dan ALAT_3 `L-CAT_B63` hanya memperlihatkan
  `ACQ START` pada potongan log terbaru, belum diketahui selesai atau tidak.

## Pemeriksaan kode dan batas bukti

`serial_wire.SerialLineFramer` menggabungkan chunk hingga newline. Batas
frame adalah 4096 byte; satu frame 272 byte bukan oversized. Parser
`stage7_bridge.decode_line` membungkus `json.JSONDecodeError` dan
`UnicodeDecodeError` sebagai `FrameError('invalid_json_or_encoding')`,
sehingga log v7 tidak membedakan keduanya. Kode firmware menggunakan
`Serial.print()` berurutan untuk 10 ADC, temperature/humidity, kemudian
`Serial.println()`; SHT30 memverifikasi checksum CRC. Hal itu tidak
menyingkirkan kemungkinan korupsi serial, restart, USB hub, atau
terpotongnya frame. Tidak ada byte asli yang gagal untuk dianalisis.

## Peningkatan diagnostik v8

- Saat FrameError memiliki `json.JSONDecodeError` sebagai cause, receiver
  melaporkan `fault_class=json_syntax`, `json_error_pos`,
  `json_error_message` dan `json_error_at_end`.
- Saat FrameError berasal dari `UnicodeDecodeError`, receiver mencatat
  `fault_class=invalid_utf8`, `invalid_byte_offset`.
- Pendeteksi `ends_with_brace` membantu membedakan frame terpotong,
  meskipun `True` saja tidak membuktikan pesan valid.
- Tidak ada data sensor mentah atau potongan frame di log; sesi rusak
  tetap ditolak, file partial disimpan, perhitungan 900 sampel tak diubah.
- Berkas ZIP v8 terpisah dari paket v7 agar pengambilan aktif tidak terganggu.

## QA offline

- `test_serial_frame_diagnostics.py`: PASS, termasuk frame malformed
  sepanjang tepat 272 bytes, error sintaks, UTF-8 tidak valid, duplicate
  key, `NaN`, dan oversized; sesi tetap incomplete.
- `test_multi_device_receiver.py`: PASS, 3 alat × 2 sesi berurutan.
- `test_usb_autodetect.py`, `test_take30_contract.py`,
  `test_acquisition_integrity.py`, `test_receiver_host_instance_lock.py`:
  PASS.
- Bundle ZIP v8 extraction/import/preflight: PASS.

**Belum terbukti:** penyebab fisik, kestabilan pasokan daya, kualitas USB
serial FTDI, atau jenis byte gagal dari ALAT_2 pada saat insiden.
Verifikasi langsung baru boleh dilakukan setelah sesi berjalan selesai.
