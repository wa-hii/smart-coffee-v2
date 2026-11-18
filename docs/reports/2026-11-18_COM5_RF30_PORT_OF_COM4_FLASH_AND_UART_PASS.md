# Port firmware RF30 yang berhasil di COM4 ke E-Nose lain pada COM5

**Tanggal:** 18 November 2026, sekitar 15.17–15.26 WIB.
**Cabang:** `wahyu`. **Status:** **RF30 Flash/verify, boot UART, dan EEPROM preservation PASS**.
**Batas:** belum ada pengujian fisik tampilan Nextion, pompa/valve,
atau inferensi Random Forest live via Raspberry Pi pada board COM5.

## Tujuan dan identitas target

Pengguna meminta langsung mengintegrasikan/upload firmware yang
berhasil pada perangkat FT232RL Windows COM4 sebelumnya
ke **alat berbeda yang kini terhubung ke laptop pada COM5**.
COM5 terdeteksi sebagai FT232RL USB `0403:6001`
serial unik **`A10KMM3SA`**, bukan perangkat COM4
`A10KMZQJA`, bukan COM11 `A10KNJBLA`.
Receiver Windows yang terdeteksi masih memakai argumen
`--usb-serial A10KNJBLA` sehingga tidak memiliki target COM5.
`data/raw/.incoming` kosong pada preflight.

Riwayat resmi proyek menyatakan COM5 `A10KMM3SA`
adalah ATmega2560 E-Nose dengan Nextion dan empat ADS1115
yang pada 11 November 2026 sudah di-flash **SVM30 standalone**:
`docs/reports/2026-11-11_B6_COM5_SVM30_FLASH_VERIFIED.md`.
Migrasi kali ini mengganti mode inferensi: dari SVM30
yang berjalan pada ATmega, ke **RF30 yang mengirim
900 sampel kepada Raspberry Pi 5** untuk prediksi RF500.
Karena itu COM5 belum otomatis memiliki prediksi AI
saat hanya disambungkan ke laptop tanpa listener Pi.

## Firmware target yang dipakai

**Firmware yang sama persis** dengan yang telah sukses
di-flash pada COM4, bukan hasil kompilasi alternatif:

```text
private/rf30_second_pcb_candidate/
  20261112_rf30_bootguard_v1/rf30_pi_return_candidate.hex
```

SHA-256:
`26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6`.
Payload Flash **35.770 byte**, seluruh alamat aplikasi
0–35769, di bawah batas aplikasi 253.952.
Build firmware yang diobservasi setelah boot:
`take30-ai30-rfhost-20261110`.

## Backup mandiri COM5 sebelum flash

Skrip:
`scripts/com5_rf30_guarded_migrate.py --backup`.
Sebelum backup, AVRDUDE read-only `-p m2560 -c wiring
-P COM5 -b 115200 -n -v` PASS signature
**`0x1e9801`**.

Backup baru disimpan hanya lokal:

```text
private/com5_rf30_migration/backup_20261118_152056_053864/
  original_flash.hex
  original_eeprom.hex
  original_flash_full_262144.bin
  original_eeprom_full_4096.bin
  manifest.json
  01_signature.log
  02_original_readback.log
  03_terminal_verify_suffix.log
  04_verify_existing_svm30.log
```

Pembacaan dan pemeriksaan:

- Flash penuh **262.144 byte** secara logis; hasil Intel HEX
  mewakili prefix **261.406 byte** dan pemangkasan
  738 byte suffix. Terminal AVRDUDE `dump flash
  0x3fd1e 738` **membaca langsung seluruh 738 byte sebagai
  `FF`**, dan checksum seluruh gambar Flash cocok.
- EEPROM **4.096 byte** terbaca penuh.
- Verifikasi AVRDUDE dengan image SVM30 historis
  SHA-256 `6d6b45f0bfcfda0c14b9cd6de1e9a32479e92ab3ee1cccd8e69dce3d530eeba2`
  **PASS**, sehingga aplikasi lama sesuai dokumentasi;
  bukan asumsi berdasarkan nama USB port saja.
- SHA-256 backup Flash lama:
  `9d927ccafd643a4904e1306f56bef8954ddfa951c821b631b0c0377e86ddfea8`.
- SHA-256 backup EEPROM lama:
  `a1f1161f0af472c902873d1050eb5f1813e883d27f823ca959ab22b9fb40c769`.

Backup lengkap tersimpan di folder privat lokal, tidak di-push
ke GitHub. **Kemampuan restore fisik image ini belum diuji**
dan tidak ada penulisan ulang firmware SVM30.

## Penulisan firmware RF30 ke COM5

Perintah:

```powershell
python scripts/com5_rf30_guarded_migrate.py --flash private/com5_rf30_migration/backup_20261118_152056_053864 --approval I_APPROVE_RF30_MIGRATE_COM5_WITH_VERIFIED_SVM30_BACKUP
```

Prosedur memverifikasi ulang identitas FTDI COM5,
checksum kandidat, backup penuh dan signature MCU;
kemudian menggunakan AVRDUDE `wiring/115200`,
`-D -U flash:w:<RF30-image>:i`.
Tidak ada perintah menulis EEPROM/fuse/lockbits,
melakukan chip erase eksplisit, atau mengganti file
HMI Nextion.

Log privat:
`private/com5_rf30_migration/flash_20261118_152252_040524/`.
Hasil AVRDUDE:

```text
Device signature = 0x1e9801 (probably m2560)
writing flash (35770 bytes): 100%
35770 bytes of flash written
35770 bytes of flash verified
avrdude.exe done. Thank you.
```

Setelah upload, dijalankan **verifikasi AVRDUDE terpisah**
`-n -U flash:v:<RF30-image>:i`, PASS:
`35770 bytes of flash verified`.
Manifest akhir:
`RF30_COM5_FLASH_AND_VERIFY_PASS_HMI_PI_TEST_PENDING`.

## Boot MCU dan preservasi EEPROM

Uji serial read-only pada COM5 @115200 selama 11 s
dengan satu DTR reset 140 ms menghasilkan
**991 byte RX**, tanpa mengirim perintah UART.

```json
{"event":"FW_HELLO",
 "protocol":"legacy-json.v1",
 "build_id":"take30-ai30-rfhost-20261110",
 "adc_channels":10,
 "data_cycles_total":30,
 "ai_cycles_total":30,
 "purge_s":25,
 "collect_s":5}
```

Pemeriksaan setelah boot:
`nextion.Serial2=9600`, `ADS1115 terdeteksi: 4/4`,
`Sistem siap`. Firmware juga melaporkan
**R0 belum dikalibrasi**, sehingga perlu evaluasi
sensor terpisah. Tidak ada perintah kalibrasi
atau aksi aktuator.

Log:
`private/com5_rf30_migration/postflash_passive_20261118_152408_010058/`.

Skrip `scripts/com5_rf30_verify_eeprom_preserved.py`
kemudian membaca ulang EEPROM via AVRDUDE `-n`,
tanpa menulisnya, dan memperoleh SHA-256
`a1f1161f0af472c902873d1050eb5f1813e883d27f823ca959ab22b9fb40c769`
**sama persis dengan sebelum flash**.
Status: `EEPROM_UNCHANGED_PASS`.
Log privat:
`private/com5_rf30_migration/eeprom_after_rf30_20261118_152506_508343/`.

## Status akhir dan langkah sesudahnya

| Pemeriksaan | Status |
|---|---|
| COM5 FTDI `A10KMM3SA` | PASS |
| Signature ATmega2560 dan bootloader | PASS |
| Backup terkini Flash/EEPROM + suffix FF | PASS |
| Firmware lama SVM30 cocok dengan image historis | PASS |
| Upload RF30 35.770 byte | **PASS** |
| Verifikasi Flash terpisah | **PASS** |
| MCU `FW_HELLO`, build RF30, ADS1115 4/4 | **PASS** |
| EEPROM identik sebelum dan setelah flash | **PASS** |
| LCD `pHome` secara visual pada COM5 | **BELUM DIKONFIRMASI** |
| Pompa/valve dan 30 siklus nyata | **BELUM DIUJI** |
| Pi5 Random Forest live pada COM5 | **BELUM DIINTEGRASIKAN** |

**Langkah operator:** amati Nextion apakah `pHome`
terlihat normal, pompa dan valve dalam keadaan
IDLE yang aman. **Jangan mulai AI Test** hingga
COM5 dipindahkan ke Pi5 dan listener RF500
dikonfigurasi untuk **FTDI serial perangkat ini**
`A10KMM3S` (nomenklatur Linux kemungkinan tanpa
akhiran `A`, harus diverifikasi pada Pi5 secara
langsung). Listener permanen yang sebelumnya
disiapkan untuk COM4 spesifik serial `A10KMZQJ`;
tidak boleh diasumsikan otomatis membaca COM5
atau diubah tanpa pemeriksaan yang aman.

## Batasan

Flash image RF30 tersimpan dan firmware boot,
tetapi model RF500 hanya berjalan di Raspberry Pi.
Ketepatan prediksi pada alat COM5 belum diketahui.
Tidak menyimpulkan sistem kedua telah PASS
end-to-end sebelum pengujian 900 sampel
dan `AI_RESULT_ACK` fisik pada Pi.
