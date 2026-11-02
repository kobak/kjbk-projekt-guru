#!/usr/bin/env python3
"""Build a dependency-free universal Mac .app using Apple's Command Line Tools."""
import argparse
import os
import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
parser = argparse.ArgumentParser()
parser.add_argument("--server-url", default="https://a.kjbk.hu")
parser.add_argument("--output", type=Path, default=ROOT / "build")
parser.add_argument("--development", action="store_true", help="Allow HTTP only on localhost; use a separate app identity")
parser.add_argument("--architecture", choices=("universal", "arm64", "x86_64"), default="universal")
args = parser.parse_args()
url = urlsplit(args.server_url)
if (url.username or url.password or url.query or url.fragment or url.path not in ("", "/") or not url.hostname
        or not (url.scheme == "https" or args.development and url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1"))):
    parser.error("Use an HTTPS origin, or loopback HTTP with --development.")
server = args.server_url.rstrip("/")
args.output.mkdir(parents=True, exist_ok=True)
name = "kjbk projekt guru" + (" QA" if args.development else "")
app = args.output / (name + ".app")
if app.exists():
    parser.error("Output app already exists. Choose a new --output folder, or remove the old build first.")
sdk = subprocess.check_output(["xcrun", "--sdk", "macosx", "--show-sdk-path"], text=True).strip()
with tempfile.TemporaryDirectory(prefix="guru-mac-build-") as staging:
    temp = Path(staging)
    source = temp / "Sources"
    shutil.copytree(ROOT / "Sources", source)
    architectures = ["arm64", "x86_64"] if args.architecture == "universal" else [args.architecture]
    binaries = []
    for arch in architectures:
        binary = temp / ("Guru-" + arch)
        subprocess.run(["xcrun", "swiftc", "-swift-version", "5", "-O", "-sdk", sdk,
            "-target", arch + "-apple-macosx14.0", "-module-cache-path", str(temp / "module-cache"),
            "-framework", "AppKit", "-framework", "SwiftUI", "-framework", "WebKit", "-framework", "UserNotifications",
            *map(str, sorted(source.glob("*.swift"))), "-o", str(binary)], check=True)
        binaries.append(binary)
    contents = temp / (name + ".app") / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    resources = contents / "Resources"
    resources.mkdir()
    if len(binaries) == 2:
        subprocess.run(["xcrun", "lipo", "-create", *map(str, binaries), "-output", str(contents / "MacOS/Guru")], check=True)
    else:
        shutil.copy2(binaries[0], contents / "MacOS/Guru")
    iconset = temp / "Guru.iconset"
    iconset.mkdir()
    icon = REPO / "frontend/public/icon-512.png"
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            target = iconset / (f"icon_{size}x{size}" + ("@2x" if scale == 2 else "") + ".png")
            subprocess.run(["sips", "-z", str(size * scale), str(size * scale), str(icon), "--out", str(target)],
                check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(resources / "Guru.icns")], check=True)
    info = {"CFBundleIdentifier": "com.kjbkinfinity.guru.mac" + (".qa" if args.development else ""),
        "CFBundleExecutable": "Guru", "CFBundleName": name, "CFBundleDisplayName": name,
        "CFBundlePackageType": "APPL", "CFBundleShortVersionString": "0.1.0", "CFBundleVersion": "1",
        "CFBundleIconFile": "Guru", "LSMinimumSystemVersion": "14.0", "NSPrincipalClass": "NSApplication",
        "NSHighResolutionCapable": True, "NSSupportsAutomaticGraphicsSwitching": True,
        "NSHumanReadableCopyright": "KJBK Infinity Kft. · MIT licence; branding: see BRANDING.md",
        "GURUServerURL": server, "GURUDevelopment": args.development}
    if args.development:
        info["NSAppTransportSecurity"] = {"NSAllowsLocalNetworking": True}
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))
    subprocess.run(["codesign", "--force", "--sign", "-", "--options", "runtime", str(contents.parent)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(contents.parent)], check=True)
    shutil.copytree(contents.parent, app)
print(str(app.resolve()))
