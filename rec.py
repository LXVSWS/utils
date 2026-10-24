#!/usr/bin/env python3

import signal
import sys
from datetime import datetime
import lameenc
import numpy as np
import soundcard as sc
import threading
#py.exe -m pip install lameenc soundcard numpy

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
    spk = sc.default_speaker()
    mics = sc.all_microphones(include_loopback=True)
    loopbacks = [m for m in mics if m.isloopback]

    print("\nDevices (loopback):")
    default_idx = 0
    for i, m in enumerate(loopbacks):
        mark = ""
        if m.name == spk.name:
            default_idx = i
            mark = "  (défaut)"
        print(f"  [{i}] {m.name}{mark}")

    while True:
        try:
            s = input(f"Select index [{default_idx}]: ").strip()
            idx = int(s) if s else default_idx
            if 0 <= idx < len(loopbacks):
                return loopbacks[idx]
        except ValueError:
            pass
        except (KeyboardInterrupt, EOFError):
            sys.exit()

def main():
    device    = pick_device()
    output    = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
    encoder   = lameenc.Encoder()
    encoder.set_bit_rate(BITRATE)
    encoder.set_in_sample_rate(SAMPLE_RATE)
    encoder.set_channels(CHANNELS)
    encoder.set_quality(2)

    print(f"Recording → {output}\nPress Enter to stop.\n")

    def worker(f, mic):
        while running:
            data = mic.record(numframes=CHUNK)
            pcm  = (data * 32767).astype(np.int16)
            f.write(encoder.encode(pcm.tobytes()))

    with open(output, "wb") as f, \
         device.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS) as mic:
        t = threading.Thread(target=worker, args=(f, mic), daemon=True)
        t.start()
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            pass
        stop(None, None)
        t.join(2)
        f.write(encoder.flush())

    print(f"Saved: {output}")

if __name__ == "__main__":
    main()
