# Deployment RF30 pada PCB kedua via FT232RL onboard COM11: signature timeout

**Tanggal:** 13 November 2026 WIB, sekitar 17.10–17.13.
**Branch:** `wahyu`.
**Tujuan:** selesaikan migrasi RF500 Pi ke PCB kedua secara terukur,
tanpa menghapus firmware awal/EEPROM yang belum di-backup.

## Bukti identitas dan preflight

- Windows: `COM11`, VID:PID `0403:6001`, USB serial `A10KNJBLA`,
  status PnP OK. FT232RL berada **di PCB kedua** sesuai operator,
  bukan modul FT232RL eksternal.
- Receiver `lcd_acquisition_service.py` dan programmer `avrdude.exe`
  tidak sedang berjalan; `data/raw/.incoming` kosong.
- Source/konfigurasi PlatformIO telah diarahkan ke COM11
  pada kedua environment; ini **bukan identifikasi bootloader**.
- Firmware kandidat RF30 di Windows, hash SHA-256
  `26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6`
  dan payload 35.770 byte aplikasi, valid.

## Prosedur otomatis yang dijalankan

Ditambahkan `scripts/com11_rf30_verified_deploy.py`.
Perangkat diverifikasi dengan port **dan** VID/PID **dan**
nomor seri USB; tool memeriksa file candidate, lokasi data
sementara, dan tidak ada listener aktif. Jika semuanya PASS,
baru dicoba read-only signature dengan perintah:

```text
avrdude.exe -C avrdude.conf -p m2560 -c wiring -P COM11 -b 115200 -n -v
```

Pemeriksaan menggunakan timeout **20 detik** untuk mencegah
programmer mengunci COM tanpa batas. **Hasil aktual:**

```text
Using Port                    : COM11
Using Programmer              : wiring
Overriding Baud Rate          : 115200
avrdude.exe: stk500v2_ReceiveMessage(): timeout
TIMEOUT_KILLED
BOOTLOADER_SIGNATURE_NOT_VERIFIED_NO_FLASH
```

Exit kode skrip **3**. Tidak ada respons
`Device signature = 0x1e9801`. Otomasi menghentikan
proses di sini, **sebelum** perintah backup Flash/EEPROM
atau upload RF30. Tidak ada upaya mengambil alih baud/
protokol secara acak atau mengubah fuse/EEPROM.

Bukti asli, log argumen yang dijalankan, dan manifest:
`private/com11_second_pcb_deployment/20261113_171023_205977/`.
Folder privat dilindungi `private/.gitignore`.

## Status Raspberry Pi dan RF500 terbaru

Setelah upaya COM11 selesai, koneksi SSH ke
`enose-v3@enose-pi5` kembali **berhasil**; status daya
`vcgencmd get_throttled=0x0`. Bukti model RF500 pada Pi:

```text
SHA256 final_model.joblib:
b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d

SHA256 rf30_pi_return_candidate.hex:
26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6
```

`pi_rf30_pi5_readiness.py` melaporkan
`HOST_READINESS_BLOCKED`, dengan blokir
`EXPECTED_PI_FTDI_BY_ID_NOT_CONNECTED`.
Hal ini **sesuai dengan sambungan saat ini**:
USB PCB kedua masih di Windows COM11, bukan Raspberry Pi,
sehingga tidak ada `/dev/ttyUSB0` pada Pi.
Dependencies Python Pi terdeteksi (scikit-learn 1.7.2,
NumPy 2.5.4, joblib 1.6.0, pyserial 3.5).
Model juga belum divalidasi prospektif untuk
pergantian perangkat ini. Tidak ada inferensi live.

## QA software

- `test_com11_rf30_verified_deploy.py`: mock FAIL-CLOSED
  ketika signature tidak terbaca, backup gagal,
  image hasil backup tidak lengkap, target salah;
  sukses upload hanya dalam simulasi tanpa membuka COM.
- `test_com11_active_target.py`: PASS.
- `test_rf30_firmware_result_contract.py`: PASS.
- `test_rf30_pi_result_bridge.py`: PASS offline, 900 sampel.
- `test_roast_rf30_pi_stream_replay.py`: PASS offline.
- PlatformIO kedua environment dan kontrak HMI pernah
  PASS compile-only sebelumnya; tidak ada upload baru.

## Keputusan

**Tidak ada firmware yang di-flash. Status saat ini:
`BOOTLOADER_SIGNATURE_NOT_VERIFIED_NO_FLASH`.**
FT232RL yang terenumerasi USB tidak membuktikan
jalur DTR#/RESET atau adanya bootloader ATmega2560.
AVRDUDE dengan programmer `wiring` lazim memakai
pulsa DTR/RTS untuk memasuki mode bootloader,
tetapi jalur reset PCB kedua tidak diketahui:
https://github.com/avrdudes/avrdude/blob/main/src/avrdude.1

**Hambatan fisik yang benar-benar perlu dihilangkan:**
jika skematik menunjukkan DTR# onboard FT232RL menuju
RESET MCU melalui rangkaian auto-reset yang benar dan
bootloader masih tersedia, COM11 dapat digunakan.
Jika jalur itu tidak ada atau bootloader hilang, gunakan
**programmer ISP melalui header/test point ICSP**
untuk membaca signature `0x1e9801` dan membuat backup
Flash/EEPROM khusus PCB kedua. Jangan menggunakan backup
COM5/SVM30 dari PCB yang berbeda.

Setelah jalur pemrograman dan backup valid,
prosedur dapat mengunggah kandidat RF30 ke area aplikasi,
memverifikasi Flash, lalu dilanjutkan pemulihan `pHome`,
perpindahan USB PCB dari Windows ke Pi, dan uji
30 siklus/900 sampel, pengembalian roast serta
`AI_RESULT_ACK` nyata. **Belum ada bukti E2E fisik.**
