# Provenance terkoreksi — Tahap 2 v2, 9 Oktober 2026

**Konfirmasi operator 9 Oktober 2026:** semua `sample_id` berakhiran `-CAW`
dan seluruh batch `B37` adalah **udara bersih**, bukan origin/roast kopi.
Empat CSV CAW B33–B35 serta dua CSV B37 dicatat di
`data/analysis/bench_only_exclusions.csv` dengan nama dan SHA256.
Entri ini **tidak diubah label/raw-nya**, hanya status kelayakan ML.

Regenerasi snapshot:

    python scripts/stage2_dataset_audit.py --output-dir data/analysis/stage2_v3

Ringkasan v2: 89 CSV final B32+ terinventarisasi; **83** kandidat berlabel kopi
yang masih **belum dibuktikan identitas spesimen/roasting fisiknya**, **6** CSV
udara bersih, dan total 87 file dalam B32–B35 lulus validator struktur.
Kandidat berlabel: dark 28, light 28, medium 27.

`data/analysis/stage2/` adalah **snapshot historis pra-koreksi CAW**,
tidak boleh lagi dipakai untuk melatih/menguji kopi. Tahap 3 menggunakan
`stage2_v2/file_manifest.csv` dengan hash yang dikunci.
