# B6 — Backup read-only Flash/EEPROM ATmega2560 melalui COM5

**Tanggal:** 11 November 2026, 17:09–17:11 WIB.
**Status:** **BACKUP READ PASS dengan catatan 738 byte Flash suffix
tidak direpresentasikan eksplisit di Intel HEX; FLASHING SVM30 NOT RUN.**

## Persetujuan dan pengamanan awal

Pengguna mengonfirmasi LCD Nextion kembali ke `pHome`,
berada dekat alat, dan menyetujui secara eksplisit
**menghentikan receiver COM5 serta mencoba satu backup
read-only Flash dan EEPROM**. Tidak ada izin menulis
firmware/EEPROM, menjalankan tes kopi, atau mereset
berulang. B6 dilakukan di checkout Windows branch `wahyu`.

- COM5: FT232R `0403:6001`, nomor seri `A10KMM3SA`.
- Receiver `lcd_acquisition_service.py --port auto --baud 115200`
  terdeteksi di PID **14628**, berstatus `connected` COM5.
- Folder `data/raw/.incoming` kosong, log receiver
  tidak memperlihatkan aktivitas baru sejak
  `CONNECTED COM5` pukul 15:16:23 WIB.
- `CloseMainWindow()` menghasilkan `False` pada proses
  `pythonw.exe` tanpa jendela. Receiver lalu dihentikan
  **dengan Stop-Process -Force hanya pada PID 14628**,
  **bukan shutdown graceful melalui handler Python**.
  Karena tidak ada file parsial aktif, tidak ada
  indikasi sesi yang sedang disimpan terputus.
- Setelahnya PID 14628 tidak ada, receiver lain 0,
  `.incoming` 0; konfigurasi autostart dan seluruh
  CSV asli **tidak diubah**.

## Satu sesi pembacaan bootloader (bukan upload)

- Programmer `avrdude`: **`-c wiring` / ATmega2560
  `-p m2560` / COM5 / 115200 baud**.
- Perintah memakai **`-n` (no write)** dan hanya:
  `-U flash:r:flash_readback.hex:i`,
  `-U eeprom:r:eeprom_readback.hex:i`.
  Tidak ada `-e`, `-U ...:w:`, flashing, atau
  perintah kendali pompa/valve/Nextion.
- Pembukaan port/programmer **mungkin memicu DTR reset**,
  tetapi reset fisik tidak diukur. Hanya **satu
  percobaan** dan tidak ada readback ulang.
- `avrdude` melaporkan **signature
  `0x1e9801` (ATmega2560)**, kedua pembacaan
  100%, exit code **0**; waktu total **73,61 detik**
  (Flash 56,25 detik; EEPROM 16,36 detik).
- COM5 FT232R `A10KMM3SA` masih terdeteksi setelah
  percobaan; proses receiver tidak dijalankan ulang.

### Bukti asli, lokal privat — JANGAN COMMIT KE GITHUB

Folder:

```text
private/b6_com5_readback/20261111_170948/
  backup_manifest.json
  avrdude_readonly.log
  flash_readback.hex
  eeprom_readback.hex
  ihex_integrity_report.json
```

| Data | SHA-256 file Intel HEX | Ukuran Intel HEX |
|---|---|---:|
| Flash asli | `92f0ff9a827192704254d30b71e7d4bf39ac0da4fc8d09586d468414a7194d94` | 629.073 byte |
| EEPROM asli | `f0831de921d017473e0d246467cc802e63e23bf266464f9a3d8c6028f1282bcc` | 9.869 byte |

Verifier offline `scripts/svm30_b6_verify_readback.py`
memastikan checksum **setiap record Intel HEX valid**,
format alamat ekstensi benar, EOF ada, tidak ada
alamat duplikat/tumpang tindih, SHA cocok dengan
manifest read-only, dan data bukan seluruhnya `0xFF`.

### Hasil validasi alamat (PENTING)

| Memori | Kapasitas ATmega2560 | Alamat dengan data eksplisit | Catatan |
|---|---:|---:|---|
| Flash | 262.144 byte | **261.406 byte** (0 sampai 261.405) | **738 byte suffix** di akhir tidak ada dalam file Intel HEX |
| EEPROM | 4.096 byte | **4.096 byte** | Seluruh alamat ada |

Pada Flash, tidak ada celah **di tengah** rekaman:
semua record data membentuk prefix berurutan mulai
alamat 0. Ini konsisten dengan ekspor Intel HEX yang
**memangkas bagian akhir berisi byte `0xFF`**,
tetapi file asli **tidak membuktikan** isi fisik
738 alamat yang tidak diwakili record. Untuk
perhitungan hash data internal, verifier mengisi
bagian yang tidak tertulis tersebut dengan `0xFF`
**sebagai asumsi**, tanpa memodifikasi file asli.
Jangan menyatakan 262.144 byte Flash semuanya
diukur atau backup identik secara fisik untuk area
yang tidak dicatat. Validasi pemulihan ke chip
belum dilakukan.

EEPROM memiliki 250 byte yang berbeda dari
`0xFF` (mungkin termasuk parameter kalibrasi;
tidak diinterpretasi tanpa skema EEPROM).
Flash memiliki 50.226 byte berbeda dari `0xFF`.
**Fuses/lock bits/bootloader recoverability tidak
diverifikasi**, dan backup memori lewat bootloader
**tidak menjamin seluruh image bisa ditulis ulang
melalui jalur bootloader yang sama**.

## Status B6 setelah backup

**PASS:** penutupan receiver terarah, identitas FT232R,
komunikasi bootloader ke ATmega2560, Flash/EEPROM
read-only, validitas Intel HEX, penguncian checksum
backup, dan preservasi private files.

**Masih wajib sebelum flash:** laporan `pHome` terbaru
**setelah** kemungkinan reset DTR ini (pengamatan
`pHome` sebelumnya adalah sebelum backup), cek
pompa/dinamo dan valve, SOP catu daya/ground/DTR
dan recovery/rollback, identifikasi jalur
programmer yang aman, dan **persetujuan spesifik
untuk flash kandidat SVM30**. Tidak ada
pengukuran stack/latensi SVM pada 16MHz atau
AI Test fisik 30 siklus.

Preflight ulang tanpa menyentuh COM:
`python scripts/svm30_b6_preflight.py
--verified-readback-dir
private/b6_com5_readback/20261111_170948`
masih **NO-GO**, dengan blockers
`NEXTION_BOOT_NOT_VERIFIED`,
`PROGRAMMER_POWER_SOP_NOT_VERIFIED`,
`SPECIFIC_UPLOAD_APPROVAL_MISSING`.
Kata `verified` mengacu pada **integritas berkas
readback yang tercatat**, **bukan** uji restore
fisik / pembuktian seluruh Flash byte.

**Firmware SVM30 belum di-flash**, EEPROM tidak
ditulis, tidak ada TFT Nextion yang di-upload,
dan receiver tidak dimulai ulang.
