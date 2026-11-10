"""Capture a normal camera image and an MLX90640 thermal image,
then upload both to Supabase Storage."""

import os
import shutil
import subprocess
import time
from datetime import datetime

import adafruit_mlx90640
import board
import busio
import matplotlib

# Use a non-interactive backend so the script also works as a
# systemd service on a headless Raspberry Pi.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from config import BASE_DIR, CAPTURE_INTERVAL, SUPABASE_BUCKET, get_supabase

supabase = get_supabase()

# ------------------------------------------------------------
# Local storage
# ------------------------------------------------------------

save_folder = BASE_DIR / "thermal_captures"
save_folder.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------
# Initialize MLX90640
# ------------------------------------------------------------

print("Initializing MLX90640...")

i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)

mlx = adafruit_mlx90640.MLX90640(i2c)

mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ

frame = [0] * 768

print("MLX90640 initialized.")
print(f"Images will be captured every {CAPTURE_INTERVAL} seconds.")
print("Press Ctrl+C to stop.\n")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------


def camera_command():
    """Return the Raspberry Pi still-camera command."""

    for command in ("rpicam-still", "libcamera-still"):
        path = shutil.which(command)

        if path:
            return path

    raise RuntimeError(
        "Neither rpicam-still nor libcamera-still was found. "
        "Install the Raspberry Pi camera apps."
    )


def upload_image(local_filename, storage_filename, content_type):
    """Upload an image to Supabase Storage."""

    try:
        with open(local_filename, "rb") as f:
            file_data = f.read()

        supabase.storage.from_(SUPABASE_BUCKET).upload(
            storage_filename,
            file_data,
            {"content-type": content_type},
        )

        print(f"Uploaded to Supabase: {storage_filename}")
        return True

    except Exception as exc:
        print(f"Supabase upload failed for {local_filename}: {exc}")
        return False


# ------------------------------------------------------------
# Capture normal camera image
# ------------------------------------------------------------


def capture_normal_image(filename, storage_filename):
    try:
        subprocess.run(
            [camera_command(), "-o", str(filename)],
            check=True,
        )

        print("Normal image saved:", filename)

        upload_image(filename, storage_filename, "image/jpeg")

    except subprocess.CalledProcessError as exc:
        print("Error capturing normal image:", exc)

    except Exception as exc:
        print("Normal camera error:", exc)


# ------------------------------------------------------------
# Capture thermal image
# ------------------------------------------------------------


def capture_thermal_image(filename, storage_filename):
    try:
        mlx.getFrame(frame)

        thermal = np.array(frame).reshape((24, 32))

        min_temp = np.min(thermal)
        max_temp = np.max(thermal)
        avg_temp = np.mean(thermal)

        print(
            "Temperature: "
            f"Min={min_temp:.2f} C, "
            f"Max={max_temp:.2f} C, "
            f"Avg={avg_temp:.2f} C"
        )

        fig = plt.figure(figsize=(8, 6))

        plt.imshow(
            thermal,
            cmap="inferno",
            interpolation="bilinear",
        )

        plt.colorbar(label="Temperature (C)")
        plt.title("MLX90640 Thermal Image")
        plt.axis("off")

        plt.savefig(
            filename,
            bbox_inches="tight",
            pad_inches=0.1,
            dpi=150,
        )

        plt.close(fig)

        print("Thermal image saved:", filename)

        upload_image(filename, storage_filename, "image/png")

    except Exception as exc:
        print("Error capturing thermal image:", exc)


# ------------------------------------------------------------
# Main loop
# ------------------------------------------------------------


def main():
    try:
        while True:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            normal_filename = save_folder / f"capture_{timestamp}_normal.jpg"
            thermal_filename = save_folder / f"capture_{timestamp}_thermal.png"

            normal_storage_path = (
                f"{timestamp}/capture_{timestamp}_normal.jpg"
            )
            thermal_storage_path = (
                f"{timestamp}/capture_{timestamp}_thermal.png"
            )

            print("=" * 60)
            print("Capturing images...")
            print("Timestamp:", timestamp)

            capture_normal_image(normal_filename, normal_storage_path)
            capture_thermal_image(thermal_filename, thermal_storage_path)

            print("Capture complete.")
            print(f"Next capture in {CAPTURE_INTERVAL} seconds...\n")

            time.sleep(CAPTURE_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopping camera capture...")
        print("Done.")


if __name__ == "__main__":
    main()
