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

    // Bangun vektor fitur: 48 fitur
    // 10 mean + 10 max + 10 sum (AUC) + 9 ratio to MQ135 + 9 ratio to TGS822
    float features[48];
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        features[i]                   = (float)(sum_[i] / count_);   // mean
        features[i + NUM_SENSORS]    = (float)max_[i];               // max
        features[i + NUM_SENSORS * 2] = (float)sum_[i];               // sum (AUC)
    }

    // Ratios to MQ135 (index 1)
    float mq135_max = (float)max_[1];
    if (mq135_max <= 0.0f) mq135_max = 1.0f;
    uint8_t feat_idx = 30;
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        if (i != 1) {
            features[feat_idx++] = (float)max_[i] / mq135_max;
        }
    }

    // Ratios to TGS822 (index 0)
    float tgs822_max = (float)max_[0];
    if (tgs822_max <= 0.0f) tgs822_max = 1.0f;
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        if (i != 0) {
            features[feat_idx++] = (float)max_[i] / tgs822_max;
        }
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
