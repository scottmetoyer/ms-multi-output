# ms-multi-output

Six channels of **per-track USB audio** for the Elektron Model:Samples.

Stock, the Model:Samples sends only the stereo mix over USB. This patch sends
**each of the six tracks on its own USB channel**, so you can record real stems
straight into a DAW instead of bouncing one track at a time.

| USB channel | carries |
|---|---|
| 1 – 6 | tracks 1 – 6 |

48 kHz, 32-bit, High Speed. The device still reports itself as OS `1.13`.

---

## ⚠️ Read this before you do anything

**This flashes modified firmware to your instrument. It is not an Elektron
product, it is not supported by Elektron, and it will almost certainly void
your warranty.** It has been tested on exactly one unit.

**On Windows you need FlexASIO with the DirectSound backend** — a DAW's normal
WASAPI or ASIO settings will not open the device. See
[Platform support](#platform-support).

**You must have a MIDI DIN interface before you start.** Recovery from a bad
flash goes over MIDI DIN only — the startup-menu updater ignores USB MIDI. If
you do not own a DIN interface, stop here; a failed flash would leave you with
no way back.

The recovery path is proven and has been used many times during development
(see [Recovery](#recovery)), because the bootloader lives in a flash sector
that OS updates never write. That is the only reason flashing a modified image
is a reasonable thing to do at all. It is still your instrument and your risk.

**One functional trade-off:** this image reuses the two bootloader USB
descriptors as code space, so **`CONFIG → UPGRADE` over USB stops working**
while it is installed. The startup-menu DIN rescue is in a different section
and is unaffected. Flash the stock OS back and USB upgrade returns.

---

## What the stems actually are

Worth knowing before you build a mix around them:

- **Mono.** The audio is tapped before the summing stage, where pan is applied
  as a coefficient. **Per-track pan is not in the stems** and cannot be,
  without doubling to 12 channels.
- **Track LEVEL is baked in**, and it is linear. Turning LEVEL down turns the
  stem down.
- **The delay and reverb sends are not included.** They are derived from the
  summed main bus, not per track.
- **The stereo mix is no longer sent over USB.** Mix from the stems instead.
- **High track LEVEL distorts, on the stems and on the analogue output alike.**
  This is the voice path saturating, not the patch: measured THD on a sine goes
  from ~10% at LEVEL 100 to ~23% at LEVEL 127. If you want clean stems, keep
  LEVEL down. It is present on stock firmware too — you just could not see it
  per-track before.

---

## Platform support

| | status |
|---|---|
| **macOS** | ✅ Working — six channels, mapping verified by per-track mute test |
| **Windows** | ✅ Working — but needs FlexASIO set to DirectSound, see below |
| **Linux** | Untested — the build is pure Python and should work, but nobody has confirmed it |

### Windows: use FlexASIO with the DirectSound backend

All six channels work on Windows — but **not** through a DAW's normal WASAPI or
ASIO settings. Use FlexASIO, configured to use DirectSound:

1. Install [FlexASIO](https://github.com/dechamps/FlexASIO).
2. Set its backend to **DirectSound** — via FlexASIO Control (the GUI), or the
   `backend` setting in `FlexASIO.toml`.
3. In your DAW, select **FlexASIO** as the ASIO device.

Confirmed in Reaper with all six channels arriving.

**What does not work**, so you don't waste time on it:

| path | result |
|---|---|
| WASAPI — Mixcraft "Core Audio" | *"unable to open device"* |
| WASAPI — Reaper | *"could not find input device format"* |
| FlexASIO on other backends (KS, WASAPI) | fails |
| MME / "Wave" | opens, but MME is stereo-only — 2 of the 6 channels |
| Ableton, default settings | *"failed to open interface"* |

**This is not a descriptor fault.** Windows enumerates the device correctly,
its own Sound → Recording test works, and it reports the device as 6 channel /
32 bit / 48000 Hz. The descriptors have been decoded and checked against every
constraint Microsoft documents for the in-box `usbaudio2.sys` driver, and they
pass. The device offers exactly **one** capture format with no stereo fallback,
which appears to be why hosts demanding an exact format refuse it while
shared-mode paths — Windows' own test, MME, and DirectSound — are happy.

Note the device is **48 kHz only**. If your DAW is set to 44.1 kHz, that alone
will fail, on stock firmware as much as on this one.

If you find a cleaner route, please open an issue — especially one that works
without FlexASIO.

## Requirements

- Model:Samples running **OS 1.13** (the version this is built against)
- A **MIDI DIN interface** wired to the Model:Samples' MIDI IN — required
- Python 3.9+ — `build.py` needs only the standard library
- `mido` and `python-rtmidi`, for flashing (installed into a venv below)
- A C compiler, to build the packer in `setup.sh`
- `numpy`, only if you want the optional stream check in [Verify](#verify)

No m68k toolchain is needed. The patch ships as a listed byte table.

## Install

```sh
git clone https://github.com/scottmetoyer/ms-multi-output.git
cd ms-multi-output
./setup.sh                                # builds the .syx packer

python3 -m venv .venv                     # keeps deps off your system Python
.venv/bin/pip install mido python-rtmidi  # for flashing
.venv/bin/pip install numpy               # optional, for the stream check
```

**Use the venv rather than bare `pip`.** A stray `pip` earlier in `PATH` than
your real one will install into — or crash on — the wrong interpreter, and the
error it produces does not look like a Python problem at all. See
[Troubleshooting](#troubleshooting).

**Get the official OS yourself.** No Elektron firmware is distributed here, so
download `model-samples_OS1.13.zip` from elektron.se and unzip it.

```sh
python3 build.py --syx model-samples_OS1.13.syx
```

The build refuses unless your input is the exact OS 1.13 image, checks the
expected stock bytes at every one of the 41 patch sites, and verifies the
finished file against a known hash:

```
  applied 41 patch runs
  patched section 3 matches the tested image
  sha256 9ab326746903bd88a460914d08137e58e863d0acc814b1dc621949b009ec0169
  ✅ reproducible build: byte-identical to the tested image
```

If you do not see that last line, **do not flash it**.

## Flash

Put the device into OS upgrade mode:

> power off → hold **[FUNC]** → power on → **[TRIG 4]** (OS UPGRADE)

Dry run first — it will list your MIDI ports and check the image:

```sh
.venv/bin/python tools/flash.py ms-multi-output.syx
```

Then send it, naming your DIN output. **Pacing matters:** at exactly wire speed
a packet eventually drops and the device sits on `RECEIVING...` forever (which
looks alarming but harms nothing — power-cycle and retry).

```sh
.venv/bin/python tools/flash.py ms-multi-output.syx --port "YOUR DIN PORT" --pace 1.4 --send
```

Roughly 6–7 minutes. Do not power off, especially once the screen says
`UPDATING FLASH`. The unit reboots itself when done.

## Verify

macOS:

```sh
system_profiler SPAudioDataType | grep -A4 "Model:Samples"
#   Input Channels: 6
```

Linux: `arecord -l`, or check the device in your DAW. You should see six input
channels. Solo one track and confirm it appears on the matching channel.

Optionally check the stream is clean — play something and capture, then:

```sh
.venv/bin/python tools/analyse_dupes.py your-capture.wav
```

Every active channel should read `CLEAN`. Muted tracks read `CONSTANT/DC`,
which is normal — a silenced track sits at a tiny DC value, not exact zero.

## Recovery

If the device will not boot, is stuck, or you simply want stock back:

1. Power off, hold **[FUNC]**, power on, press **[TRIG 4]** for OS UPGRADE.
2. Send the **official** `model-samples_OS1.13.syx` over MIDI DIN:

```sh
.venv/bin/python tools/flash.py model-samples_OS1.13.syx --port "YOUR DIN PORT" --pace 1.4 --send
```

This works even when the main OS is unbootable, because the bootloader is in a
sector OS updates never touch. It does **not** work over USB MIDI.

---

## How it works

The audio engine renders each track into its own mono block in SRAM — six
blocks of 32 frames — and then sums them to stereo. The stock USB feeder is fed
from the summed stereo buffer, which is why you normally only get the mix.

This patch:

1. widens the USB audio descriptors from 2 to 6 channels, and the endpoint's
   queue-head `MaxPacketLength` to match (missing that one constant silently
   breaks the stream — it is the single most important value here);
2. re-dimensions the transfer ring for 24 bytes per frame;
3. replaces the feeder's copy loop with a stub that interleaves the six
   per-track blocks directly.

The stubs live in USB descriptor space that is dead on a High Speed host. Their
assembly sources are in [`patch/`](patch/); the exact bytes applied are in
[`patch/rung10.json`](patch/rung10.json), so nothing about this is opaque — you
can read every byte that changes and why.

**Ring depth is load-bearing.** The engine delivers 32 frames every 0.667 ms,
so the ring must span more than that or the controller re-sends stale slots —
audible as a bell-like ringing on transients. This build uses depth 8 (48
frames, 1.0 ms). An earlier build used depth 4 (24 frames) and repeated ~25% of
all frames. If you fork this, do not shrink it.

## Troubleshooting

### `pip` crashes before it installs anything

If `pip` fails with a *dynamic linker* error rather than a package error — on
macOS something like `dyld: Library not loaded: ...`, on Linux
`error while loading shared libraries: ...` — then **the interpreter is broken,
not the package.** Python cannot start, so `pip` dies before doing any work,
and whichever package you named on the command line takes the blame for it.

Two common causes:

- A Python built against a library path that has since moved or been removed.
  A version-manager build (pyenv, asdf, conda) that predates an OS, package
  manager or CPU-architecture change is the usual culprit.
- A stale `pip` script sitting earlier in `PATH` than your real one and
  pointing at that dead interpreter. `python3` can be perfectly healthy while
  every `pip` on your `PATH` is not, which makes this confusing to spot.

Work out which you have:

```sh
which pip                 # which pip are you actually getting?
head -1 "$(which pip)"    # its shebang names the interpreter it will use
python3 -m pip --version  # bypasses stray pip scripts entirely
```

Version-specific names are not automatically safe — a `pip3.N` can carry a
shebang pointing at a different, dead Python.

Fixes, best first:

1. **Use the venv** from [Install](#install). `python3 -m venv .venv` builds on
   whatever `python3` resolves to and generates its own `pip` inside the venv,
   so nothing on `PATH` can interfere. This is why the install steps use one.
2. `python3 -m pip install ...` instead of bare `pip`.
3. Remove or repair the stale script — check its shebang first, since the
   directory it lives in usually holds unrelated tools worth keeping.

### The device sits on `RECEIVING...` forever

A packet was dropped mid-transfer. Harmless — power-cycle, re-enter OS upgrade
mode, and send again. If it recurs, raise `--pace` above 1.4.

## Credits

- [`mischa85/elektron-firmware-tool`](https://github.com/mischa85/elektron-firmware-tool)
  by Marcel Bierling (MIT) — unpacks, repacks and re-signs the `.syx`. This
  project would not exist without it.
- [`mxldyn/octamax`](https://github.com/mxldyn/octamax) — the Octatrack work
  that established the OS format and the code-cave detour technique.

## Licence and firmware

The code here is MIT ([LICENSE](LICENSE)).

**No Elektron firmware — original or modified — is distributed in this
repository.** You supply your own lawfully obtained copy of the public OS
image, and the build patches it locally. Elektron, Model:Samples and
Model:Cycles are trademarks of Elektron Music Machines; this project is not
affiliated with or endorsed by them.
