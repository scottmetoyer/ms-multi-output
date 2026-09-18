#!/usr/bin/env python3
"""Exact-frame duplication: the instrument that found the ring-depth defect.

WHY THIS AND NOT A SPECTRUM OR A PHASE TRACK. Six indirect metrics failed on
this problem because none had ground truth: on drum material "defect" and
"that is what a kick looks like" are inseparable, and every comparison pitted a
tap channel against the stereo *mix*, which cannot duplicate or freeze and so
always looks cleaner. Exact 32-bit sample equality needs no threshold, no
model, and no reference recording -- two frames either are the same bytes or
they are not.

WHAT IT MEANS. A USB TX ring that cannot hold one refill period underruns and
re-sends stale slots, so the stream repeats itself at a lag equal to the RING
CAPACITY in frames (`depth x frames_per_transfer`). That is a structural
constant, which is what makes this diagnostic rather than suggestive:

    lag == depth * frames_per_transfer   ->  ring underrun (FIRMWARE.md rule 12)
    rewind events ~= one per audio tick  ->  the ring laps every block
    run length   == frames_per_transfer  ->  one transfer's worth re-sent

Measured history, all in captures/:

    stock / stock path      0.03%   coincidence floor on 16-bit material
    rung 4, 5  (depth 9)    ~0%     54-frame ring, no lapping
    rung 6,7,8 (depth 4)    ~25%    at lag 24 == 4 slots x 6 frames
    rung 10    (depth 8)    0.00%   48-frame ring

Near-silence is excluded: silent runs are trivially "duplicates" and swamp the
result on percussive material.

    .venv/bin/python tools/analyse_dupes.py captures/foo.wav [more.wav ...]
"""
import argparse
import struct
import sys

import numpy as np

FS32 = 2 ** 31


def read_wav(path):
    """Minimal RIFF reader. Kept inline so tools/ is self-contained."""
    raw = open(path, "rb").read()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        sys.exit(f"{path}: not a RIFF/WAVE file")
    i, fmt, data = 12, None, None
    while i + 8 <= len(raw):
        cid = raw[i:i + 4]
        sz = struct.unpack_from("<I", raw, i + 4)[0]
        if cid == b"fmt ":
            fmt = raw[i + 8:i + 8 + sz]
        elif cid == b"data":
            data = raw[i + 8:i + 8 + sz]
        i += 8 + sz + (sz & 1)
    if fmt is None or data is None:
        sys.exit(f"{path}: missing fmt or data chunk")
    tag, ch, rate, _, align, bits = struct.unpack_from("<HHIIHH", fmt, 0)
    sub = struct.unpack_from("<H", fmt, 24)[0] if tag == 0xFFFE and len(fmt) >= 40 else tag
    if sub == 3 and bits == 32:
        f = np.frombuffer(data, dtype="<f4").astype(np.float64)
        ints = None
    elif bits == 32:
        ints = np.frombuffer(data, dtype="<i4")
        f = ints.astype(np.float64) / FS32
    elif bits == 16:
        ints = np.frombuffer(data, dtype="<i2").astype(np.int32) * (2 ** 16)
        f = ints.astype(np.float64) / FS32
    else:
        sys.exit(f"{path}: unhandled bit depth {bits}")
    n = (f.size // ch) * ch
    f = f[:n].reshape(-1, ch)
    ints = ints[:n].reshape(-1, ch) if ints is not None else None
    return f, ints, rate, bits, sub


def analyse(v, rate, maxlag, floor):
    pk = int(np.abs(v).max())
    loud = np.abs(v) > pk * floor
    rates = {}
    for lag in range(1, maxlag + 1):
        m = loud[lag:] & loud[:-lag]
        if m.sum() < 1000:
            continue
        rates[lag] = float((v[lag:][m] == v[:-lag][m]).mean())
    if not rates:
        return None
    best = max(rates, key=rates.get)
    return best, rates[best], rates


def cadence(v, lag, floor):
    """Rewind events and how long each replay runs. The spacing says how often
    the ring laps; the run length says how much is re-sent each time."""
    pk = int(np.abs(v).max())
    loud = np.abs(v) > pk * floor
    eq = np.zeros(v.size, dtype=bool)
    eq[lag:] = (v[lag:] == v[:-lag]) & loud[lag:] & loud[:-lag]
    starts = np.flatnonzero(eq & ~np.concatenate(([False], eq[:-1])))
    ends = np.flatnonzero(eq & ~np.concatenate((eq[1:], [False])))
    n = min(starts.size, ends.size)
    if n == 0:
        return None
    runlen = ends[:n] - starts[:n] + 1
    keep = runlen >= 3
    return starts[:n][keep], runlen[keep]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav", nargs="+")
    ap.add_argument("--maxlag", type=int, default=128)
    ap.add_argument("--floor", type=float, default=0.02,
                    help="fraction of peak below which samples are ignored")
    args = ap.parse_args()

    for path in args.wav:
        x, ints, rate, bits, sub = read_wav(path)
        if ints is None:
            print(f"\n{path}: float capture -- re-capture with pcm_s32le")
            continue
        nf, nch = x.shape
        print(f"\n=== {path}  {nch} ch, {rate} Hz, {bits}-bit, {nf/rate:.2f}s")
        if bits != 32:
            print("  note: 16-bit capture, exact-equality rates run high by chance")
        for c in range(nch):
            v = ints[:, c].astype(np.int64)
            if not np.any(v):
                print(f"  ch{c+1}  (silent)")
                continue
            # A constant / DC channel is trivially 100% "duplicated" at EVERY
            # lag. Reporting that as DUPLICATION is a false alarm that looks
            # exactly like the ring defect. Muted tracks on the M:S sit at a
            # tiny DC value (~-129 dBFS), not at exact zero, so this is the
            # normal state of a soloed-out track, not a fault.
            uniq = np.unique(v)
            if uniq.size < 16:
                pkdb = 20*np.log10(np.abs(v).max()/2**31)
                print(f"  ch{c+1}  CONSTANT/DC -- {uniq.size} distinct value(s), "
                      f"peak {pkdb:.1f} dBFS. Not audio; no duplication verdict.")
                continue
            r = analyse(v, rate, args.maxlag, args.floor)
            if r is None:
                print(f"  ch{c+1}  too little loud material")
                continue
            best, rate_best, rates = r
            verdict = "CLEAN" if rate_best < 0.01 else "DUPLICATION"
            print(f"  ch{c+1}  best lag {best:3d} = {rate_best*100:6.2f}%   {verdict}")
            if rate_best < 0.01:
                continue
            cad = cadence(v, best, args.floor)
            if cad is None:
                continue
            starts, runlen = cad
            if starts.size < 2:
                continue
            print(f"        {starts.size} rewind events = {starts.size/(nf/rate):.0f}/s"
                  f"   (audio tick is {rate/32:.0f}/s)")
            print(f"        replay run: median {np.median(runlen):.0f} frames, "
                  f"max {runlen.max()}   gap median {np.median(np.diff(starts)):.0f}")
            print(f"        => if lag {best} == depth x frames_per_transfer, this is"
                  f" a ring underrun (rule 12)")


if __name__ == "__main__":
    main()
