#!/usr/bin/env python3
"""Send an Elektron OS .syx to a Model:Samples over MIDI.

Dry-run by default. Sending requires --send, and the device must already be
sitting in the STARTUP MENU's OS UPGRADE mode:

    power off -> hold [FUNC] -> power on -> [TRIG 4]

The startup-menu upgrade does NOT work over USB MIDI (manual 13.4), so the
port must be a DIN interface wired to the Model:Samples' MIDI IN.
"""
import argparse
import sys
import time

ELEKTRON_ID = (0x00, 0x20, 0x3C)
DEV_MODEL_SAMPLES = 0x0F
DIN_BYTES_PER_SEC = 31250 / 10  # 8N1 on the MIDI wire


def split_sysex(raw: bytes) -> list[bytes]:
    """Split a .syx file into individual F0..F7 messages."""
    msgs, i = [], 0
    while True:
        start = raw.find(b"\xf0", i)
        if start < 0:
            break
        end = raw.find(b"\xf7", start)
        if end < 0:
            raise ValueError(f"unterminated sysex at offset {start}")
        msgs.append(raw[start : end + 1])
        i = end + 1
    trailing = raw[i:]
    if trailing.strip(b"\n\r\t "):
        print(f"  note: {len(trailing)} trailing bytes after the last F7 (ignored)")
    return msgs


def identify(msgs: list[bytes]) -> int:
    """Check the manufacturer id and return the device id."""
    head = msgs[0]
    if tuple(head[1:4]) != ELEKTRON_ID:
        raise SystemExit(f"!! not an Elektron sysex: header {head[:5].hex(' ')}")
    dev = head[4]
    names = {0x0F: "Model:Samples", 0x11: "Model:Cycles", 0x05: "Octatrack"}
    print(f"  manufacturer : Elektron ({bytes(ELEKTRON_ID).hex(' ')})")
    print(f"  device id    : 0x{dev:02x} ({names.get(dev, 'unknown')})")
    return dev


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("syx", help="the OS .syx to send")
    ap.add_argument("-p", "--port", help="MIDI output port name (substring match)")
    ap.add_argument("--send", action="store_true", help="actually transmit (default: dry run)")
    ap.add_argument("--ms", type=float, default=None,
                    help="fixed inter-message delay in ms; overrides --pace")
    ap.add_argument("--pace", type=float, default=1.4,
                    help="multiple of DIN wire time to wait per message (default 1.4). "
                         "1.0 is 100%% utilisation with no headroom and WILL eventually "
                         "overrun the interface's buffer; a dropped packet leaves the "
                         "device stuck on RECEIVING...")
    ap.add_argument("--allow-any-device", action="store_true",
                    help="skip the Model:Samples device-id check")
    args = ap.parse_args()

    raw = open(args.syx, "rb").read()
    msgs = split_sysex(raw)
    sizes = [len(m) for m in msgs]
    wire_s = len(raw) / DIN_BYTES_PER_SEC

    print(f"file          : {args.syx}")
    print(f"  bytes        : {len(raw):,}")
    print(f"  messages     : {len(msgs):,}  (min {min(sizes)} / max {max(sizes)} bytes)")
    dev = identify(msgs)
    print(f"  wire time    : {wire_s:,.0f} s at DIN baud ({wire_s/60:.1f} min) — a floor, not a promise")

    if dev != DEV_MODEL_SAMPLES and not args.allow_any_device:
        raise SystemExit("!! not a Model:Samples image; pass --allow-any-device if deliberate")

    import mido

    try:
        ports = mido.get_output_names()
    except ModuleNotFoundError as e:
        # `import mido` succeeds without a backend — python-rtmidi is only
        # loaded lazily on the first port query, so a missing backend surfaces
        # here as a traceback out of mido internals rather than at import.
        # Nothing has been sent at this point; the device is untouched.
        raise SystemExit(
            f"!! MIDI backend missing ({e.name}). Install it with:\n"
            "     pip install python-rtmidi\n"
            "   (mido imports fine without a backend and only fails on the first\n"
            "    port query, so nothing was sent — the device is untouched)"
        ) from None
    if not args.port:
        print("\nMIDI outputs:")
        for p in ports:
            print("   ", p)
        raise SystemExit("\npick one with --port (substring is enough)")
    match = [p for p in ports if args.port.lower() in p.lower()]
    if len(match) != 1:
        raise SystemExit(f"!! --port {args.port!r} matched {len(match)}: {match or ports}")
    port_name = match[0]
    print(f"  port         : {port_name}")

    if "model:samples" in port_name.lower():
        print("\n!! That is the device's own USB MIDI port. The STARTUP MENU upgrade")
        print("   does not work over USB — use the DIN interface's output instead.")
        if args.send:
            raise SystemExit("refusing to send over USB MIDI")

    if not args.send:
        print("\nDRY RUN — nothing sent. Re-run with --send when the device shows")
        print("OS UPGRADE mode (hold [FUNC] at power-on, then [TRIG 4]).")
        return

    # Header lines above are block-buffered when stdout is a file, which makes an
    # early progress check look like a stall. Flush before the long loop starts.
    print("\nSending. Do NOT power off, especially once the screen says UPDATING FLASH.",
          flush=True)
    t0 = time.monotonic()
    with mido.open_output(port_name) as out:
        for n, m in enumerate(msgs, 1):
            out.send(mido.Message("sysex", data=m[1:-1]))
            time.sleep(args.ms / 1000 if args.ms is not None
                       else args.pace * len(m) / DIN_BYTES_PER_SEC)
            if n % 250 == 0 or n == len(msgs):
                pct = 100 * n / len(msgs)
                el = time.monotonic() - t0
                print(f"  {n:>6,}/{len(msgs):,}  {pct:5.1f}%  {el:6.0f}s", flush=True)
    print(f"done in {time.monotonic() - t0:.0f}s — wait for the device to finish and reboot.")


if __name__ == "__main__":
    main()
