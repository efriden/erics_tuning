import pyaudio
import numpy as np

# Parameters
FORMAT = pyaudio.paInt16  # Audio format (16-bit)
CHANNELS = 1              # Mono audio
RATE = 44100              # Sampling rate (samples per second)
CHUNK = 1024              # Number of frames per buffer

# Initialize PyAudio
p = pyaudio.PyAudio()

# List available audio devices
print("Available audio devices:")
for i in range(p.get_device_count()):
    device_info = p.get_device_info_by_index(i)
    print(f"{i}: {device_info['name']} (Input Channels: {device_info['maxInputChannels']})")

# Open audio stream
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    output=False,
    frames_per_buffer=CHUNK
)

print("Recording... Press Ctrl+C to stop.")

try:
    while True:
        # Read audio data from stream
        data = stream.read(CHUNK, exception_on_overflow=False)
        data = np.frombuffer(data, dtype=np.int16)

        # Print the audio data (first 10 samples)
        print(data[:10])

except KeyboardInterrupt:
    print("Stopping...")

# Clean up
stream.stop_stream()
stream.close()
p.terminate()