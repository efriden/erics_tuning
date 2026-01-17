import logging
import pyaudio
import numpy as np
import sys

logger = logging.getLogger(__name__)

# Parameters
FORMAT = pyaudio.paInt16  # 16-bit audio format
CHANNELS = 1              # Mono audio
RATE = 44100              # Sampling rate (Hz)
CHUNK = 1024              # Frames per buffer
DURATION = 5              # Optional: max recording duration in seconds


def get_audio_device_info():
    """Get information about audio devices as a dictionary.
    
    Returns:
        dict with keys:
        - 'devices': list of device info dicts
        - 'default_input': default input device info dict or None
        - 'error': error message if any
    """
    result = {'devices': [], 'default_input': None, 'error': None}
    
    try:
        p = pyaudio.PyAudio()
        
        # Get all input devices
        for i in range(p.get_device_count()):
            try:
                device_info = p.get_device_info_by_index(i)
                if device_info['maxInputChannels'] > 0:
                    result['devices'].append({
                        'index': i,
                        'name': device_info['name'],
                        'channels': device_info['maxInputChannels'],
                        'rate': device_info['defaultSampleRate'],
                    })
            except Exception as e:
                logger.warning(f"Couldn't query device {i}: {e}")
        
        # Get default input device
        try:
            default_input = p.get_default_input_device_info()
            result['default_input'] = {
                'index': default_input['index'],
                'name': default_input['name'],
                'channels': default_input['maxInputChannels'],
                'rate': default_input['defaultSampleRate'],
            }
        except Exception as e:
            logger.warning(f"Error getting default input device: {e}")
            result['error'] = f"No default input device: {e}"
        
        p.terminate()
    except Exception as e:
        logger.exception("Error initializing PyAudio")
        result['error'] = f"PyAudio error: {e}"
    
    return result


def list_audio_devices(p):
    """Legacy function for logging audio devices."""
    logger.info("Available audio input devices:")
    for i in range(p.get_device_count()):
        try:
            device_info = p.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                logger.info(
                    "%d: %s (Channels: %d, Rate: %s Hz)",
                    i,
                    device_info['name'],
                    device_info['maxInputChannels'],
                    device_info['defaultSampleRate'],
                )
        except Exception:
            logger.exception("Couldn't query device %d", i)


def main():
    p = pyaudio.PyAudio()
    list_audio_devices(p)
    try:
        default_input = p.get_default_input_device_info()
        logger.info("Default Input Device:")
        logger.info("Index: %s", default_input['index'])
        logger.info("Name: %s", default_input['name'])
        logger.info("Max Input Channels: %s", default_input['maxInputChannels'])
        logger.info("Default Sample Rate: %s Hz", default_input['defaultSampleRate'])
    except Exception:
        logger.exception("Error getting default input device")
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
    except Exception:
        logger.exception("Error opening stream")
        p.terminate()
        sys.exit(1)

    logger.info("Starting recording... Press Ctrl+C to stop.")
    try:
        stream.start_stream()
        frame_count = 0
        max_frames = int(RATE / CHUNK * DURATION) if DURATION else float('inf')
        
        while frame_count < max_frames:
            try:
                # Read audio data
                data = stream.read(CHUNK, exception_on_overflow=False)
                samples = np.frombuffer(data, dtype=np.int16)
                
                # Log some stats at debug level to avoid spamming stdout
                logger.debug(
                    "Frame %d: Max: %6d Min: %6d RMS: %6.1f",
                    frame_count,
                    int(np.max(samples)),
                    int(np.min(samples)),
                    float(np.sqrt(np.mean(samples**2))),
                )
                
                frame_count += 1
                
            except IOError:
                logger.exception("Audio overflow")
                continue
            
            

    except KeyboardInterrupt:
        logger.info("User interrupted recording.")
    except Exception:
        logger.exception("Error during recording")
    finally:
        logger.info("Cleaning up...")
        stream.stop_stream()
        stream.close()
        p.terminate()


if __name__ == "__main__":
    main()