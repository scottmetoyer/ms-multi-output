#!/usr/bin/env python3
"""Build multi-output firmware from YOUR OWN copy of the official OS 1.13.

No Elektron firmware is distributed with this project -- original or modified.
This applies a small, fully-listed set of byte patches to the official OS image
you supply, then repacks and re-signs it.

Two targets:

    # Model:Samples -- one input
    python3 build.py --syx model-samples_OS1.13.syx

    # Model:Cycles -- needs BOTH images, see below
    python3 build.py --target cycles \\
        --syx model-cycles_OS1.13.syx \\
        --container model-samples_OS1.13.syx

WHY THE CYCLES BUILD NEEDS TWO FILES
The Model:Samples bootloader checks the device id in the .syx CONTAINER
(0x0f Samples, 0x11 Cycles) and SILENTLY IGNORES a foreign image -- the screen
sits on READY TO RECEIVE while the whole file goes past at the correct rate,
with no error anywhere. So a Model:Cycles .syx cannot be flashed to a
Model:Samples directly.

The way round it is to keep the SAMPLES container and replace only its
section 3 (MAIN OS) with the patched Cycles one. That is what --container is:
the Samples .syx supplies the wrapper, the Cycles .syx supplies the code.

The result is a Samples-container image carrying Cycles code. Flashing it turns
a Model:Samples into a six-channel Model:Cycles. Because only MAIN OS is
replaced, the Samples bootstrap and its bootloader are untouched, so plain
model-samples_OS1.13.syx remains the rescue image.

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
        "desc":          "Model:Samples, six per-track USB channels",
        "patch":         "patch/rung10.json",
        "input_name":    "model-samples_OS1.13.syx",
        "input_sha":     SAMPLES_SYX_SHA,
        "container_sha": None,                 # the input is its own container
        "built_sha":     "9ab326746903bd88a460914d08137e58e863d0acc814b1dc621949b009ec0169",
        "out":           "ms-multi-output.syx",
    },
    "cycles": {
        "desc":          "Model:Cycles, six per-track USB channels (cross-flash)",
        "patch":         "patch/cycles6.json",
        "input_name":    "model-cycles_OS1.13.syx",
        "input_sha":     CYCLES_SYX_SHA,
        "container_sha": SAMPLES_SYX_SHA,      # REQUIRED -- see the docstring
        "built_sha":     "7929a251de4f464affecd78e8ac87918249006c1142612e91ba5f26eb5c99e52",
        "out":           "mc-multi-output.syx",
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
            f"  {k:<9} {v['desc']}" for k, v in sorted(TARGETS.items())))
    ap.add_argument("--target", choices=sorted(TARGETS), default="samples",
                    help="which instrument to build for (default: samples)")
    ap.add_argument("--syx", required=True,
                    help="your official OS 1.13 .syx for the TARGET instrument")
    ap.add_argument("--container", default=None,
                    help="Model:Samples OS 1.13 .syx, supplying the container. "
                         "Required for --target cycles; ignored otherwise.")
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
    check_sha(args.syx, t["input_sha"], f"--syx ({t['input_name']})", args.allow_any_input)

    container = args.syx
    if t["container_sha"]:
        if not args.container:
            sys.exit(
                f"!! --target {args.target} also needs --container "
                f"model-samples_OS1.13.syx.\n"
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
        if args.target == "cycles":
            print("\n  This is a Model:SAMPLES container carrying Model:CYCLES code.")
            print("  Flash it to a Model:Samples; it boots as a six-channel Cycles.")
    else:
        print("  ⚠️  hash differs from the tested image -- do not flash this")
        sys.exit(1)


if __name__ == "__main__":
    main()
