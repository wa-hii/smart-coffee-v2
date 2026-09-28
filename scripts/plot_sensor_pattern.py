from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# KONFIGURASI
# ============================================================

# Jika file Python berada di folder scripts/
# dan folder data sejajar dengan folder scripts/
DATA_DIR = Path("../data")

# Folder hasil grafik
OUTPUT_DIR = Path("../hasil_plot_sensor")

# Sensor yang digunakan
SENSORS = [
    "adc_tgs822",
    "adc_mq135",
    "adc_mq3",
    "adc_tgs2611",
    "adc_tgs2620",
    "adc_tgs2600",
    "adc_tgs2602",
    "adc_mq8",
    "adc_tgs813",
    "adc_tgs816",
]

# True = mencari CSV sampai ke subfolder dark/light/medium
RECURSIVE = True

# Tampilkan grafik saat program berjalan
SHOW_PLOT = False

# Simpan grafik
SAVE_PLOT = True


# ============================================================
# FUNGSI BANTU
# ============================================================

def safe_name(text):
    """Mengubah nama menjadi aman untuk nama file."""
    return (
        str(text)
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
        .replace(":", "_")
    )


def get_csv_files():
    """Mengambil semua file CSV."""
    if RECURSIVE:
        files = list(DATA_DIR.rglob("*.csv"))
    else:
        files = list(DATA_DIR.glob("*.csv"))

    return sorted(files)


def load_data(file_path):
    """Membaca dan membersihkan satu CSV."""
    df = pd.read_csv(file_path)

    # Validasi kolom minimum
    required = ["run_id", "phase"]

    for col in required:
        if col not in df.columns:
            raise ValueError(
                f"Kolom '{col}' tidak ditemukan pada {file_path.name}"
            )

    # Ubah sensor menjadi numeric
    for sensor in SENSORS:
        if sensor in df.columns:
            df[sensor] = pd.to_numeric(
                df[sensor],
                errors="coerce"
            )

    # Pastikan run_id numeric
    df["run_id"] = pd.to_numeric(
        df["run_id"],
        errors="coerce"
    )

    # Buang baris tanpa run_id
    df = df.dropna(subset=["run_id"])

    df["run_id"] = df["run_id"].astype(int)

    # Rapikan phase
    df["phase"] = (
        df["phase"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    return df


def make_sample_label(df, filename):
    """Membuat nama sampel dari metadata CSV."""

    sample_id = (
        df["sample_id"].iloc[0]
        if "sample_id" in df.columns
        else filename
    )

    roast = (
        df["roast_level"].iloc[0]
        if "roast_level" in df.columns
        else "-"
    )

    origin = (
        df["origin"].iloc[0]
        if "origin" in df.columns
        else "-"
    )

    batch = (
        df["batch_id"].iloc[0]
        if "batch_id" in df.columns
        else "-"
    )

    return f"{sample_id} | {roast} | {origin} | {batch}"


# ============================================================
# 1. RAW SIGNAL TIAP SENSOR
# ============================================================

def plot_raw_signal(df, sensor, output_folder, title):

    data = df[sensor].dropna()

    if data.empty:
        return

    plt.figure(figsize=(15, 5))

    x = np.arange(len(df))

    plt.plot(
        x,
        df[sensor],
        linewidth=1
    )

    # Tandai pergantian siklus
    run_changes = df["run_id"].ne(
        df["run_id"].shift()
    )

    change_positions = np.where(run_changes)[0]

    for pos in change_positions:
        plt.axvline(
            pos,
            linestyle="--",
            linewidth=0.5,
            alpha=0.4
        )

    plt.title(
        f"Raw Signal\n{title}\n{sensor.upper()}"
    )

    plt.xlabel("Urutan Sampel")
    plt.ylabel("ADC")
    plt.grid(alpha=0.25)
    plt.tight_layout()

    if SAVE_PLOT:
        filename = output_folder / f"raw_{sensor}.png"
        plt.savefig(filename, dpi=160)

    if SHOW_PLOT:
        plt.show()

    plt.close()


# ============================================================
# 2. OVERLAY 40 SIKLUS
# ============================================================

def plot_cycle_overlay(df, sensor, output_folder, title):

    plt.figure(figsize=(12, 6))

    run_ids = sorted(df["run_id"].unique())

    valid_run = 0

    for run_id in run_ids:

        run = df[
            df["run_id"] == run_id
        ].copy()

        run = run.dropna(subset=[sensor])

        if len(run) < 2:
            continue

        # Posisi relatif 0-1
        # sehingga setiap siklus dapat dibandingkan
        x = np.linspace(
            0,
            1,
            len(run)
        )

        plt.plot(
            x,
            run[sensor],
            alpha=0.25,
            linewidth=1
        )

        valid_run += 1

    if valid_run == 0:
        plt.close()
        return

    # Batas teori:
    # 2 menit purging + 1 menit collecting
    # purging = 2/3 siklus
    phase_boundary = 2 / 3

    plt.axvline(
        phase_boundary,
        linestyle="--",
        linewidth=2,
        label="Purging → Collecting"
    )

    plt.title(
        f"Overlay Siklus ({valid_run} run)\n"
        f"{title}\n"
        f"{sensor.upper()}"
    )

    plt.xlabel("Posisi Relatif dalam 1 Siklus")
    plt.ylabel("ADC")

    plt.xticks(
        [0, 1/3, 2/3, 1],
        ["0", "1", "2", "3 menit"]
    )

    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()

    if SAVE_PLOT:
        filename = output_folder / f"overlay_{sensor}.png"
        plt.savefig(filename, dpi=160)

    if SHOW_PLOT:
        plt.show()

    plt.close()


# ============================================================
# 3. MEAN ± STD DARI SELURUH SIKLUS
# ============================================================

def plot_mean_cycle(df, sensor, output_folder, title):

    sequences = []

    # Semua siklus dibuat memiliki panjang yang sama
    # agar bisa dihitung mean ± std
    TARGET_LENGTH = 180

    for run_id in sorted(df["run_id"].unique()):

        run = df[
            df["run_id"] == run_id
        ].copy()

        values = (
            run[sensor]
            .dropna()
            .to_numpy()
        )

        if len(values) < 2:
            continue

        old_x = np.linspace(
            0,
            1,
            len(values)
        )

        new_x = np.linspace(
            0,
            1,
            TARGET_LENGTH
        )

        interpolated = np.interp(
            new_x,
            old_x,
            values
        )

        sequences.append(interpolated)

    if not sequences:
        return

    sequences = np.array(sequences)

    mean_signal = np.mean(
        sequences,
        axis=0
    )

    std_signal = np.std(
        sequences,
        axis=0
    )

    x = np.linspace(
        0,
        3,
        TARGET_LENGTH
    )

    plt.figure(figsize=(12, 6))

    plt.plot(
        x,
        mean_signal,
        linewidth=2,
        label="Mean"
    )

    plt.fill_between(
        x,
        mean_signal - std_signal,
        mean_signal + std_signal,
        alpha=0.2,
        label="±1 SD"
    )

    # 2 menit purging → 1 menit collecting
    plt.axvline(
        2,
        linestyle="--",
        linewidth=2,
        label="Purging → Collecting"
    )

    plt.title(
        f"Rata-rata Pola Siklus\n"
        f"{title}\n"
        f"{sensor.upper()}"
    )

    plt.xlabel("Waktu Relatif (menit)")
    plt.ylabel("ADC")

    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()

    if SAVE_PLOT:
        filename = output_folder / f"mean_{sensor}.png"
        plt.savefig(filename, dpi=160)

    if SHOW_PLOT:
        plt.show()

    plt.close()


# ============================================================
# 4. GRAFIK SEMUA SENSOR - NORMALISASI
# ============================================================

def plot_all_sensors_normalized(
    df,
    output_folder,
    title
):

    plt.figure(figsize=(15, 7))

    for sensor in SENSORS:

        if sensor not in df.columns:
            continue

        values = df[sensor].astype(float)

        minimum = values.min()
        maximum = values.max()

        if pd.isna(minimum) or pd.isna(maximum):
            continue

        if maximum == minimum:
            continue

        normalized = (
            values - minimum
        ) / (
            maximum - minimum
        )

        plt.plot(
            np.arange(len(normalized)),
            normalized,
            linewidth=1,
            label=sensor.replace("adc_", "")
        )

    plt.title(
        f"Perbandingan Semua Sensor - Normalisasi Min-Max\n"
        f"{title}"
    )

    plt.xlabel("Urutan Sampel")
    plt.ylabel("Normalized ADC (0–1)")

    plt.legend(
        ncol=2,
        fontsize=8
    )

    plt.grid(alpha=0.25)
    plt.tight_layout()

    if SAVE_PLOT:
        plt.savefig(
            output_folder / "all_sensors_normalized.png",
            dpi=160
        )

    if SHOW_PLOT:
        plt.show()

    plt.close()


# ============================================================
# MAIN
# ============================================================

def process_file(file_path):

    print("=" * 70)
    print(f"Memproses : {file_path}")

    try:
        df = load_data(file_path)

    except Exception as error:
        print(f"GAGAL: {error}")
        return

    sample_name = safe_name(
        file_path.stem
    )

    output_folder = (
        OUTPUT_DIR / sample_name
    )

    output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    title = make_sample_label(
        df,
        file_path.stem
    )

    print(f"Sample     : {title}")
    print(f"Jumlah row : {len(df)}")
    print(
        f"Jumlah run : "
        f"{df['run_id'].nunique()}"
    )

    available_sensors = [
        sensor
        for sensor in SENSORS
        if sensor in df.columns
    ]

    print(
        f"Sensor     : "
        f"{len(available_sensors)}"
    )

    for sensor in available_sensors:

        print(
            f"  Plot {sensor}..."
        )

        plot_raw_signal(
            df,
            sensor,
            output_folder,
            title
        )

        plot_cycle_overlay(
            df,
            sensor,
            output_folder,
            title
        )

        plot_mean_cycle(
            df,
            sensor,
            output_folder,
            title
        )

    plot_all_sensors_normalized(
        df,
        output_folder,
        title
    )

    print(
        f"Hasil tersimpan di: "
        f"{output_folder}"
    )


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    files = get_csv_files()

    if not files:
        print(
            f"Tidak ada CSV di {DATA_DIR.resolve()}"
        )
        return

    print(
        f"Ditemukan {len(files)} file CSV."
    )

    for file_path in files:
        process_file(file_path)

    print("\nSELESAI")
    print(
        f"Semua grafik tersimpan di "
        f"{OUTPUT_DIR.resolve()}"
    )


if __name__ == "__main__":
    main()