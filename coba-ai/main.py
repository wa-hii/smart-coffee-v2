"""
main.py
--------
Entry point pipeline RoastSense - Random Forest.

Cara pakai:
    python main.py --data_dir data --model_dir models --output_dir outputs

Pipeline:
    1. Load semua file .txt dari data/AQ_Coffee, data/HQ_Coffee, data/LQ_Coffee
    2. Ekstraksi fitur statistik dari 8 sensor
    3. Training Random Forest untuk klasifikasi kualitas/cacat mutu kopi
       (Adulterated Quality / High Quality / Low Quality)
    4. Evaluasi model (classification report, confusion matrix, feature importance)
"""

import argparse
from src.data_loader import load_dataset, QUALITY_LABEL_MAP
from src.feature_extraction import extract_features
from src.train_model import train_random_forest
from src.evaluate_model import evaluate


def main():
    parser = argparse.ArgumentParser(description="RoastSense Random Forest Pipeline - Quality Classification")
    parser.add_argument("--data_dir", default="data", help="Folder utama dataset")
    parser.add_argument("--model_dir", default="models", help="Folder simpan model")
    parser.add_argument("--output_dir", default="outputs", help="Folder simpan hasil evaluasi")
    parser.add_argument("--test_size", type=float, default=0.2)
    parser.add_argument("--no_grid_search", action="store_true",
                         help="Matikan GridSearchCV (pakai kalau data sedikit / mau cepat)")
    args = parser.parse_args()

    print("=== 1. Load dataset ===")
    records = load_dataset(args.data_dir, label_map=QUALITY_LABEL_MAP)

    print("\n=== 2. Ekstraksi fitur ===")
    df = extract_features(records)
    print(df["quality_label"].value_counts())

    print("\n=== 3. Training Random Forest (kualitas/cacat mutu) ===")
    result = train_random_forest(
        df, model_dir=args.model_dir, test_size=args.test_size,
        use_grid_search=not args.no_grid_search
    )

    print("\n=== 4. Evaluasi model ===")
    evaluate(result, output_dir=args.output_dir)

    print("\nSelesai. Model tersimpan di:", args.model_dir)
    print("Hasil evaluasi & plot tersimpan di:", args.output_dir)


if __name__ == "__main__":
    main()
