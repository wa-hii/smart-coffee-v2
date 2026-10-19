"""Offline regression for non-destructive 30-cycle dataset sorting."""
from __future__ import annotations
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import pandas as pd

from audit_dataset_30_siklus import do_audit, FOLDERS
from test_acquisition_integrity import make_complete_run


def main():
    with TemporaryDirectory() as tmp:
        source = Path(tmp)/'data 30 siklus'
        source.mkdir()
        good = make_complete_run(30)
        good['sample_id'] = 'D-GAW'
        good['batch_id'] = 'B60'
        good.to_csv(source/'D-GAW_B60.csv',index=False)
        good.to_csv(source/'D-GAW_B67.csv',index=False)
        mislabeled = good.assign(batch_id='B60').copy()
        mislabeled['adc_tgs822'] += 1
        mislabeled.to_csv(source/'D-GAW_B66.csv',index=False)
        damaged = good.drop(index=[28])
        damaged.to_csv(source/'D-GAW_B61_INCOMPLETE.csv',index=False)
        wrong_phase = good.copy()
        wrong_phase.loc[25,'phase'] = 'purging'
        wrong_phase.loc[25,'sample_idx'] = 26
        wrong_phase.to_csv(source/'D-GAW_B62.csv',index=False)
        baseline = good.assign(sample_id='BASELINE',roast_level='',origin='')
        baseline.to_csv(source/'BASELINE_B60.csv',index=False)
        before = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.csv')}
        dry = do_audit(source,None,False)
        assert len(list(source.iterdir())) == 6, 'Dry run modified input'
        assert dry['categories']['VALID'] == 1
        assert dry['categories']['DUPLICATE'] == 1
        assert dry['categories']['INCOMPLETE'] == 1
        assert dry['categories']['PHASE_OR_TIMING'] == 1
        assert dry['categories']['METADATA'] == 1
        assert dry['categories']['BASELINE_OR_UNKNOWN'] == 1
        output = source/'HASIL_AUDIT_TEST'
        written = do_audit(source,output,True)
        assert written['total_csv'] == 6
        assert (output/'AUDIT_DETAIL_PER_SIKLUS.csv').exists()
        assert (output/'AUDIT_REKAP_PER_FILE.csv').exists()
        assert (output/'README_HASIL_AUDIT.md').exists()
        assert sum(len(list((output/folder).glob('*.csv'))) for folder in FOLDERS.values()
                   if (output/folder).exists()) == 6
        # Idempotent, no replacement of existing classified copies.
        do_audit(source,output,True)
        after = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.csv')}
        assert before == after, 'Source CSV modified by audit'
    print('AUDIT_30_SIKLUS_CLASSIFICATION_NO_SOURCE_MUTATION_PASS')


if __name__ == '__main__':
    main()
