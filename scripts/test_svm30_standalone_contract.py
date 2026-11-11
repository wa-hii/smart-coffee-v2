#!/usr/bin/env python3
"""Source-level standalone B4 release-gate QA; DOES NOT access any hardware.

This catches accidentally unguarded receiver/CSV behavior, mismatched
30-cycle paths and stale Nextion result handling before compile-only builds.
Native streaming-SVM parity and actual AVR compilation are separate gates.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/"src/main.cpp").read_text(encoding="utf8")
PROFILE=(ROOT/"scripts/platformio_svm30_standalone.ini").read_text(encoding="utf8")
MODEL=(ROOT/"src/embedded_svm30_classifier.cpp").read_text(encoding="utf8")
FEATURES=(ROOT/"src/embedded_svm30_features.cpp").read_text(encoding="utf8")


def body(before:str,after:str)->str:
    assert SOURCE.count(before)==1,(before,SOURCE.count(before))
    return SOURCE.split(before,1)[1].split(after,1)[0]


def run():
    assert "[env:svm30_standalone]" in PROFILE
    for setting in (
        "-DENABLE_AVR_SVM30=1",
        "-DSMART_COFFEE_STANDALONE_SVM30=1",
        "-DENABLE_PI_RF30_RETURN=0",
        "-DENABLE_MANUAL_ACTUATOR_TESTS=0",
        "-DUSE_ON_DEVICE_INFERENCE=0",
        "-fstack-usage",
    ):
        assert setting in PROFILE,setting
    assert "upload_port" not in PROFILE and "monitor_port" not in PROFILE
    assert "pio run" not in PROFILE or "upload" not in PROFILE.lower().split("do not")
    assert "#define ACQ_DATA_REPETITIONS 30" in SOURCE
    assert "#define ACQ_AI_REPETITIONS ACQ_DATA_REPETITIONS" in SOURCE
    assert "#define ACQ_PURGE_SECONDS 25" in SOURCE
    assert "#define ACQ_COLLECTION_SECONDS 5" in SOURCE
    assert "#error \"Standalone SVM mode cannot enable Pi reply" in SOURCE

    start=body("void startAcquisition(AcquisitionMode mode) {",
               "\nvoid stopAcquisition() {")
    assert start.index("svm30Capture.reset();") < start.index(
        "acqState = AcqState::PURGING;")
    assert "#if !SMART_COFFEE_STANDALONE_SVM30" in start
    cancel=body("void stopAcquisition() {","\nvoid pauseAcquisition() {")
    assert "svm30Capture.reset();" in cancel
    assert "aiRf30Roast = AiRf30Return::Roast::NONE;" in cancel
    assert cancel.index("svm30Capture.reset();") < cancel.index(
        "acqState = AcqState::IDLE;")

    adc=body("void adsCallback() {", "\n") if False else SOURCE.split(
        "void adsCallback() {",1)[1]
    assert "sensors.readAll();" in adc
    assert adc.index("++acqSampleIdx;") < adc.index("svm30Capture.add(")
    assert "sensors.adcAvailable(SENSOR_TGS822)" in adc
    assert "sensors.adcAvailable(SENSOR_TGS2602)" in adc
    assert "sensors.adcAvailable(SENSOR_TGS816)" in adc
    assert "sensors.adcAvailable(SENSOR_MQ8)" in adc
    assert "stopAcquisition();" in adc and "sendNextionAlert(" in adc
    assert "#else\n    if (acqState == AcqState::COLLECTING) {" in adc
    assert "sensors.printJsonData(acqStateName(), acqCycle, acqSampleIdx);" in adc
    assert "#endif" in adc

    complete=body("void processAcquisitionState() {",
                  "\nvoid setActuators() {")
    assert complete.index("acqState = AcqState::COMPLETE;") < complete.index(
        "setActuators();",complete.index("acqState = AcqState::COMPLETE;"))
    assert complete.index("doInference();") < complete.index(
        'showNextionPage("pResult");')
    assert "++testSequence;" in complete
    infer=body("void doInference() {","\nvoid showNextionPage(")
    assert "acqTotalSamples != EmbeddedSvm30::kSamples" in infer
    assert "!svm30Capture.complete()" in infer
    assert "standaloneFreeRam() < 2048" in infer
    assert "!svm30Capture.copyFeatures(raw)" in infer
    assert "EmbeddedSvm30::Classifier::predict(raw)" in infer
    for label in ("LIGHT","MEDIUM","DARK"):
        assert f"EmbeddedSvm30::{label}" in infer
    assert "aiRf30Roast = AiRf30Return::Roast::NONE;" in infer

    result=body("void updateNextionInferenceResult() {",
                "\nvoid restoreNextionPageAfterBoot() {")
    assert "AiRf30Return::label(aiRf30Roast)" in result
    for comp in ('"tRoast"','"tRConf"','"tOrigin"','"tOConf"',
                 '"jLight"','"jMedium"','"jDark"'):
        assert comp in result
    assert '"N/A"' in result

    ui=body("void handleNextionEvent(const char *event) {",
            "\n// ═")
    assert '"EVT:DATA_START"' in ui
    assert '"EVT:AI_START"' in ui
    assert '"EVT:AI_CANCEL"' in ui
    assert '"EVT:RESULT_SAVE"' in ui
    assert "MODE DATA TIDAK TERSEDIA" in SOURCE
    assert "nextion.touch(\"mStart\", false);" in SOURCE
    assert "Simpan nonaktif" in ui
    assert "Tidak ada penyimpanan CSV" in ui
    assert '"LOCAL MCU"' in SOURCE
    assert "nextion.begin(NEXTION_BAUD);" in SOURCE
    assert "NextionTransport nextion(Serial2);" in SOURCE

    serial=body("void serialCallback() {","\nvoid uiCallback() {")
    assert "#if !SMART_COFFEE_STANDALONE_SVM30" in serial
    assert "while (Serial.available())" in serial
    assert 'nextion.poll(handleNextionEvent);' in serial

    assert "pgm_read_float" in MODEL
    assert "float kernel[125];" in MODEL
    assert "PROGMEM" in (ROOT/"private/embedded_svm30_model.h").read_text(
        encoding="utf8")
    assert "new " not in FEATURES
    print("SVM30_STANDALONE_B4_SOURCE_CONTRACT_PASS", {
        "cycles":30, "samples":900, "features":30,
        "nextion_page":"pResult", "pi_required":False,
        "storage_required":False,"physical_flash":False})


if __name__=="__main__":
    run()
