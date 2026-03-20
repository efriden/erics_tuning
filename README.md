# Tune

## Description: 
A multiprocess distributed application for audio analysis - aimed specifically at piano tuning.

## Parts:
The project has several more or less self-sufficient parts.

 - ### Analyzer:
    A heavily threaded and config-controlled audioanalysis pipeline that wraps a pyaudiostream and does various forms of analysis. The resulting data (packed into numpy arrays and encoded into bytes objects) is sent to a zmq-layer through transponders (see below).
    (uses numpy, scipy and aubio)

 - ### Transponders:
    Transponder objects wrapps ZeroMQ socket objects into performant and plug-and-play objects. Simply initialize the object with a set of topics to subscribe or publish to, and you get simple thread-safe get and put methods that gets you the latest data.
    The transponders always communicates with a broker object that proxies and helps with the communication, so there is also a module included to start that.
    It is only tested on one-machine-setups, but in theory should work on local networks and even remotely via https.
    (uses pyzmq)

 - ### Visualizer:
    A Qt application that natively expects a transponder to get data and displays (hopefully) useful graphs and information to help with piano tuning.
    (uses pyqtgraph)

 - ### Tune tui:
    The dashboard that launches and surveys the different parts. Starts the other parts as subprocesses and communicates to them via transponder control strings.
    (uses textual)

## Examples:

`uv run tune` - launch the tui
`uv run analyzer` - launch the audio processing application
`uv run visualizer` - launch the graphing app
`uv run broker` - start a broker instance
