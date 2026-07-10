import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import os

try:
    from micromlgen import port
except ImportError:
    print("⚠️ micromlgen belum terinstall.")
    print("Silakan buka terminal dan ketik: pip install micromlgen scikit-learn pandas")
    exit()

# Konfigurasi path
DATA_CSV = '../data/dataset_fitur.csv'
OUTPUT_HEADER = '../include/model_rf.h'

def train_and_export():
    if not os.path.exists(DATA_CSV):
        print(f"❌ File {DATA_CSV} tidak ditemukan.")
        print("Silakan jalankan 'python 1_ekstraksi_fitur.py' terlebih dahulu.")
        return

    # 1. Load Data
    df = pd.read_csv(DATA_CSV)
    print("✅ Data Load Sukses. Distribusi kelas:")
    print(df['label'].value_counts())
    print("-" * 30)

    # 2. Pisahkan Fitur (X) dan Label (y)
    # Ambil semua kolom yang berakhiran '_max'
    feature_cols = [col for col in df.columns if col.endswith('_max')]
    X = df[feature_cols]
    y = df['label']

    # Jika dataset terlalu kecil (awal eksperimen), kita train tanpa displit agar model bisa belajar
    if len(df) > 5:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    else:
        print("⚠️ Dataset sangat kecil, menggunakan seluruh data untuk training (tanpa testing split).")
        X_train, X_test, y_train, y_test = X, X, y, y

    # 3. Train Random Forest Classifier
    print("⚙️ Melatih model Random Forest...")
    # Parameter n_estimators & max_depth diset kecil agar modelnya sangat ringan di RAM ESP32
    clf = RandomForestClassifier(n_estimators=15, max_depth=5, random_state=42)
    clf.fit(X_train, y_train)

    # 4. Evaluasi Akurasi
    if len(df) > 5:
        y_pred = clf.predict(X_test)
        print("\n📊 === Hasil Evaluasi ===")
        print(f"Akurasi: {accuracy_score(y_test, y_pred) * 100:.2f}%")
        print(classification_report(y_test, y_pred))

    # 5. Konversi Model AI Python ke Kode C (Header)
    print("\n🔄 Mengubah model Random Forest ke sintaks C++...")
    c_code = port(clf)
    
    # 6. Simpan File ke folder include/
    with open(OUTPUT_HEADER, 'w') as f:
        f.write(c_code)
        
    print(f"\n🎉 SUKSES! Model tersimpan di: {OUTPUT_HEADER}")
    print("   Langkah selanjutnya:")
    print("   1. Buka src/main.cpp")
    print("   2. Tambahkan: #include \"model_rf.h\"")
    print("   3. Untuk mendeteksi, panggil: predict(array_nilai_sensor)")

if __name__ == "__main__":
    train_and_export()
