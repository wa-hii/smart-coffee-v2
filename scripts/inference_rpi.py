#!/usr/bin/env python3
"""
inference_rpi.py — AI Inference untuk Raspberry Pi

Karakteristik Raspberry Pi:
  - RAM: 1-8 GB (melimpah!)
  - CPU: ARM 1.5+ GHz (cukup untuk RF)
  - Storage: MicroSD card (umumnya 32 GB+)
  - OS: Linux (Raspbian/Ubuntu)
  - Python: 3.7+

Fitur:
  1. Load model Random Forest dari pickle/joblib
  2. Akumulasi fitur dari data sensor (mean + max)
  3. Real-time inference dan logging
  4. Integration dengan MQTT/HTTP untuk remote monitoring
  5. Support multiple input modes:
     - Serial (dari Arduino/ESP32)
     - File CSV
     - Direct Python function call

Instalasi:
    pip install scikit-learn pandas numpy joblib

Contoh penggunaan:
    from inference_rpi import InferenceRPi
    
    inf = InferenceRPi()
    inf.load_model('model_rf.joblib')
    
    # Mode 1: Akumulasi dari array ADC
    inf.reset()
    for cycle in range(10):
        adc_values = [sensor.read() for sensor in sensors]
        inf.accumulate(adc_values)
    result = inf.predict()
    print(result['label'])  # "light" / "medium" / "dark"
    
    # Mode 2: Load dari CSV dan batch predict
    results = inf.predict_batch('data.csv')
    for row in results:
        print(f"{row['label']}: {row['confidence']:.2%}")
"""

import os
import sys
import json
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
import numpy as np

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import joblib
    HAS_JOBLIB = True
except ImportError:
    HAS_JOBLIB = False

try:
    from sklearn.ensemble import RandomForestClassifier
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Konfigurasi
NUM_SENSORS = 8
NUM_CLASSES = 3
CLASS_LABELS = ["dark", "light", "medium"]  # Urutan sesuai LabelEncoder dari training
ADC_COLS = [
    'adc_mq135', 'adc_mq136', 'adc_mq137', 'adc_mq138',
    'adc_mq2', 'adc_mq3', 'adc_tgs822', 'adc_tgs2620'
]


@dataclass
class InferenceResult:
    """Hasil dari inference"""
    class_id: int          # 0=dark, 1=light, 2=medium (-1 jika error)
    label: str             # "dark", "light", "medium", atau "N/A"
    confidence: float      # 0.0-1.0
    sample_count: int      # Jumlah sampel yang digunakan
    features: Optional[List[float]] = None  # Fitur yang digunakan (optional)
    
    def to_dict(self) -> Dict:
        """Konversi ke dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Konversi ke JSON string"""
        d = self.to_dict()
        d['features'] = d.get('features', [])[:4] + ['...']  # Potong untuk readability
        return json.dumps(d, indent=2)


class InferenceRPi:
    """Inference engine untuk Raspberry Pi"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Inisialisasi inference engine
        
        Args:
            model_path: Path ke model (pickle/joblib). Jika None, load dari default.
        """
        self.model = None
        self.feature_cols = None
        self.encoder = None
        
        # Akumulasi fitur
        self.adc_sum = np.zeros(NUM_SENSORS, dtype=np.float64)
        self.adc_max = np.zeros(NUM_SENSORS, dtype=np.uint16)
        self.sample_count = 0
        
        if model_path:
            self.load_model(model_path)
        else:
            logger.warning("No model path provided. Load model with load_model()")
    
    def reset(self):
        """Reset akumulasi fitur"""
        self.adc_sum.fill(0)
        self.adc_max.fill(0)
        self.sample_count = 0
    
    def accumulate(self, adc_values: List[int]):
        """
        Tambahkan sampel ADC ke akumulasi
        
        Args:
            adc_values: List of NUM_SENSORS uint16 values
        """
        if len(adc_values) != NUM_SENSORS:
            logger.error(f"Expected {NUM_SENSORS} values, got {len(adc_values)}")
            return
        
        vals = np.array(adc_values, dtype=np.uint16)
        self.adc_sum += vals
        self.adc_max = np.maximum(self.adc_max, vals)
        self.sample_count += 1
    
    def load_model(self, model_path: str) -> bool:
        """
        Load model dari file (pickle atau joblib)
        
        Args:
            model_path: Path ke file model
            
        Returns:
            True jika berhasil, False jika gagal
        """
        try:
            model_path = str(model_path)
            
            if not os.path.exists(model_path):
                logger.error(f"Model file not found: {model_path}")
                return False
            
            # Coba joblib dulu (lebih efficient)
            if model_path.endswith('.joblib') and HAS_JOBLIB:
                self.model = joblib.load(model_path)
                logger.info(f"Model loaded from joblib: {model_path}")
            else:
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)
                logger.info(f"Model loaded from pickle: {model_path}")
            
            # Ekstrak feature columns dari model jika ada
            if hasattr(self.model, 'n_features_in_'):
                self.feature_cols = [f'feat_{i}' for i in range(self.model.n_features_in_)]
            
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
    
    def predict(self, features: Optional[List[float]] = None) -> InferenceResult:
        """
        Jalankan inference
        
        Args:
            features: Optional list of 16 features (mean + max). 
                     Jika None, gunakan yang sudah terakumulasi.
        
        Returns:
            InferenceResult dengan prediksi kelas dan confidence
        """
        if self.model is None:
            logger.error("Model not loaded")
            return InferenceResult(
                class_id=-1, label="N/A", confidence=0.0, sample_count=0
            )
        
        # Build feature vector jika belum diberikan
        if features is None:
            if self.sample_count == 0:
                return InferenceResult(
                    class_id=-1, label="N/A", confidence=0.0, sample_count=0
                )
            
            # Features: 8 means + 8 maxes
            means = self.adc_sum / self.sample_count
            features = np.concatenate([means, self.adc_max.astype(np.float64)])
        
        features = np.array([features])  # Reshape untuk sklearn
        
        try:
            # Predict
            class_id = self.model.predict(features)[0]
            
            # Get confidence (rata-rata vote dari trees)
            if hasattr(self.model, 'predict_proba'):
                proba = self.model.predict_proba(features)[0]
                confidence = float(np.max(proba))
            else:
                confidence = 0.0
            
            # Map numeric to label
            if isinstance(class_id, str):
                label = class_id
            else:
                label = CLASS_LABELS[int(class_id)] if 0 <= class_id < NUM_CLASSES else "N/A"
            
            return InferenceResult(
                class_id=int(class_id),
                label=label,
                confidence=confidence,
                sample_count=self.sample_count,
                features=features[0].tolist()
            )
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            return InferenceResult(
                class_id=-1, label="N/A", confidence=0.0, sample_count=self.sample_count
            )
    
    def predict_batch(self, csv_path: str) -> List[InferenceResult]:
        """
        Batch predict dari CSV file
        
        Args:
            csv_path: Path ke CSV dengan kolom ADC
            
        Returns:
            List of InferenceResult
        """
        if not HAS_PANDAS:
            logger.error("pandas not installed")
            return []
        
        try:
            df = pd.read_csv(csv_path)
            
            # Filter hanya kolom ADC
            adc_data = df[ADC_COLS]
            
            # Groupby cycle jika ada
            results = []
            if 'cycle' in df.columns:
                for cycle, group in df.groupby('cycle'):
                    self.reset()
                    for _, row in group.iterrows():
                        self.accumulate(row[ADC_COLS].values)
                    result = self.predict()
                    results.append(result)
            else:
                # Semua data sebagai 1 siklus
                self.reset()
                for _, row in adc_data.iterrows():
                    self.accumulate(row.values)
                result = self.predict()
                results.append(result)
            
            return results
        except Exception as e:
            logger.error(f"Batch predict failed: {e}")
            return []
    
    def print_result(self):
        """Print hasil inference ke console (JSON format)"""
        result = self.predict()
        print(json.dumps(result.to_dict(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Contoh penggunaan
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Inference AI untuk Raspberry Pi')
    parser.add_argument('--model', type=str, help='Path ke model file')
    parser.add_argument('--input', type=str, help='Input CSV file')
    parser.add_argument('--mode', choices=['predict', 'batch'], default='predict',
                       help='Mode operasi')
    args = parser.parse_args()
    
    inf = InferenceRPi(args.model)
    
    if args.mode == 'batch' and args.input:
        results = inf.predict_batch(args.input)
        for i, r in enumerate(results):
            print(f"Cycle {i+1}: {r.label} (confidence: {r.confidence:.2%})")
    else:
        # Demo mode dengan data dummy
        print("Demo mode (no input file)")
        inf.reset()
        for i in range(10):
            adc = [1000 + i*100, 2000, 3000, 4000, 5000, 6000, 7000, 8000]
            inf.accumulate(adc)
        inf.print_result()
