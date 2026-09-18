#!/usr/bin/env python3
"""Build the multi-output Model:Samples firmware from YOUR OWN copy of OS 1.13.

No Elektron firmware is distributed with this project -- original or modified.
This applies a small, fully-listed set of byte patches (patch/rung10.json) to
the official OS image you supply, then repacks and re-signs it.

The patch set is 237 bytes in 41 runs. Every one asserts the expected stock
bytes before writing, so the build refuses rather than corrupting an image it
does not recognise.

    python3 build.py --syx model-samples_OS1.13.syx
"""
import argparse, hashlib, json, pathlib, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
# SHA-256 of the official OS 1.13 .syx, as downloaded from elektron.se
STOCK_SYX_SHA = "e11859b68deb7e5e3fe86ab32581212093849c4be5d3950add011eac398a2ce8"
# SHA-256 of the finished .syx. The packer is deterministic, so this is an
# exact reproducible-build check: your output must match the tested image.
BUILT_SYX_SHA = "9ab326746903bd88a460914d08137e58e863d0acc814b1dc621949b009ec0169"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--syx", required=True, help="your official model-samples_OS1.13.syx")
    ap.add_argument("--out", default="ms-multi-output.syx")
    ap.add_argument("--tool", default=None, help="path to elektron-firmware-tool")
    ap.add_argument("--allow-any-input", action="store_true",
                    help="skip the stock .syx hash check (not recommended)")
    args = ap.parse_args()

    eft = args.tool or shutil.which("elektron-firmware-tool") or str(
        HERE / "vendor/elektron-firmware-tool/elektron-firmware-tool")
    if not pathlib.Path(eft).exists():
        sys.exit("!! elektron-firmware-tool not found. Run ./setup.sh first.")

    got = sha(args.syx)
    if got != STOCK_SYX_SHA:
        msg = (f"!! input is not the OS 1.13 image this patch set was built against.\n"
               f"   expected {STOCK_SYX_SHA}\n   got      {got}")
        if not args.allow_any_input:
            sys.exit(msg + "\n   (patching a different OS version would produce a broken image)")
        print(msg + "\n   --allow-any-input given, continuing anyway")

    work = HERE / "build"
    work.mkdir(exist_ok=True)
    subprocess.run([eft, "-i", args.syx, "-d", "3", "-o", str(work)], check=True,
                   stdout=subprocess.DEVNULL)
    sec3 = work / "section_3_MAIN_OS.bin"
    img = bytearray(sec3.read_bytes())

    table = json.loads((HERE / "patch/rung10.json").read_text())
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

    patched = work / "mainos_patched.bin"
    patched.write_bytes(bytes(img))
    subprocess.run([eft, "-i", args.syx, "-c", "3", str(patched), "-o", args.out],
                   check=True, stdout=subprocess.DEVNULL)

    out_sha = sha(args.out)
    print(f"\nwrote {args.out}")
    print(f"  sha256 {out_sha}")
    if out_sha == BUILT_SYX_SHA:
        print("  ✅ reproducible build: byte-identical to the tested image")
    else:
        print("  ⚠️  hash differs from the tested image -- do not flash this")
        sys.exit(1)


if __name__ == "__main__":
    main()
