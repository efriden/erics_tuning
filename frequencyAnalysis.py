import pyaudio
import numpy as np
import pyqtgraph as pg
import librosa
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks
from pyqtgraph.Qt import QtCore, QtGui
from number_input import start_gui_thread, get_value1, get_value2

# Start the GUI (it runs in background)
start_gui_thread()

# Parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1              # Mono audio
RATE = 44100              # Sampling rate (samples per second)
CHUNK = 1024 * 2        # Number of frames per buffer

TIME_AVERAGE_BUFFER_SIZE = 20  # Increased for better stability
CONFIDENCE_THRESHOLD = 0.7      # Minimum confidence to display result

# Initialize PyAudio
p = pyaudio.PyAudio()


stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    output=False,
    frames_per_buffer=CHUNK
)

# Enhanced time averaging with confidence tracking
class AdaptiveFilter:
    def __init__(self, window_size=TIME_AVERAGE_BUFFER_SIZE, confidence_threshold=CONFIDENCE_THRESHOLD):
        self.window_size = window_size
        self.pitch_buffer = []
        self.confidence_buffer = []
        self.confidence_threshold = confidence_threshold
        
    def add_measurement(self, pitch, confidence):
        if pitch is not None and not np.isnan(pitch):
            self.pitch_buffer.append(pitch)
            self.confidence_buffer.append(confidence)
            
            if len(self.pitch_buffer) > self.window_size:
                self.pitch_buffer.pop(0)
                self.confidence_buffer.pop(0)
    
    def get_filtered_pitch(self):
        if not self.pitch_buffer:
            return None, 0.0
            
        # Weight recent measurements more heavily
        weights = np.exp(np.linspace(-1, 0, len(self.pitch_buffer)))
        
        # Only use high-confidence measurements for stability calculation
        high_conf_mask = np.array(self.confidence_buffer) > self.confidence_threshold * 0.8
        
        if not np.any(high_conf_mask):
            # If no high-confidence measurements, use median of all
            return np.median(self.pitch_buffer), np.mean(self.confidence_buffer)
            
        # Use weighted average of high-confidence measurements
        filtered_pitches = np.array(self.pitch_buffer)[high_conf_mask]
        filtered_weights = weights[high_conf_mask]
        filtered_confidences = np.array(self.confidence_buffer)[high_conf_mask]
        
        weighted_pitch = np.average(filtered_pitches, weights=filtered_weights)
        avg_confidence = np.mean(filtered_confidences)
        
        return weighted_pitch, avg_confidence

# Initialize adaptive filter
filter_system = AdaptiveFilter()

app = pg.mkQApp()
win = pg.GraphicsLayoutWidget(show=True)
win.setWindowTitle('Live Frequency Analysis')
plot = win.addPlot()
plot.showGrid(x=True, y=True)
plot.setYRange(0, 1)         # Adjust y-axis limits
plot.setXRange(20, 5000)    # Limit x-axis to audible frequencies
# plot.setAutoVisible(x=False, y=True)
# plot.setLogMode(x=False, y=True)  # Logarithmic scale for frequencies
plot.setLabel('left', 'Magnitude')
plot.setLabel('bottom', 'Frequency (Hz)')


curve = plot.plot(fillLevel=0, fillOutline=True, brush='y')


peak_label = pg.TextItem(text="", color='r', anchor=(0.5, 1), border='w', fill=(0, 0, 255))
peak_label.setFont(QtGui.QFont('Mono', 14))  # Set font size and style
plot.addItem(peak_label)


region = pg.LinearRegionItem(brush=(0, 255, 0, 50), pen=(0, 255, 0, 100))
plot.addItem(region)


def calculate_fft(data):
    N = len(data)
    # Apply Hanning window to reduce spectral leakage
    windowed_data = data * np.hanning(N)
    discrete_fourier_transform = fft(windowed_data)
    amplitude_spectrum = np.abs(discrete_fourier_transform)
    if np.max(amplitude_spectrum) > 0:  # Prevent division by zero
        normalized_amplitude_spectrum = amplitude_spectrum / np.max(amplitude_spectrum)
    else:
        normalized_amplitude_spectrum = amplitude_spectrum
    frequencies = fftfreq(N, 1/RATE)
    Nyquist_frequency = N // 2
    frequencies = frequencies[:Nyquist_frequency]
    normalized_amplitude_spectrum = normalized_amplitude_spectrum[:Nyquist_frequency]
    return frequencies, normalized_amplitude_spectrum

def calculate_harmonic_confidence(data, detected_pitch, sr):
    """Calculate confidence based on harmonic content."""
    if detected_pitch is None or detected_pitch <= 0:
        return 0.0
        
    # Get FFT for harmonic analysis
    freqs, mags = calculate_fft(data)
    
    # Look for harmonics at 2f, 3f, 4f
    harmonic_strength = 0.0
    harmonics_found = 0
    
    for harmonic in [2, 3, 4]:
        target_freq = detected_pitch * harmonic
        if target_freq < sr/2:  # Below Nyquist
            # Find closest frequency bin
            freq_idx = np.argmin(np.abs(freqs - target_freq))
            if np.abs(freqs[freq_idx] - target_freq) < 10:  # Within 10 Hz
                harmonic_strength += mags[freq_idx]
                harmonics_found += 1
    
    if harmonics_found > 0:
        return min(harmonic_strength / harmonics_found, 1.0)
    return 0.1  # Low confidence if no harmonics found

def calculate_pitch_confidence(data, detected_pitch, sr):
    """Calculate overall pitch confidence from multiple metrics."""
    if detected_pitch is None or np.isnan(detected_pitch):
        return 0.0
    
    # Harmonic confidence
    harmonic_conf = calculate_harmonic_confidence(data, detected_pitch, sr)
    
    # Signal strength confidence (RMS)
    rms = np.sqrt(np.mean(data**2))
    rms_conf = min(rms / 1000.0, 1.0)  # Normalize based on typical values
    
    # Frequency stability (if we have previous measurements)
    stability_conf = 1.0  # Default high stability for single measurement
    if len(filter_system.pitch_buffer) > 5:
        recent_pitches = filter_system.pitch_buffer[-5:]
        pitch_std = np.std(recent_pitches)
        stability_conf = max(0.1, 1.0 - (pitch_std / detected_pitch) * 10)
    
    # Combined confidence (weighted average)
    combined_confidence = (harmonic_conf * 0.4 + rms_conf * 0.3 + stability_conf * 0.3)
    return min(combined_confidence, 1.0)


# Old time_average function replaced by AdaptiveFilter class


def update():
    try:
        data = stream.read(CHUNK, exception_on_overflow=False)
    except OSError as e:
        print(f'Error on stream.read(): {e}')
        return
    
    fmin_from_input = get_value1()
    fmax_from_input = get_value2()

    region.setRegion([fmin_from_input, fmax_from_input])

    # Convert to numpy array and apply windowing
    data = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    
    # Calculate and display FFT spectrum
    xf, yf = calculate_fft(data)
    curve.setData(xf, yf)

    # YIN pitch detection with windowed data
    windowed_data = data * np.hanning(len(data))
    
    try:
        pitch = librosa.yin(windowed_data,
                            fmin=fmin_from_input,
                            fmax=fmax_from_input,
                            sr=RATE,
                            frame_length=CHUNK)

        mask = (
            ~np.isnan(pitch)
            & (pitch >= fmin_from_input)
            & (pitch <= fmax_from_input)
        )
        pitch = pitch[mask]
        
        if len(pitch) > 0:
            detected_pitch = np.median(pitch)
            
            # Calculate confidence for this measurement
            confidence = calculate_pitch_confidence(data, detected_pitch, RATE)
            
            # Add to adaptive filter
            filter_system.add_measurement(detected_pitch, confidence)
            
            # Get filtered pitch and overall confidence
            filtered_pitch, avg_confidence = filter_system.get_filtered_pitch()
            
            if filtered_pitch and avg_confidence >= CONFIDENCE_THRESHOLD:
                # High confidence - display result
                note = librosa.hz_to_note(filtered_pitch, cents=True)
                peak_label.setText(f"{filtered_pitch:.2f} Hz\n{note}\nConf: {avg_confidence:.1%}")
                peak_label.setPos(filtered_pitch, 0.8)
                peak_label.setColor('g')  # Green for high confidence
            elif filtered_pitch:
                # Low confidence - display with warning
                note = librosa.hz_to_note(filtered_pitch, cents=True)
                peak_label.setText(f"{filtered_pitch:.2f} Hz\n{note}\nConf: {avg_confidence:.1%}\n(Low)")
                peak_label.setPos(filtered_pitch, 0.8)
                peak_label.setColor('orange')  # Orange for low confidence
            else:
                # No valid measurement
                peak_label.setText("No signal")
                peak_label.setColor('r')  # Red for no signal
        else:
            peak_label.setText("Out of range")
            peak_label.setColor('r')
            
    except Exception as e:
        print(f'Error in pitch detection: {e}')
        peak_label.setText("Detection Error")
        peak_label.setColor('r')


timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(50)  # Update interval in milliseconds - reduced for stability

# Start the application
stream.start_stream()
app.exec()

# Clean uppip 
stream.stop_stream()
stream.close()
p.terminate()