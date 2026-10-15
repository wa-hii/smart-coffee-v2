# Import CSV irfan-pria-solo — baseline B36–B40 dan MING B40

Sumber branch `origin/irfan-pria-solo`, commit `d5bd43e1e7d19325b8fe1cf2c8f18bbf152c18a8`.
Berhasil mengimpor **7/8 berkas diminta** secara byte-identical ke `data/raw/irfan_baseline_B36_B40/` dengan manifest/checksum di `data/analysis/irfan_baseline_B36_B40_manifest.csv`. `BASELINE_B38.csv` **tidak ditemukan** dalam branch tersebut. Tidak ada overwrite atau modifikasi hardware/firmware.

| Data | Jumlah siklus | Jumlah sampel purging/siklus | Collecting/siklus | Catatan |
|---|---:|---:|---:|---|
| BASELINE B36 | 5 | 25 | 5–6 | Skema lama |
| BASELINE B37 | 5 | 25 | 5–6 | Skema lama |
| BASELINE B39 | 5 | 50–51 | 5 | Skema lama |
| BASELINE B40 | 40 | 25–26 | 5–6 | Ada kolom `datetime` |
| D-MING B40 | 40 | 25–26 | 5–6 | Ada kolom `datetime` |
| L-MING B40 | 40 | 25–26 | 5–6 | Tanpa `datetime` |
| M-MING B40 | 40 | 25–26 | 5–6 | Ada kolom `datetime` |

**Temuan kritis:** klaim protokol B40 `50 s purging + 5 s collecting` **tidak sesuai jumlah sampel yang direkam**. Jika cadence sekitar 1 Hz, pola B40 dekat dengan 25–26 s purging dan 5–6 s collecting. Perlu pemeriksaan timestamp dan firmware/penjadwalan aktual sebelum menyimpulkan lama fase dalam detik. B39 mendekati pola 50+5 dalam jumlah baris. Jangan mengubah isi CSV, memalsukan fase, atau menyatakan empat file B40 sebagai data protokol 50+5 yang valid.

B40 memiliki **40 run** dari `run_id=1..40`. Skema CSV tidak homogen: kolom `datetime` muncul pada BASELINE B40, D-MING B40, dan M-MING B40, namun tidak pada L-MING B40. Tidak boleh langsung dicampur dengan pipeline canonical 5 siklus (B32–B35) tanpa kontrak baru dan QA detail.

Semua file berada dalam status **data mentah untuk audit**, bukan uji blind independen, bukan izin melatih atau mempromosikan model. Verifikasi lot, spesimen, label dan sesi tetap diperlukan.
