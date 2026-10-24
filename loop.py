#!/usr/bin/env python3

import argparse
import sys
import wave
from pathlib import Path
# py.exe -m pip install numpy soundfile

import numpy as np

try:
    import soundfile as sf
except ImportError:
    sf = None

BUDGETS_MS = [1, 2, 5, 10, 20, 50, 100, 200, 500]
TOLS = [0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0]


def load(path):
    """Retourne (données float64 shape (n, ch), samplerate, info_écriture)."""
    if sf is not None:
        data, sr = sf.read(path, dtype="float64", always_2d=True)
        info = sf.info(path)
        return data, sr, ("sf", info.subtype, info.format)
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        a = np.frombuffer(raw, "<i2").astype(np.float64) / 32768
    elif sw == 4:
        a = np.frombuffer(raw, "<i4").astype(np.float64) / 2147483648
    elif sw == 1:
        a = (np.frombuffer(raw, "u1").astype(np.float64) - 128) / 128
    else:
        sys.exit("WAV 24 bits: installe soundfile (pip install soundfile)")
    return a.reshape(-1, ch), sr, ("wave", sw)


def save(path, data, sr, info):
    if info[0] == "sf":
        sf.write(path, data, sr, subtype=info[1], format=info[2])
        return
    sw = info[1]
    if sw == 2:
        out = np.clip(np.round(data * 32768), -32768, 32767).astype("<i2")
    elif sw == 4:
        out = np.clip(np.round(data * 2147483648), -2147483648, 2147483647).astype("<i4")
    else:
        out = np.clip(np.round(data * 128 + 128), 0, 255).astype("u1")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(data.shape[1])
        w.setsampwidth(sw)
        w.setframerate(sr)
        w.writeframes(out.tobytes())


def error_for_total_cut(x, k):
    """Pour un total k retiré, meilleure répartition (a début, b=k-a fin). -> (erreur, a) ou None."""
    n = len(x)
    a = np.arange(k + 1)
    b = k - a
    ok = (a + 2 < n - 1 - b - 1) & (n - 2 - b >= 0)
    a, b = a[ok], b[ok]
    if len(a) == 0:
        return None
    first, nxt = x[a], x[a + 1]
    last, prv = x[n - 1 - b], x[n - 2 - b]
    jump = first - last
    err = np.maximum.reduce([np.abs(jump),
                             np.abs(jump - (last - prv)),
                             np.abs((nxt - first) - jump)]).max(axis=1)
    i = int(err.argmin())
    return float(err[i]), int(a[i])


def find_loop(x, sr):
    """Retourne (a, b, erreur, tol) ou None si FAIL."""
    n = len(x)
    d = np.abs(np.diff(x, axis=0))
    step = np.median(d) or d.mean()
    if step == 0:
        return None
    max_cut = n // 4
    limits = sorted({min(int(ms * sr / 1000), max_cut) for ms in BUDGETS_MS} | {max_cut})
    emin, amin = [], []
    k = 0
    for limit in limits:
        while k <= limit:
            r = error_for_total_cut(x, k)
            emin.append(r[0] if r else np.inf)
            amin.append(r[1] if r else 0)
            k += 1
        e = np.array(emin)
        for tol in TOLS:
            good = np.nonzero(e <= tol * step)[0]
            if len(good):
                kk = int(good[0])
                return amin[kk], kk - amin[kk], float(e[kk]) / step, tol
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input")
    p.add_argument("-o", "--output")
    args = p.parse_args()

    src = Path(args.input)
    x, sr, info = load(src)
    res = find_loop(x, sr)
    if res is None:
        print("FAIL : aucune jonction trouvée (tous les paliers de coupe et d'exigence essayés). Aucun fichier écrit.")
        sys.exit(1)
    a, b, err, tol = res

    y = x[a:len(x) - b]
    out = Path(args.output) if args.output else src.with_name(src.stem + "_loop" + src.suffix)
    save(out, y, sr, info)

    ms = lambda s: f"{s / sr * 1000:.1f} ms"
    what = "rien (déjà bouclable)" if not (a or b) else "début" if not b else "fin" if not a else "début et fin"
    print("SUCCÈS : jonction trouvée")
    print(f"Coupe       : {what}")
    print(f"Début coupé : {a} éch. ({ms(a)})")
    print(f"Fin coupée  : {b} éch. ({ms(b)})")
    print(f"Durée       : {len(x) / sr:.4f} s -> {len(y) / sr:.4f} s")
    print(f"Exigence    : trouvée au niveau {tol}x le pas médian (erreur réelle {err:.2f}x)")
    print(f"Fichier     : {out}")


if __name__ == "__main__":
    main()
