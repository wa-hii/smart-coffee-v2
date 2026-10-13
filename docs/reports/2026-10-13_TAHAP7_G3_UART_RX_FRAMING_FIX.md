# G3 Nextion PCB custom — rekonsiliasi operator dan perbaikan listener USB

**Tanggal:** 13 Oktober 2026
**Perangkat fisik:** PCB custom ATmega2560 Smart Coffee + Nextion
→ FT232R USB → Raspberry Pi 5.
**Status:** bug framing serial ditemukan dan diperbaiki pada source host;
regresi offline **PASS di Windows**; bukti Pi live G3 ulang **BELUM ADA**.

## A. Koreksi fakta percobaan G3 pertama

Setelah laporan percobaan G3 `NOT_STARTED`,
operator mengonfirmasi bahwa **tombol START AI TEST
benar-benar ditekan pada LCD Nextion selama listener
aktif**, dan **lima siklus tampak berjalan pada alat**.
Oleh karena itu hipotesis 'START belum ditekan'
tidak lagi sesuai dengan kesaksian operator.

Evidence asli Pi tidak dimodifikasi:
`results/pi_stage7/custom_pcb_usb_g3_nextion_run01.json`
berhash
`304234c8f950932bc5a907b0b1ff3c8411ace1c32c1f79ecae63738025862748`.
File lama merekam **304 pembacaan nonempty** yang
dikirim ke validator, `final.quality=NOT_STARTED`,
`terminal_event_count=0`. **304 bukan jumlah
baris/sampel yang telah tervalidasi**. Listener
lama tidak merekam isi frame sehingga bukti
historis **tidak cukup untuk membuktikan**
jumlah siklus/sampel di Pi atau menentukan
satu-satunya penyebab event tidak terbaca.

Pengamatan lima siklus adalah **bukti perilaku
alat menurut operator**, bukan hasil pengukuran
durasi pompa/valve atau verifikasi host E2E.

## B. Bug yang teridentifikasi pada source

Sebelumnya adapter `scripts/stage7_pi_adapter.py`
menggunakan `read_until(b'\\n', 4097)` dengan
timeout 1 detik dan langsung memanggil
`receive_lines(...)` → `LegacySessionBridge.feed`.
**pySerial dapat mengembalikan potongan data
tanpa newline ketika timeout**, sedangkan frame
sensor firmware dikirim kira-kira 1 Hz.
Jika event `ACQ_START` terpotong, fragmen
tersebut diinterpretasikan sebagai JSON
rusak, sehingga session tracker
**mungkin tetap NOT_STARTED**.

Kasus kegagalan ini **berhasil direproduksi
secara deterministik offline**: memisah
`ACQ_START` menjadi dua data chunk
menghasilkan `NOT_STARTED` pada
`receive_lines` lama, padahal event lengkap
tersedia pada stream jika chunk disatukan.

## C. Perbaikan host receiver (tanpa perubahan firmware)

1. Menambahkan `SerialLineFramer`:
   menyimpan byte secara inkremental hingga
   karakter LF, tanpa menganggap timeout
   sebagai batas paket. Mempertahankan
   baris pertama yang lengkap agar
   `ACQ_START` tidak otomatis terbuang.
2. Panjang baris maksimum 4096 byte;
   baris terlalu panjang dibuang dan
   parser menunggu LF berikutnya untuk
   sinkronisasi kembali.
3. `receive_serial_chunks` memasukkan
   **hanya baris lengkap** ke state tracker.
   Ringkasan menambahkan jumlah byte/chunk,
   baris newline lengkap, JSON rusak,
   event yang terlihat, sampel sensor
   tervalidasi, serta overflow/potongan
   akhir yang dibuang.
4. Mode `serial-readonly` memakai fungsi
   `receive_serial_chunks` sebagai
   pengganti `receive_lines`. Tidak ada
   instruksi serial write, Nextion, pompa,
   valve, firmware upload, atau penggunaan
   model AI yang ditambahkan.
5. Hasil sensor **tidak disimpan mentah**
   pada laporan; provenance data untuk
   eksperimen pengambilan kopi harus
   tetap melalui kontrak dataset terpisah.

## D. Uji regresi dan batas penilaian

| Skenario | Hasil |
|---|---|
| Event START dipotong dengan timeout di tengah JSON | **PASS**, START dideteksi oleh receiver baru |
| Protokol satu sesi dari CSV nyata `D-GAW_B33.csv` | **PASS** offline: 151 sampel dan terminal `COMPLETE_QA` |
| Event PHASE_CHANGE / COMPLETE dalam simulasi | **PASS**, terhitung pada diagnostik |
| Frame overlong lalu payload valid | **PASS**, pulih setelah newline |
| Mock serial port, DTR/RTS sebelum open, lock dan close | **PASS** offline Windows |
| Skrip `test_stage7_pi_adapter.py` | **PASS** Windows |
| `test_stage7_bridge.py`, `test_stage7_usb_readonly_probe.py`, `test_stage8_offline_e2e.py` | **PASS** Windows |
| Uji live G3 kedua di Raspberry Pi | **BELUM DIJALANKAN** |

**Verifikasi versi baru di Pi:** transfer source
ke lingkungan Pi telah dicoba, tetapi
verifikasi remote lanjutan terhambat;
status deployment/test langsung di Pi
**jangan diklaim PASS** sebelum checksum
dan regresi remote kembali berhasil.

## E. Langkah berikutnya

1. Verifikasi SHA256 skrip yang terpasang
   di Pi dan jalankan regresi offline
   tanpa membuka USB.
2. Konfirmasi alat sudah selesai dan kembali
   dalam kondisi IDLE; monitor fisik siap.
3. Setelah operator memberi izin baru untuk
   **satu** sesi G3 tambahan, mulai listener
   dengan nama evidence baru dan minta
   operator melakukan START via Nextion
   **sesudah status listener siap**.
4. QA: wajib `ACQ_START`, lima siklus
   purging→collecting, `ACQ_COMPLETE`,
   timestamp/sample_idx valid dan
   `final.quality=COMPLETE_QA`.
   Total nominal 150; toleransi 151/152
   harus diberi catatan variance.
5. Jika masih `NOT_STARTED`, gunakan
   `diagnostics.wire_events_seen`,
   `complete_newline_frames`,
   `malformed_json_lines` untuk
   membedakan event yang tidak dipancarkan,
   kerusakan stream, atau perbedaan firmware.
   Jangan promosi model; AI tetap `N/A`.

**Keputusan:** kegagalan deteksi G3 pertama
**belum tuntas pada hardware**. Bug receiver
telah diperbaiki dan diuji offline.
