# Audit dan pembaruan overlay L/M/D — semua nomor batch valid

## Perubahan kebijakan

Nomor batch tidak dipakai untuk membatasi pengambilan data. Semua nama batch dengan metadata, fase, timestamp, dan ADC valid diberi perlakuan **sama**. Dengan demikian `L-MING_B69.csv` adalah satu dari lima rekaman MING Light sah, bukan pengecualian buatan. Origin yang memenuhi syarat sekarang **CAT, GAW, GRB, MING, TEM, TOR**.

Sebanyak 112 CSV diaudit ulang; 93 rekaman representatif dari enam origin dipakai dalam plot. Masing-masing roast mempunyai setidaknya lima batch unik. Terdapat dua pasangan CSV berbeda dengan origin+roast+batch yang sama (GRB Medium B60 dan TEM Medium B62); salinan ekstra tidak dimasukkan sebagai replikasi independen, tetapi tercatat dalam `duplicate_same_batch_qa.csv`.

## Ringkasan perubahan visualisasi

- Hasil sebelumnya: 5 origin, 78 rekaman, 100 grafik (50 RAW, 50 normalisasi t0).
- Hasil sekarang: **6 origin, 93 rekaman, 120 grafik** (60 RAW, 60 normalisasi t0).
- MING ditambahkan dengan Light B60/B66/B67/B68/B69, Medium B61/B62/B63/B64/B65, Dark B60/B61/B62/B63/B64.
- Dua mode overlay masing-masing menampilkan *semua* kurva valid yang dipilih pada satu area grafik, tanpa perataan antar-rekaman, interpolasi, atau smoothing.
- t0 tiap CSV ialah purging siklus pertama `sample_idx=25`, tepat sebelum collecting pertama t26; normalisasi adalah `ADC(t)-ADC(t0)`.

## Hasil deskriptif MING

Lima batch tiap roast diperiksa berdasarkan fitur **rata-rata dari 30 nilai** `(mean collecting 5 sampel) - (median lima titik purging terakhir)` per rekaman. Peringkat yang paling menonjol pada MING:

| Sensor | Rasio variasi antar-roast terhadap dalam-roast | Urutan rerata respons | Irisan rentang ketiga roast |
|---|---:|---|---|
| TGS2611 | 2,46 | Medium < Light < Dark | Ada |
| TGS2602 | 0,78 | Light < Medium < Dark | Ada |
| MQ135 | 0,69 | Light < Medium < Dark | Ada |
| TGS822 | 0,63 | Light < Medium < Dark | Ada |

Untuk fitur **rerata collecting setelah pengurangan t0** tiap rekaman, rasio terbesar MING diamati pada TGS822 (0,83), diikuti TGS2620 (0,54), TGS816 (0,40). Pada fitur ini, rentang ketiga roast masih saling overlap di **semua 10 sensor MING**.

## Interpretasi untuk seluruh origin

Pada fitur respons collecting di atas, rentang tiga roasting saling beririsan pada **53 dari 60 kombinasi origin–sensor**. Untuk rerata collecting dikurangi t0, nilai itu menjadi **57 dari 60**. Tidak terdapat bukti bahwa ketiga roasting konsisten dapat dipisahkan sempurna hanya dari overlay tersebut.

Kandidat yang layak diuji sebagai fitur tahap berikutnya antara lain TGS2611 untuk respons relatif purging pada TEM/MING, serta TGS822 untuk fitur respons normalized terhadap t0 pada MING/TEM/CAT. Namun nilai-nilai di sini **bukan** akurasi model AI, p-value, atau bukti kausalitas level roasting. Variasi baseline awal, drift sepanjang 30 siklus, identitas spesimen, dan perbedaan instrumen masih mungkin menjadi faktor pengganggu. Untuk pelatihan/evaluasi AI, pisahkan berdasarkan rekaman/sesi/spesimen, bukan mengacak tiap titik ADC atau siklus dari rekaman yang sama.

## QA

PASS: 112 CSV tervalidasi; seluruh 93 rekaman plot mempunyai hash unik dan nomor batch unik per origin/roast; **120 PNG** berisi kurva RAW dan normalized, **930 anchor ADC t0** bernilai ΔADC(t0)=0; checksum seluruh sumber tidak berubah. File `eligible_origins.csv`, `plot_index.csv`, `input_provenance.csv`, `baseline_t0_per_sensor.csv`, `sensor_separation_diagnostics.csv`, dan `summary.json` memuat jejak audit. Galeri lokal dapat dibuka melalui `GALERI_LMD_MERGE.html`.

Seluruh output B60–B68 yang lama tetap disimpan secara terpisah sebagai hasil historis, dan CSV sumber tidak dimodifikasi.
