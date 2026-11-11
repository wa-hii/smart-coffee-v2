# G2 USB precheck dan keenam artefak SVM pengguna — 11 November 2026

**Status:** G2 serial live **NOT RUN / NO-GO**. Precheck melalui SSH/sysfs
**PASS**, tetapi data USB menunjukkan peristiwa disconnect baru dan
persyaratan SOP pengawasan onsite belum dikonfirmasi. Tidak ada
`open('/dev/ttyUSB0')`, serial read/write, reset paksa, flashing, atau
pengoperasian pompa/valve.

## Hasil precheck Raspberry Pi (11.46 WIB)

- SSH ke Pi 5 melalui Tailscale berhasil dengan host-key checking aktif.
- Symlink port: `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0`
  → `/dev/ttyUSB0`.
- `fuser /dev/ttyUSB0` tidak menemukan proses pemilik.
- ModemManager dan serial-getty pada ttyUSB0: inactive.
- `vcgencmd get_throttled=0x0`.
- Kernel 10.35.08 WIB: `usb usb3-port1: disabled by hub (EMI?), re-enabling...`;
  setelah itu FT232R `A10KNJBL` terputus dan kembali terdeteksi pada
  `/dev/ttyUSB0`. Kalimat `EMI?` adalah dugaan dari kernel,
  **bukan diagnosis pasti** interferensi.
- Sebelumnya juga ada disconnect 02.29 WIB/reconnect 02.31 WIB.
- Probe `scripts/stage7_usb_readonly_probe.py` di repository masih
  *hard-pin* board lama `A10KMM3S` dan mewajibkan persetujuan G2,
  konfirmasi IDLE serta operator **onsite**. Walaupun pengguna
  mengonfirmasi status IDLE dan meminta G2, operator onsite belum
  disebut. **Tidak boleh mengarang token pengawasan** ataupun
  mengganti ID perangkat pada skrip untuk melewati gate.

**Keputusan:** hentikan sebelum port dibuka. Minta konfirmasi pengawas
onsite dan peninjauan koneksi/USB power/backfeed untuk FT232 baru
`A10KNJBL`; setelah pemeriksaan dinyatakan aman, update gate by-id
melalui review dan jalankan G2 *bounded passive RX* satu kali.
Pembacaan tidak mengirim perintah ke MCU tetapi `open()` pada serial
masih mungkin memicu reset karena DTR.

## Inventaris 6 file model yang diberikan pengguna

Berikut adalah *hash file terlampir*, bukan verifikasi isi model
melalui deserialisasi. Artefak binary `joblib` tidak dijalankan,
disalin ke Pi, atau di-commit.

| Nama file | Ukuran byte | SHA256 |
|---|---:|---|
| `predict_roast_svm.py` | 9781 | `f21aa7d50bf677d145a55776ff9cd842e0d957563ea657232c8f88a0d6bba133` |
| `final_svm_info.json` | 737 | `1116a3d1505d8c5a4f692ef93f55319f85ba94bd7594375ea109bb19dd64e488` |
| `final_svm.joblib` | 38331 | `d71e74a037860b0c7d7da241c448dcda65a2b736c343577a62307baed3cb1e33` |
| `features_dataset_maybe.csv` | 1809607 | `0bf696e0762bb85e825b2fcd927f07580da55caa03b4890449fb6dd09d8e2812` |
| `nested_cv_svm_maybe.csv` | 962 | `fe728e3b7556e0c948ff309c8b2623fda07b28cd8f6be4844612bc106bf8d495` |
| `final_svm_maybe.joblib` | 52988 | `142f662bd241802a93b568d27fe5ef06bbbabed1545ea9a36cd9305a2708bec5` |

**Metadata final** `final_svm_info.json` melaporkan
SVC kernel RBF, C=1, gamma=0.1, **30 fitur**, 176 sesi,
kelas dark/light/medium, nested CV weighted acc=0.8523,
macro-F1=0.8223. Angka berasal dari metadata pengguna,
**belum direproduksi atau dibuktikan pada sesi baru**.
Model ini **berbeda dari kandidat 9 fitur** di staging Pi
(C=1, gamma=scale, 133 sesi, 9 fitur). Jangan mengirim
vektor 9 fitur ke model 30 fitur atau sebaliknya.

`predict_roast_svm.py` mengharapkan bundle
`{'model','scaler','feature_names'}`, menghitung
`sc.transform(x_raw)` lalu `model.predict()` dan
`model.predict_proba()`. Model path hard-coded ke
`/home/aj/...` dan **tidak cocok** dengan Pi
`/home/enose-v3/...`. Helper juga menangkap error ADC dengan
`except: pass` dan dapat mengisi fitur tidak dikenal dengan
0, sehingga **belum fail-closed untuk 900 sampel**.
Sebelum deployment, wajib validasi 30 × (25+5),
urutan/nama/tipe semua fitur yang sebenarnya pada joblib,
versi scikit-learn yang cocok serta pemeriksaan no-leakage.

`features_dataset_maybe.csv` berisi **285 baris, 364 kolom,
27 batch** dengan protokol a=91, b=117, c=77 dan kelas
medium=113, dark=93, light=79. `nested_cv_svm_maybe.csv`
berisi 27 baris uji batch, total n_test=285; rata-rata
akurasi berbobot jumlah test pada file tersebut sekitar **70,88%**.
Hasil ini **bukan pengganti** metadata nested CV model
`final_svm.joblib` (85,23%); belum ada bukti
`final_svm_maybe.joblib` memakai konfigurasi yang sama.

**Kesimpulan model:** kenali `final_svm.joblib` sebagai kandidat
utama yang baru diberikan pengguna, sementara versi `maybe`
harus diperlakukan sebagai eksperimen terpisah. Jangan menimpa
staging model lama sebelum verifikasi aman dan uji kesetaraan.
