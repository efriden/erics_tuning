# Erics tuning

This is an in-development tuning software made for personal use in piano tuning by Eric Friden and the company rfetc.

It is coded in python, uses the Textual library for a launch tui, pyqt for graphing and pyaudio for... well, audio.

The audio analysis combines several different techniques, some from existing libraries (such as yin from librosa) and some made from scratch (like beat detection by a rolling fft window of a hamilton amplitude envelope.)