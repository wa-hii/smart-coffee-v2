# RF500 Pi — pemeriksaan pasif FT232R dan kesiapan transisi firmware

**Tanggal:** 12 November 2026 (WIB)

**Workspace:** `D:\ENOSE\smart-coffee-v2-hardware\smart-coffee-v2-hardware`

**Branch:** `wahyu`
**Batas pekerjaan:** pemeriksaan read-only FT232R/Pi dan QA offline firmware; **tanpa membuka port serial, reset, flash, EEPROM, pengendalian aktuator atau modifikasi Nextion**.

## Hasil poin 1 — FT232R tanpa serial-open

- SSH menggunakan host key yang sudah dikenal (`StrictHostKeyChecking=yes`) berhasil ke `enose-v3@enose-pi5`.
- Boot Pi yang diperiksa menunjukkan FTDI terpasang sebagai `/dev/ttyUSB0` pada **12 November 2026 pukul 15:22:01 WIB**. Symlink `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0` tetap menuju `../../ttyUSB0`.
- Lima pemeriksaan berkala selama sekitar **61 detik** mengembalikan symlink yang sama, dan kelimanya menunjukkan `vcgencmd get_throttled=0x0`.
- Pemeriksaan akhir pukul **15:38:45 WIB**: `journalctl -k -b -g ttyUSB` hanya mencatat attachment awal; `journalctl -k -b -g disconnect` dan `-g under-voltage` tidak menemukan entri. `fuser /dev/ttyUSB0` tidak melaporkan pemilik port saat diperiksa.
- Status akhir poin 1: **PASS untuk enumerasi dan observasi pasif sesaat; NOT VERIFIED untuk stabilitas ketika port dibuka dan saat 900 sampel/15 menit dikirim.** Tidak ada uji transfer byte atau sensor live.

## Persiapan poin 2 — pemeriksaan lokal, belum flashing

| Pemeriksaan | Hasil |
|---|---|
| Build `pio run -c scripts/platformio_rf30_bench.ini -e rf30_return_bench` | **PASS**; Flash 35.748 B, SRAM global 3.917 B |
| HEX RF30 privat `private/rf30_pi_restore_image/20261112/rf30_pi_return_candidate.hex` | SHA256 `13b764d4f8b4aad3c09413bdc7a18094c1e90bf18be83dec5b6b2cb103e92440`, sesuai manifest |
| HEX SVM30 kandidat sebelumnya `private/b6_com5_svm30_deployment/svm30_candidate.hex` | SHA256 `6d6b45f0bfcfda0c14b9cd6de1e9a32479e92ab3ee1cccd8e69dce3d530eeba2`, cocok |
| Backup historis Flash dan EEPROM, `private/b6_com5_readback/20261111_170948/` | Manifest dan file ditemukan; kemampuan *restore* fisik **belum terbukti** |
| Branch rollback `backup/atmega-svm30-standalone-20261112` | Lokal dan remote menunjuk commit identik `7db96db006f780a9e78dcbea3830b21a170ae6cd` |
| Delapan pemeriksaan offline RF30, bridge, fitur/replay, akuisisi 30 siklus, standalone dan kontrak Nextion | **PASS**; hanya simulator/kontrak, bukan fisik |

Readiness Pi sebelumnya mengembalikan `HOST_STAGED_NOT_MCU_VERIFIED` dengan hash model cocok dan modul bridge tersedia. Hal ini **bukan** izin untuk mengaktifkan mode live.

## Gerbang keselamatan berikutnya

1. **Konfirmasi identitas rangkaian fisik**: FTDI pada Pi (`A10KNJBL`) berbeda dari FTDI Windows COM5 (`A10KMM3SA`) yang digunakan saat flash SVM30. Ini bisa hanya perbedaan adaptor/kabel, namun tidak boleh menganggap keduanya otomatis menuju MCU yang sama tanpa konfirmasi.
2. Verifikasi status daya, urutan recovery, jalur pemrograman dan SOP onsite sebelum melakukan upload. Pertahankan rollback dan backup asli; **jangan menulis EEPROM**.
3. Perlu persetujuan spesifik untuk satu kali flashing image RF30 ke ATmega dan operator di dekat alat. Setelah flash, buktikan `FW_HELLO`/`fw_build_id`, ACK protokol, kestabilan USB selama akuisisi dan hasil `pResult` dalam uji terawasi.

**Keputusan:** poin 1 selesai untuk batas pemeriksaan pasif. **Poin 2: PREPARED / NO-GO untuk flashing tanpa persetujuan dan verifikasi identitas board.** Bridge live dan uji L-TOR belum dijalankan. Working tree pengguna, dataset mentah, HMI, layanan dan perangkat fisik dibiarkan apa adanya.

## Addendum pukul 15:42 WIB — Pi menjadi tidak terjangkau

Setelah laporan awal dibuat, pemeriksaan penutup melalui SSH kembali menghasilkan **`Connection timed out`**. `ping -n 2 enose-pi5` kehilangan 2/2 paket; `tailscale status` pada Windows melaporkan `enose-pi5` **offline (last seen sekitar 1 menit)** dan `tailscale ping --c 2 enose-pi5` berakhir `no reply`. Pada pengecekan sekitar **15:42:24 WIB** SSH tetap gagal.

Ini membatalkan anggapan bahwa Pi dapat diandalkan untuk pengujian live saat ini. **Pemeriksaan pasif FT232R sebelum timeout tetap valid pada jendela pengamatan itu**, tetapi status Pi/USB terbaru setelah putus jaringan **tidak diketahui**. Tidak ada bukti apakah penyebabnya Wi-Fi/Tailscale, reboot, power, USB, atau faktor lain; tidak boleh mengklaim FT232R sebagai penyebab.

**Keputusan akhir yang diperbarui:** poin 1 **PARTIAL/BLOCKED** untuk kesiapan end-to-end karena host tidak terjangkau; poin 2 flashing **NO-GO**. Tidak dilakukan tindakan reset, serial open, flashing atau akses aktuator. Setelah Pi terhubung kembali, ulangi pemeriksaan uptime, daya, sysfs dan log kernel (apakah boot baru atau USB disconnect) sebelum evaluasi ulang.
