# Dataset eksternal asli dan sumber ilmiah

Folder `zenodo_15425922/` adalah **cache lokal terpisah** untuk rekaman
BME688 asli dari artikel:

Stefanone, A., Meacci, L., Rossoni, M., & Colombo, G. (2025).
*Transformer-based odor recognition on E-nose platforms*,
Results in Engineering, 27, 106309.
https://doi.org/10.1016/j.rineng.2025.106309

Dataset resmi: https://doi.org/10.5281/zenodo.15425922
Kode penulis: https://github.com/mrc-rossoni/TransformerOdorClassification
(repo penulis mencantumkan lisensi MIT; tinjau ketentuan atribusi sumber
sebelum redistribusi).

| File | MD5 yang diterbitkan Zenodo | SHA256 lokal terverifikasi |
|---|---|---|
| `CoffeePow-4.csv` | `81d373ba934046490862e3964ca77392` | `34f5e8a4875375ff5f7d802f0e958b3cdcf1c273dbecae1051589f79bea99bd4` |
| `Aroma-7.csv` | `94562d5bb44d7ee7d28100dd00367975` | `4c1195ccdacd33e8f04593186786623a3a8fb6a5a78ad6b77224b1f4066d98aa` |

Unduh sumber asli (tanpa dummy, tidak mengubah CSV):

    python scripts/research_external_coffee_datasets.py
    python scripts/test_external_coffee_enose.py
    python scripts/evaluate_external_coffee_enose.py --output-dir results/external_coffee_enose_v2

**File sumber asli tidak dimasukkan ke Git**; `.gitignore` mencegah
duplikasi publikasi dan menjaga reproduksi melalui DOI+MD5/SHA256.
Data tidak pernah dipindah ke `data/raw/` ATmega; tidak boleh dipakai
sebagai baris feature82 atau label roast/origin alat kita.

**Temuan integritas:** CoffeePow-4 = 3.583 rangkaian 10 langkah lengkap;
Aroma-7 = 4.750 rangkaian lengkap dan 4 pembacaan tersisa yang tidak
membentuk rangkaian. Rangkaian CoffeePow-4 (3.583) identik dengan
bagian awal Aroma-7. Keduanya **tidak independen**; penggabungan
seolah 8.333 sampel baru adalah keliru.

Kolom sebenarnya hanya `Resistance Gassensor,label` dalam bentuk
*long-format*, 10 pembacaan per rangkaian. Walaupun publikasi membahas
perangkat BME688 8 sensor, berkas ini **tidak** menyediakan kesepadanan
langsung ke **10 kolom ADC MQ/TGS/SHT30** milik kita. Tidak ada
`physical_specimen_id` atau `session_id` dalam berkas.
