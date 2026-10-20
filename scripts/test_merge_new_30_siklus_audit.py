"""Offline fixtures: safe merge, mislabeled archival data, hash duplicates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from audit_dataset_30_siklus import FOLDERS
from merge_new_30_siklus_audit import merge,checksum
from test_acquisition_integrity import make_complete_run


def make_csv(df, path:Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(path,index=False)


def old_entry(p:Path,folder:Path,category:str,filename:str,sample:str='D-GAW',batch:str='B60'):
    file=folder/FOLDERS[category]/filename
    make_csv(p,file)
    return {'filename':filename,'sha256':checksum(file),'category':category,
            'sample_ids':sample,'batch_ids':batch,'roast_levels':'dark',
            'rows':len(p),'anomalies':[]}


def main():
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        old=root/'old';old.mkdir()
        new=root/'new';new.mkdir()
        valid=make_complete_run(30)
        valid['batch_id']='B60'
        misplaced=valid.copy()
        misplaced['batch_id']='B62'
        misplaced['adc_tgs822']+=25
        old_manifest=[
            old_entry(valid,old,'VALID','D-GAW_B60.csv'),
            old_entry(misplaced,old,'METADATA','D-GAW_B67.csv',batch='B62'),
        ]
        (old/'audit_manifest.json').write_text(json.dumps({
            'total_csv':len(old_manifest),'files':old_manifest,
        }),encoding='utf-8')
        changed=valid.copy();changed['adc_tgs822']+=100
        make_csv(changed,new/'D-GAW_B60.csv')  # collides by name, not bytes
        make_csv(misplaced,new/'D-GAW_B62.csv') # valid corrected metadata
        make_csv(valid,new/'D-GAW_B60_20261021.csv') # exact old valid
        one_more=valid.copy();one_more['batch_id']='B65';one_more['adc_tgs822']+=200
        make_csv(one_more,new/'D-GAW_B65.csv')
        incomplete=valid.drop(index=[103]).copy();incomplete['batch_id']='B64'
        make_csv(incomplete,new/'D-GAW_B64_A_INCOMPLETE.csv')
        make_csv(incomplete,new/'D-GAW_B64_B_INCOMPLETE.csv')
        all_sources=list(old.rglob('*.csv'))+list(new.glob('*.csv'))
        old_hashes={str(p):checksum(p) for p in all_sources}
        result=merge(new,old,old/'MERGE_CHECK')
        assert result['old_audit_csv']==2
        assert result['new_csv_audited']==6
        assert result['new_structural_pass']==4
        assert result['new_structural_fail']==2
        assert result['new_unique_valid_added']==3
        assert result['new_unique_incomplete_added']==1
        assert result['new_duplicates_quarantined']==2
        assert result['merged_valid_unique_recordings']==4
        assert result['merged_invalid_quarantined']==2
        assert len(result['filename_collisions_resolved'])==1
        out=old/'MERGE_CHECK'
        assert len(list((out/'01_VALID_GABUNGAN').glob('*.csv')))==4
        assert len(list((out/'02_INCOMPLETE_DAN_ANOMALI').rglob('*.csv')))==2
        assert len(list((out/'03_DUPLIKAT_BARU_TIDAK_DIGABUNG').glob('*.csv')))==2
        assert any(p.name.startswith('D-GAW_B60__NEW_') for p in
                   (out/'01_VALID_GABUNGAN').glob('*.csv'))
        assert old_hashes=={str(p):checksum(p) for p in all_sources}
        try:
            merge(new,old,out)
        except FileExistsError:
            pass
        else:
            raise AssertionError('Accidental overwrite was allowed')
    print('MERGE_NEW_30C_ARCHIVE_FIXTURE_HASH_DUPLICATE_FILENAME_COLLISION_PASS')


if __name__=='__main__':
    main()
