import pandas as pd, os, glob

data_dir = r'd:\ENOSE\smart-coffee-v2-hardware\smart-coffee-v2-hardware\data'
files = sorted(glob.glob(os.path.join(data_dir, '*_B*.csv')))
print(f'Total standardized CSVs: {len(files)}')
print()
for f in files[:4]:
    df = pd.read_csv(f)
    fn = os.path.basename(f)
    print(f'=== {fn} ===')
    print(f'  Columns : {list(df.columns)}')
    print(f'  Rows    : {len(df)}')
    if 'phase' in df.columns:
        print(f'  Phases  : {df["phase"].value_counts().to_dict()}')
    if 'run_id' in df.columns:
        print(f'  Runs    : {sorted(df["run_id"].unique())}')
    if 'sample_id' in df.columns:
        print(f'  sample_id: {df["sample_id"].iloc[0]}')
    if 'roast_level' in df.columns:
        print(f'  roast_level: {df["roast_level"].iloc[0]}')
    print()
