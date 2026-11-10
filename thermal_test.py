"""Quick test for the MLX90640 thermal camera."""

import adafruit_mlx90640
import board
import busio
import numpy as np

# Create the I2C connection.
i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)

# Initialize the MLX90640.
mlx = adafruit_mlx90640.MLX90640(i2c)

# Set refresh rate.
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ

# MLX90640 has 32 x 24 = 768 pixels.
frame = [0] * 768


def main():
    print("Reading MLX90640 thermal camera...")
    print("Press Ctrl+C to stop")

    try:
        while True:
            mlx.getFrame(frame)

            thermal = np.array(frame).reshape((24, 32))

            print("\nThermal Frame:")
            print("Minimum temperature:", round(np.min(thermal), 2), "C")
            print("Maximum temperature:", round(np.max(thermal), 2), "C")
            print("Average temperature:", round(np.mean(thermal), 2), "C")

    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    main()
