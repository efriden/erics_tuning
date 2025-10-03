import pyaudio
import numpy as np
import pyqtgraph as pg
import librosa
from scipy.fft import fft, fftfreq
from pyqtgraph.Qt import QtCore, QtGui
from number_input import start_gui_thread, get_value1, get_value2

# Start the GUI (it runs in background)
start_gui_thread()

# Parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1              # Mono audio
RATE = 44100              # Sampling rate (samples per second)
CHUNK = 1024 * 2        # Number of frames per buffer

TIME_AVERAGE_BUFFER_SIZE = 10

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

time_buffer = [0 for _ in range(TIME_AVERAGE_BUFFER_SIZE)]

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
    discrete_fourier_transform = fft(data)
    amplitude_spectrum = np.abs(discrete_fourier_transform)
    normalized_amplitude_spectrum = amplitude_spectrum / np.max(amplitude_spectrum)
    frequencies = fftfreq(N, 1/RATE)
    Nyquist_frequency = N // 2
    frequencies = frequencies[:Nyquist_frequency]
    normalized_amplitude_spectrum = normalized_amplitude_spectrum[:Nyquist_frequency]
    return frequencies, normalized_amplitude_spectrum


def time_average(newest_input):
    for index in range(len(time_buffer)-1):
        time_buffer[index] = time_buffer[index + 1]
    time_buffer[-1] = newest_input
    sum_sans_outliers = (sum(time_buffer) - max(time_buffer) - min(time_buffer))
    average_sans_outliers = sum_sans_outliers/(len(time_buffer)-2)
    return average_sans_outliers


def update():
    try:
        data = stream.read(CHUNK, exception_on_overflow=False)
    except OSError as e:
        print(f'Error on stream.read(): {e}')
        return
    
    fmin_from_input = get_value1()
    fmax_from_input = get_value2()

    region.setRegion([fmin_from_input, fmax_from_input])

    data = np.frombuffer(data, dtype=np.int16)
    xf, yf = calculate_fft(data)
    curve.setData(xf, yf)
    #  plot.setXRange(fmin_from_input, fmax_from_input)

    pitch = librosa.yin(data.astype(np.float32),
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

        time_averaged_pitch = time_average(detected_pitch)

        note = librosa.hz_to_note(time_averaged_pitch, cents=True)

        peak_label.setText(f"{time_averaged_pitch:.2f} \n {note}")
        peak_label.setPos(time_averaged_pitch, 0)


timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(10)  # Update interval in milliseconds

# Start the application
stream.start_stream()
app.exec()

# Clean uppip 
stream.stop_stream()
stream.close()
p.terminate()