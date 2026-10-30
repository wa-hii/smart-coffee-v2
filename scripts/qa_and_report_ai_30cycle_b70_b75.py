"""Reproducibility checks, diagnostics and research interpretation of B70..B75."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix,recall_score

from merge_30cycle_b70_b75_provenance import OUT as MERGED, checksum
from model_30cycle_b70_b75_global_zscore import (
    OUT,CLASSES,LOCAL,metric,train_cv,estimator)

ROOT=Path(__file__).resolve().parents[1]
DRIFT=ROOT/'results/combined_drift_B70_B75_20261031'
FIXED_AUDIT_SENSORS=['adc_tgs822','adc_tgs2602','adc_tgs816']


def run():
    assert OUT.is_dir() and MERGED.is_dir()
    prov=pd.read_csv(MERGED/'accepted_provenance.csv')
    rejected=pd.read_csv(MERGED/'quarantined_records.csv')
    feats=pd.read_csv(OUT/'features_per_recording.csv')
    ranks=pd.read_csv(OUT/'sensor_ranking_train_cv_and_new_test.csv')
    results=pd.read_csv(OUT/'model_comparison_traincv_newtest.csv')
    desc=pd.read_csv(OUT/'sensor_drift_quality_old_vs_new.csv')
    scale=pd.read_csv(OUT/'global_zscore_mu_sigma_from_training.csv')
    preds=pd.read_csv(OUT/'new_test_predictions.csv')
    summary=json.loads((MERGED/'summary.json').read_text(encoding='utf8'))
    assert (len(prov),len(rejected),len(feats))==(233,5,231)
    assert len(ranks)==10 and ranks.sensor.nunique()==10
    assert summary['independent_origin_roast_batch_unique']==231
    assert all(checksum(Path(r.source_path))==r.sha256 for r in prov.itertuples())
    assert all(checksum(MERGED/'01_VALID_GABUNGAN'/r.filename)==r.sha256 for r in prov.itertuples())
    assert all(rejected.filename.str.contains('INCOMPLETE',case=False))
    train=feats[(feats.source_type=='previous_audit')&feats.origin.isin(['CAT','GAW','GRB','MING','TEM','TOR'])].copy()
    test=feats[(feats.source_type=='B70_B75')&feats.origin.isin(['CAT','GAW','GRB','MING','TEM','TOR'])].copy()
    assert len(train)==93 and len(test)==103
    assert set(train.filename).isdisjoint(test.filename)
    assert not train.duplicated(['origin','roast','batch']).any()
    assert not test.duplicated(['origin','roast','batch']).any()
    # Check global scaling reference for the full, no-PCA, local baseline pipeline.
    local_ref=scale[(scale.feature_set=='ALL10_local_baseline')&(scale.model=='LogReg_L2')]
    for row in local_ref.itertuples():
        assert abs(row.train_global_mu-train[row.feature].mean())<1e-7
        assert abs(row.train_global_sigma-train[row.feature].std(ddof=0))<1e-7 or (
           row.train_global_sigma==1 and train[row.feature].std(ddof=0)==0)
    # No single device sampled all three roast levels for every coffee origin:
    # device is a confounder; compute explicit table.
    mapping=test.groupby(['origin','roast','device_id']).size().reset_index(name='n')
    classes_per_device=(test.groupby(['origin','device_id']).roast.nunique()
                        .rename('n_roasting_classes').reset_index())
    mapping.to_csv(OUT/'new_device_origin_roast_distribution.csv',index=False,encoding='utf-8-sig')
    classes_per_device.to_csv(OUT/'new_device_origin_class_coverage.csv',index=False,encoding='utf-8-sig')

    fixed_cols=[f'{f}__{sensor}' for sensor in FIXED_AUDIT_SENSORS for f in LOCAL]
    comparison=[]
    for name in ['LogReg_L2','SVM_RBF','RandomForest']:
        cv=train_cv(train,fixed_cols,name)
        model=estimator(name).fit(train[fixed_cols],train.roast)
        predict=model.predict(test[fixed_cols])
        new=metric(test.roast,predict)
        rec=recall_score(test.roast,predict,labels=CLASSES,average=None,zero_division=0)
        comparison.append({'feature_set':'PREAUDIT3_TGS822_TGS2602_TGS816_local',
            'model':name,'train_origin_cv_balanced_accuracy':cv['balanced_accuracy'],
            'train_origin_cv_macro_f1':cv['macro_f1'],
            'new_batch_test_balanced_accuracy':new['balanced_accuracy'],
            'new_batch_test_macro_f1':new['macro_f1'],
            'recall_light':float(rec[0]),'recall_medium':float(rec[1]),'recall_dark':float(rec[2]),
            'new_test_confusion_matrix':json.dumps(confusion_matrix(test.roast,predict,labels=CLASSES).tolist())})
    pd.DataFrame(comparison).to_csv(OUT/'preaudit_fixed_3sensor_control.csv',index=False,encoding='utf-8-sig')

    recall=[]
    for (feat,model),group in preds.groupby(['feature_set','model']):
        vals=recall_score(group.roast_actual,group.roast_predicted,labels=CLASSES,average=None,zero_division=0)
        recall.append({'feature_set':feat,'model':model,
                       'recall_light':float(vals[0]),'recall_medium':float(vals[1]),'recall_dark':float(vals[2]),
                       'all_three_class_predicted':len(set(group.roast_predicted))==3})
    pd.DataFrame(recall).to_csv(OUT/'new_test_per_class_recall.csv',index=False,encoding='utf-8-sig')
    top=results.sort_values('train_origin_cv_balanced_accuracy',ascending=False).iloc[0]
    top3=results[(results.feature_set=='TOP3_local_baseline')&(results.model=='LogReg_L2')].iloc[0]
    raw=results[(results.feature_set=='ALL10_raw_ADC')&(results.model=='LogReg_L2')].iloc[0]
    tem=desc[(desc.source_type=='B70_B75')&(desc.sensor=='adc_tgs822')].iloc[0]
    # Display two rank orders with truthful non-selected new-test comparison.
    display=ranks[['sensor','rank_train_cv','train_cv_balanced_accuracy','new_batch_test_balanced_accuracy','new_batch_test_macro_f1']].copy()
    display['median_drift_over_response_new']=display.sensor.map(
        desc[desc.source_type=='B70_B75'].set_index('sensor').median_drift_over_response)
    display.to_csv(OUT/'sensor_ranking_with_drift_combined.csv',index=False,encoding='utf-8-sig')

    lines=['# Smart Coffee E-Nose — gabungan B70–B75 dan screening model AI','',
        '## 1. Penggabungan dan QC','',
        '- Arsip lama: **112 CSV** valid; B70–B75: **126 CSV**, dengan **121 valid dan 5 incomplete**.',
        '- Total **233 CSV valid** dari 238 input, **231 rekaman dengan kombinasi origin–roast–batch unik**.',
        '- Lima incomplete: '+', '.join('`'+v+'`' for v in rejected.filename.tolist())+'.',
        '- Semua 5 incomplete berjumlah 888–893 titik; jangan membuat sampel 900 titik sintetis dengan interpolasi. '
         'Periksa sambungan receiver/USB, loss frame dan validasi index sebelum mengulang.',
        '- Dua rekaman lama dengan ID origin–roast–batch yang sama tetap ada di arsip tetapi tidak dianggap pengulangan independen.',
        '', '## 2. Preprocessing yang diuji', '',
        '1. Validasi per CSV: 900 baris, 30 siklus, urutan purging 25 detik dan collecting 5 detik, metadata dan hash.',
        '2. Baseline lokal **di setiap siklus** dan sensor: median ADC purging sampel 21–25. '
        'Collecting dikoreksi dengan mengurangi baseline tersebut dari lima pembacaan ADC saat collecting.',
        '3. Ringkas 30 siklus menjadi fitur satu rekaman: median respons, IQR, slope tren antarsiklus, '
        'median amplitudo puncak relatif baseline, median slope lima titik collecting.',
        '4. Pisahkan **training 93 rekaman lama** dan **testing 103 rekaman baru B70–B75**, hanya enam origin yang '
        'masing-masing mempunyai ketiga roasting (CAT, GAW, GRB, MING, TEM, TOR). '
        'RAT/GAY/MUK tetap terarsip namun tidak dijadikan label kelas roasting lintas-origin.',
        '5. **Global Z-score**: setiap fitur memakai μ dan σ dari 93 rekaman training untuk semua kelas bersama-sama. '
        'Tidak melakukan fit ulang pada testing, tidak menghitung Z-score terpisah per roasting atau CSV.',
        '6. Ranking sensor dihitung menggunakan **leave-one-origin-out CV dari training saja** dengan Logistic Regression L2 '
        '(fit scaler setiap fold). Model gabungan dibandingkan pada B70–B75 yang tidak dipakai untuk memilih sensor.',
        '', '## 3. Ranking sensor', '',
        '| Ranking CV lama | Sensor | Balanced accuracy CV training | Balanced accuracy batch baru | Drift/respons median batch baru |',
        '|---:|---|---:|---:|---:|']
    for r in display.itertuples():
        lines.append(f'| {r.rank_train_cv} | {r.sensor.removeprefix("adc_").upper()} | '
                     f'{r.train_cv_balanced_accuracy*100:.1f}% | '
                     f'{r.new_batch_test_balanced_accuracy*100:.1f}% | '
                     f'{r.median_drift_over_response_new:.2f} |')
    lines += ['', '**Penting:** urutan pada tabel adalah ranking **di training**. '
              'Skor pada kolom testing adalah pemeriksaan generalisasi, bukan kriteria seleksi sensor. '
              'Ranking dari batch lama tidak selalu konsisten dengan batch baru.',
              '', '## 4. Akurasi dan pemilihan metode', '',
              f'- Kombinasi dengan CV training tertinggi adalah `{top.feature_set}` + `{top.model}` '
              f'({100*top.train_origin_cv_balanced_accuracy:.1f}% CV), tetapi pada batch baru hanya '
              f'{100*top.new_batch_test_balanced_accuracy:.1f}% balanced accuracy.',
              f'- Pendekatan sederhana 3 sensor peringkat teratas + Logistic Regression: '
              f'{100*top3.train_origin_cv_balanced_accuracy:.1f}% CV training, '
              f'{100*top3.new_batch_test_balanced_accuracy:.1f}% testing. '
              '**Model ini tidak memprediksi satu pun Dark** di batch baru, sehingga skor keseluruhan menyesatkan jika dibaca sendirian.',
              f'- Perbandingan raw ADC + Logistic Regression turun dari '
              f'{100*raw.train_origin_cv_balanced_accuracy:.1f}% CV ke '
              f'{100*raw.new_batch_test_balanced_accuracy:.1f}% testing. '
              'Ini konsisten dengan potensi pergeseran distribusi/alat/sesi.',
              '- Fitur t0-only dan suhu/RH-only tidak secara konsisten meningkatkan generalisasi; '
              'tetap gunakan sebagai *negative control* untuk melihat model yang memakai informasi perancu.',
              '', '### Uji kontrol sensor terpilih sebelum B70–B75', '',
              'TGS822, TGS2602, TGS816 telah diusulkan dari audit drift sebelum tambahan B70–B75. '
              'Hasilnya disimpan dalam `preaudit_fixed_3sensor_control.csv` agar pilihan yang sudah ada '
              'tidak disamakan dengan pilihan berdasarkan test set.',
              '', '## 5. Drift dan kondisi alat', '',
              f'- Pada dataset B70–B75, sensor TGS822 mempunyai median drift/respons {tem.median_drift_over_response:.2f}; '
              'ini lebih rendah daripada sebagian besar sensor lain, tetapi **bukan bukti klasifikasi paling baik**.',
              '- `ALAT_1/2/3` kini tersedia dari `.quality.json` untuk B70–B75; perangkat pada dataset lama '
              'tidak tercatat, sehingga tidak bisa dipastikan train dan test berasal dari domain alat yang sama.',
              '- Pada banyak origin, kelas Light/Medium/Dark dibagi antarperangkat secara tidak seimbang. '
              'Penting mengulang **setiap level roasting di setiap perangkat**, bukan satu level per alat.',
              '- Outlier dan drift bukan otomatis kegagalan sensor; perlu uji blank clean-air, persiapan spesimen '
              'terpisah, urutan sampel acak, serta log suhu dan RH.',
              '', '## 6. Keputusan metode dan roadmap', '',
              '1. **Belum deploy model AI final.** Data baru membuktikan generalisasi masih rendah dan '
              'beberapa model gagal memprediksi seluruh kelas.',
              '2. Prioritaskan **baseline lokal per siklus → fitur level rekaman → global Z-score yang di-fit hanya pada training → '
              'Logistic Regression L2** sebagai baseline mudah diaudit; bandingkan SVM dan Random Forest.',
              '3. Untuk pemilihan hardware dan rencana dataset, **TGS822, TGS2602 dan TGS816** layak menjadi kandidat '
              'fisik yang lebih stabil berdasarkan respons/drift; MQ8 dan TGS2611 tetap diuji secara terkontrol '
              'karena performa CV lama tidak cukup stabil saat diuji pada batch baru.',
              '4. Rekam data baru dengan desain faktorial **origin × roast × device**, minimal lima persiapan kopi '
              'independen tiap sel yang memungkinkan, dengan `device_id`, `preparation_id`, `run_id`, '
              '`roast_date`, berat, suhu/RH, operator dan jam absolut.',
              '5. Evaluasi melalui *held-out device/session/batch cohort*, lalu nested CV untuk memilih hiperparameter, '
              'jumlah fitur dan PCA. Jangan memilih fitur dengan skor set B70–B75 lalu mengklaim skor yang sama '
              'sebagai estimasi performa unbiased.',
              '', '## 7. Berkas audit', '',
              '- `../combined_30cycle_B70_B75_20261031/` — CSV gabungan, manifest dan karantina.',
              '- `../combined_drift_B70_B75_20261031/` — drift, variasi dan per-record flags.',
              '- `features_per_recording.csv` — tabel fitur setelah baseline correction per siklus.',
              '- `global_zscore_mu_sigma_from_training.csv` — parameter scaler global untuk training.',
              '- `sensor_ranking_train_cv_and_new_test.csv` — ranking sepuluh sensor dan holdout.',
              '- `model_comparison_traincv_newtest.csv` — model, prepro pembanding dan confusion matrix.',
              '- `new_test_per_class_recall.csv` — recall Light, Medium, Dark untuk setiap pipeline.',
              '- `new_device_origin_roast_distribution.csv` — confounding device × origin × roast.',
              '', '**Batas hasil:** skor bukan kinerja klasifikasi produksi; batch berbeda belum membuktikan '
              'spesimen independen, dan data lama tidak memiliki device_id.', '']
    (OUT/'ANALISIS_DAN_REKOMENDASI.md').write_text('\n'.join(lines),encoding='utf8')
    print('QA_PASS',json.dumps({'valid':len(prov),'train':len(train),'test':len(test),
                                'rejected':len(rejected),'top3_prior':FIXED_AUDIT_SENSORS,
                                'device_by_roast':mapping.to_dict('records')[:5],
                                'preaudit_results':comparison},ensure_ascii=True),flush=True)


if __name__=='__main__':run()
