// inference_common.h — Platform-agnostic Inference Base Class
// Digunakan oleh ESP32, ATmega, dan platform lainnya
//
// Akumulasi fitur (mean + max ADC) dari sensor array
// dan klasifikasi menggunakan Random Forest model yang di-export dari Python
//
// Platform-specific:
//   - ESP32: inference.cpp (menggunakan Eloquent ML)
//   - ATmega: inference_atmega.cpp (optimized untuk RAM terbatas)
//   - Raspberry Pi: inference_rpi.py (Python + NumPy/Pandas)
#pragma once

#include <stdint.h>
#include <stddef.h>

// Jumlah sensor ADC yang digunakan
#define NUM_SENSORS 8

// Jumlah kelas output (light, medium, dark)
#define NUM_CLASSES 3

// Struktur hasil inferensi
typedef struct {
    int class_id;        // 0=dark, 1=light, 2=medium (atau -1 jika error)
    const char* label;   // "dark", "light", "medium", atau "N/A"
    uint32_t sample_count;
    float confidence;    // 0.0-1.0 (hanya untuk platform yang support)
} InferenceResult;

// Base class untuk inference di berbagai platform
class InferenceBase {
public:
    InferenceBase() : count_(0) {}
    
    virtual ~InferenceBase() {}
    
    // Reset akumulasi fitur
    virtual void reset() = 0;
    
    // Tambahkan sampel ADC ke running sum dan max
    // adc: array of NUM_SENSORS uint16_t values
    virtual void accumulate(const uint16_t* adc) = 0;
    
    // Dapatkan jumlah sampel yang sudah terakumulasi
    uint32_t getFeatureCount() const { return count_; }
    
    // Jalankan inferensi berdasarkan fitur yang sudah terakumulasi
    virtual InferenceResult predict() = 0;
    
    // Return predicted label string
    virtual const char* predictLabel() = 0;
    
    // Print result ke Serial/console (platform specific)
    virtual void printResult() = 0;

protected:
    uint32_t count_;
};

// Label kelas dalam urutan yang sesuai dengan sklearn LabelEncoder (alphabetical)
// dark=0, light=1, medium=2
static const char* const CLASS_LABELS[] = { "dark", "light", "medium" };
