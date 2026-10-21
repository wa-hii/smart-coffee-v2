"""QA for all-input strict audit, unique-batch eligibility and LMD 100 PNG."""
from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path

from merge_new_30_siklus_audit import checksum
from plot_lmd_origin_merged_b60_b68 import (
    OUT, SRC, ORIGINS, ROASTS, read_and_audit, choose_groups,
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
    assert len(candidates)==111, 'B69 should be excluded'
    assert eligible==['GAW','GRB','TEM','CAT','TOR']
    assert len(conflicts)==2
    assert len(selected)==5
    assert len([r for v in selected.values() for r in v])==78
    assert next(x for x in matrix if x['origin']=='MING')['light_valid_batch']==4
    for origin,entries in selected.items():
        assert all(60<=r['batch_number']<=68 for r in entries)
        assert len(set((r['level'],r['batch_id']) for r in entries))==len(entries)
        assert all(sum(r['level']==level for r in entries)>=5 for level in ROASTS)
        assert len(set(r['sha256'] for r in entries))==len(entries)
        assert len(set(r['signal_sha256'] for r in entries))==len(entries)
    anchors,metrics=build_measurements(selected)
    assert len(anchors)==78*10 and len(metrics)==78*10
    assert all(x['delta_adc_at_t0']==0 and x['t0_index_zero_based']==24
               for x in anchors)
    assert len(compute_comparison(metrics))==5*10

    assert OUT.is_dir()
    summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    index=rows(OUT/'plot_index.csv')
    p=rows(OUT/'input_provenance.csv')
    a=rows(OUT/'baseline_t0_per_sensor.csv')
    assert len(index)==summary['total_plots']==100
    assert len(list(OUT.rglob('*.png')))==100
    assert len(a)==780
    assert len(p)==112
    assert set(x['origin'] for x in index)==set(eligible)
    assert Counter(x['mode'] for x in index)=={'RAW':50,'T0NORM':50}
    assert len(set(x['plot_path'] for x in index))==100
    assert all(Path(x['plot_path']).is_file() and Path(x['plot_path']).stat().st_size>10000 for x in index)
    assert all(checksum(Path(x['source_path']))==x['sha256'] for x in p)
    assert all('B69.csv' not in x['inputs'] for x in index)
    assert (OUT/'GALERI_LMD_MERGE.html').is_file()
    assert len(rows(OUT/'sensor_separation_diagnostics.csv'))==50
    print('LMD_B60_B68_QA_PASS: 112 audited, 5 eligible origins, 78 unique-batch CSV, 100 PNG, 780 t0 anchors')


if __name__=='__main__':
    main()
