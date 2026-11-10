# Rencana integrasi kandidat RF 500 ke Raspberry Pi 5 dan Nextion (tanpa deployment fisik)

**Status:** software-only feature/integrity QA PASS; joblib belum dieksekusi, inferensi model asli dan jalur hasil Pi → ATmega → Nextion **BELUM DIVERIFIKASI**. Tidak ada flashing, port serial dibuka, atau perubahan visual HMI/firmware.

## 1. Pemeriksaan tiga artefak yang diterima

User mengirim `final_model.joblib` (2.363.398 byte; SHA256 `b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`), `final_model_info.json` dan `predict_roast.py`. Metadata **melaporkan**, bukan membuktikan, RF 500 pohon, 176 sesi, OOB 0,8352, nested-CV weighted accuracy 0,8011, macro F1 0,7492. Detail 27 fold, training specimen IDs, group split, nama/masa pemakaian alat, confusion matrix, preprocessing training, dan calibration belum diberikan sehingga metrik itu tidak dapat diverifikasi independen. OOB bukan bukti generalisasi pada sampel prospektif, dan CV biasa yang tidak memisahkan alat/spesimen mungkin optimistis.

Marker serialisasi pada artifact menyebut scikit-learn **1.7.2** (dibaca statis tanpa `joblib.load`). Versi numpy/joblib/scipy dan Python pelatihan belum diketahui; samakan lingkungan agar model portable. **Model joblib tidak dimasukkan dalam Git repo dan tidak dieksekusi pada audit ini** karena deserialisasi pickle dapat mengeksekusi kode Python. Gunakan hanya artifact dari pembuat yang dipercaya dan cocokkan checksum resmi.

Fitur **urut persis**:

1. `tgs822_max_mean`: rata-rata dari 30 puncak ADC TGS822 pada 5 sampel collecting/siklus.
2. `tgs822_purging_mean_mean`: rata-rata dari 30 nilai rerata ADC TGS822 pada 25 sampel purging/siklus.
3. `mq8_max_mean`: rata-rata dari 30 puncak ADC MQ8 pada 5 sampel collecting/siklus.

Fitur adalah **raw absolute ADC**, **bukan** baseline correction, bukan Z-score dan bukan fitur `median_phase_response` pada ablation sebelumnya. Tidak boleh menukar rumus tanpa retraining model. Hasil `predict_proba` Random Forest adalah probabilitas mentah yang belum dikalibrasi; jangan menyebutnya kepastian hasil atau menampilkan confidence terkalibrasi tanpa pengujian tambahan.

**Masalah pada helper yang diunggah:** jalur joblib hardcoded ke komputer peneliti lain (tidak akan ada di Pi), `python3 predict_roast.py` tanpa argumen hanya menghasilkan pesan penggunaan, `except: pass` pada ADC rusak bisa menghilangkan titik diam-diam, pengisian nilai 0.0 ketika fase/sensor hilang menutupi data incomplete, tidak ada pembatas 30 siklus atau validasi indeks/fase, dan kelas/probabilitas diterima tanpa kontrak versi. Helper hanya untuk referensi fitur, bukan Pi production receiver.

## 2. Kontrak aplikasi sebelumnya dan hambatan integrasi

Menurut `src/main.cpp`, firmware saat ini:

- `ACQ_DATA_REPETITIONS = 30` pada **Take Data**, sedangkan `ACQ_AI_REPETITIONS = 5` pada **Start AI Test**.
- Fase tiap siklus **purging 25 s + collecting 5 s**; 30 siklus = sekitar 900 detik/15 menit, 5 siklus = sekitar 150 detik/2,5 menit.
- Sensor dikirim melalui ATmega USB `Serial` pada **115200 baud**; Nextion terhubung langsung ke **`Serial2` 9600 baud** pada ATmega2560, bukan dari Pi langsung. Pi sebelumnya menerima FT232R `/dev/ttyUSB0`; gunakan `/dev/serial/by-id/` untuk stabilitas jika tersedia.
- `EVT:AI_START` dari Nextion menjalankan **5 siklus**, lalu ATmega memanggil `doInference()` yang saat ini memberi `N/A` dan langsung membuka `pResult`. `updateNextionInferenceResult()` menulis `tRoast`, `tRConf`, `tOrigin`, `tOConf`, serta bar `jLight,jMedium,jDark` (nol bila N/A).
- `scripts/stage7_pi_adapter.py` dan `scripts/stage7_bridge.py` berkontrak **5 siklus** dengan AI `N/A`; tidak boleh diubah diam-diam agar lama transport G3 tidak rusak. Upaya menyuntik hasil dari Pi ke Nextion saat ini tidak memiliki handler firmware produksi dan tidak boleh diklaim telah bekerja.

**Konsekuensi:** `RF 30-siklus` **tidak boleh dipakai langsung untuk Start AI Test 5-siklus** karena jendela waktu fitur dan pola drift berbeda. Menambahkan nilai puncak/rerata dari lima siklus ke model yang dilatih 30 siklus menyebabkan *distribution shift*. Panjang vektor sama (3 fitur) bukan bukti kompatibilitas.

## 3. Modul baru software-only (sudah diuji)

- `scripts/roast_rf30_pi_inference.py`: baca CSV 900 baris dengan 30×(25 purge + 5 collect), verifikasi kolom, fase, timestamp, indeks, seluruh 10 ADC, ekstrak **tepat tiga fitur raw ADC**, dan menghasilkan JSON host-only. Mode `--validate-only` **tidak memuat joblib**. Mode prediksi hanya bekerja jika file model sesuai SHA256 dan metadata/urutan fitur, tidak menulis ke MCU.
- `scripts/roast_rf30_pi_stream_replay.py`: terima log **NDJSON firmware yang direkam sebelumnya**, validasi `ACQ_START` 30 siklus, sensor frames, `ACQ_COMPLETE` 900 titik, mengabaikan label operator pada mode labeled_data. Membuat CSV hanya sementara di direktori temp; tidak ada data unknown yang ditulis ke training.
- `scripts/test_roast_rf30_pi_inference.py` dan `scripts/test_roast_rf30_pi_stream_replay.py`: tes ekspor fitur dibandingkan rumus helper asli, reject data 5 siklus/899 titik/ADC invalid, replay 900 sensor frame tanpa label, fail-closed pada data hilang/phase salah. Semua tes offline; tidak ada `joblib.load` aktual, USB, aktuator atau HMI fisik.

## 4. Cara mencoba pada Pi (tanpa koneksi hardware)

**Jalankan secara manual**, tanpa mengubah aplikasi Nextion/firmware.

1. Copy `scripts/roast_rf30_pi_inference.py`, `scripts/roast_rf30_pi_stream_replay.py`, `scripts/requirements-roast-rf30-pi.txt`, model `final_model.joblib`, metadata `final_model_info.json`, dan contoh 900-sampel CSV ke direktori baru di Pi, misal `~/smart-coffee/rf30/`. Jangan menaruh artefak model yang belum diverifikasi ke proses dengan hak root.
2. Di terminal Pi:

```bash
cd ~/smart-coffee/rf30
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-roast-rf30-pi.txt
sha256sum final_model.joblib
# Wajib sesuai: b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d
python3 roast_rf30_pi_inference.py --input contoh_30_siklus.csv --validate-only
```

3. Setelah sumber model dipercaya, verifikasi checksum, versi dan kontrak preprocessing:

```bash
python3 roast_rf30_pi_inference.py --input contoh_30_siklus.csv \
  --model ./final_model.joblib --metadata ./final_model_info.json
```

4. Contoh replay dari log serial yang **sudah direkam sebelumnya** dan mengandung `ACQ_START`, 900 frame ADC 30 siklus, serta `ACQ_COMPLETE`:

```bash
python3 roast_rf30_pi_stream_replay.py --input-ndjson capture_30_siklus.ndjson --validate-only
```

File 5-siklus `Start AI Test` secara sengaja ditolak. Berkas invalid/missing tidak diberi prediksi. Path model lama `/home/aj/workspace/...` tidak lagi digunakan.

## 5. Dua opsi untuk integrasi LCD fisik

**Opsi A — disarankan untuk menjaga durasi UI sekarang:** **retrain dan validasi RF untuk 5 siklus** memakai fitur yang dihitung hanya dari siklus 1–5, termasuk validasi pengelompokan per spesimen/sesi/perangkat. Model baru harus diekspor bersama manifest baru dan uji prospektif. Mode `Start AI Test` 5-siklus yang sudah teruji dapat dipertahankan; setelah hasil valid, implementasikan return protocol Pi → ATmega → Nextion.

**Opsi B — gunakan model RF500 30-siklus yang ada:** ubah spesifikasi mode `Start AI Test` menjadi 30 siklus secara **terkoordinasi** setelah persetujuan SOP dan user (durasi ~15 menit); ubah firmware mode, host collector, timeout, dan progres `pTestRun`. Jangan hanya mengubah konstanta `ACQ_AI_REPETITIONS`—adapter `Stage7` lama menolak selain lima, dan hasil N/A akan keluar terlalu awal. `Take Data` 30-siklus boleh dipakai untuk **replay data berlabel yang sudah valid**, bukan untuk menyimpan kopi unknown sebagai ground truth training.

Untuk keduanya, desain kontrak hasil yang direkomendasikan (BELUM DIDEPLOY):

1. Nextion `EVT:AI_START` → ATmega memulai sesi AI dan menerbitkan **token sesi sekali pakai** pada `ACQ_START`, beserta build ID, `cycles_total`, dan versi protokol.
2. Pi mengunci kepemilikan satu port USB 115200, memvalidasi semua frame, membangun fitur dari raw ADC, dan menjalankan model hanya setelah `ACQ_COMPLETE` yang valid.
3. Pi mengirim pesan kandidat hanya bila sesi sama dan status pasca-COMPLETE masih menunggu, misalnya proposal protokol `PI_INFERENCE_RESULT(session_token, roast, model_hash)` + error/ACK. Format final perlu diputuskan dengan ukuran buffer `cmdBuf[64]`, terminator `;`, checksum, timeout dan aturan duplikasi. **Jangan mengirim JSON hasil mentah ke serial firmware sekarang: belum ada parser.**
4. ATmega memverifikasi token, build/mode, replay/timeout, lalu pada `pResult` memperbarui `tRoast` menjadi LIGHT/MEDIUM/DARK. `tOrigin`, `tOConf` dan `tRConf` **tetap N/A** sebelum ada model origin/kalibrasi confidence. Bar `jLight/jMedium/jDark` **tetap 0** sampai reliabilitas probabilitas diuji. Tampilan HMI (font/posisi/gambar) tidak diubah.
5. Bila sesi gagal, sumber model belum siap, Pi disconnect atau protokol tidak cocok, hasil `N/A`; **pompa/valve tetap ditangani ATmega** tanpa instruksi kontrol dari Pi.

Uji bertahap: replay CSV 30 dan NDJSON offline → uji serial loopback *tanpa aktuator* → firmware/HMI virtual → G0/G2 supervisi USB (risiko DTR auto-reset/VBUS) → G3 uji hardware → uji prospektif blind. Tidak ada flashing TFT atau firmware pada milestone ini.

## 6. Feedback model dan perbaikan yang disarankan

- **Rumus preprocessing harus cocok persis** dengan training RF500 (ADC absolut). Tidak ada baseline correction/Z-score bila memang model hanya dilatih dengan 3 fitur raw; purging mean TGS822 adalah fitur yang dapat membawa offset instrument/temperature drift. Bandingkan dengan model baseline-corrected *melalui retraining*, bukan memodifikasi fitur inference saja.
- Data yang dilaporkan 176 sesi perlu **manifest sumber dan group leakage**: identitas origin, roasting, batch, device, preparation, date, sensor/time, train/validation/holdout, hash, dan apakah 27-fold benar-benar nested berdasarkan grup. Tidak ada cukup bukti untuk menyebut OOB 83,5% sebagai akurasi produksi atau nested CV 80,1% sebagai prediksi batch baru.
- Uji kelas Dark/Light/Medium per origin dan per perangkat; minimal `balanced_accuracy`, `macro_f1`, confusion matrix, recall per kelas, ECE/Brier reliability dan *reject/unknown* pada blank/udara bersih. Sampel kopi unknown jangan dipaksa menjadi salah satu kelas tanpa gate kualitas/unknown.
- Lakukan unit test paritas fitur pada sampel 900 titik dan **benchmark latensi/CPU/RAM** pada Pi yang sebenarnya sebelum memberi izin integrasi HMI.
- Model berukuran 2,36 MB secara file, masih **bukan bukti** penggunaan RAM/latensi terukur. Kompatibilitas versi scikit-learn 1.7.2 pada Pi harus diuji dengan venv sama seperti training.

**Keputusan:** source adaptasi dan simulasi integrasi host 30-siklus siap untuk uji offline. Model akhir maupun jalur Pi→Nextion **belum GO** dan **belum diubah pada perangkat**.
