#include "inference.h"

#if USE_ON_DEVICE_INFERENCE
#include "model_rf.h"   // dihasilkan oleh micromlgen (scripts/4_train_rf.py)
#endif

// Label kelas — urutan mengikuti sklearn LabelEncoder (alfabetis)
static const char* const CLASS_LABELS[] = { "dark", "light", "medium" };
#define NUM_CLASSES 3

void Inference::reset() {
    memset(sum_, 0, sizeof(sum_));
    memset(max_, 0, sizeof(max_));
    count_ = 0;
}

void Inference::accumulate(const uint16_t* adc) {
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        sum_[i] += adc[i];
        if (adc[i] > max_[i]) max_[i] = adc[i];
    }
    count_++;
}

int Inference::predict() {
#if USE_ON_DEVICE_INFERENCE
    if (count_ == 0) return -1;

    // Bangun vektor fitur: 8 mean + 8 max = 16 fitur
    float features[NUM_SENSORS * 2];
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        features[i]               = (float)(sum_[i] / count_);   // mean
        features[i + NUM_SENSORS] = (float)max_[i];               // max
    }

    Eloquent::ML::Port::RandomForest classifier;
    return classifier.predict(features);
#else
    return -1;
#endif
}

const char* Inference::predictLabel() {
    int idx = predict();
    if (idx < 0 || idx >= NUM_CLASSES) return "N/A";
    return CLASS_LABELS[idx];
}

void Inference::printResult() {
#if USE_ON_DEVICE_INFERENCE
    if (count_ == 0) {
        Serial.println(F("{\"event\":\"INFERENCE\",\"error\":\"no collecting data\"}"));
        return;
    }

    const char* label = predictLabel();
    Serial.print(F("{\"event\":\"INFERENCE\",\"result\":\""));
    Serial.print(label);
    Serial.print(F("\",\"feat_count\":"));
    Serial.print(count_);
    Serial.println(F("}"));
#else
    Serial.println(F("{\"event\":\"INFERENCE\",\"result\":\"N/A\","
                     "\"info\":\"Set USE_ON_DEVICE_INFERENCE=1 dan sertakan model_rf.h\"}"));
#endif
}
