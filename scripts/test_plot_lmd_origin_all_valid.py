"""QA for all-batch strict audit, unique-batch eligibility and LMD 120 PNG."""
from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path

from merge_new_30_siklus_audit import checksum
from plot_lmd_origin_merged_all_valid import (
    OUT, SRC, ROASTS, read_and_audit, choose_groups,
    build_measurements, compute_comparison,
)


def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    candidates,provenance,issues=read_and_audit(SRC)
    matrix,eligible,selected,conflicts=choose_groups(candidates,provenance)
    assert len(provenance)==len(list(SRC.glob('*.csv')))==112
    assert len(issues)==0
    assert len(candidates)==112, 'All 112 valid source CSVs must be eligible candidates'
    assert eligible==['CAT','GAW','GRB','MING','TEM','TOR']
    assert len(conflicts)==2
    assert len(selected)==6
    assert len([r for v in selected.values() for r in v])==93
    assert next(x for x in matrix if x['origin']=='MING')['light_valid_batch']==5
    assert any(r['filename']=='L-MING_B69.csv' for r in selected['MING'])
    for origin,entries in selected.items():
        assert all(r['batch_number']>=0 for r in entries)
        assert len(set((r['level'],r['batch_id']) for r in entries))==len(entries)
        assert all(sum(r['level']==level for r in entries)>=5 for level in ROASTS)
        assert len(set(r['sha256'] for r in entries))==len(entries)
        assert len(set(r['signal_sha256'] for r in entries))==len(entries)
    anchors,metrics=build_measurements(selected)
    assert len(anchors)==93*10 and len(metrics)==93*10
    assert all(x['delta_adc_at_t0']==0 and x['t0_index_zero_based']==24
               for x in anchors)
    assert len(compute_comparison(metrics))==6*10

    assert OUT.is_dir()
    summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    assert summary['input_candidates_valid_all_batches']==112
    assert 'no maximum or minimum cutoff' in summary['batch_policy']
    index=rows(OUT/'plot_index.csv')
    p=rows(OUT/'input_provenance.csv')
    a=rows(OUT/'baseline_t0_per_sensor.csv')
    assert len(index)==summary['total_plots']==120
    assert len(list(OUT.rglob('*.png')))==120
    assert len(a)==930
    assert len(p)==112
    assert set(x['origin'] for x in index)==set(eligible)
    assert Counter(x['mode'] for x in index)=={'RAW':60,'T0NORM':60}
    assert len(set(x['plot_path'] for x in index))==120
    assert all(Path(x['plot_path']).is_file() and Path(x['plot_path']).stat().st_size>10000 for x in index)
    assert all(checksum(Path(x['source_path']))==x['sha256'] for x in p)
    assert sum('L-MING_B69.csv' in x['inputs'] for x in index)==20
    assert (OUT/'GALERI_LMD_MERGE.html').is_file()
    assert len(rows(OUT/'sensor_separation_diagnostics.csv'))==60
    print('LMD_ALL_BATCH_QA_PASS: 112 audited, 6 eligible origins, 93 unique-batch CSV, 120 PNG, 930 t0 anchors')


if __name__=='__main__':
    main()
