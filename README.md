# ms-multi-output

Six channels of **per-track USB audio** for the Elektron **Model:Samples** and
**Model:Cycles**.

Stock, both boxes send only the stereo mix over USB. This patch sends **each of
the six tracks on its own USB channel**, so you can record real stems straight
into a DAW instead of bouncing one track at a time.

| USB channel | carries |
|---|---|
| 1 – 6 | tracks 1 – 6 |

48 kHz, 32-bit, High Speed. The device still reports itself as OS `1.13`.

| target | status |
|---|---|
| **Model:Samples** | ✅ Working — verified on hardware, channel map confirmed by per-track mute test |
| **Model:Cycles** | ✅ Working — verified on hardware (see [Model:Cycles](#modelcycles) — it installs differently) |

⚠️ **The Model:Cycles build has only been tested by cross-flashing a
Model:Samples**, which is how it was developed. It has **never been run on
actual Model:Cycles hardware**. See [Model:Cycles](#modelcycles) before you try
it on a real one.

---

## ⚠️ Read this before you do anything

**This flashes modified firmware to your instrument. It is not an Elektron
product, it is not supported by Elektron, and it will almost certainly void
your warranty.** It has been tested on exactly one unit — a Model:Samples,
including for the Model:Cycles build, which was developed by cross-flashing
that same box and has **never run on real Model:Cycles hardware**.

**On Windows you need FlexASIO, at 48 kHz** — a DAW's normal WASAPI or ASIO
settings will not open the device. MME, DirectSound and WASAPI-shared all work;
WASAPI-exclusive does not. See [Platform support](#platform-support).

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
| **macOS** | ✅ Working — six channels on both targets |
| **Windows** | ✅ Working — needs FlexASIO at 48 kHz, see below |
| **Linux** | Untested — the build is pure Python and should work, but nobody has confirmed it |

### Windows: FlexASIO on MME, DirectSound or WASAPI — at 48 kHz

All six channels work on Windows, but **not** through a DAW's normal WASAPI or
ASIO settings. Use [FlexASIO](https://github.com/dechamps/FlexASIO):

1. Install FlexASIO.
2. Set its `backend` to **MME**, **Windows DirectSound** or **Windows WASAPI** —
   via FlexASIO Control (the GUI) or `FlexASIO.toml`. All three are confirmed.
3. Set `channels = 6` on the input, and **make sure your DAW project is at
   48 kHz**.
4. In your DAW, select **FlexASIO** as the ASIO device.

Measured on Windows 11 24H2 (build 26100.9457, in-box `usbaudio2.sys`), with
the sequencer running and the capture checked for per-channel independence:

| FlexASIO backend | result |
|---|---|
| MME | ✅ six distinct channels |
| Windows DirectSound | ✅ six distinct channels |
| Windows WASAPI (shared) | ✅ six distinct channels |
| Windows WDM-KS | ⚠️ intermittent — streamed cleanly in one run, failed in the next |
| Windows WASAPI (**exclusive**) | ❌ never works |

> **An earlier version of this README told you to use DirectSound
> specifically.** That was wrong — not about DirectSound, but about singling
> out any one backend. If a guide or forum post insists only one backend works,
> it is probably describing a wedged device rather than a backend limitation.

**⚠️ If it stops working, power-cycle the instrument before changing any
setting.** The device occasionally wedges on Windows and needs an
unplug/replug. While wedged it still enumerates but refuses to stream, so
whichever backend you happen to be trying looks broken — which is exactly how
people end up convinced that only *their* backend works. This was reproduced
accidentally during testing: in a wedged state DirectSound failed 12 times out
of 12 with a clean, convincing error, then worked perfectly after a power
cycle. There is no known cause yet; please open an issue if you can reproduce
it reliably.

**48 kHz is not optional.** The device offers exactly one capture format and no
stereo fallback. PortAudio reports its *default* rate as 44100 under MME and
DirectSound, so a host that accepts that default fails negotiation — on stock
firmware just as readily as on this one.

**This is not a descriptor fault.** Windows enumerates the device correctly and
every host API reports it as 6-channel. The descriptors were decoded and
checked against every constraint Microsoft documents for `usbaudio2.sys`, and
they pass.

## Requirements

- A **Model:Samples** running **OS 1.13** (the version this is built against).
  The Model:Cycles build is installed onto a Model:Samples too — see
  [Model:Cycles](#modelcycles)
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
download the OS `.zip` from elektron.se and unzip it.

```sh
# Model:Samples
python3 build.py --syx model-samples_OS1.13.syx

# Model:Cycles -- needs BOTH images, see the Model:Cycles section for why
python3 build.py --target cycles \
    --syx model-cycles_OS1.13.syx \
    --container model-samples_OS1.13.syx
```

The build refuses unless your inputs are the exact OS 1.13 images, checks the
expected stock bytes at every patch site (41 for Samples, 29 for Cycles), and
verifies the finished file against a known hash:

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
.venv/bin/python tools/flash.py ms-multi-output.syx     # or mc-multi-output.syx
```

Then send it, naming your DIN output. **Pacing matters:** at exactly wire speed
a packet eventually drops and the device sits on `RECEIVING...` forever (which
looks alarming but harms nothing — power-cycle and retry).

```sh
.venv/bin/python tools/flash.py ms-multi-output.syx --port "YOUR DIN PORT" --pace 1.4 --send
```

**Watch the screen for the first few seconds.** It must change from
`READY TO RECEIVE` to `RECEIVING...`. If it stays on `READY TO RECEIVE` the
image is being **silently ignored** and nothing is being written — the progress
counter will still run to 100% looking perfectly healthy. See
[Model:Cycles](#modelcycles).

Roughly 6–7 minutes. Do not power off, especially once the screen says
`UPDATING FLASH`. The unit reboots itself when done.

## Verify

macOS:

```sh
system_profiler SPAudioDataType | grep -A4 "Model:"
#   Input Channels: 6
```

A Model:Samples carrying the Cycles build reports itself as
**`Elektron Model:Cycles`** — that is expected, and is how you know the
cross-flash took.

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

## Model:Cycles

**Verified working on hardware.** Six independent per-track channels, with zero
ring duplicates — the same result as the Model:Samples build.

⚠️ **It was developed and tested by cross-flashing a Model:Samples, and has
never been run on real Model:Cycles hardware.** Everything below describes
putting Cycles firmware onto a **Model:Samples**. If you own an actual
Model:Cycles, this build is untested on it and the install described here does
not apply to you — please do not assume it is symmetric.

### You cannot just flash a Cycles .syx

The Model:Samples bootloader checks the **device id in the `.syx` container**
(`0x0f` Samples, `0x11` Cycles) and **silently ignores a foreign image**. There
is no error. The screen sits on `READY TO RECEIVE` while the entire 890 kB goes
past at the correct rate and your flashing tool reports a clean 100%. It is
indistinguishable from a dead MIDI cable, and it is the single most confusing
failure in this whole project.

**The fix** — [originally found by a user on
r/Elektron](https://www.reddit.com/r/Elektron/comments/1w87ta6/flashing_modelcycles_firmware_into_a_modelsamples/p80jsvo/)
— is to keep the **Samples** container and replace only its `section_3` (MAIN
OS) with the Cycles one. `build.py --target cycles` does exactly that, which is
why it needs both `.syx` files:

| argument | supplies |
|---|---|
| `--syx model-cycles_OS1.13.syx` | the **code** (Cycles MAIN OS, patched) |
| `--container model-samples_OS1.13.syx` | the **wrapper** the bootloader accepts |

The output is a Samples-container image carrying Cycles code. Flash it exactly
like the Samples build.

### Recovery is unaffected

The post above warns that once cross-flashed the box "thinks it's a Cycles" and
needs a Cycles container to go back. **That was tested here and is not the case
for this build.** After cross-flashing, a `0x11` container was still ignored
and a `0x0f` one still accepted — because only MAIN OS is replaced, so the
Samples bootstrap and its bootloader are untouched.

**Plain `model-samples_OS1.13.syx` remains your rescue image**, exactly as in
[Recovery](#recovery). Nothing special is needed.

### What you get

The box boots as a Model:Cycles — Cycles machines, Cycles UI — with six
per-track USB channels. It identifies over USB as `Elektron Model:Cycles`.

Everything in [What the stems actually are](#what-the-stems-actually-are)
applies, with one difference: **track LEVEL is confirmed pre-tap on the
Model:Samples but untested on the Cycles**, so whether the stems carry it is
unknown.

⚠️ The box runs Cycles OS on top of Model:Samples project data. How it handles
saving and loading is unexplored — **back up your +Drive with Elektron Transfer
before you start.**

⚠️ The per-track mute test has not been run on the Cycles. Six independent
channels arrive at sensible levels, but that does not strictly prove channel
*n* is track *n* rather than some permutation. Check it before trusting the map
for real work — and please open an issue with what you find.

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
assembly sources are in [`patch/`](patch/); the exact bytes applied are listed
in [`patch/rung10.json`](patch/rung10.json) (Model:Samples, 41 runs) and
[`patch/cycles6.json`](patch/cycles6.json) (Model:Cycles, 29 runs), so nothing
about this is opaque — you can read every byte that changes and why.

The two firmwares share the same USB stack **at byte-identical addresses**, so
the Cycles port is almost entirely an address translation: the same four stubs,
relocated to where that image keeps its descriptors, its mode table and its
per-track audio blocks.

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

### The screen never leaves `READY TO RECEIVE`

The image is being **silently rejected** on its container device id, and
nothing is being written — even though the transfer runs to 100% normally.
You are almost certainly flashing a Model:Cycles `.syx` to a Model:Samples;
build it with `--target cycles --container model-samples_OS1.13.syx` instead,
and see [Model:Cycles](#modelcycles).

To confirm the MIDI path itself is fine, send the official
`model-samples_OS1.13.syx`: if *that* moves to `RECEIVING...` on the same cable
and port, your wiring is good and the container was the problem.

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
