# Fitur Tahap 3 v2 — cohort kopi setelah pengecualian CAW

**Input canonical untuk benchmark Tahap 4:** 83 file B32–B35, dengan CAW dan
B37 dikecualikan. Semua 83 file lolos kontrak fitur ketat; tidak ada file
`HOLD` dalam cohort ini. Fitur `legacy62` dan `expanded82` beserta
tujuh grup a priori tersedia pada `feature_groups.json`.

    python scripts/stage3_feature_pipeline.py --manifest data/analysis/stage2_v2/file_manifest.csv --output-dir data/processed/stage3_v3

Status: **FITUR KANDIDAT**, bukan label spesimen/roast terverifikasi dan bukan
model. Jangan gunakan `stage3_v1` (historis; mengandung tiga CAW yang
sekarang diketahui sebagai udara bersih). `snapshot.json` menyimpan hash
manifest dan daftar file beserta SHA256. Batch minimal adalah unit grup untuk
evaluasi; identitas spesimen/hari masih belum tersedia.
