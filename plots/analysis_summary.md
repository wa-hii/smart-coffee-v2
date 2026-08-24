# Analisis Deskriptif Visualisasi E-NOSE

Dokumen ini dibuat dari RAW CSV secara deskriptif. Tidak ada machine learning, Random Forest, atau training model.
Raw CSV tidak diubah.

## Cakupan Data
- CSV terbaca: 21
- Sample terdeteksi: 9 (D-GAY, D-MAN, D-RAT, L-GAY, L-MAN, L-MER, M-TEM, M-TIM, UNKNOWN)
- Batch terdeteksi: 5 (B01, B02, B03, B04, UNKNOWN)
- Sensor divisualisasikan: 10
- Baris collecting: 37,827

## Ringkasan Respons Sensor

| Sensor | Mean ADC | SD | CV (%) | Range | Slope indikatif |
|---|---:|---:|---:|---:|---:|
| adc_tgs822 | 13743.41 | 2396.02 | 17.43 | 65533.00 | -0.0501 |
| adc_mq135 | 2864.92 | 54.38 | 1.90 | 221.00 | -0.0012 |
| adc_mq9 | 2851.64 | 54.63 | 1.92 | 210.00 | -0.0011 |
| adc_tgs2611 | 8908.42 | 1572.12 | 17.65 | 18947.00 | -0.0189 |
| adc_tgs2620 | 10294.43 | 1630.61 | 15.84 | 65530.00 | -0.0264 |
| adc_tgs2600 | 2848.57 | 59.09 | 2.07 | 216.00 | -0.0012 |
| adc_tgs2602 | 8776.42 | 1443.91 | 16.45 | 65534.00 | -0.0034 |
| adc_mq8 | 15687.58 | 2550.35 | 16.26 | 65534.00 | -0.0420 |
| adc_tgs813 | 14239.45 | 2538.27 | 17.83 | 65504.00 | -0.0307 |
| adc_tgs816 | 13946.39 | 1987.81 | 14.25 | 65515.00 | -0.0227 |

## Temuan Indikatif

- **Respons kuat:** adc_tgs2602 memiliki rentang ADC terbesar. Ini merupakan indikasi respons amplitudo yang lebih besar pada data ini, bukan bukti bahwa sensor pasti paling penting.
- **Noise relatif tinggi:** adc_tgs813 memiliki CV relatif tertinggi. Kemungkinan variasinya dipengaruhi noise, perubahan aroma, atau baseline; perlu dianalisis lebih lanjut.
- **Respons relatif stabil:** adc_mq135 memiliki CV relatif terendah. Stabilitas ini tidak otomatis berarti responsnya informatif.
- **Drift:** adc_tgs822 memiliki kemiringan waktu absolut terbesar pada penggabungan collecting. Ini adalah indikasi drift dan perlu dibandingkan per run serta setelah baseline purging.

## Perbedaan Roast Level

- adc_tgs822: mean tertinggi pada **dark** dan terendah pada **light**. Ini hanya indikasi perbedaan visual/deskriptif.
- adc_mq135: mean tertinggi pada **dark** dan terendah pada **light**. Ini hanya indikasi perbedaan visual/deskriptif.
- adc_mq9: mean tertinggi pada **dark** dan terendah pada **light**. Ini hanya indikasi perbedaan visual/deskriptif.
- adc_tgs2611: mean tertinggi pada **medium** dan terendah pada **light**. Ini hanya indikasi perbedaan visual/deskriptif.
- adc_tgs2620: mean tertinggi pada **dark** dan terendah pada **light**. Ini hanya indikasi perbedaan visual/deskriptif.
- adc_tgs2600: mean tertinggi pada **dark** dan terendah pada **light**. Ini hanya indikasi perbedaan visual/deskriptif.
- adc_tgs2602: mean tertinggi pada **medium** dan terendah pada **dark**. Ini hanya indikasi perbedaan visual/deskriptif.
- adc_mq8: mean tertinggi pada **dark** dan terendah pada **medium**. Ini hanya indikasi perbedaan visual/deskriptif.
- adc_tgs813: mean tertinggi pada **dark** dan terendah pada **light**. Ini hanya indikasi perbedaan visual/deskriptif.
- adc_tgs816: mean tertinggi pada **dark** dan terendah pada **light**. Ini hanya indikasi perbedaan visual/deskriptif.

## Perbedaan Batch

- adc_tgs813: memiliki selisih mean antar batch relatif besar (3722.90 ADC); kemungkinan ada efek batch atau kondisi akuisisi.
- adc_tgs822: memiliki selisih mean antar batch relatif besar (3197.78 ADC); kemungkinan ada efek batch atau kondisi akuisisi.
- adc_mq8: memiliki selisih mean antar batch relatif besar (2972.57 ADC); kemungkinan ada efek batch atau kondisi akuisisi.
- adc_tgs816: memiliki selisih mean antar batch relatif besar (2839.83 ADC); kemungkinan ada efek batch atau kondisi akuisisi.
- adc_tgs2620: memiliki selisih mean antar batch relatif besar (2677.36 ADC); kemungkinan ada efek batch atau kondisi akuisisi.

## Outlier dan Keterbatasan

- Kandidat outlier: adc_tgs822 (772 titik menurut aturan IQR), adc_tgs2611 (570 titik menurut aturan IQR), adc_tgs2620 (2209 titik menurut aturan IQR), adc_tgs2602 (573 titik menurut aturan IQR), adc_mq8 (3127 titik menurut aturan IQR), adc_tgs813 (569 titik menurut aturan IQR), adc_tgs816 (1642 titik menurut aturan IQR)
- Data purging tetap divisualisasikan bila tersedia; analisis respons roast level memakai fase collecting.
- File dengan metadata tidak lengkap diberi label UNKNOWN. Perbandingan antar sample untuk file tersebut perlu dianalisis lebih lanjut.
- Kesimpulan visual bersifat indikatif dan tidak membuktikan kepentingan sensor tanpa analisis statistik lanjutan.
