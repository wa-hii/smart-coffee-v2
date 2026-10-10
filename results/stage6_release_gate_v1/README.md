# Gerbang Tahap 6 — NO-GO yang dapat diuji

Evaluasi lokal Tahap 5 dan benchmark eksternal dari Zenodo **bukan**
dasar valid untuk otomatis menerbitkan model. Berkas `decision.json`
disusun oleh:

    python scripts/test_stage6_release_gate.py
    python scripts/stage6_release_gate.py --output results/stage6_release_gate_v2/decision.json

Keputusan saat ini: `model_promotion_allowed=false`, status
`NO_GO_PENDING_LOCAL_VALIDATION`, dan hasil default AI_TEST = `N/A`.
Gerbang ini tidak mengakses hardware, tidak menyentuh COM5,
tidak menulis model artefak dan tidak melatih ulang.

Gerbang bukan prosedur pengecualian yang dapat di-bypass hanya dengan
mengganti suatu angka confidence; syarat model final dan validasi
prospektif tercantum sebagai blocker eksplisit dalam keputusan.
