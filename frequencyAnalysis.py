import pyaudio
import numpy as np
import pyqtgraph as pg
import librosa
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks, hilbert, butter, filtfilt
from pyqtgraph.Qt import QtCore, QtGui
from number_input import start_gui_thread, get_value1, get_value2, get_beat_detection_enabled

# Start the GUI (it runs in background)
start_gui_thread()

# Parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1              # Mono audio
RATE = 44100              # Sampling rate (samples per second)
CHUNK = 1024 * 2        # Number of frames per buffer

TIME_AVERAGE_BUFFER_SIZE = 20  # Increased for better stability
CONFIDENCE_THRESHOLD = 0.7      # Minimum confidence to display result
BEAT_DETECTION_ENABLED = True   # Enable beat detection feature
BEAT_HISTORY_SIZE = 100         # Number of beat measurements to keep
BEAT_FREQUENCY_RANGE = (0.1, 10.0)  # Hz - audible beat range

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

# Beat detection system
class BeatDetector:
    def __init__(self, sample_rate=RATE, history_size=BEAT_HISTORY_SIZE):
        self.sample_rate = sample_rate
        self.beat_history = []
        self.history_size = history_size
        self.last_envelope = None
        
    def create_bandpass_filter(self, low_freq, high_freq, order=4):
        """Create a bandpass filter for isolating frequency range"""
        nyquist = self.sample_rate / 2
        low = max(0.1, low_freq) / nyquist
        high = min(high_freq, nyquist - 1) / nyquist
        
        if low >= high:
            return None
        
        try:
            b, a = butter(order, [low, high], btype='band')
            return b, a
        except:
            return None
    
    def detect_beats_amplitude_modulation(self, audio_data, freq_min, freq_max):
        """Detect beats through amplitude modulation analysis"""
        if len(audio_data) < 512:  # Need minimum data
            return None, None, 0.0
        
        # Create bandpass filter for target frequency range
        filter_params = self.create_bandpass_filter(freq_min, freq_max)
        if filter_params is None:
            return None, None, 0.0
        
        b, a = filter_params
        
        try:
            # Apply bandpass filter
            filtered_signal = filtfilt(b, a, audio_data)
            
            # Calculate envelope using Hilbert transform
            analytic_signal = hilbert(filtered_signal)
            envelope = np.abs(analytic_signal)
            
            # Smooth the envelope to reduce noise
            if len(envelope) > 32:
                window_size = min(32, len(envelope) // 4)
                envelope = np.convolve(envelope, np.ones(window_size)/window_size, mode='same')
            
            # Store current envelope
            self.last_envelope = envelope
            
            # Find beat frequency from envelope variations
            beat_frequency = self.analyze_envelope_for_beats(envelope)
            
            # Update beat history
            if beat_frequency is not None:
                self.beat_history.append(beat_frequency)
                if len(self.beat_history) > self.history_size:
                    self.beat_history.pop(0)
            
            # Calculate average beat frequency
            avg_beat_freq = np.mean(self.beat_history) if self.beat_history else 0.0
            
            return filtered_signal, envelope, beat_frequency if beat_frequency else 0.0
        
        except Exception as e:
            print(f"Beat detection error: {e}")
            return None, None, 0.0
    
    def analyze_envelope_for_beats(self, envelope):
        """Analyze envelope for beat frequency"""
        if len(envelope) < 64:
            return None
        
        try:
            # Remove DC component
            envelope_centered = envelope - np.mean(envelope)
            
            # FFT of envelope to find beat frequencies
            envelope_fft = np.fft.fft(envelope_centered)
            envelope_magnitude = np.abs(envelope_fft)
            
            # Create frequency axis for envelope FFT
            n_samples = len(envelope)
            dt = n_samples / self.sample_rate  # Total time duration
            envelope_freqs = np.fft.fftfreq(n_samples, dt)
            
            # Only consider positive frequencies in beat range
            positive_freq_mask = (
                (envelope_freqs > BEAT_FREQUENCY_RANGE[0]) & 
                (envelope_freqs < BEAT_FREQUENCY_RANGE[1])
            )
            
            if not np.any(positive_freq_mask):
                return None
            
            valid_freqs = envelope_freqs[positive_freq_mask]
            valid_magnitudes = envelope_magnitude[positive_freq_mask]
            
            # Find peaks in the envelope spectrum
            if len(valid_magnitudes) < 3:
                return None
            
            peaks, properties = find_peaks(
                valid_magnitudes, 
                height=np.max(valid_magnitudes) * 0.1,  # At least 10% of max
                distance=max(1, len(valid_magnitudes) // 20)  # Minimum separation
            )
            
            if len(peaks) == 0:
                return None
            
            # Return the frequency of the strongest peak
            strongest_peak_idx = peaks[np.argmax(valid_magnitudes[peaks])]
            beat_frequency = valid_freqs[strongest_peak_idx]
            
            return abs(beat_frequency)  # Return absolute frequency
        
        except Exception as e:
            print(f"Envelope analysis error: {e}")
            return None
    
    def get_beat_stability(self):
        """Calculate beat detection stability/confidence"""
        if len(self.beat_history) < 5:
            return 0.0
        
        recent_beats = self.beat_history[-10:]  # Last 10 measurements
        if len(recent_beats) < 2:
            return 0.0
        
        mean_beat = np.mean(recent_beats)
        std_beat = np.std(recent_beats)
        
        if mean_beat == 0:
            return 0.0
        
        # Stability is higher when standard deviation is low relative to mean
        stability = max(0, 1.0 - (std_beat / max(mean_beat, 0.1)))
        return min(stability, 1.0)

# Initialize beat detector
beat_detector = BeatDetector() if BEAT_DETECTION_ENABLED else None

# Track beat detection state for UI updates
previous_beat_state = True

def toggle_beat_plots_visibility(show_plots):
    """Show or hide beat detection plots"""
    try:
        for plot_item in beat_plots:
            if show_plots:
                plot_item.show()
            else:
                plot_item.hide()
        
        # Also show/hide the beat label
        if show_plots:
            beat_label.show()
        else:
            beat_label.hide()
            
    except Exception as e:
        print(f"Error toggling beat plot visibility: {e}")

def update_beat_displays(envelope, beat_frequency, beat_stability):
    """Update all beat detection visualizations"""
    global beat_data, envelope_data, beatrate_data
    
    try:
        # Update envelope display
        if envelope is not None and len(envelope) > 0:
            envelope_data = envelope[:min(len(envelope), 1024)]  # Limit display size
            x_envelope = np.arange(len(envelope_data))
            envelope_curve.setData(x_envelope, envelope_data)
        
        # Update beat frequency history
        if beat_frequency > 0:
            beat_data.append(beat_frequency)
            if len(beat_data) > 100:  # Keep last 100 measurements
                beat_data.pop(0)
            
            # Update beat curve
            x_beat = np.arange(len(beat_data))
            beat_curve.setData(x_beat, beat_data)
        
        # Update beat rate history (smoothed)
        if len(beat_data) >= 5:  # Need some history for smoothing
            recent_beats = beat_data[-10:]  # Last 10 measurements
            avg_beat_rate = np.mean(recent_beats)
            beatrate_data.append(avg_beat_rate)
            
            if len(beatrate_data) > 50:  # Keep last 50 averaged measurements
                beatrate_data.pop(0)
            
            x_beatrate = np.arange(len(beatrate_data))
            beatrate_curve.setData(x_beatrate, beatrate_data)
            
            # Update beat rate plot range
            if len(beatrate_data) > 0:
                beatrate_plot.setXRange(0, len(beatrate_data))
        
        # Update beat detection label
        if beat_frequency > 0.1:
            stability_text = f"Stability: {beat_stability:.1%}"
            if beat_stability > 0.8:
                status = "STABLE"
                # Use dark green for good contrast
                beat_label.setHtml(f'<div style="color: #006400; font-weight: bold;">Beat: {beat_frequency:.2f} Hz<br>{stability_text}<br>Status: {status}</div>')
            elif beat_stability > 0.5:
                status = "MODERATE"
                # Use dark orange for good contrast
                beat_label.setHtml(f'<div style="color: #FF4500; font-weight: bold;">Beat: {beat_frequency:.2f} Hz<br>{stability_text}<br>Status: {status}</div>')
            else:
                status = "UNSTABLE"
                # Use dark red for good contrast
                beat_label.setHtml(f'<div style="color: #8B0000; font-weight: bold;">Beat: {beat_frequency:.2f} Hz<br>{stability_text}<br>Status: {status}</div>')
            
            beat_label.setPos(15, 8)  # Position in beat plot - moved right
        else:
            beat_label.setHtml('<div style="color: #666666; font-weight: bold;">No beats detected</div>')
            beat_label.setPos(15, 8)  # Position in beat plot - moved right
            
    except Exception as e:
        print(f"Beat display update error: {e}")

app = pg.mkQApp()
win = pg.GraphicsLayoutWidget(show=True)
win.setWindowTitle('Live Frequency Analysis with Beat Detection')
win.resize(1200, 800)  # Larger window for multiple plots

# Main frequency spectrum plot
plot = win.addPlot(title='Frequency Spectrum')
plot.showGrid(x=True, y=True)
plot.setYRange(0, 1)         # Adjust y-axis limits
plot.setXRange(20, 5000)    # Limit x-axis to audible frequencies
plot.setLabel('left', 'Magnitude')
plot.setLabel('bottom', 'Frequency (Hz)')

# Beat detection plot (right side) - initially visible
beat_plot = win.addPlot(title='Beat Detection')
beat_plot.showGrid(x=True, y=True)
beat_plot.setYRange(0, 10)   # Beat frequency range 0-10 Hz
beat_plot.setXRange(0, 100)  # Show last 100 measurements
beat_plot.setLabel('left', 'Beat Frequency (Hz)')
beat_plot.setLabel('bottom', 'Time (samples)')

# Move to next row
win.nextRow()

# Envelope plot (bottom left) - initially visible
envelope_plot = win.addPlot(title='Amplitude Envelope')
envelope_plot.showGrid(x=True, y=True)
envelope_plot.setLabel('left', 'Amplitude')
envelope_plot.setLabel('bottom', 'Time (samples)')

# Beat rate history plot (bottom right) - initially visible
beatrate_plot = win.addPlot(title='Beat Rate History')
beatrate_plot.showGrid(x=True, y=True)
beatrate_plot.setYRange(0, 5)    # Focus on typical beat rates
beatrate_plot.setXRange(0, 50)   # Last 50 measurements
beatrate_plot.setLabel('left', 'Beat Rate (Hz)')
beatrate_plot.setLabel('bottom', 'Time')

# Store references for show/hide functionality
beat_plots = [beat_plot, envelope_plot, beatrate_plot]


# Add frequency range region FIRST (behind other elements)
region = pg.LinearRegionItem(brush=(0, 255, 0, 30), pen=(0, 255, 0, 80))  # More transparent
plot.addItem(region)

# Main spectrum curve
curve = plot.plot(fillLevel=0, fillOutline=True, brush='y')

# Beat detection curves
beat_curve = beat_plot.plot(pen='r', symbol='o', symbolSize=4)
envelope_curve = envelope_plot.plot(pen='b')
beatrate_curve = beatrate_plot.plot(pen='g', symbol='o', symbolSize=3)

# Beat detection data buffers
beat_data = []
envelope_data = []
beatrate_data = []

# Main pitch detection label - fixed position with darker text (added LAST for top layer)
peak_label = pg.TextItem(text="", color=(0, 0, 0), anchor=(0, 0), border='w', fill=(255, 255, 255, 240))
peak_label.setFont(QtGui.QFont('Arial', 12, QtGui.QFont.Weight.Bold))
plot.addItem(peak_label)
# Position at top-left corner of the plot
peak_label.setPos(50, 0.9)
# Ensure the text label is on top
peak_label.setZValue(100)  # High z-value to stay on top

# Beat detection label with darker text
beat_label = pg.TextItem(text="", color=(0, 0, 0), anchor=(0.5, 1), border='w', fill=(255, 255, 255, 240))
beat_label.setFont(QtGui.QFont('Arial', 11, QtGui.QFont.Weight.Bold))
beat_plot.addItem(beat_label)
beat_label.setZValue(100)  # High z-value to stay on top

# Beat rate target indicator line
target_beat_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('g', width=2, style=QtCore.Qt.PenStyle.DashLine))
beatrate_plot.addItem(target_beat_line)
target_beat_line.setPos(1.0)  # Default target: 1 Hz


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
            
            # Beat detection analysis
            beat_frequency = 0.0
            beat_stability = 0.0
            
            # Check if beat detection is currently enabled via GUI
            current_beat_enabled = get_beat_detection_enabled()
            
            # Toggle beat plot visibility if state changed
            global previous_beat_state
            if current_beat_enabled != previous_beat_state:
                toggle_beat_plots_visibility(current_beat_enabled)
                previous_beat_state = current_beat_enabled
            
            if current_beat_enabled and beat_detector and len(data) > 512:
                # Perform beat detection on the current frequency range
                filtered_signal, envelope, beat_freq = beat_detector.detect_beats_amplitude_modulation(
                    data, fmin_from_input, fmax_from_input
                )
                
                if beat_freq is not None:
                    beat_frequency = beat_freq
                    beat_stability = beat_detector.get_beat_stability()
                    
                    # Update beat visualization
                    update_beat_displays(envelope, beat_frequency, beat_stability)
            
            # Beat information is handled by dedicated beat detection panel
            # No need to show beat info in pitch display
            
            if filtered_pitch and avg_confidence >= CONFIDENCE_THRESHOLD:
                # High confidence - display pitch information only
                note = librosa.hz_to_note(filtered_pitch, cents=True)
                peak_label.setHtml(f'<div style="color: #006400; font-weight: bold;">{filtered_pitch:.2f} Hz<br>{note}<br>Conf: {avg_confidence:.1%}</div>')
            elif filtered_pitch:
                # Low confidence - display with orange color
                note = librosa.hz_to_note(filtered_pitch, cents=True)
                peak_label.setHtml(f'<div style="color: #FF4500; font-weight: bold;">{filtered_pitch:.2f} Hz<br>{note}<br>Conf: {avg_confidence:.1%}</div>')
            else:
                # No valid measurement
                peak_label.setHtml('<div style="color: #8B0000; font-weight: bold;">No signal detected</div>')
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