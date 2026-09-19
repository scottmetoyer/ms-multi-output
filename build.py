#!/usr/bin/env python3
"""Build multi-output firmware from YOUR OWN copy of the official OS 1.13.

No Elektron firmware is distributed with this project -- original or modified.
This applies a small, fully-listed set of byte patches to the official OS image
you supply, then repacks and re-signs it.

Pick the target that matches the instrument in front of you:

    # You own a Model:Samples, you want six channels on it
    python3 build.py --target samples --syx model-samples_OS1.13.syx

    # You own a Model:Cycles, you want six channels on it
    python3 build.py --target cycles --syx model-cycles_OS1.13.syx

    # You own a Model:Samples and want to turn it into a six-channel Cycles
    python3 build.py --target cycles-crossflash \
        --syx model-cycles_OS1.13.syx \
        --container model-samples_OS1.13.syx

All three apply the same per-instrument patch table; the targets differ only in
which .syx CONTAINER the patched MAIN OS is packed back into.

WHY THE CONTAINER MATTERS
The bootloader checks the device id in the .syx container (0x0f Samples,
0x11 Cycles) and SILENTLY IGNORES a foreign image -- no error, the screen sits
on READY TO RECEIVE while the whole file goes past at the correct rate and your
flashing tool reports a clean 100%. So the container has to match the box you
are flashing, not the code inside it.

That is why cycles-crossflash needs two files: --syx supplies the Cycles code,
--container supplies the Samples wrapper the Model:Samples bootloader accepts.
Because only MAIN OS is replaced, the Samples bootstrap and its bootloader are
untouched, so plain model-samples_OS1.13.syx remains the rescue image.

Every patch asserts the expected stock bytes before writing, so the build
refuses rather than corrupting an image it does not recognise.
"""
import argparse, hashlib, json, pathlib, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent

# SHA-256 of the official .syx files, as unzipped from elektron.se
SAMPLES_SYX_SHA = "e11859b68deb7e5e3fe86ab32581212093849c4be5d3950add011eac398a2ce8"
CYCLES_SYX_SHA  = "44fe586269631a0ca7da25a3383fc6733c314809505fc3cc52f1e0ed9800640c"

# The packer is deterministic, so built_sha is an exact reproducible-build
# check: your output must match the tested image, byte for byte.
TARGETS = {
    "samples": {
        "desc":          "six channels on a Model:Samples",
        "flash_to":      "Model:Samples",
        "patch":         "patch/rung10.json",
        "input_name":    "model-samples_OS1.13.syx",
        "input_sha":     SAMPLES_SYX_SHA,
        "container_sha": None,                 # the input is its own container
        "built_sha":     "9ab326746903bd88a460914d08137e58e863d0acc814b1dc621949b009ec0169",
        "out":           "ms-multi-output.syx",
        "tested":        True,
    },
    "cycles": {
        "desc":          "six channels on a Model:Cycles",
        "flash_to":      "Model:Cycles",
        "patch":         "patch/cycles6.json",
        "input_name":    "model-cycles_OS1.13.syx",
        "input_sha":     CYCLES_SYX_SHA,
        "container_sha": None,                 # the input is its own container
        "built_sha":     "9c631bc276baaae52270a8256a0213b3c1e9076f9b192137bd6e06d887fe22f6",
        "out":           "mc-multi-output.syx",
        # The PATCHED CODE in this image is hardware-verified -- it is
        # byte-identical to the cycles-crossflash build, which was tested on a
        # Model:Samples running Cycles OS. What has NOT been tested is this
        # image on real Model:Cycles hardware, because no Model:Cycles was
        # available. The pairing is the natural one (0x11 container to a 0x11
        # device, exactly as Elektron's own updates are packed).
        "tested":        False,
    },
    "cycles-crossflash": {
        "desc":          "turn a Model:Samples into a six-channel Model:Cycles",
        "flash_to":      "Model:Samples",
        "patch":         "patch/cycles6.json",
        "input_name":    "model-cycles_OS1.13.syx",
        "input_sha":     CYCLES_SYX_SHA,
        "container_sha": SAMPLES_SYX_SHA,      # REQUIRED -- see the docstring
        "built_sha":     "7929a251de4f464affecd78e8ac87918249006c1142612e91ba5f26eb5c99e52",
        "out":           "mc-on-ms-multi-output.syx",
        "tested":        True,
    },
}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def check_sha(path, want, what, allow):
    got = sha(path)
    if got == want:
        return
    msg = (f"!! {what} is not the image this patch set was built against.\n"
           f"   expected {want}\n   got      {got}")
    if not allow:
        sys.exit(msg + "\n   (patching a different OS version would produce a broken image)")
    print(msg + "\n   --allow-any-input given, continuing anyway")


def main():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="targets:\n" + "\n".join(
            f"  {k:<18} {v['desc']}\n  {'':<18} -> flash to a {v['flash_to']}"
            + ("" if v["tested"] else "   [UNTESTED on that hardware]")
            for k, v in sorted(TARGETS.items())))
    ap.add_argument("--target", choices=sorted(TARGETS), required=True,
                    help="which instrument you are flashing")
    ap.add_argument("--syx", required=True,
                    help="your official OS 1.13 .syx for the TARGET instrument")
    ap.add_argument("--container", default=None,
                    help="Model:Samples OS 1.13 .syx, supplying the container. "
                         "Required for --target cycles-crossflash; ignored otherwise.")
    ap.add_argument("--out", default=None)
    ap.add_argument("--tool", default=None, help="path to elektron-firmware-tool")
    ap.add_argument("--allow-any-input", action="store_true",
                    help="skip the .syx hash checks (not recommended)")
    args = ap.parse_args()

    t = TARGETS[args.target]
    out = args.out or t["out"]

    eft = args.tool or shutil.which("elektron-firmware-tool") or str(
        HERE / "vendor/elektron-firmware-tool/elektron-firmware-tool")
    if not pathlib.Path(eft).exists():
        sys.exit("!! elektron-firmware-tool not found. Run ./setup.sh first.")

    # ---- inputs -------------------------------------------------------------
    print(f"target: {args.target} -- {t['desc']}")
    print(f"  flash the result to a {t['flash_to']}")
    if not t["tested"]:
        print(f"  ⚠️  this exact image has NOT been tested on {t['flash_to']} hardware.\n"
              f"      The patched code in it IS hardware-verified -- it is byte-identical\n"
              f"      to the cycles-crossflash build, which was tested on a Model:Samples\n"
              f"      running Cycles OS. Only the container pairing is untried, and it is\n"
              f"      the natural one. Have a MIDI DIN interface and the official\n"
              f"      {t['input_name']} to hand before you flash.")
    check_sha(args.syx, t["input_sha"], f"--syx ({t['input_name']})", args.allow_any_input)

    container = args.syx
    if t["container_sha"]:
        if not args.container:
            sys.exit(
                f"!! --target {args.target} also needs --container "
                f"model-samples_OS1.13.syx.\n"
                f"   (If you own a Model:Cycles and want six channels on IT, you want\n"
                f"    --target cycles instead, which needs only --syx.)\n"
                f"   The Model:Samples bootloader checks the CONTAINER's device id and\n"
                f"   silently ignores a foreign one -- it would sit on READY TO RECEIVE\n"
                f"   while the whole file went past, with no error. The Samples .syx\n"
                f"   supplies the wrapper; your --syx supplies the code.")
        container = args.container
        check_sha(container, t["container_sha"],
                  "--container (model-samples_OS1.13.syx)", args.allow_any_input)
        print(f"container: {pathlib.Path(container).name} (device id 0x0f)")

    # ---- unpack, patch ------------------------------------------------------
    work = HERE / "build"
    work.mkdir(exist_ok=True)
    subprocess.run([eft, "-i", args.syx, "-d", "3", "-o", str(work)], check=True,
                   stdout=subprocess.DEVNULL)
    sec3 = work / "section_3_MAIN_OS.bin"
    img = bytearray(sec3.read_bytes())

    table = json.loads((HERE / t["patch"]).read_text())
    if not args.allow_any_input and hashlib.sha256(bytes(img)).hexdigest() != table["section3_sha256_stock"]:
        sys.exit("!! section 3 does not match the expected stock image")

    for p in table["patches"]:
        off, exp, new = p["off"], bytes.fromhex(p["expect"]), bytes.fromhex(p["write"])
        if bytes(img[off:off + len(exp)]) != exp:
            sys.exit(f"!! {p['va']}: expected {exp.hex(' ')}, "
                     f"found {bytes(img[off:off+len(exp)]).hex(' ')} -- refusing to patch")
        img[off:off + len(new)] = new
    print(f"  applied {len(table['patches'])} patch runs")

    if hashlib.sha256(bytes(img)).hexdigest() != table["section3_sha256_patched"]:
        sys.exit("!! patched section 3 does not match the expected hash")
    print("  patched section 3 matches the tested image")

    # ---- repack into the container -----------------------------------------
    patched = work / "mainos_patched.bin"
    patched.write_bytes(bytes(img))
    subprocess.run([eft, "-i", container, "-c", "3", str(patched), "-o", out],
                   check=True, stdout=subprocess.DEVNULL)

    out_sha = sha(out)
    print(f"\nwrote {out}")
    print(f"  sha256 {out_sha}")
    if out_sha == t["built_sha"]:
        print("  ✅ reproducible build: byte-identical to the tested image")
        if args.target == "cycles-crossflash":
            print("\n  This is a Model:SAMPLES container carrying Model:CYCLES code.")
            print("  Flash it to a Model:Samples; it boots as a six-channel Cycles.")
        print(f"\n  Flash to: {t['flash_to']}  (power off, hold FUNC, power on, TRIG 4)")
        print("  Watch for RECEIVING... within a few seconds. If the screen stays on")
        print("  READY TO RECEIVE, the image is being silently ignored -- wrong target.")
    else:
        print("  ⚠️  hash differs from the tested image -- do not flash this")
        sys.exit(1)


if __name__ == "__main__":
    main()
