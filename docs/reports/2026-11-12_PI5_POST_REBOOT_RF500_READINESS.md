# Pemeriksaan Raspberry Pi 5 setelah hidup kembali — RF500

Tanggal: 12 November 2026 (WIB). Branch: `wahyu`.

## Kondisi dan metode

- Sebelumnya Pi `enose-pi5` tidak terjangkau sekitar 15:42 WIB. Operator menyatakan Pi telah menyala lagi.
- SSH dengan host key yang dikenal kembali berhasil. `journalctl --list-boots` menampilkan satu boot yang tersimpan pada journal saat ini; `uptime -s` sekitar **15:45:50 WIB**. Baris awal kernel dan symlink USB tertanggal sekitar **15:37 WIB**, tetapi catatan monotonic kernel menunjukkan USB terhubung **3,96 detik setelah boot**. Kemungkinan waktu dinding berubah saat sinkronisasi, sehingga jangan memakai 15:37 sebagai bukti USB telah terhubung sebelum boot.
- **Penyebab restart/hilangnya konektivitas sebelumnya tidak diketahui** dari bukti ini. Tidak ada journal boot sebelumnya yang tersedia untuk menentukan apakah terjadi gangguan daya, reboot operator, atau sebab lain.

## Status host dan FT232R setelah restart

| Parameter | Bukti | Status |
|---|---|---|
| SSH Tailscale | Perintah `date -Is` berhasil, waktu 15:46:36 WIB | PASS saat diperiksa |
| Pi | Raspberry Pi 5 Model B Rev 1.1, `uptime` dimulai dari boot baru | PASS identitas |
| Daya | `vcgencmd get_throttled=0x0` setiap pemeriksaan | PASS flag kernel saat ini; bukan pengukuran langsung 5V |
| FT232R | by-id serial `A10KNJBL` -> `../../ttyUSB0` | PASS enumerasi |
| USB | `journalctl -k -b -o short-monotonic -g ttyUSB`: attach di 3,964 s; tidak ada entri `disconnect` pada journal boot saat dicek | PASS terbatas |
| Pemegang port | `fuser /dev/ttyUSB0` tidak menemukan pemilik; ModemManager/getty tidak aktif | PASS passive |
| Pemantauan berulang | Tujuh sampel selama sekitar 90 detik: SSH/uptime, by-id dan `get_throttled=0x0` konsisten | PASS observasi pasif |
| Windows | `python -m serial.tools.list_ports -v` -> `no ports found` | Windows COM5 lama tidak tersedia saat dicek |

Tidak ada pembukaan serial USB, DTR/RTS, reset MCU, flashing, start AI Test, aktuator, perubahan service atau EEPROM. **Stabilitas serial transfer 900 data selama 15 menit tetap NOT VERIFIED.**

## Kesiapan Pi RF500 offline

- `pi_rf30_pi5_readiness.py`: `HOST_STAGED_NOT_MCU_VERIFIED`, blockers host kosong, dan model RF500 memiliki SHA256 `b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`.
- Python 3.13.5, scikit-learn 1.7.2, NumPy 2.5.4, SciPy 1.18.1, joblib 1.6.0, pyserial 3.5 tersedia pada venv staging Pi.
- Pengecekan model tanpa deserialisasi PASS.
- Replay model asli pada **900 sampel D-CAT_B70.csv** PASS: prediksi `dark`, paket kandidat `#rf30:B1F503A9:dark;`, hanya ACK simulasi; **0 byte transmisi UART fisik**.
- Firmware RF30 pasangan Pi tetap baru berupa kandidat HEX pada workstation. MCU yang terakhir diverifikasi masih memakai **SVM30 standalone**, sehingga bridge Pi belum boleh diaktifkan live.

## Keputusan dan batas langkah berikutnya

**Poin 1 PASS terbatas untuk pemeriksaan pasif setelah reboot. Poin 2 READY FOR ONSITE PREFLIGHT, NO-GO untuk flashing otomatis.**

Jalur FT232R Pi `A10KNJBL` berbeda dari adaptor Windows COM5 `A10KMM3SA` yang sebelumnya berhasil mem-flash ATmega. Pi tidak memiliki `avrdude` atau `pio` sebagai perintah sistem pada pemeriksaan ini, dan workstation Windows tidak menampilkan port COM. Karena itu identitas hubungan fisik dan jalur flashing perlu dikonfirmasi sebelum membuka port. Persetujuan flashing SVM30 pada 11 November **bukan** persetujuan mengganti ke RF30.

Sebelum flash: konfirmasi Pi/ATmega/Nextion/valve pada kondisi aman, sumber suplai 5V, jalur bootloader yang benar, image rollback lokal, dan izin spesifik untuk **satu** flashing RF30 (tanpa EEPROM atau TFT). Lalu lakukan verifikasi firmware dan uji AI Test 30 siklus terawasi; jangan klaim E2E sebelum itu.
