# tune todo

- config centralization
  there is a lot of defaults spread around that should be collected in the yaml.

- broker logging
  id like a periodic log from the zmq broker - eg per 10 seconds '214 packages proxied' divided by topic.

- det här spectrogrammet:
https://librosa.org/doc/0.11.0/generated/librosa.pyin.html

- break datatypes into the types folder

- widen transponder to accept custom dataclasses with a 'pack' method.
  (more elegant than packing to np, then bytes, then back and back again)
  ACTUALLY - that should be the way that the system works - with built in
  typechecking.
