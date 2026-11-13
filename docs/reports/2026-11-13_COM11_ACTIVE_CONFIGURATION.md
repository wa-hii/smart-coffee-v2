# Migrasi konfigurasi kerja E-Nose PCB kedua ke COM11

**Waktu:** 13 November 2026 WIB. **Branch:** `wahyu`.

## Identitas perangkat

Perangkat aktif adalah **PCB ATmega2560 kedua** dengan FT232RL
onboard. Deteksi Windows melalui pySerial/Device Manager:
`COM11`, `VID:PID=0403:6001`, `SER=A10KNJBLA`.
Identitas serial ini **berbeda** dari FT232R alat lama
COM5 `A10KMM3SA`; jangan gunakan readback/rollback
alat lama untuk perangkat COM11.

## Implementasi

1. `platformio.ini` untuk `mega2560` dan
   `nextion_test`: upload/monitor COM11, 115200 baud.
   Profil khusus firmware RF30 tetap compile-only.
2. `scripts/3_collect_data.py`: port default/manual
   contoh COM11, tanpa melewati `--arm-hardware`
   yang diwajibkan saat membuka port dan mengirim `#start;`.
3. `scripts/5_realtime_dashboard.py`: contoh dan
   bantuan COM11; petunjuk penggunaan memuat
   `--no-start` untuk hanya memantau.
4. `scripts/check_usb_receiver.py` menambahkan
   opsi `--expect-port` dan `--usb-serial` read-only.
   Jika target salah, fail closed dengan exit code 2.
   Tanpa argumen, diagnostik generik masih bisa dipakai.
5. `scripts/install_lcd_autosave.ps1` dan
   `windows_receiver/install_autostart.ps1`
   mendukung pinning `--usb-serial A10KNJBLA`
   agar mengikuti PCB walaupun nomor COM berubah.
   Installer generik tetap dapat dijalankan tanpa serial
   hardcoded untuk perangkat lain.
6. Shortcut Windows Startup existing
   `Smart Coffee E-Nose Receiver.lnk` telah dicadangkan
   ke `private/com11_startup_backup/` (tidak masuk Git),
   lalu diperbarui menggunakan `-SkipLaunch` serta
   `-PythonwPath` yang menunjuk interpreter Windows
   yang dipakai pada laptop pengembangan.
   **Tidak ada listener yang dimulai.** Shortcut tetap
   bisa mulai otomatis pada login Windows berikutnya;
   jangan gunakan serial monitor/programmer secara
   bersamaan dengan receiver yang aktif.

## Verifikasi yang diwajibkan

```powershell
python scripts/test_com11_active_target.py
python scripts/check_usb_receiver.py --expect-port COM11 --usb-serial A10KNJBLA
python scripts/test_usb_autodetect.py
python scripts/receiver_preflight.py
```

**Hasil pelaksanaan 13 November 2026:**

| Pemeriksaan | Hasil |
|---|---|
| `test_com11_active_target.py` (termasuk kasus port/serial salah) | **PASS** |
| `check_usb_receiver.py --expect-port COM11 --usb-serial A10KNJBLA` | **PASS_USB_BRIDGE_ONLY** |
| `test_usb_autodetect.py` | **PASS** |
| `test_receiver_host_instance_lock.py` | **PASS** |
| `test_receiver_bundle.py` | **PASS** |
| `receiver_preflight.py` | **PASS**, COM11 terpilih, dependencies/folder tersedia |
| `test_30cycle_take_ai_sync.py` | **PASS offline** |
| `pio run -e mega2560 -e nextion_test` | **2 SUCCESS, build only** |
| Shortcut Windows Startup | **Terverifikasi** memuat `--usb-serial A10KNJBLA`, Pythonw dan folder kerja benar |
| Proses receiver/AVRDUDE yang membuka COM11 | **Tidak ada** setelah perubahan |

Pengujian **tidak membuka COM11**, mengirim perintah serial,
menjalankan aktuator, membuat sesi CSV, atau mem-flash ATmega.
Ini bukan bukti bahwa bootloader ATmega atau Nextion fisik normal.

Status signature/bootloader ATmega **belum berubah**:
`avrdude -p m2560 -c wiring -P COM11 -b 115200 -n`
sebelumnya timeout. *Upload_port* COM11 adalah pilihan
port, **bukan bukti** perangkat siap diprogram.
Jangan flash tanpa signature MCU, backup Flash/EEPROM
PCB ini dan verifikasi rollback. Service receiver
tidak perlu aktif selama inspeksi bootloader.

Konfigurasi COM5/COM6/COM7 tiga alat, backup alat lama,
file HMI dan data mentah tidak termasuk migrasi.
