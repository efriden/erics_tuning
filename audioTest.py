import pyaudio
import numpy as np
import sys

# Parameters
FORMAT = pyaudio.paInt16  # 16-bit audio format
CHANNELS = 1              # Mono audio
RATE = 44100              # Sampling rate (Hz)
CHUNK = 1024              # Frames per buffer
DURATION = 5              # Optional: max recording duration in seconds


def list_audio_devices(p):
    print("\nAvailable audio input devices:")
    for i in range(p.get_device_count()):
        try:
            device_info = p.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                print(f"{i}: {device_info['name']} "
                      f"(Channels: {device_info['maxInputChannels']}, "
                      f"Rate: {device_info['defaultSampleRate']} Hz)")
        except Exception as e:
            print(f"Couldn't query device {i}: {e}")


def main():
    p = pyaudio.PyAudio()
    list_audio_devices(p)
    try:
        default_input = p.get_default_input_device_info()
        print("\nDefault Input Device:")
        print(f"Index: {default_input['index']}")
        print(f"Name: {default_input['name']}")
        print(f"Max Input Channels: {default_input['maxInputChannels']}")
        print(f"Default Sample Rate: {default_input['defaultSampleRate']} Hz")
    except Exception as e:
        print(f"\nError getting default input device: {e}")
        sys.exit(1)

    try:
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            output=False,
            frames_per_buffer=CHUNK,
            input_device_index=default_input['index'],
            start=False
        )
    except Exception as e:
        print(f"Error opening stream: {e}")
        p.terminate()
        sys.exit(1)

    print("\nStarting recording... Press Ctrl+C to stop.")
    try:
        stream.start_stream()
        frame_count = 0
        max_frames = int(RATE / CHUNK * DURATION) if DURATION else float('inf')
        
        while frame_count < max_frames:
            try:
                # Read audio data
                data = stream.read(CHUNK, exception_on_overflow=False)
                samples = np.frombuffer(data, dtype=np.int16)
                
                # Print some stats
                print(f"\rFrame {frame_count}: "
                      f"Max: {np.max(samples):6d} "
                      f"Min: {np.min(samples):6d} "
                      f"RMS: {np.sqrt(np.mean(samples**2)):6.1f}", end='')
                
                frame_count += 1
                
            except IOError as e:
                print(f"\nAudio overflow: {e}")
                continue
            
            

    except KeyboardInterrupt:
        print("\nUser interrupted recording.")
    except Exception as e:
        print(f"\nError during recording: {e}")
    finally:
        print("\nCleaning up...")
        stream.stop_stream()
        stream.close()
        p.terminate()


if __name__ == "__main__":
    main()