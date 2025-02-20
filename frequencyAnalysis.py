import pyaudio
import numpy as np
import pyqtgraph as pg
import librosa
from scipy.fftpack import fft
from pyqtgraph.Qt import QtCore
from pyqtgraph.Qt import QtGui

# Parameters
FORMAT = pyaudio.paInt32  # Audio format (32-bit)
CHANNELS = 1              # Mono audio
RATE = 44100              # Sampling rate (samples per second)
CHUNK = 1024 * 4          # Number of frames per buffer

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


app = pg.mkQApp()
win = pg.GraphicsLayoutWidget(show=True)
win.setWindowTitle('Live Frequency Analysis')
plot = win.addPlot()
#plot.setYRange(-10, 10**3)         # Adjust y-axis limits
plot.setXRange(20, 5000)    # Limit x-axis to audible frequencies (20Hz - 20kHz)
plot.setAutoVisible(x=False, y=True)
#plot.setLogMode(x=False, y=True)  # Logarithmic scale for frequencies
plot.setLabel('left', 'Magnitude')
plot.setLabel('bottom', 'Frequency (Hz)')


curve = plot.plot(pen='y')


peak_label = pg.TextItem(text="", color='r', anchor=(0.5, 1), border='w', fill=(0, 0, 255))
peak_label.setFont(QtGui.QFont('Mono', 14))  # Set font size and style
plot.addItem(peak_label)


def calculate_fft(data):
    N = len(data)
    yf = fft(data)
    xf = np.linspace(0, RATE, N)
    return xf, N * np.abs(yf[:N])


def update():
    data = stream.read(CHUNK, exception_on_overflow=False)
    data = np.frombuffer(data, dtype=np.int32)
    xf, yf = calculate_fft(data)
    curve.setData(xf, yf)

    pitch = librosa.yin(data.astype(np.float32), fmin=20, fmax=4200, sr=RATE)

    # Get the most prominent pitch (ignore NaN values)
    pitch = pitch[~np.isnan(pitch)]
    if len(pitch) > 0:
        detected_pitch = np.median(pitch)  # Average pitch over the frame

    peak_label.setText(f"{detected_pitch:.2f}")
    peak_label.setPos(detected_pitch, 0) # peak_magnitude)


timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(10)  # Update interval in milliseconds

# Start the application
app.exec()

# Clean uppip 
stream.stop_stream()
stream.close()
p.terminate()