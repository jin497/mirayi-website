#!/usr/bin/env python3
"""Copy every image the site uses from the old Wix host into assets/img/.

Run this ONCE on your own computer, BEFORE you cancel Wix (Wix image links stop working after that):

    python3 _tools/download_images.py --dry-run    # just list what would be downloaded
    python3 _tools/download_images.py              # download, then run: python3 _tools/build.py

It needs only Python 3 and an internet connection. Files that already exist are skipped, so it is safe to re-run.
After it finishes, any image that failed is listed at the end; re-run to retry.
"""
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "assets" / "img"
SITE = "https://www.mirayi.my"
DRY = "--dry-run" in sys.argv

ID = r"(?:[0-9a-f]{6}_)?[0-9a-f]{32}(?:f000)?(?:~mv2)?(?:_d_\d+_\d+_s_\d+(?:_\d+)?)?\.(?:jpg|jpeg|png|gif|webp)"
ID_RE = re.compile(ID, re.I)
URL_RE = re.compile(r"https://static\.wixstatic\.com/media/(" + ID + r")(?:/v1/[^\s\"'<>)]*)?", re.I)
CONTENT_URL_RE = re.compile(r'(content=")https://static\.wixstatic\.com/media/(' + ID + r')(?:/v1/[^"]*)?(")', re.I)
JSON_URL_RE = re.compile(r'(:\s*")https://static\.wixstatic\.com/media/(' + ID + r')(?:/v1/[^"]*)?(")', re.I)


def safe(name):
    return name.replace("~", "-")


def text_files():
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in {".html", ".js", ".json", ".xml", ".md"} and "_tools" not in p.parts \
                and "_preview" not in p.parts and "node_modules" not in p.parts:
            yield p


def main():
    ids = set()
    for p in text_files():
        ids.update(m.group(0) for m in ID_RE.finditer(p.read_text(encoding="utf-8")))
    ids = sorted(ids)
    print(f"{len(ids)} distinct images found")
    if DRY:
        for i in ids:
            print("  ", i)
        return

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for n, i in enumerate(ids, 1):
        dest = IMG_DIR / safe(i)
        webp = dest.with_suffix('.webp')
        if (dest.exists() and dest.stat().st_size > 0) or (webp.exists() and webp.stat().st_size > 0) \
                or (ROOT / '_originals' / dest.name).exists():
            continue
        url = "https://static.wixstatic.com/media/" + i
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (mirayi site migration)"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                dest.write_bytes(r.read())
            print(f"[{n}/{len(ids)}] ok   {i}")
        except (urllib.error.URLError, TimeoutError) as e:
            failed.append((i, str(e)))
            print(f"[{n}/{len(ids)}] FAIL {i}  ({e})")
        time.sleep(0.15)

    if failed:
        print(f"\n{len(failed)} image(s) failed:")
        for i, e in failed:
            print("  ", i, "-", e)
        print("Re-run the script to retry. Images that failed keep loading from Wix until they are downloaded.")
        sys.exit(1)

    print("\nDone. Now run:  python3 _tools/build.py")
    print("The build shrinks every picture to WebP (needs: pip install Pillow) and uses them automatically;")
    print("images that are missing keep loading from Wix.")
    print("Then upload / commit the whole folder, including assets/img/.")


if __name__ == "__main__":
    main()
