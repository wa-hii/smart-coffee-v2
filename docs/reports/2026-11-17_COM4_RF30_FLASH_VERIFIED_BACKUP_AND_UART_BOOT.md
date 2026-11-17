# RF30 berhasil di-flash via laptop COM4 setelah backup firmware asli

**Tanggal:** 17 November 2026 WIB
**Branch:** `wahyu`.
**Tindakan operator:** secara eksplisit meminta upload/flash firmware
RF30 (kandidat yang sebelumnya gagal di COM11) pada ATmega2560 via COM4.
**Status akhir:** **RF30 FLASH VERIFIED + FIRMWARE BOOT CONFIRMED**,
kalibrasi dan HMI fisik belum divalidasi.

## 1. Memastikan COM4 adalah E-Nose berbeda dari COM11

- COM4: FT232RL `0403:6001`, USB serial **`A10KMZQJA`**,
  perangkat yang dalam riwayat 17 Oktober telah berhasil
  di-flash sebagai Smart Coffee E-Nose dengan Nextion 12 halaman,
  4/4 ADS1115 dan 10 kanal sensor. Bukan FT232RL PCB kedua COM11.
- COM11 sebelumnya: FT232RL serial **`A10KNJBLA`**,
  uji `wiring/115200` berulang kali timeout.
- Saat pemeriksaan port kali ini, Windows hanya melihat COM4.
  Receiver `lcd_acquisition_service.py` PID 14204 tetap hidup,
  namun terkunci `--usb-serial A10KNJBLA` dan
  statusnya `waiting_for_device`. Proses tidak dihentikan
  dan tidak mengakses COM4.
- Bootloader ATmega COM4 diuji read-only:
  `avrdude -p m2560 -c wiring -P COM4 -b 115200 -n -v`
  **PASS signature `0x1e9801`**, exit 0.

## 2. Menyiapkan backup PCB COM4 sebelum menulis

Target COM4 sebelumnya memiliki firmware berbeda dari target COM11,
sehingga backup perangkat khusus ini wajib dicoba sebelum flashing.

Jalankan skrip guarded:

```text
python scripts/com4_rf30_verified_deploy.py --upload --approval I_APPROVE_RF30_COM4_AFTER_VERIFIED_ORIGINAL_BACKUP
```

Hasil pertama: signature PASS, AVRDUDE berhasil read-only
Flash dan EEPROM, tetapi Intel HEX menampilkan 261.406 byte
dari ruang Flash 262.144 byte (738 byte suffix tidak direpresentasikan).
Skrip **STOP, tidak menulis firmware**.

Pemeriksaan lanjut:

1. `scripts/com4_rf30_verify_binary_original.py` membaca ulang
   Flash dan EEPROM via AVRDUDE read-only dalam format raw binary;
   Flash tetap 261.406 byte karena AVRDude memotong suffix FF.
   EEPROM adalah 4.096 byte dan sama dengan hasil pembacaan pertama.
2. AVRDUDE terminal read-only `dump flash 0x3fd1e 738`
   berhasil membaca **seluruh 738 byte suffix sebagai `FF`**.
   Tidak ada erase/write.
3. `scripts/com4_finalize_original_recovery_backup.py`
   melakukan lagi dump suffix, memeriksa alamat kontigu dan
   isi semua FF, kemudian merekonstruksi backup 262.144 byte.
   SHA-256 dibandingkan dengan hasil pembacaan Intel HEX
   (mengasumsikan suffix FF, kini diverifikasi secara langsung)
   dan EEPROM dari dua pembacaan. **PASS**.

**Backup firmware asli COM4 tersimpan hanya lokal**, di:
`private/com4_rf30_deployment/20261117_184947_198494/`.
File pemulihan final:
`terminal_suffix_20261117_185547_369390/original_flash_262144_fully_checked.bin`;
`terminal_suffix_20261117_185547_369390/original_eeprom_4096_checked.bin`.

| Memori asli | Ukuran | SHA256 |
|---|---:|---|
| Flash | 262.144 | `23bbe8db52de49136164a4ecdef9edfd61ca3dbe266e78fb19fee69955e43a89` |
| EEPROM | 4.096 | `1591bf837dc368617fbc4f3460800b01255c1c34b2b3e1bbe72c2e8e06ce8e87` |

**Batas:** backup logis konsisten dan lengkap menurut bootloader,
tetapi lockbit protection dan kemampuan restore fisik
belum diuji secara independen. Fuse/lockbit tidak diubah.

## 3. Firmware yang di-upload ke COM4

Kandidat RF30 dari pekerjaan PCB COM11:
`private/rf30_second_pcb_candidate/20261112_rf30_bootguard_v1/rf30_pi_return_candidate.hex`,
SHA-256:
`26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6`.
Payload aplikasi Flash **35.770 byte**, target `ATmega2560`.
Codebase memiliki kontrak perangkat E-Nose kompatibel secara sumber
(4 ADS1115, sensor, Nextion Serial2 9600, driver valve D10/D11),
namun revisi PCB tidak diverifikasi dari skematik fisik.

Perintah rilis yang dijalankan:

```text
python scripts/com4_rf30_release_from_verified_backup.py
```

Hasil AVRDUDE:

```text
Port: COM4
Programmer: wiring @ 115200
Device signature: 0x1e9801
Writing flash (35770 bytes): 100%
35770 bytes of flash written
35770 bytes of flash verified

Separate verify pass:
avrdude -n -U flash:v:<pinned-RF30-image>:i
35770 bytes of flash verified
status: RF30_APP_VERIFIED_ON_COM4_HMI_SENSOR_E2E_UNTESTED
```

Tidak menulis EEPROM, fuse atau lockbits.
Upload dilakukan melalui bootloader UART0 COM4
dan menggunakan `-D` untuk tidak memicu chip-erase ekstra.
Log:
`private/com4_rf30_deployment/20261117_184947_198494/rf30_release_20261117_185708_835522/`.

## 4. Verifikasi pasca-flash melalui UART0

`scripts/com4_rf30_passive_postflash.py` membuka COM4 read-only
@115200 selama 11 detik. Capture pertama menerima 0 byte.
Dengan satu pulse DTR 140 ms untuk reset terkontrol:

```text
uart_tx_bytes: 0
uart_rx_bytes: 991
FW_HELLO: seen
build_id: take30-ai30-rfhost-20261110
adc_channels: 10
data_cycles_total: 30
ai_cycles_total: 30
purge_s: 25
collect_s: 5
Nextion: Serial2 @ 9600
ADS1115 terdeteksi: 4/4
Sistem siap. Kirim #start; untuk mulai akuisisi.
```

**Kalibrasi:** firmware mengeluarkan
`Sensor belum dikalibrasi` dan
`Kalibrasi belum ada`; tidak ada kalibrasi
baru atau penulisan EEPROM saat pekerjaan ini.

**Perbedaan bukti:** verifikasi Flash berhasil dan firmware
secara nyata memberikan pesan boot, tetapi pembacaan ini
tidak memastikan layar Nextion telah menampilkan `pHome`,
sensor memberikan ADC yang benar, pompa/valve berfungsi,
atau model Random Forest di Pi telah live.
Tidak dilakukan perintah `#start;`, pengambilan data,
kontrol aktuator, atau prediksi AI.

## 5. Hasil dan tindak lanjut

| Tahap | Status |
|---|---|
| COM4 USB FT232RL `A10KMZQJA` | PASS |
| Signature ATmega2560 via COM4 | PASS |
| Backup firmware lama Flash 256KiB + EEPROM 4KiB | PASS (logis; restore belum diuji) |
| Upload firmware RF30 35.770 byte | **PASS** |
| Verifikasi Flash pasca-upload terpisah | **PASS** |
| FW_HELLO UART0 setelah pulse DTR | **PASS** |
| Keempat ADS1115 terdeteksi | **PASS 4/4** |
| Kalibrasi sensor / baseline | **BELUM ADA** |
| Tampilan `pHome` fisik Nextion | **BELUM DIPASTIKAN** |
| Raspberry Pi RF model live | **BELUM DIUJI** |
| Receiver yang terkunci ke serial COM11 | Tidak diubah |

Pemeriksaan selanjutnya: lihat halaman Nextion tanpa memulai
akuisisi, cocokkan ID halaman, lalu lakukan kalibrasi di udara bersih
melalui SOP terpisah jika memang diperlukan dan didukung firmware.
Lakukan pengujian Raspberry Pi/Random Forest secara terawasi,
bukan mengklaim inferensi selesai dari `FW_HELLO` saja.
