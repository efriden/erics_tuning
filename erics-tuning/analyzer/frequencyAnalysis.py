import argparse
import json
import os
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import warnings

import pyaudio
import numpy as np
import pyqtgraph as pg
import librosa
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks, hilbert, butter, filtfilt
from pyqtgraph.Qt import QtCore, QtGui


logger = logging.getLogger(__name__)

# Base paths and shared configuration
ROOT = Path(__file__).resolve().parent.parent
APP_CONFIG_PATH = ROOT / "config.json"


def _load_logging_path() -> Path:
    """Load analyzer log path from config.json with a safe default."""
    config_data: dict = {}
    if APP_CONFIG_PATH.is_file():
        try:
            config_data = json.loads(APP_CONFIG_PATH.read_text("utf-8"))
        except Exception:
            config_data = {}

    logging_cfg = config_data.get("logging", {})
    analyzer_log_rel = logging_cfg.get("analyzer_log", "logs/analyzer.log")
    log_path = ROOT / analyzer_log_rel
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return log_path


def _load_layout_flags() -> tuple[bool, bool, bool, bool, bool, bool, bool]:
    """Load analyzer layout flags from config.json with safe defaults."""
    config_data: dict = {}
    if APP_CONFIG_PATH.is_file():
        try:
            config_data = json.loads(APP_CONFIG_PATH.read_text("utf-8"))
        except Exception:
            config_data = {}
    
    layout_cfg = config_data.get("analyzer_layout", {})
    show_main_spectrum = layout_cfg.get("show_main_spectrum", True)
    show_beat_scatter = layout_cfg.get("show_beat_scatter", True)
    show_envelope = layout_cfg.get("show_envelope", True)
    show_beat_history = layout_cfg.get("show_beat_history", True)
    show_main_spectrogram = layout_cfg.get("show_main_spectrogram", False)
    show_beat_spectrogram = layout_cfg.get("show_beat_spectrogram", False)
    show_pitch_scatter = layout_cfg.get("show_pitch_scatter", False)
    return (show_main_spectrum, show_beat_scatter, show_envelope, show_beat_history,
            show_main_spectrogram, show_beat_spectrogram, show_pitch_scatter)


# Analyzer logging configuration (separate from TUI logging).
ANALYZER_LOG_PATH = _load_logging_path()
(SHOW_MAIN_SPECTRUM, SHOW_BEAT_SCATTER, SHOW_ENVELOPE, SHOW_BEAT_HISTORY,
 SHOW_MAIN_SPECTROGRAM, SHOW_BEAT_SPECTROGRAM, SHOW_PITCH_SCATTER) = _load_layout_flags()
_analyzer_handler = RotatingFileHandler(ANALYZER_LOG_PATH, maxBytes=1_000_000, backupCount=3)
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for detailed logging
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[_analyzer_handler],
)
logger = logging.getLogger(__name__)

# Capture warnings in the logging system instead of stderr
logging.captureWarnings(True)
warnings_logger = logging.getLogger('py.warnings')
warnings_logger.addHandler(_analyzer_handler)
warnings_logger.setLevel(logging.WARNING)

# Parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1              # Mono audio
RATE = 44100              # Sampling rate (samples per second)
CHUNK = 1024 * 2          # Number of frames per buffer

TIME_AVERAGE_BUFFER_SIZE = 20   # Increased for better stability
CONFIDENCE_THRESHOLD = 0.7      # Minimum confidence to display result
BEAT_DETECTION_ENABLED = True   # Default beat detection feature
BEAT_HISTORY_SIZE = 100         # Number of beat measurements to keep
BEAT_FREQUENCY_RANGE = (0.1, 10.0)  # Hz - audible beat range

# YIN has a lower bound on fmin based on frame_length and sample rate.
MIN_YIN_FMIN = RATE / CHUNK  # e.g. ~21.5 Hz for 44100 / 2048

# Configuration handling
DEFAULT_CONFIG = {
    "fmin": 20.0,
    "fmax": 5000.0,
    "beat_detection_enabled": True,
}


def _parse_args():
    """Parse CLI arguments, using config.json to choose a sensible default.

    --config defaults to the tuning config path from config.json, or
    analyzer/tuning_config.json under the project root.
    """
    # Determine default tuning config path from shared config
    default_config_path = ROOT / "analyzer" / "tuning_config.json"
    if APP_CONFIG_PATH.is_file():
        try:
            cfg = json.loads(APP_CONFIG_PATH.read_text("utf-8"))
            analyzer_cfg = cfg.get("analyzer", {})
            rel = analyzer_cfg.get("config")
            if isinstance(rel, str) and rel:
                default_config_path = ROOT / rel
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Live frequency analysis with Qt")
    parser.add_argument(
        "--config",
        type=str,
        default=str(default_config_path),
        help="Path to JSON config with fmin/fmax/beat_detection_enabled.",
    )
    return parser.parse_args()


ARGS = _parse_args()
CONFIG_PATH = Path(ARGS.config).expanduser()


def load_config():
    """Load tuning configuration from JSON, falling back to defaults.

    This is intentionally lightweight and safe to call from the realtime
    update loop; errors just return the previous/default values.
    """
    logger.debug(f"load_config() called, checking {CONFIG_PATH}")
    try:
        if CONFIG_PATH.is_file():
            with CONFIG_PATH.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        else:
            logger.debug("Config file not found, using defaults")
            data = DEFAULT_CONFIG
    except Exception as exc:
        logger.warning(f"Failed to load config: {exc}, using defaults")
        data = DEFAULT_CONFIG

    fmin = float(data.get("fmin", DEFAULT_CONFIG["fmin"]))
    fmax = float(data.get("fmax", DEFAULT_CONFIG["fmax"]))
    beat_enabled = bool(data.get("beat_detection_enabled", DEFAULT_CONFIG["beat_detection_enabled"]))
    audio_device = data.get("audio_device_index", None)  # None means use system default

    # Basic sanity constraints
    if fmin < 0:
        logger.debug(f"Invalid fmin={fmin}, using default={DEFAULT_CONFIG['fmin']}")
        fmin = DEFAULT_CONFIG["fmin"]
    if fmax <= fmin:
        logger.debug(f"Invalid fmax={fmax} (must be > fmin={fmin}), using default={DEFAULT_CONFIG['fmax']}")
        fmax = DEFAULT_CONFIG["fmax"]

    logger.debug(f"load_config() returning: fmin={fmin}, fmax={fmax}, beat_enabled={beat_enabled}, audio_device={audio_device}")
    return fmin, fmax, beat_enabled, audio_device

# Load configuration once at startup and keep values for the entire
# runtime of the analyzer.
FMIN_FROM_CONFIG, FMAX_FROM_CONFIG, BEAT_ENABLED_FROM_CONFIG, initial_audio_device = load_config()

# Initialize PyAudio
p = pyaudio.PyAudio()

# Get device name for display
device_name = "System Default"
if initial_audio_device is not None:
    try:
        device_info = p.get_device_info_by_index(initial_audio_device)
        device_name = device_info['name']
        logger.info(f"Using audio device: {device_name} (index {initial_audio_device})")
    except Exception as e:
        logger.warning(f"Could not get device name for index {initial_audio_device}: {e}")
        device_name = f"Device {initial_audio_device}"
else:
    try:
        default_device = p.get_default_input_device_info()
        device_name = default_device['name']
        logger.info(f"Using default audio device: {device_name}")
    except Exception as e:
        logger.warning(f"Could not get default device name: {e}")

# Open stream with selected device (or None for system default)
stream_kwargs = {
    "format": FORMAT,
    "channels": CHANNELS,
    "rate": RATE,
    "input": True,
    "output": False,
    "frames_per_buffer": CHUNK,
}

if initial_audio_device is not None:
    stream_kwargs["input_device_index"] = initial_audio_device

stream = p.open(**stream_kwargs)

# Spectrogram data management
class SpectrogramData:
    """Maintains rolling history of FFT frames for spectrogram display."""
    def __init__(self, max_frames=100, num_freq_bins=512):
        logger.debug(f"SpectrogramData initialized: max_frames={max_frames}, num_freq_bins={num_freq_bins}")
        self.max_frames = max_frames
        self.num_freq_bins = num_freq_bins
        # Store as 2D array: [time_index, frequency_bin]
        self.data = np.zeros((max_frames, num_freq_bins), dtype=np.float32)
        self.frame_index = 0
        
    def add_frame(self, fft_magnitudes):
        """Add a new FFT frame to the rolling buffer."""
        # Ensure we have the right number of bins
        if len(fft_magnitudes) != self.num_freq_bins:
            # Resample or truncate to match
            if len(fft_magnitudes) > self.num_freq_bins:
                fft_magnitudes = fft_magnitudes[:self.num_freq_bins]
            else:
                # Pad with zeros
                padded = np.zeros(self.num_freq_bins, dtype=np.float32)
                padded[:len(fft_magnitudes)] = fft_magnitudes
                fft_magnitudes = padded
        
        # Roll the array and add new frame at the end
        self.data = np.roll(self.data, -1, axis=0)
        self.data[-1, :] = fft_magnitudes
        self.frame_index += 1
    
    def get_image_data(self):
        """Get the spectrogram data as a 2D array for display.
        Returns transposed array for proper orientation (freq x time)."""
        # Apply log scale for better visibility
        log_data = np.log10(self.data.T + 1e-10)  # Transpose and add small value to avoid log(0)
        return log_data

# Enhanced time averaging with confidence tracking
class AdaptiveFilter:
    def __init__(self, window_size=TIME_AVERAGE_BUFFER_SIZE, confidence_threshold=CONFIDENCE_THRESHOLD):
        logger.debug(f"AdaptiveFilter initialized: window_size={window_size}, confidence_threshold={confidence_threshold}")
        self.window_size = window_size
        self.pitch_buffer = []
        self.confidence_buffer = []
        self.confidence_threshold = confidence_threshold
        
    def add_measurement(self, pitch, confidence):
        if pitch is not None and not np.isnan(pitch):
            logger.debug(f"AdaptiveFilter.add_measurement: pitch={pitch:.2f}, confidence={confidence:.3f}")
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
        logger.debug(f"BeatDetector initialized: sample_rate={sample_rate}, history_size={history_size}")
        self.sample_rate = sample_rate
        self.beat_history = []
        self.history_size = history_size
        self.last_envelope = None

        # Rolling buffer of audio samples used for envelope/beat analysis.
        # We keep roughly 2 seconds of history to resolve low beat rates
        # down to ~0.5 Hz.
        self.window_seconds = 2.0
        self.max_samples = int(self.sample_rate * self.window_seconds)
        self._buffer = np.array([], dtype=np.float32)
        
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
        """Detect beats through amplitude modulation analysis.

        A rolling buffer of several chunks (≈2 seconds) is used so that
        we have enough temporal aperture to resolve low beat
        frequencies.
        """
        # Append new samples to the rolling buffer
        if audio_data is None or len(audio_data) == 0:
            return None, None, 0.0

        # Ensure float32 for processing
        audio_data = np.asarray(audio_data, dtype=np.float32)
        self._buffer = np.concatenate([self._buffer, audio_data]) if self._buffer.size else audio_data.copy()

        # Keep only the most recent window
        if self._buffer.size > self.max_samples:
            self._buffer = self._buffer[-self.max_samples :]

        if self._buffer.size < 512:  # Need minimum data
            return None, None, 0.0
        
        work_data = self._buffer

        # Create bandpass filter for target frequency range
        filter_params = self.create_bandpass_filter(freq_min, freq_max)
        if filter_params is None:
            return None, None, 0.0
        
        b, a = filter_params
        
        try:
            # Apply bandpass filter
            filtered_signal = filtfilt(b, a, work_data)
            
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
            logger.exception("Beat detection error")
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
            # Time between samples (seconds per sample), not total duration
            dt = 1.0 / self.sample_rate
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
            logger.exception("Envelope analysis error")
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

# Initialize spectrogram data
main_spectrogram = SpectrogramData(max_frames=100, num_freq_bins=512) if SHOW_MAIN_SPECTROGRAM else None
beat_spectrogram = SpectrogramData(max_frames=100, num_freq_bins=256) if SHOW_BEAT_SPECTROGRAM else None

# Initialize pitch scatter data
pitch_scatter_history = []  # [(frequency, confidence, timestamp), ...]
max_pitch_scatter_points = 200

# Track beat detection state for UI updates
previous_beat_state = True

def toggle_beat_plots_visibility(show_plots):
    """Show or hide beat detection plots"""
    logger.debug(f"toggle_beat_plots_visibility: show_plots={show_plots}")
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
            
    except Exception:
        logger.exception("Error toggling beat plot visibility")

def update_beat_displays(envelope, beat_frequency, beat_stability):
    """Update all beat detection visualizations"""
    global beat_data, envelope_data, beatrate_data
    
    try:
        # Update beat spectrogram (NEW)
        if beat_spectrogram and beat_spectrogram_img and envelope is not None and len(envelope) > 64:
            # Compute FFT of envelope for beat spectrogram
            envelope_fft = np.fft.fft(envelope - np.mean(envelope))
            envelope_magnitude = np.abs(envelope_fft[:len(envelope)//2])
            # Normalize
            if np.max(envelope_magnitude) > 0:
                envelope_magnitude = envelope_magnitude / np.max(envelope_magnitude)
            beat_spectrogram.add_frame(envelope_magnitude)
            beat_spec_data = beat_spectrogram.get_image_data()
            beat_spectrogram_img.setImage(beat_spec_data, autoLevels=True)
        
        # Update envelope display over the full rolling window
        mod_depth = 0.0
        if SHOW_ENVELOPE and envelope is not None and len(envelope) > 0:
            envelope_data = envelope
            env_arr = np.asarray(envelope_data, dtype=np.float32)
            env_mean = float(np.mean(env_arr)) if env_arr.size else 0.0
            if env_mean > 0:
                mod_depth = float(np.clip((env_arr.max() - env_arr.min()) / env_mean, 0.0, 2.0))
            # X-axis in seconds so we see the full ~2s window
            x_envelope = np.arange(len(envelope_data)) / RATE
            envelope_curve.setData(x_envelope, envelope_data)
            try:
                envelope_plot.setXRange(0, len(envelope_data) / RATE)
            except Exception:
                pass
        
        # Update beat scatter: x = beat frequency (Hz), y = modulation depth,
        # dot size encodes *inverse* stability (larger = less stable).
        if SHOW_BEAT_SCATTER and beat_frequency > 0:
            beat_data.append(beat_frequency)
            depth_data.append(mod_depth)
            stability_data.append(beat_stability)

            # Keep only the most recent N points
            max_points = 100
            if len(beat_data) > max_points:
                beat_data.pop(0)
                depth_data.pop(0)
                stability_data.pop(0)

            x_vals = np.array(beat_data, dtype=float)
            y_vals = np.array(depth_data, dtype=float)
            stab_vals = np.clip(np.array(stability_data, dtype=float), 0.0, 1.0)

            # Base size plus a stability term: 0 -> small, 1 -> large
            base_size = 4.0
            extra_size = 10.0
            sizes = base_size + stab_vals * extra_size

            # Colour encodes age of the point: oldest ~black, newest bright.
            n_pts = len(x_vals)
            if n_pts > 0:
                ages = np.linspace(0.1, 1.0, n_pts)  # 0.1 to avoid fully black
                brushes = [pg.mkBrush(0, int(255 * a), 0, 255) for a in ages]
            else:
                brushes = None

            beat_curve.setData(x=x_vals, y=y_vals, size=sizes, brush=brushes)
            # Axes labels and ranges for the scatter view
            beat_plot.setLabel('bottom', 'Beat frequency (Hz)')
            beat_plot.setLabel('left', 'Mod depth')
            try:
                beat_plot.setXRange(BEAT_FREQUENCY_RANGE[0], BEAT_FREQUENCY_RANGE[1])
                beat_plot.setYRange(0, 2.0)
            except Exception:
                pass
        
        # Update beat rate history (smoothed) using beat frequency history
        if SHOW_BEAT_HISTORY and len(beat_data) >= 5:  # Need some history for smoothing
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
        
        # Update beat detection label (fixed-width text to avoid flicker)
        if beat_frequency > 0.1:
            beat_line = f"Beat: {beat_frequency:6.2f} Hz"
            stab_line = f"Stab: {beat_stability * 100:5.1f}%"
            if beat_stability > 0.8:
                status = "STABLE"
                color = "#006400"  # dark green
            elif beat_stability > 0.5:
                status = "MODERATE"
                color = "#FF4500"  # dark orange
            else:
                status = "UNSTABLE"
                color = "#8B0000"  # dark red
            status_line = f"Status: {status.ljust(8)}"

            beat_label.setHtml(
                f'<div style="color: {color}; font-weight: bold;">'
                f'{beat_line}<br>{stab_line}<br>{status_line}'
                f'</div>'
            )
            beat_label.setPos(15, 8)  # Position in beat plot - moved right
        else:
            # Always three lines with padded placeholders to keep label size stable
            beat_line = "Beat:   --.-- Hz"
            stab_line = "Stab:   --.-%"
            status_line = "Status: NONE    "
            beat_label.setHtml(
                '<div style="color: #666666; font-weight: bold;">'
                f'{beat_line}<br>{stab_line}<br>{status_line}'
                '</div>'
            )
            beat_label.setPos(15, 8)  # Position in beat plot - moved right
            
    except Exception:
        logger.exception("Beat display update error")

def calculate_grid_layout(num_plots):
    """Calculate optimal grid dimensions based on number of plots.
    Returns (rows, cols) tuple."""
    if num_plots == 0:
        return (1, 1)
    elif num_plots == 1:
        return (1, 1)
    elif num_plots <= 4:
        return (2, 2)
    elif num_plots <= 6:
        return (2, 3)
    else:  # 7-9 plots
        return (3, 3)

app = pg.mkQApp()
win = pg.GraphicsLayoutWidget(show=True)
win.setWindowTitle(f'Live Frequency Analysis - {device_name}')

# Count enabled plots
enabled_plots = sum([SHOW_MAIN_SPECTRUM, SHOW_BEAT_SCATTER, SHOW_ENVELOPE, 
                     SHOW_BEAT_HISTORY, SHOW_MAIN_SPECTROGRAM, 
                     SHOW_BEAT_SPECTROGRAM, SHOW_PITCH_SCATTER])

# Determine grid layout
rows, cols = calculate_grid_layout(enabled_plots)
logger.info(f"Grid layout: {rows}x{cols} for {enabled_plots} plots")

# Resize window based on grid
win.resize(400 * cols, 300 * rows)

# Create all plots in order, adding to grid dynamically
plot_index = 0

# 1. Main frequency spectrum plot
if SHOW_MAIN_SPECTRUM:
    row, col = plot_index // cols, plot_index % cols
    plot = win.addPlot(row=row, col=col, title='Frequency Spectrum')
    plot.showGrid(x=True, y=True)
    plot.setYRange(0, 1)
    plot.setXRange(20, 5000)
    plot.setLabel('left', 'Magnitude')
    plot.setLabel('bottom', 'Frequency (Hz)')
    plot_index += 1
else:
    plot = None

# 2. Beat detection scatter plot
if SHOW_BEAT_SCATTER:
    row, col = plot_index // cols, plot_index % cols
    beat_plot = win.addPlot(row=row, col=col, title='Beat Detection')
    beat_plot.showGrid(x=True, y=True)
    beat_plot.setYRange(0, 10)
    beat_plot.setXRange(0, 100)
    beat_plot.setLabel('left', 'Beat Frequency (Hz)')
    beat_plot.setLabel('bottom', 'Time (samples)')
    plot_index += 1
else:
    beat_plot = None

# 3. Pitch scatter plot (NEW)
if SHOW_PITCH_SCATTER:
    row, col = plot_index // cols, plot_index % cols
    pitch_scatter_plot = win.addPlot(row=row, col=col, title='Pitch Detection')
    pitch_scatter_plot.showGrid(x=True, y=True)
    pitch_scatter_plot.setYRange(FMIN_FROM_CONFIG, FMAX_FROM_CONFIG)
    pitch_scatter_plot.setXRange(0.5, 1.0)  # Only show higher confidence
    pitch_scatter_plot.setLabel('left', 'Frequency (Hz)')
    pitch_scatter_plot.setLabel('bottom', 'Confidence')
    plot_index += 1
else:
    pitch_scatter_plot = None

# 4. Main spectrogram (NEW)
if SHOW_MAIN_SPECTROGRAM:
    row, col = plot_index // cols, plot_index % cols
    main_spectrogram_plot = win.addPlot(row=row, col=col, title='Main Spectrogram')
    main_spectrogram_plot.showGrid(x=False, y=True)
    main_spectrogram_plot.setLabel('left', 'Time (s)')  # Swapped
    main_spectrogram_plot.setLabel('bottom', 'Frequency (Hz)')  # Swapped
    plot_index += 1
else:
    main_spectrogram_plot = None

# 5. Beat spectrogram (NEW)
if SHOW_BEAT_SPECTROGRAM:
    row, col = plot_index // cols, plot_index % cols
    beat_spectrogram_plot = win.addPlot(row=row, col=col, title='Beat Spectrogram')
    beat_spectrogram_plot.showGrid(x=False, y=True)
    beat_spectrogram_plot.setLabel('left', 'Time (s)')  # Swapped
    beat_spectrogram_plot.setLabel('bottom', 'Beat Frequency (Hz)')  # Swapped
    plot_index += 1
else:
    beat_spectrogram_plot = None

# 6. Envelope plot
if SHOW_ENVELOPE:
    row, col = plot_index // cols, plot_index % cols
    envelope_plot = win.addPlot(row=row, col=col, title='Amplitude Envelope')
    envelope_plot.showGrid(x=True, y=True)
    envelope_plot.setLabel('left', 'Amplitude')
    envelope_plot.setLabel('bottom', 'Time (s)')
    plot_index += 1
else:
    envelope_plot = None

# 7. Beat rate history plot
if SHOW_BEAT_HISTORY:
    row, col = plot_index // cols, plot_index % cols
    beatrate_plot = win.addPlot(row=row, col=col, title='Beat Rate History')
    beatrate_plot.showGrid(x=True, y=True)
    beatrate_plot.setYRange(0, 5)
    beatrate_plot.setXRange(0, 50)
    beatrate_plot.setLabel('left', 'Beat Rate (Hz)')
    beatrate_plot.setLabel('bottom', 'Time')
    plot_index += 1
else:
    beatrate_plot = None

# Store references for show/hide functionality
beat_plots = []
if beat_plot:
    beat_plots.append(beat_plot)
if envelope_plot:
    beat_plots.append(envelope_plot)
if beatrate_plot:
    beat_plots.append(beatrate_plot)

# === Add plot items (curves, images, scatter plots) ===

# Main spectrum plot items
if plot:
    # Frequency range region (behind other elements)
    region = pg.LinearRegionItem(brush=(0, 255, 0, 30), pen=(0, 255, 0, 80))
    plot.addItem(region)
    # Main spectrum curve
    curve = plot.plot(fillLevel=0, fillOutline=True, brush='y')
    # Pitch detection label
    peak_label = pg.TextItem(text="", color=(0, 0, 0), anchor=(0, 0), border='w', fill=(255, 255, 255, 240))
    peak_label.setFont(QtGui.QFont('Arial', 12, QtGui.QFont.Weight.Bold))
    plot.addItem(peak_label)
    peak_label.setPos(50, 0.9)
    peak_label.setZValue(100)
    # Device name label
    device_label = pg.TextItem(text=f"Input: {device_name}", color=(0, 0, 0), anchor=(1, 0), border='w', fill=(200, 220, 255, 240))
    device_label.setFont(QtGui.QFont('Arial', 10, QtGui.QFont.Weight.Normal))
    plot.addItem(device_label)
    device_label.setPos(4950, 0.9)
    device_label.setZValue(100)
else:
    region = curve = peak_label = device_label = None

# Beat detection scatter plot items
if beat_plot:
    beat_curve = pg.ScatterPlotItem(pen=None)
    beat_plot.addItem(beat_curve)
    # Beat detection label
    beat_label = pg.TextItem(text="", color=(0, 0, 0), anchor=(0.5, 1), border='w', fill=(255, 255, 255, 240))
    beat_label.setFont(QtGui.QFont('Courier New', 11, QtGui.QFont.Weight.Bold))
    beat_plot.addItem(beat_label)
    beat_label.setZValue(100)
else:
    beat_curve = beat_label = None

# Pitch scatter plot items (NEW)
if pitch_scatter_plot:
    pitch_scatter_curve = pg.ScatterPlotItem(pen=None)
    pitch_scatter_plot.addItem(pitch_scatter_curve)
else:
    pitch_scatter_curve = None

# Main spectrogram items (NEW)
if main_spectrogram_plot and main_spectrogram:
    # Create ImageItem for heatmap display
    main_spectrogram_img = pg.ImageItem()
    main_spectrogram_plot.addItem(main_spectrogram_img)
    # Set color map (viridis-like)
    colormap = pg.colormap.get('viridis')
    main_spectrogram_img.setColorMap(colormap)
else:
    main_spectrogram_img = None

# Beat spectrogram items (NEW)
if beat_spectrogram_plot and beat_spectrogram:
    beat_spectrogram_img = pg.ImageItem()
    beat_spectrogram_plot.addItem(beat_spectrogram_img)
    colormap = pg.colormap.get('viridis')
    beat_spectrogram_img.setColorMap(colormap)
else:
    beat_spectrogram_img = None

# Envelope plot items
if envelope_plot:
    envelope_curve = envelope_plot.plot(pen='b')
else:
    envelope_curve = None

# Beat rate history plot items
if beatrate_plot:
    beatrate_curve = beatrate_plot.plot(pen='g', symbol='o', symbolSize=3)
    target_beat_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('g', width=2, style=QtCore.Qt.PenStyle.DashLine))
    beatrate_plot.addItem(target_beat_line)
    target_beat_line.setPos(1.0)  # Default target: 1 Hz
else:
    beatrate_curve = target_beat_line = None

# === Data buffers ===
beat_data = []           # beat frequency history (Hz)
depth_data = []          # modulation depth history
stability_data = []      # stability values history (0-1)
envelope_data = []
beatrate_data = []


def calculate_fft(data):
    """Calculate FFT of audio data, returning raw amplitudes."""
    N = len(data)
    # Apply Hanning window to reduce spectral leakage
    windowed_data = data * np.hanning(N)
    discrete_fourier_transform = fft(windowed_data)
    amplitude_spectrum = np.abs(discrete_fourier_transform)
    frequencies = fftfreq(N, 1/RATE)
    Nyquist_frequency = N // 2
    frequencies = frequencies[:Nyquist_frequency]
    amplitude_spectrum = amplitude_spectrum[:Nyquist_frequency]
    return frequencies, amplitude_spectrum

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
    except OSError:
        logger.exception("Error on stream.read()")
        return
    
    # Use configuration loaded once at startup.
    fmin_from_input = FMIN_FROM_CONFIG
    fmax_from_input = FMAX_FROM_CONFIG
    current_beat_enabled = BEAT_ENABLED_FROM_CONFIG

    if region:
        region.setRegion([fmin_from_input, fmax_from_input])

    # Convert to numpy array and apply windowing
    data = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    
    # Calculate FFT once (raw amplitudes)
    xf, yf_raw = calculate_fft(data)
    
    # Normalize for display in main spectrum plot
    if curve:
        yf_normalized = yf_raw / np.max(yf_raw) if np.max(yf_raw) > 0 else yf_raw
        curve.setData(xf, yf_normalized)
    
    # Update main spectrogram with raw (non-normalized) FFT data
    if main_spectrogram and main_spectrogram_img:
        main_spectrogram.add_frame(yf_raw)
        spectrogram_data = main_spectrogram.get_image_data()
        main_spectrogram_img.setImage(spectrogram_data, autoLevels=True)

    # YIN pitch detection with windowed data
    windowed_data = data * np.hanning(len(data))
    
    try:
        # Clamp fmin to YIN's minimum valid value to avoid runtime errors.
        yin_fmin = max(fmin_from_input, MIN_YIN_FMIN)
        if yin_fmin >= fmax_from_input:
            # Configuration is invalid; skip detection for this frame.
            raise ValueError(f"Invalid YIN range: fmin={yin_fmin}, fmax={fmax_from_input}")

        pitch = librosa.yin(
            windowed_data,
            fmin=yin_fmin,
            fmax=fmax_from_input,
            sr=RATE,
            frame_length=CHUNK,
        )

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
            
            # Update pitch scatter plot (NEW)
            if pitch_scatter_curve and filtered_pitch:
                pitch_scatter_history.append((filtered_pitch, avg_confidence))
                if len(pitch_scatter_history) > max_pitch_scatter_points:
                    pitch_scatter_history.pop(0)
                
                # Prepare data for scatter plot
                if len(pitch_scatter_history) > 0:
                    confidences = np.array([p[1] for p in pitch_scatter_history])
                    frequencies = np.array([p[0] for p in pitch_scatter_history])
                    
                    # Size based on confidence
                    sizes = 5 + confidences * 10
                    
                    # Color based on age (newest = bright, oldest = dim)
                    n_pts = len(confidences)
                    ages = np.linspace(0.2, 1.0, n_pts)
                    brushes = [pg.mkBrush(int(255 * a), int(100 * a), 255, 255) for a in ages]
                    
                    pitch_scatter_curve.setData(x=confidences, y=frequencies, size=sizes, brush=brushes)
            
            # Beat detection analysis
            beat_frequency = 0.0
            beat_stability = 0.0
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
            
            if peak_label:
                if filtered_pitch and avg_confidence >= CONFIDENCE_THRESHOLD:
                    # High confidence - display pitch information only
                    note = librosa.hz_to_note(filtered_pitch, cents=True)
                    peak_label.setHtml(
                        f'<div style="color: #006400; font-weight: bold;">'
                        f'{filtered_pitch:.2f} Hz<br>{note}<br>Conf: {avg_confidence:.1%}'
                        f'</div>'
                    )
                elif filtered_pitch:
                    # Low confidence - display with orange color
                    note = librosa.hz_to_note(filtered_pitch, cents=True)
                    peak_label.setHtml(
                        f'<div style="color: #FF4500; font-weight: bold;">'
                        f'{filtered_pitch:.2f} Hz<br>{note}<br>Conf: {avg_confidence:.1%}'
                        f'</div>'
                    )
                else:
                    # No valid measurement - keep three lines to avoid flicker
                    peak_label.setHtml(
                        '<div style="color: #8B0000; font-weight: bold;">'
                        'No signal detected<br>--<br>Conf: --'
                        '</div>'
                    )
        elif peak_label:
            # Out of range - still use three lines
            peak_label.setHtml(
                '<div style="color: #8B0000; font-weight: bold;">'
                'Out of range<br>--<br>Conf: --'
                '</div>'
            )
            
    except Exception:
        logger.exception("Error in pitch detection")
        # Detection error - also three lines
        if peak_label:
            peak_label.setHtml(
                '<div style="color: #8B0000; font-weight: bold;">'
                'Detection Error<br>--<br>Conf: --'
                '</div>'
            )


timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(50)  # Update interval in milliseconds - reduced for stability

# Start the application
logger.info("Starting frequency analyzer")
stream.start_stream()
logger.info("Audio stream started")
try:
    app.exec()
finally:
    # Clean up
    logger.info("Shutting down frequency analyzer")
    stream.stop_stream()
    stream.close()
    p.terminate()
    logger.info("Frequency analyzer shutdown complete")
