#!/usr/bin/env python3
import signal
import sys
from datetime import datetime
import lameenc
import numpy as np
import soundcard as sc
#pip install soundcard lameenc numpy

SAMPLE_RATE = 48000
CHANNELS    = 2
CHUNK       = 4096
BITRATE     = 320

running = True

def stop(sig, frame):
    global running
    running = False

signal.signal(signal.SIGINT, stop)

def pick_device():
    mics = sc.all_microphones(include_loopback=True)
    if not mics:
        sys.exit("No audio input/loopback devices found.")

    loopbacks = [m for m in mics if "loopback" in m.name.lower() or "monitor" in m.name.lower()]
    if len(loopbacks) == 1:
        print(f"Using: {loopbacks[0].name}")
        return loopbacks[0]

    print("\nAvailable devices:")
    for i, m in enumerate(mics):
        print(f"  [{i}] {m.name}")
    while True:
        try:
            idx = int(input("Select index: "))
            if 0 <= idx < len(mics):
                return mics[idx]
        except (ValueError, KeyboardInterrupt):
            sys.exit()

def main():
    device    = pick_device()
    output    = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
    encoder   = lameenc.Encoder()
    encoder.set_bit_rate(BITRATE)
    encoder.set_in_sample_rate(SAMPLE_RATE)
    encoder.set_channels(CHANNELS)
    encoder.set_quality(2)

    print(f"Recording → {output}\nCtrl+C to stop.\n")

    with open(output, "wb") as f, \
         device.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS) as mic:
        while running:
            data = mic.record(numframes=CHUNK)
            pcm  = (data * 32767).astype(np.int16)
            f.write(encoder.encode(pcm.tobytes()))

        f.write(encoder.flush())

    print(f"Saved: {output}")

if __name__ == "__main__":
    main()
