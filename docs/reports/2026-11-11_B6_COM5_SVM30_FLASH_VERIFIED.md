# B6 — SVM30 standalone benar-benar di-flash ke ATmega2560 COM5

**Tanggal:** 11 November 2026, waktu lokal WIB. **Cabang:** `wahyu`.
**Status:** **FLASH & AVRDUDE VERIFY PASS; END-TO-END NEXTION / AI TEST PHYSICAL PENDING.**

## Perintah dan batas izin

Operator sebelumnya menyatakan bahwa setelah backup read-only
PCB berada pada kondisi **Nextion `pHome`**, pompa/dinamo
berjalan seperti biasa dan valve solenoid diam pada IDLE.
Setelah diminta izin mengganti firmware, pengguna menyetujui
dengan kata **"jalankan"**; izin mencakup **flashing satu
kali** firmware standalone SVM30 yang telah diidentifikasi,
bukan kalibrasi, perubahan EEPROM, Nextion HMI/TFT,
flash firmware alternatif, atau pengendalian pompa/valve.

## Bukti preflash

- Port Windows **COM5**, FTDI VID/PID `0403:6001`,
  serial unik `A10KMM3SA`.
- Proses penerima lama `lcd_acquisition_service.py`
  sudah dihentikan sebelumnya. Pemeriksaan ulang:
  **tidak ada proses `pythonw.exe` receiver**;
  `data/raw/.incoming` kosong.
- Readback sebelum flashing: `avrdude` melalui
  `-c wiring -p m2560 -b 115200 -P COM5 -n`,
  signature `0x1e9801`; EEPROM **4096/4096 byte**.
  Flash HEX mencatat prefix berurutan **261406/262144
  byte**, suffix 738 byte tidak direpresentasikan
  secara eksplisit, diperkirakan karena `0xFF`
  trailing — **tidak dibuktikan secara fisik**.
- Backup mentah dan checksum tetap privat di:
  `private/b6_com5_readback/20261111_170948/`.
- Image rollback **khusus area aplikasi**
  `legacy_app_only_rollback.hex` disiapkan dan
  diverifikasi secara **offline** untuk alamat
  **0–253951** tanpa menyertakan region bootloader.
  SHA256 rollback:
  `dad19c18f4ae0e432604bd008fc45388c10bed78f596265de42dac549367221f`.
  Rollback **belum diuji melalui flashing fisik**,
  tidak digunakan selama sesi ini.
- Kandidat SVM30 `private/svm30_standalone_firmware.hex`,
  SHA256 **`6d6b45f0bfcfda0c14b9cd6de1e9a32479e92ab3ee1cccd8e69dce3d530eeba2`**.
  Seluruh **50.006 byte** payload Flash berada pada
  alamat aplikasi **0–50005** (batas aplikasi
  `253952`); tidak ada rekaman menulis bootloader.
- Model asli tim `final_svm.joblib` SHA256
  `d71e74a037860b0c7d7da241c448dcda65a2b736c343577a62307baed3cb1e33`,
  **30 fitur**, SVC RBF, **125 support vector**.
  Sebelumnya **199/199 prediksi native C++ sama
  dengan scikit-learn 1.7.2** pada corpus uji offline;
  ini tidak menunjukkan akurasi kopi fisik baru.

## Satu kali upload (berhasil)

Kode penjaga: `scripts/svm30_b6_flash_once.py`.
Program memeriksa serial FT232, tidak adanya receiver,
backup/rollback/EEPROM, SHA firmware+model, dan alamat
HEX tidak melewati batas aplikasi.

Perintah `avrdude` yang dijalankan memakai:
`-p m2560 -c wiring -P COM5 -b 115200 -D`
dengan **`-U flash:w:svm30_candidate.hex:i`**,
tanpa opsi `-V`. `-D` mematikan auto chip erase;
Bootloader `wiring` menulis page Flash aplikasi.
Tidak ada `-e`, `-U eeprom:w`, atau instruksi
untuk menulis fuse/lock bits.

Log `avrdude` privat secara eksplisit mencatat:

```text
Device signature = 0x1e9801 (probably m2560)
writing flash (50006 bytes)
50006 bytes of flash written
verifying flash memory against svm30_candidate.hex
50006 bytes of flash verified
avrdude.exe done. Thank you.
```

**Exit code = 0**, durasi **24,27 detik** (tulis
12,53 detik, baca-verifikasi 10,76 detik).
Tidak ada percobaan kedua, tidak ada auto-rollback,
reset/flash eksternal, atau penulisan EEPROM
yang diperintahkan. Perlu dicatat bahwa **EEPROM
belum dibaca ulang setelah flashing**, sehingga
tidak ada klaim kesetaraan isi EEPROM pasca-upload.

Setelahnya Windows masih mendeteksi **COM5**
dengan serial FT232 `A10KMM3SA`,
tidak ada proses receiver lama aktif, dan
`data/raw/.incoming` tetap kosong.

### Artefak dan log privat

```text
private/b6_com5_svm30_deployment/
  deployment_manifest.json
  avrdude_flash_once.log
  svm30_candidate.hex
```

File `deployment_manifest.json` memiliki
`status=FLASH_WRITE_AND_AVRDUDE_VERIFY_PASS`,
signature dan verifikasi `true`. Semua
artefak firmware/model/backup/log tetap
**di lokal**, diabaikan GitHub.

## Status hardware dan lanjutan B6

**Belum terbukti secara fisik setelah flash:**
boot Nextion `pSplash → pHome`, pompa/dinamo
normal dan valve OFF di IDLE, respon tombol
`START AI TEST`, akuisisi 900 sampel selama
30 siklus (nominal 15 menit), batas waktu dan
performa inferensi MCU, tampilan kelas
`LIGHT/MEDIUM/DARK` pada `pResult`,
atau ketepatan prediksi terhadap roast kopi
yang belum dilatih.

**Langkah aman yang memerlukan operator:**

1. **Sebelum menekan tombol:** amati layar
   fisik setelah flashing; harus masuk
   `pHome` dalam beberapa detik. Pastikan
   pompa/dinamo sesuai IDLE dan valve diam.
   Jika stuck/valve bergerak tidak semestinya,
   **jangan mulai AI Test** dan laporkan.
2. Jika startup normal, buka `pTest` dan
   tekan **START AI TEST** satu kali pada Nextion
   dengan sampel kopi yang diketahui kelasnya.
   Ini interaksi fisik di LCD, **tidak ada
   kontrol USB atau Raspberry Pi**.
3. Monitor fase 25s PURGING dan 5s COLLECTING
   selama 30 siklus (~900s) serta aktifkan
   prosedur STOP/CANCEL jika ada anomali.
4. Setelah selesai pastikan `pResult.tRoast`
   menampilkan LIGHT/MEDIUM/DARK, sementara
   Origin dan Confidence tetap `N/A`.
   Catat apakah hasil sesuai label kopi.
5. Jika hasil `N/A` atau macet, jangan
   flashing ulang otomatis. Kaji ADC, state
   machine, waktu inferensi, RAM dan komunikasi
   Nextion. Image rollback dipakai **hanya
   setelah otorisasi SOP pemulihan tersendiri**.

**Kesimpulan:** milestone **flash B6 sudah PASS**,
tetapi **B6 end-to-end AI Nextion masih PENDING**.
