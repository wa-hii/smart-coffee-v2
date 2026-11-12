# Gerbang terakhir deployment RF30 pada PCB E-Nose kedua

**Tanggal:** 12 November 2026, sekitar 17:22–17:29 WIB

**Cabang:** `wahyu`

## Tujuan

Mengeksekusi permintaan deployment RF500 hingga dapat dibuktikan
berfungsi pada PCB kedua, melalui SSH/Tailscale dari Windows
ke Raspberry Pi 5. Target fisik berbeda dari PCB COM5/SVM30
tanggal 11 November. Pemeriksaan di bawah bersifat **read-only**.

## Hasil pemeriksaan perangkat

- SSH `enose-v3@enose-pi5` berhasil.
- Raspberry Pi `vcgencmd get_throttled=0x0`.
- FT232R `A10KNJBL` tetap terdeteksi sebagai
  `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0`
  → `/dev/ttyUSB0`, tanpa port owner.
- `lsusb` hanya memperlihatkan FT232R `0403:6001`
  dan USB root hubs. Tidak ditemukan USB ISP
  programmer pada pemeriksaan ini.
- `avrdude` Debian 7.1 arm64 sudah siap secara
  terisolasi di staging Pi; tidak memerlukan akses
  COM5 Windows.
- Percobaan `avrdude -p m2560 -c wiring -b 115200`
  sebelumnya gagal menerima signature; upaya terakhir
  sekitar 17:16 dibatasi 15 detik dan berhenti dengan
  `stk500v2_recv() timeout` (exit 124). **Tidak diulang
  di milestone ini**, agar tidak mereset perangkat
  terus-menerus tanpa jalur reset/bootloader terverifikasi.

## Perangkat lunak yang selesai

- Kandidat firmware RF30 bootguard: SHA256
  `26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6`.
- Model RF500 500 pohon: SHA256
  `b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`.
- Kedua berkas telah ada di Raspberry Pi, checksum cocok.
- Build firmware terakhir PASS, replay 900 sampel
  D-CAT_B70 PASS **offline**, ACK masih simulasi.
- Ditambahkan `scripts/pi_rf30_second_pcb_release_gate.py`,
  pengecekan status sebelum deployment yang **tidak
  pernah membuka serial, menjalankan avrdude, menulis
  Flash/EEPROM, atau mengaktifkan bridge**.
- Pengujian `scripts/test_pi_rf30_second_pcb_release_gate.py`
  PASS, menguji kondisi tanpa backup secara fail-closed.
- Skrip pemeriksaan disalin ke Pi di
  `~/smart-coffee-stage7/rf30_staging/second_pcb_20261112_bootguard_v1/`.

Output pemeriksaan langsung:

```text
status: NO_GO_PHYSICAL_DEPLOYMENT
ftdi_attached_to_ttyUSB0: true
model_sha256_verified: true
rf30_candidate_sha256_verified: true
pi_avrdude_locally_staged: true
pi_get_throttled: throttled=0x0
second_pcb_original_backup_verified: false
flash_allowed: false
blockers:
  - SECOND_PCB_FLASH_AND_EEPROM_BACKUP_NOT_VERIFIED
  - SAME_SESSION_MCU_PROGRAMMER_SIGNATURE_NOT_VERIFIED
```

## Mengapa upload belum dilakukan

FT232R berfungsi sebagai adaptor **UART**, bukan bukti
bahwa programmer berhasil masuk bootloader atau ISP.
Bootloader Mega2560 standar umumnya membutuhkan reset
tepat waktu melalui DTR dan rangkaian reset yang benar.
Tidak dapat diketahui hanya dari enumerasi USB apakah
PCB kedua memiliki jalur DTR/RESET, bootloader yang
kompatibel, dan kabel RX/TX yang tepat. Timeout menunjukkan
protokol belum memperoleh respons, bukan bukti chip rusak.

Melakukan `-U flash:w:` saat chip signature belum terbaca
tidak bisa dianggap sebagai deployment yang berhasil dan
berisiko apabila protokol/wiring berbeda. Backup SVM30
PCB COM5 **tidak boleh** digunakan sebagai rollback
untuk PCB kedua.

## Gerbang fisik yang masih diperlukan

1. Jalur pemrograman ke **PCB kedua** yang terbukti
   dapat membaca signature `0x1e9801`. Bila via
   FT232R UART, harus ada bootloader yang kompatibel
   beserta reset DTR/RESET yang benar. Bila tidak,
   gunakan ISP dengan programmer dan wiring yang sesuai.
2. Flash dan EEPROM asli **PCB kedua** dibaca dan
   disimpan dengan hash serta rollback aplikasi
   tersendiri; lokasi backup dapat diakses dari Pi.
3. Baru jalankan satu upload RF30 dengan verify,
   tanpa erase chip/EEPROM/HMI. Setelah itu uji
   `FW_HELLO`, `pHome`, 30 siklus/900 ADC, hasil
   roast `pResult`, dan `AI_RESULT_ACK` dari MCU
   secara langsung.

**Keputusan final sesi:** kondisi perangkat fisik **NO-GO**.
Kode, image, dependencies, model, dan staging siap.
Firmware **belum diunggah ke PCB**, LCD belum diuji
dengan RF30, dan klasifikasi end-to-end belum terverifikasi.
Menuntaskan sisanya memerlukan perubahan/konektivitas
fisik yang saat ini tidak tersedia melalui SSH.
