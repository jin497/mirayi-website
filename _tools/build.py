#!/usr/bin/env python3
"""Generates every page of the Mirayi site.

    python3 _tools/build.py             -> production files in the site root
    python3 _tools/build.py --preview   -> clickable preview in _preview/ (relative links, noindex)

Everything you edit lives in content/ (works.json, home.json, seo.json, settings.json, posts/*.md).
The admin page (/admin) edits those files. This script turns them into the website.
Requires: pip install -r requirements.txt   (markdown, pyyaml)
"""
import datetime
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PREVIEW = "--preview" in sys.argv
OUT = ROOT / "_preview" if PREVIEW else ROOT
SITE = "https://www.mirayi.my"
TODAY = "2026-10-13"

# --- SEO identifiers copied from the old Wix site (kept so Search Console / Bing / Yandex stay verified)
VERIFY = [
    ("name", "google-site-verification", "9TpsocKjD3hdFCnQhYZ-nyRJqa1dNDT7utWd3lJGeI4"),
    ("name", "msvalidate.01", "99BBB5EE519618B657D344C6FC482B27"),
    ("name", "yandex-verification", "2625c16d29da6128"),
    ("name", "p:domain_verify", "2f1c20ba0aa0a16baf119e1723cd907e"),
    ("property", "fb:admins", "jinchongng"),
]

ID_RE = re.compile(
    r"^(?:[0-9a-f]{6}_)?[0-9a-f]{32}(?:f000)?(?:~mv2)?(?:_d_\d+_\d+_s_\d+(?:_\d+)?)?\.(?:jpg|jpeg|png|gif|webp)$"
)
USED_IDS = set()


IMG_DIR = ROOT / "assets" / "img"
WIXM = "https://static.wixstatic.com/media/"


def media_id(src):
    """Wix media id from an id or a wixstatic URL, else None (e.g. an uploaded /assets/... path)."""
    m = re.search(r"wixstatic\.com/media/([^/?#\"']+)", src)
    cand = m.group(1) if m else src
    return cand if ID_RE.match(cand) else None


def safe(i):
    return i.replace("~", "-")


def local_file(i):
    """The downloaded copy of a Wix image: the optimised .webp if there is one, else the original."""
    base = IMG_DIR / safe(i)
    for f in (base.with_suffix(".webp"), base):
        if f.is_file() and f.stat().st_size:
            return f
    return None


def optimize_images():
    """Shrink every picture in assets/img/ to WebP (long edge max 1600 px). Originals move to _originals/.
    Runs automatically at the start of every build. Needs Pillow (pip install Pillow); skipped if missing."""
    try:
        from PIL import Image, ImageSequence
    except ImportError:
        print("NOTE: Pillow is not installed, so images were not shrunk (pip install Pillow).")
        return
    if not IMG_DIR.is_dir():
        return
    keep = ROOT / "_originals"
    before = after = done = 0
    for f in sorted(IMG_DIR.iterdir()):
        ext = f.suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif") or not f.is_file():
            continue
        out = f.with_suffix(".webp")
        size = f.stat().st_size
        src = None
        try:
            src = im = Image.open(f)
            if ext == ".gif":
                if size < 400_000 or not getattr(im, "is_animated", False):
                    src.close()
                    continue              # small GIFs stay as they are
                frames = []
                for fr in ImageSequence.Iterator(im):
                    fr = fr.convert("RGBA")
                    if fr.width > 800:
                        fr = fr.resize((800, round(fr.height * 800 / fr.width)))
                    frames.append(fr)
                frames[0].save(out, "WEBP", save_all=True, append_images=frames[1:], quality=75,
                               duration=im.info.get("duration", 80), loop=0)
            else:
                if im.mode in ("P", "LA", "PA"):
                    im = im.convert("RGBA")
                elif im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGB")
                im.thumbnail((1600, 1600))
                im.save(out, "WEBP", quality=80, method=6)
        except Exception as e:
            if src is not None:
                src.close()
            print(f"  could not shrink {f.name}: {e}")
            out.unlink(missing_ok=True)
            continue
        src.close()                       # Windows cannot move a file that is still open
        keep.mkdir(exist_ok=True)
        f.replace(keep / f.name)
        before += size
        after += out.stat().st_size
        done += 1
    if done:
        print(f"shrank {done} images: {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB (originals kept in _originals/)")


def loc(path):
    """Site-absolute path ('/assets/..') -> link that also works in the _preview folder."""
    if not PREVIEW:
        return path
    return "../" * (DEPTH + 1) + path.lstrip("/")


def wix(i, w, h):
    """Image URL: the downloaded local copy if it exists, else the old Wix media host. Accepts an id, a
    wixstatic URL, or an uploaded '/assets/img/..' path."""
    mid = media_id(i)
    if mid is None:
        return i if i.startswith("http") else loc(i)
    USED_IDS.add(mid)
    if local_file(mid):
        return loc("/assets/img/" + local_file(mid).name)
    if mid.endswith(".gif"):
        return WIXM + mid
    return f"{WIXM}{mid}/v1/fill/w_{w},h_{h},al_c,q_85/{mid}"


def absu(i, w=None, h=None):
    """Absolute https URL of an image (for og:image and structured data)."""
    mid = media_id(i)
    if mid is None:
        return i if i.startswith("http") else SITE + i
    USED_IDS.add(mid)
    if local_file(mid):
        return f"{SITE}/assets/img/{local_file(mid).name}"
    if w and h and not mid.endswith(".gif"):
        return f"{WIXM}{mid}/v1/fill/w_{w},h_{h},al_c/{mid}"
    return WIXM + mid


def image_size(path):
    """(width, height) of a PNG/JPEG/GIF/WebP file, or None."""
    import struct
    try:
        d = pathlib.Path(path).read_bytes()
        if d[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", d[16:24])
        if d[:6] in (b"GIF87a", b"GIF89a"):
            return struct.unpack("<HH", d[6:10])
        if d[:4] == b"RIFF" and d[8:12] == b"WEBP":
            if d[12:16] == b"VP8X":
                return (int.from_bytes(d[24:27], "little") + 1, int.from_bytes(d[27:30], "little") + 1)
            if d[12:16] == b"VP8 ":
                return struct.unpack("<HH", d[26:30])
            if d[12:16] == b"VP8L":
                v = int.from_bytes(d[21:25], "little")
                return ((v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1)
        if d[:2] == b"\xff\xd8":
            i = 2
            while i < len(d):
                if d[i] != 0xFF:
                    i += 1
                    continue
                mk = d[i + 1]
                if mk in (0xC0, 0xC1, 0xC2, 0xC3):
                    h, w = struct.unpack(">HH", d[i + 5:i + 9])
                    return (w, h)
                i += 2 + struct.unpack(">H", d[i + 2:i + 4])[0]
    except Exception:
        pass
    return None


def dims_of(src, w=None, h=None):
    """Width/height for an image source: given values, else measured from the local file, else 1200x630."""
    if w and h:
        return int(w), int(h)
    mid = media_id(src)
    f = local_file(mid) if mid else (ROOT / src.lstrip("/") if src.startswith("/") else None)
    if f and pathlib.Path(f).is_file():
        sz = image_size(f)
        if sz:
            return sz
    return 1200, 630


# ---------------------------------------------------------------- content (edited via /admin)

def load_json(name):
    return json.loads((ROOT / "content" / name).read_text(encoding="utf-8"))


def split_front(text):
    import yaml
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    return (yaml.safe_load(m.group(1)) or {}, m.group(2)) if m else ({}, text)


def iso(v):
    if isinstance(v, datetime.datetime):
        v = v.astimezone(datetime.timezone.utc) if v.tzinfo else v
        return v.strftime("%Y-%m-%dT%H:%M:%S.") + f"{v.microsecond // 1000:03d}Z"
    if isinstance(v, datetime.date):
        return v.isoformat() + "T00:00:00.000Z"
    return str(v)


def paras(text):
    return "".join(f"<p>{E(x.strip())}</p>" for x in re.split(r"\n\s*\n", text.strip()) if x.strip())


def load_posts():
    posts = []
    for f in sorted((ROOT / "content" / "posts").glob("*.md")):
        fm, body = split_front(f.read_text(encoding="utf-8"))
        pub = iso(fm.get("published") or fm.get("date") or TODAY)
        d = datetime.datetime.strptime(pub[:10], "%Y-%m-%d")
        words = len(re.findall(r"\w+", body))
        first = re.sub(r"[#*_>\[\]!`]|\(https?://[^)]*\)|\(/[^)]*\)", "", body.strip().split("\n\n")[0]).strip()
        img = fm.get("image") or ""
        w, h = dims_of(img, fm.get("image_w"), fm.get("image_h"))
        desc = fm.get("meta_desc") or first[:155]
        posts.append(dict(
            slug=f.stem, h1=fm.get("title", f.stem), title=fm.get("seo_title") or fm.get("title", f.stem),
            author=fm.get("author", "Mirayi"), published=pub, modified=iso(fm.get("modified") or pub),
            date=f"{d.strftime('%b')} {d.day}, {d.year}", read=fm.get("read") or f"{max(1, round(words / 200))} min read",
            img=(img, w, h), meta_desc=desc, og_desc=fm.get("og_desc") or desc,
            excerpt=fm.get("excerpt") or (first[:140] + ("..." if len(first) > 140 else "")), md=body))
    posts.sort(key=lambda p: p["published"], reverse=True)
    return posts


def load_guides():
    out = []
    for f in sorted((ROOT / "content" / "pages").glob("*.md")):
        fm, body = split_front(f.read_text(encoding="utf-8"))
        pub = iso(fm.get("published") or TODAY)
        mod = iso(fm.get("modified") or pub)
        img = fm.get("image") or "c08280_97853ac24bf54b97a6738ef0a0de4944~mv2.jpg"
        w, h = dims_of(img, fm.get("image_w"), fm.get("image_h"))
        out.append(dict(slug=f.stem, h1=fm.get("title", f.stem), title=fm.get("seo_title") or fm.get("title", f.stem),
                        desc=fm.get("description", ""), keywords=fm.get("keywords", ""), intro=fm.get("intro", ""),
                        img=(img, w, h), published=pub, modified=mod, faq=fm.get("faq") or [], md=body, legal=bool(fm.get("legal"))))
    return out


def md_to_html(md_text):
    import markdown
    h = markdown.markdown(md_text, extensions=["extra", "sane_lists"])

    def img_sub(m):
        src = m.group(2)
        mid = media_id(src)
        wm = re.search(r"w_(\d+),h_(\d+)", src)
        if mid:
            new = wix(mid, int(wm.group(1)) if wm else 980, int(wm.group(2)) if wm else 551)
        else:
            new = wix(src, 980, 551)
        pw, ph = (int(wm.group(1)), int(wm.group(2))) if wm else dims_of(src)
        return f'{m.group(1)}"{new}" width="{pw}" height="{ph}"'

    h = re.sub(r'(<img [^>]*?src=)"([^"]+)"', img_sub, h)
    h = h.replace("<img ", '<img loading="lazy" ')

    def link_sub(m):
        path = m.group(1).strip("/")
        return f'href="{u(path)}"'

    h = re.sub(r'href="(/(?!assets/)[a-z0-9\-/]*)"', link_sub, h)
    return h


E = html.escape
DEPTH = 0
LOGO_ID = "7c4f43_f0df2f6e0f2a432ca3ad71466344a9fd~mv2.png"


def logo(cls="logo-img"):
    return (f'<img class="{cls}" src="{wix(LOGO_ID, 340, 96) if local_file(LOGO_ID) else WIXM + LOGO_ID}" alt="Mirayi" '
            'width="170" height="48">')


LANG = "en"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from i18n import LANGS, META, UI  # noqa: E402

LANG_DIRS = {l: ROOT / "content" / l for l in LANGS}
SLUGS = {l: ({f.stem for f in d.glob("*.md")} | ({""} if (d / "home.json").exists() else set())) if d.is_dir() else set()
         for l, d in LANG_DIRS.items()}
LANGS = [l for l in LANGS if SLUGS[l]]


def T():
    return UI[LANG]


def split_lang(path):
    """'ko/gameproduction' -> ('ko', 'gameproduction'); 'ko' -> ('ko', ''); 'whoweare' -> ('en', 'whoweare')."""
    for l in LANGS:
        if path == l:
            return l, ""
        if path.startswith(l + "/"):
            return l, path[len(l) + 1:]
    return "en", path


def u(path="", frag=""):
    if path in LANGS:
        return ("/" + path + "/" + frag) if not PREVIEW else "../" * DEPTH + path + "/index.html" + frag
    if not PREVIEW:
        return "/" + path + frag
    return "../" * DEPTH + (path + ".html" if path else "index.html") + frag


def lu(slug="", frag=""):
    """Link to a page in the current language (/ko/..., /zh/..., or English /...)."""
    if LANG in LANGS:
        return u(LANG if slug == "" else LANG + "/" + slug, frag)
    return u(slug, frag)


def page_url(path):
    if path == "":
        return SITE
    if path in LANGS:
        return SITE + "/" + path + "/"
    return SITE + "/" + path


def lang_path(lang, slug):
    return slug if lang == "en" else (lang if slug == "" else lang + "/" + slug)


def alt_links(p):
    """hreflang alternates between the English page and each translated counterpart that exists."""
    path = p["path"]
    if path == "404" or path.startswith("post/"):
        return []
    _, slug = split_lang(path)
    out = [("en", page_url(slug))]
    for l in LANGS:
        if slug in SLUGS[l]:
            out.append((META[l]["hreflang"], page_url(lang_path(l, slug))))
    if len(out) == 1:
        return []
    return out + [("x-default", page_url(slug))]


def a(name):
    # preview pages live in _preview/, one level below the real assets folder
    return ("../" * (DEPTH + 1) + "assets/" + name) if PREVIEW else "/assets/" + name


SOCIAL = [
    ("LinkedIn", "https://www.linkedin.com/company/mirayi-sdn-bhd/"),
    ("Facebook", "https://www.facebook.com/Mirayianimation/"),
    ("YouTube", "https://www.youtube.com/channel/UCfM6FyyJSHMrGU8dE-t3Tsg"),
    ("ArtStation", "https://mirayi.artstation.com/"),
]

KW_PROD = ("top animation studios, top asian animation studios, best 3d animation, top animation studios in malaysia, "
           "animation companies, 3d animation studio in malaysia, animation company in malaysia, "
           "animation studio malaysia, 3d animation")
KW_BLOG = ("Malaysia Animation Studio, Authentic Malaysian Animation, Animation Company, International Animation Company, "
           "Globally Recognized, High-Quality 2D & 3D Animation, Animation Expertise You Can Trust, Creative Animation Solutions")
OG_SERVICES = ("c08280_f7cb02a2172841abbccb20609efcec70~mv2.jpg", 2500, 1330)
HERO_IMG = "c08280_4881f0ecbca94f9a94d5d181bbb151f8f000.jpg"

# ---------------------------------------------------------------- layout

NAV = [
    ("home", "Home", "", None),
    ("who", "Who we are", "whoweare", [("About us", "whoweare"), ("Our business", "ourbusiness")]),
    ("brands", "Our brands", "mirayibrand", None),
    ("prod", "Production", "production", [
        ("Animated series & feature", "seriesandfilms"), ("Game services", "gameproduction"),
        ("TV commercial", "tvcommercials"), ("Visual development", "visualdevelopment")]),
    ("fimi", "FIMI 30% rebate", "fimi-cash-rebate-animation", None),
    ("blog", "Blog", "blog", None),
    ("join", "Join us", "join-with-us", None),
    ("contact", "Contact", "contact", None),
]


def lang_switch(path):
    cur, slug = split_lang(path)
    items = [("en", "EN", "en", u(slug))]
    for l in LANGS:
        items.append((l, META[l]["label"], META[l]["hreflang"], u(lang_path(l, slug)) if slug in SLUGS[l] else u(l)))
    aria = UI[cur]["lang_aria"] if cur in LANGS else "Language"
    out = []
    for l, label, hl, href in items:
        if l == cur:
            out.append(f'<a class="on" aria-current="true" href="{href}">{label}</a>')
        else:
            out.append(f'<a hreflang="{hl}" lang="{l}" href="{href}">{label}</a>')
    return f'<div class="lang-switch" role="group" aria-label="{aria}">{"".join(out)}</div>'


def header(active, path):
    items = []
    here = split_lang(path)[1]
    nav = T()["nav"] if LANG in LANGS else NAV
    for key, label, target, subs in nav:
        cur = ' aria-current="page"' if key == active else ""
        if subs:
            sub = "".join(
                f'<li><a href="{lu(t)}"{" aria-current=page" if t == here else ""}>{E(l)}</a></li>' for l, t in subs)
            items.append(f'<li class="has-sub"><a href="{lu(target)}"{cur}>{E(label)}</a><ul class="sub">{sub}</ul></li>')
        else:
            items.append(f'<li><a href="{lu(target)}"{cur}>{E(label)}</a></li>')
    tr = LANG in LANGS
    return f"""<header class="site-header"><div class="wrap bar">
<a class="brand" href="{lu()}" aria-label="{T()['home_aria'] if tr else 'Mirayi home'}">{logo()}</a>
<button class="menu-btn" type="button" aria-expanded="false" aria-controls="nav">{T()['menu'] if tr else 'Menu'}</button>
<nav id="nav" aria-label="{T()['main_nav'] if tr else 'Main'}"><ul>{''.join(items)}</ul></nav>
{lang_switch(path)}
</div></header>"""


def footer_tr():
    t = T()
    soc = "".join(f'<a href="{h}" rel="noopener" target="_blank">{n}</a>' for n, h in SOCIAL)
    ab = "".join(f'<a href="{lu(s)}">{E(n)}</a>' for n, s in t["foot_about"])
    pr = "".join(f'<a href="{lu(s)}">{E(n)}</a>' for n, s in t["foot_prod"])
    return f"""<footer><div class="wrap">
<div class="foot-grid">
<div class="foot-brand"><a class="brand" href="{lu()}">{logo()}</a>
<p>{E(t['foot_tag'])}</p>{contact_lines("foot-contact")}</div>
<div class="foot-cols">
<div><h4>{t['foot_h'][0]}</h4>{ab}</div>
<div><h4>{t['foot_h'][1]}</h4>{pr}</div>
<div><h4>{t['foot_h'][2]}</h4>{soc}</div>
</div></div>
<div class="foot-bottom"><span>&copy; {YEAR} MIRAYI SDN BHD.</span><a href="{u('')}">{t['foot_en']}</a></div>
</div></footer>"""


def footer():
    if LANG in LANGS:
        return footer_tr()
    soc = "".join(f'<a href="{h}" rel="noopener" target="_blank">{n}</a>' for n, h in SOCIAL)
    return f"""<footer><div class="wrap">
<div class="foot-grid">
<div class="foot-brand"><a class="brand" href="{u()}">{logo()}</a>
<p>3D animation and IP development studio in Malaysia. MSC Malaysia status, FINAS licensed.</p>{contact_lines("foot-contact")}</div>
<div class="foot-cols">
<div><h4>Studio</h4><a href="{u('whoweare')}">About us</a><a href="{u('ourbusiness')}">Our business</a><a href="{u('mirayibrand')}">Our brands</a><a href="{u('join-with-us')}">Join us</a><a href="{u('animation-outsourcing-malaysia')}">Animation outsourcing</a><a href="{u('fimi-cash-rebate-animation')}">FIMI cash rebate</a></div>
<div><h4>Production</h4><a href="{u('seriesandfilms')}">Series &amp; feature</a><a href="{u('gameproduction')}">Game services</a><a href="{u('tvcommercials')}">TV commercial</a><a href="{u('visualdevelopment')}">Visual development</a></div>
<div><h4>Follow</h4>{soc}</div>
</div></div>
<div class="foot-bottom"><span>&copy; {YEAR} MIRAYI SDN BHD.</span><span><a href="{u('contact')}">Contact</a> &middot; <a href="{u('blog')}">Blog</a> &middot; <a href="{u('privacy-policy')}">Privacy</a> &middot; <a href="{u('terms-of-use')}">Terms</a></span></div>
</div></footer>"""


def breadcrumb_ld(p):
    path = p["path"]
    lang, slug = split_lang(path)
    if not path or path == "404" or path in LANGS:
        return None
    if lang in LANGS:
        return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": UI[lang]["crumb_home"], "item": page_url(lang)},
            {"@type": "ListItem", "position": 2, "name": p.get("crumb") or p["title"], "item": page_url(path)}]}
    names = {t: l for _, l, t, _ in NAV}
    for _, _, _, subs in NAV:
        for l, t in (subs or []):
            names[t] = l
    trail = [("Home", SITE)]
    if path.startswith("post/"):
        trail += [("Blog", SITE + "/blog"), (p["title"], SITE + "/" + path)]
    else:
        if path in ("seriesandfilms", "gameproduction", "tvcommercials", "visualdevelopment"):
            trail.append(("Production", SITE + "/production"))
        trail.append((names.get(path, p.get("crumb") or p["title"]), SITE + "/" + path))
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": n, "name": nm, "item": url} for n, (nm, url) in enumerate(trail, 1)]}


def head(p):
    path = p["path"]
    canon = page_url(path)
    lang = p.get("lang", "en")
    tr = lang in LANGS
    title = p["title"]
    shown = "Mirayi Site Preview" if (PREVIEW and not path) else title
    ogt = p.get("og_title", title)
    desc = p["desc"]
    oimg, ow, oh = p["og_img"]
    ogimg = absu(oimg, ow, oh)
    t = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{E(shown)}</title>",
        f'<meta name="description" content="{E(desc)}">',
    ]
    if p.get("keywords"):
        t.append(f'<meta name="keywords" content="{E(p["keywords"])}">')
    if PREVIEW:
        t.append('<meta name="robots" content="noindex">')
    t.append(f'<link rel="canonical" href="{canon}">')
    t.append('<meta name="format-detection" content="telephone=no">')
    for attr, name, val in VERIFY:
        t.append(f'<meta {attr}="{name}" content="{val}">')
    for name, key in (("baidu-site-verification", "baidu_verification"), ("sogou_site_verification", "sogou_verification"),
                      ("360-site-verification", "so360_verification"), ("shenma-site-verification", "shenma_verification")):
        if SETTINGS.get(key):
            t.append(f'<meta name="{name}" content="{E(SETTINGS[key])}">')
    if lang == "zh":
        t += ['<meta name="applicable-device" content="pc,mobile">', '<meta http-equiv="Cache-Control" content="no-transform">',
              '<meta http-equiv="Cache-Control" content="no-siteapp">']
    if tr:
        t.append(f'<meta http-equiv="Content-Language" content="{META[lang]["header"]}">')
    if lang == "ko" and SETTINGS.get("naver_verification"):
        t.append(f'<meta name="naver-site-verification" content="{E(SETTINGS["naver_verification"])}">')
    for hl, href in alt_links(p):
        t.append(f'<link rel="alternate" hreflang="{hl}" href="{href}">')
    og_desc = p.get("og_desc", desc)
    t += [
        f'<meta property="og:title" content="{E(ogt)}">',
        f'<meta property="og:description" content="{E(og_desc)}">',
        f'<meta property="og:type" content="{p.get("og_type", "website")}">',
        f'<meta property="og:url" content="{canon}">',
        '<meta property="og:site_name" content="Mirayi">',
        f'<meta property="og:locale" content="{META[lang]["og"] if tr else "en_US"}">',
        f'<meta property="og:image" content="{ogimg}">',
        f'<meta property="og:image:width" content="{ow}">',
        f'<meta property="og:image:height" content="{oh}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{E(ogt)}">',
        f'<meta name="twitter:description" content="{E(og_desc)}">',
        f'<meta name="twitter:image" content="{ogimg}">',
    ]
    art = p.get("article")
    if art:
        t += [
            f'<meta property="article:author" content="{E(art["author"])}">',
            f'<meta property="article:published_time" content="{art["published"]}">',
            f'<meta property="article:modified_time" content="{art["modified"]}">',
        ]
    if (path == "" or path in LANGS) and HERO_PRELOAD:
        t.append(f'<link rel="preload" as="image" href="{HERO_PRELOAD}" fetchpriority="high">')
    if tr:      # CJK pages use system fonts: Google Fonts is blocked in mainland China and the CJK files are heavy
        t.append(f'<link rel="stylesheet" href="{a("style.css")}">')
    else:
      t += [
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Raleway:wght@500;600;700;800&family=Noticia+Text:ital,wght@0,400;0,700;1,400&family=Rajdhani:wght@400;500;600&display=swap" media="print" onload="this.media=\'all\'">',
        '<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Raleway:wght@500;600;700;800&family=Noticia+Text:ital,wght@0,400;0,700;1,400&family=Rajdhani:wght@400;500;600&display=swap"></noscript>',
        f'<link rel="stylesheet" href="{a("style.css")}">',
      ]
    crumbs = breadcrumb_ld(p)
    for ld in p.get("jsonld", []) + ([crumbs] if crumbs else []):
        t.append('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>")
    return "\n".join(t)


def render(p):
    global DEPTH, LANG
    LANG = p.get("lang", "en")
    DEPTH = 1 if p["path"] in LANGS else p["path"].count("/")
    body = p["body"]()
    scripts = [a("config.js")]
    if p.get("portfolio"):
        scripts += [a("works.js"), a("portfolio.js")]
    scripts.append(a("site.js"))
    sc = "\n".join(f'<script src="{s}" defer></script>' for s in scripts)
    doc = f"""<!doctype html>
<html lang="{META[LANG]["html"] if LANG in LANGS else "en"}">
<head>
{head(p)}
</head>
<body id="top">
<a class="skip" href="#main">{T()["skip"] if LANG in LANGS else "Skip to content"}</a>
{header(p.get("active"), p["path"])}
<main id="main">
{body}
</main>
{footer()}
<div class="float-btns"><a class="fb-mail" href="{lu('', '#contact')}" aria-label="{T()['contact'] if LANG in LANGS else 'Contact us'}"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#fff" stroke-width="2"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg></a><a class="fb-up" href="#top" aria-label="{T()['top'] if LANG in LANGS else 'Back to top'}"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#fff" stroke-width="2.4"><path d="m6 15 6-6 6 6"/></svg></a></div>
{sc}
</body>
</html>
"""
    dest = OUT / (p["path"] + "/index.html" if p["path"] in LANGS else p["path"] + ".html" if p["path"] else "index.html")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(doc, encoding="utf-8")


# ---------------------------------------------------------------- shared blocks

def works_list(kinds, cats):
    """Plain-text list of the works (for visitors, search engines and AI crawlers that do not run JavaScript)."""
    ks = [x for x in kinds.split(",") if x]
    cs = [x for x in cats.split(",") if x]
    items = []
    for w in load_json("works.json")["works"]:
        if (ks and w.get("kind") not in ks) or (cs and w.get("cat") not in cs):
            continue
        tr = LANG in LANGS
        name = E((w.get("title_" + LANG) if tr else "") or w["title"])
        vid = (w.get("video_cn") if LANG == "zh" else "") or w.get("video")
        if vid:
            name = f'<a href="{E(vid)}" rel="noopener">{name}</a>'
        kind = (T()["kind_ip"] if tr else "Mirayi original IP") if w.get("kind") == "ip" else (T()["kind_svc"] if tr else "Animation services")
        typ = (w.get("type_" + LANG) if tr else "") or w.get("type") or kind
        note = (w.get("note_" + LANG) if tr else "") or w.get("note")
        items.append(f"<li>{name} &mdash; {E(typ)}{' (' + E(note) + ')' if note else ''}</li>")
    return "<ul>" + "".join(items) + "</ul>" if items else ""


def portfolio(limit=0, filters=True, kinds="", cats="", button=True):
    more = ('<div class="work-more" hidden><button class="btn btn-ghost" type="button" aria-expanded="false">'
            'View all works</button></div>') if (limit and button) else ""
    return (f'<div data-portfolio data-limit="{limit}" data-filters="{"true" if filters else "false"}" '
            f'data-kinds="{kinds}" data-cats="{cats}">'
            '<div class="work-filters" role="group" aria-label="Filter works"></div>'
            '<div class="work-grid" aria-live="polite"></div>'
            f'{more}'
            f'<noscript>{works_list(kinds, cats)}<p class="work-empty">' + (
                T()["noscript"].format(link=lu("", "#contact"))
                if LANG in LANGS else
                f'Please enable JavaScript for the picture gallery, or <a href="{u("", "#contact")}">contact us</a> for the showreel.')
            + '</p></noscript></div>')


def prod_subnav(current):
    items = [("All production", "production"), ("Original work", "mirayibrand"),
             ("Feature film & series", "seriesandfilms"), ("Game services", "gameproduction"),
             ("Commercials", "tvcommercials"), ("Visual dev", "visualdevelopment")]
    links = "".join(
        f'<a href="{u(t)}"{" aria-current=page" if t == current else ""}>{E(l)}</a>' for l, t in items)
    return f'<nav class="subnav" aria-label="Production">{links}</nav>'


def page_hero(h1, intro="", crumbs=None, extra=""):
    cr = ""
    if crumbs:
        cr = '<div class="crumbs">' + " / ".join(
            f'<a href="{u(t)}">{E(l)}</a>' if t is not None else E(l) for l, t in crumbs) + "</div>"
    ip = f"<p>{intro}</p>" if intro else ""
    return f'<section class="page-hero"><div class="wrap">{cr}<h1>{h1}</h1>{ip}{extra}</div></section>'


def contact_cta_tr(text=None):
    t = T()
    return f"""<section class="block"><div class="wrap sec-head" style="margin-bottom:0">
<h2>{E(text or t['cta'])}</h2><a class="btn" href="{lu('', '#contact')}">{t['contact']}</a></div></section>"""


def prod_subnav_tr(current):
    t = T()
    links = "".join(f'<a href="{lu(s)}"{" aria-current=page" if s == current else ""}>{E(l)}</a>' for l, s in t["subnav"])
    return f'<nav class="subnav" aria-label="{t["subnav_aria"]}">{links}</nav>'


def contact_cta(text="For business or collaboration proposals, contact us."):
    return f"""<section class="block"><div class="wrap sec-head" style="margin-bottom:0">
<h2>{E(text)}</h2><a class="btn" href="{u('', '#contact')}">Contact us</a></div></section>"""


# ---------------------------------------------------------------- pages

HOME = load_json("home.json")
HOME_L = {l: load_json(l + "/home.json") for l in LANGS if (ROOT / "content" / l / "home.json").exists()}
SETTINGS = load_json("settings.json")
import datetime as _dt
YEAR = _dt.date.today().year  # copyright year follows the build date


def tel_digits(t):
    return re.sub(r"[^\d+]", "", t)


def contact_lines(cls="contact-details"):
    """Visible email / phone / location from content/settings.json."""
    bits = []
    tr = LANG in LANGS
    t = T() if tr else {}
    if SETTINGS.get("public_email"):
        e = E(SETTINGS["public_email"])
        bits.append(f'<li><span>{t["email"] if tr else "Email"}</span><a href="mailto:{e}">{e}</a></li>')
    if SETTINGS.get("phone"):
        ph = E(SETTINGS["phone"])
        bits.append(f'<li><span>{t["phone"] if tr else "Phone / WhatsApp"}</span><a href="tel:{E(tel_digits(SETTINGS["phone"]))}">{ph}</a></li>')
    if SETTINGS.get("region"):
        bits.append(f'<li><span>{t["loc"] if tr else "Location"}</span>{E(SETTINGS["region"])}{t["loc_suffix"] if tr else ", Malaysia"}</li>')
    if SETTINGS.get("address") and LANG == "en":
        bits.append(f'<li><span>Address</span>{E(SETTINGS["address"])}</li>')
    if SETTINGS.get("hours") and LANG == "en":
        bits.append(f'<li><span>Hours</span>{E(SETTINGS["hours"])}</li>')
    return f'<ul class="{cls}">{"".join(bits)}</ul>' if bits else ""


QR_LARK = "c08280_8929712c14c5411996076d431067abe4~mv2.jpg"
QR_WECHAT = "c08280_dd32c5296338445bba9a2264c2f63fe4~mv2.png"


def contact_section():
    if LANG in LANGS:
        tt = T()
        t = dict(h=tt["c_h"], intro=HOME_L.get(LANG, {}).get("contact_intro", tt["c_intro"]), chinese=tt["c_note"], scan=tt["c_scan"],
                 lark="飞书 Lark", wechat="微信 WeChat", name=tt["f_name"], company=tt["f_company"], email=tt["f_email"],
                 msg=tt["f_msg"], send=tt["f_send"], qa1="添加飞书（Lark）的二维码", qa2="添加微信（WeChat）的二维码")
        qr_on = tt["qr"]
    else:
        t = dict(h="Get in touch", intro=HOME["contact_intro"],
                 chinese="我们可以用中文沟通。Our team communicates in both English and Chinese.",
                 scan="请加我的飞书或微信以获得更多讯息", lark="Lark 飞书", wechat="WeChat 微信", name="Name", company="Company",
                 email="Email", msg="Project details", send="Send", qa1="QR code to add Mirayi on Lark (Feishu)",
                 qa2="QR code to add Mirayi on WeChat")
        qr_on = True
    note_lang = {"zh": "zh", "ko": "ko", "ja": "ja"}.get(LANG, "zh")
    qr_html = (f"""<p class="qr-note"><span lang="zh">{E(t['scan'])}</span></p>
<div class="qr">
<figure><img src="{wix(QR_LARK, 240, 294)}" alt="{t['qa1']}" width="120" height="147" loading="lazy"><figcaption>{t['lark']}</figcaption></figure>
<figure><img src="{wix(QR_WECHAT, 240, 366)}" alt="{t['qa2']}" width="120" height="183" loading="lazy"><figcaption>{t['wechat']}</figcaption></figure>
</div>""" if qr_on else "")
    return f"""<section class="contact" id="contact"><img class="bg" src="{wix('7c4f43_af7e16dca72b45cd80b0f3bbafee04fd~mv2.jpg', 1400, 760)}" alt="" aria-hidden="true" loading="lazy"><div class="wrap contact-grid">
<div><h2>{t['h']}</h2>
{contact_lines()}
<p class="qr-note"><strong lang="{note_lang}">{E(t['chinese'])}</strong></p>
{qr_html}</div>
<form data-contact novalidate>
<p>{E(t['intro'])}</p>
<div class="field"><label for="f-name">{t['name']}</label><input id="f-name" name="name" type="text" placeholder="{t['name']}" autocomplete="name" required></div>
<div class="field"><label for="f-company">{t['company']}</label><input id="f-company" name="company" type="text" placeholder="{t['company']}" autocomplete="organization"></div>
<div class="field"><label for="f-email">{t['email']}</label><input id="f-email" name="email" type="email" placeholder="{t['email']}" autocomplete="email" required></div>
<div class="field"><label for="f-msg">{t['msg']}</label><textarea id="f-msg" name="message" rows="4" placeholder="{t['msg']}"></textarea></div>
<button class="btn" type="submit">{t['send']}</button>
<p class="form-note" role="status" aria-live="polite"></p>
</form></div></section>"""


HERO_PRELOAD = ""


def body_home():
    logos = "".join(
        f'<div class="client"><img src="{wix(c["logo"], 240, 120)}" alt="{E(c["name"])}" loading="lazy" decoding="async" width="120" height="60"></div>'
        for c in HOME["clients"])
    slides = "".join(
        (f'<img class="slide on" src="{wix(sl["image"], 1600, 900)}" alt="{E(sl.get("alt", ""))}" width="1600" height="900" fetchpriority="high">'
         if n == 0 else
         f'<img class="slide" data-src="{wix(sl["image"], 1600, 900)}" alt="{E(sl.get("alt", ""))}" width="1600" height="900">')
        for n, sl in enumerate(HOME["hero_slides"]))
    global HERO_PRELOAD
    HERO_PRELOAD = wix(HOME["hero_slides"][0]["image"], 1600, 900)
    return f"""
<section class="hero-slider" aria-roledescription="carousel" aria-label="Featured work">
{slides}
<div class="hero-text"><h1>{E(HOME["hero_title"])}</h1>
<p class="lead">{E(HOME["hero_lead"])}</p>
<p class="sr">Mirayi delivers high-quality 3D animation for games, TV series, and commercials. Trusted by studios in the U.S., Europe, and Asia since 2005.</p>
<p class="hero-cta"><a class="btn" href="{u('contact')}">Get a quote</a><a class="btn btn-ghost" href="{u('production')}">See our work</a></p></div>
<button class="hs-arrow prev" type="button" aria-label="Previous slide">&#8249;</button><button class="hs-arrow next" type="button" aria-label="Next slide">&#8250;</button>
<div class="hs-dots"></div></section>

<section class="block"><div class="wrap">
<div class="sec-head"><h2>Our Clientele</h2><p>Studios, broadcasters and game publishers across the U.S., Europe and Asia.</p></div>
<div class="clients">{logos}</div>
</div></section>

<section class="block svc-sec"><div class="wrap">
<div class="sec-head"><h2>Our Services</h2><p>Game and broadcast animation run through one pipeline.</p></div>
<div class="svc-split">
<div class="svc-panel"><h3>Game</h3><p>Cinematics, cutscenes and engine-ready assets for game developers.</p><ul>
<li><a href="{u('gameproduction')}">Game Cinematic<span>Details</span></a></li>
<li><a href="{u('gameproduction')}">Cutscene Animation<span>Details</span></a></li>
<li><a href="{u('gameproduction')}">Game Assets<span>Details</span></a></li>
<li><a href="{u('gameproduction')}">Rigging<span>Details</span></a></li></ul></div>
<div class="svc-panel"><h3>Animation</h3><p>Series, commercials and films, plus original IP development.</p><ul>
<li><a href="{u('seriesandfilms')}">Cartoon Series<span>Details</span></a></li>
<li><a href="{u('tvcommercials')}">TV Commercial<span>Details</span></a></li>
<li><a href="{u('seriesandfilms')}">Animated Movie<span>Details</span></a></li>
<li><a href="{u('mirayibrand')}">IP Development<span>Details</span></a></li></ul></div>
</div></div></section>

<section class="block" id="work"><div class="wrap">
<div class="sec-head"><h2>Selected work</h2><p>Mirayi's own IP and the animation we produce for clients. Switch between them, or open the full list.</p></div>
{portfolio(limit=12, filters=True)}
<p style="margin-top:26px"><a href="{u('production')}">Open the full production portfolio</a></p>
</div></section>

<section class="block alt"><div class="wrap two-col">
<div>
<img class="photo" src="{wix(HOME["story_image"], 733, 399)}" alt="Mirayi artists at work" width="733" height="399" loading="lazy">
<div class="badges"><span class="badge">MSC Malaysia status</span><span class="badge">FINAS licensed</span><span class="badge">50-person studio</span></div>
</div>
<div class="story-copy">
<div class="year">{E(HOME["story_year"])}</div>
<h3>{E(HOME["story_heading_1"])}</h3>
{paras(HOME["story_text_1"])}
<h3>{E(HOME["story_heading_2"])}</h3>
{paras(HOME["story_text_2"])}
<p><a href="{u('whoweare')}">Know more about Mirayi</a></p>
</div></div></section>

<section class="block alt"><div class="wrap"><div class="sec-head"><h2>What people say</h2></div>
<blockquote class="quote"><p>"{E(HOME["testimonial_quote"])}"</p><cite>{E(HOME["testimonial_by"])}</cite></blockquote></div></section>

<section class="block"><div class="wrap"><div class="inc">
<div><h2>{E(HOME["rebate_title"])}</h2>
{paras(HOME["rebate_text"])}
<p><a href="{u('fimi-cash-rebate-animation')}">How the FIMI cash rebate works</a> &middot; <a href="{u('animation-outsourcing-malaysia')}">3D animation outsourcing in Malaysia</a></p>
<div class="logos">
<img src="{wix('7c4f43_86a92f7dc5054b2397a19f15f692620b~mv2.png', 172, 170)}" alt="FINAS" width="86" height="85" loading="lazy">
<img src="{wix('7c4f43_6a1047bfa1904aba94a4aea1b3ce6351~mv2.png', 254, 94)}" alt="MDEC" width="127" height="47" loading="lazy">
<img src="{wix('7c4f43_54ad31da47944267b8539420c00a7fe9~mv2.png', 200, 150)}" alt="MSC Malaysia" width="100" height="75" loading="lazy">
</div></div>
<div class="pct">30%<small>FIMI cash rebate on service projects</small></div>
</div></div></section>

{contact_section()}
"""


def body_whoweare():
    return f"""
{page_hero("Your International Partner",
 "Mirayi is passionate in creating and sharing heartwarming stories to inspire and bring courage to our audiences around the world. Our office has dynamic environment that boosts our artists’ creativity, which lead us to success.<br><br>If you also love what we do, we would love to hear from you!",
 extra=f'<div class="actions"><a class="btn" href="{u("", "#contact")}">Contact us</a><a class="btn btn-ghost" href="{u("join-with-us")}">Join the team</a></div>')}
<section class="block"><div class="wrap">
<img class="photo" src="{wix('7c4f43_61a9cceb6ff940a3b5e9a91f67378c49~mv2.jpg', 1552, 597)}" alt="The Mirayi studio team" width="1552" height="597" style="aspect-ratio:1552/597">
</div></section>
<section class="block"><div class="wrap two-col">
<div><h2 style="font-size:clamp(1.8rem,3vw,2.5rem)">About us</h2></div>
<div class="prose">
<p>Mirayi is a Malaysian 3D animation and IP development studio trusted by leading studios in the U.S., Europe, and Asia. Since 2005, we’ve delivered high-quality animation for games, TV series, commercials, and feature films—combining cinematic artistry with efficient, deadline-focused production. Our experienced team works seamlessly across time zones, using clear communication and industry-standard pipelines to ensure smooth collaboration with international partners. With MSC status, FINAS licensing, and access to Malaysia’s 30% Film-in-Malaysia rebate, we provide global clients with not only top-tier creative work but also strategic production value.</p>
<h3>Exploring creative solutions</h3>
<p>To meet the growing demand for animation services worldwide, our research department constantly develops CG production tools, systems and new technologies to support and facilitate our software. Production pipelines are conducted in order to achieve a new level of creative, innovative and technological finesse.</p>
<h3>Collaboration is a cinch</h3>
<p>We bring your projects to life with the support of our investors and various Malaysian government organizations via access to various government funds and production incentives.</p>
</div></div></section>
<section class="block"><div class="wrap">
<img class="photo" src="{wix('7c4f43_aafd5c38c01a434884b61dbb0d5e15bf~mv2.jpg', 1170, 652)}" alt="Mirayi team meeting" width="1170" height="652" loading="lazy" style="aspect-ratio:1170/652">
</div></section>
<section class="block"><div class="wrap sec-head" style="margin-bottom:0">
<div><h2>Join with us!</h2><p style="margin-top:12px">We are zealous about our creative and dynamic force where success is relentless. If you are passionate about what you do, have befitting skills and experiences, join our team!</p></div>
<a class="btn" href="{u('join-with-us')}">Apply now</a></div></section>
"""


def body_ourbusiness():
    return f"""
{page_hero("Creating animation is what we love.", "Sharing joy and courage is our passion.")}
<section class="block"><div class="wrap two-col">
<div><h2 style="font-size:clamp(1.8rem,3vw,2.5rem)">Our business</h2>
<img class="photo" style="margin-top:28px" src="{wix('0e22db_925bcc6d3102413997634e1190d3d2ee~mv2.jpg', 743, 557)}" alt="Mirayi animation production" width="743" height="557" loading="lazy"></div>
<div class="prose"><p>We are adept at providing full-fledged animation services with our best support.</p>
<p>We also accept requests for specific production stages; such as 2D illustration designing, 3D animation production, compositing, and more.</p>
<p><a href="{u('animation-outsourcing-malaysia')}">Read more about outsourcing animation to Mirayi in Malaysia</a> and the <a href="{u('fimi-cash-rebate-animation')}">30% FIMI cash rebate</a>.</p></div>
</div></section>
<section class="block"><div class="wrap">
<div class="sec-head"><h2>We can cover you for the following stages</h2></div>
<div class="stages">
<div class="stage"><h3>Pre-Production</h3><ul><li>Concept design</li><li>Character design</li><li>Storyboard</li><li>Mood board</li></ul></div>
<div class="stage"><h3>3D Production</h3><ul><li>Modeling</li><li>Texturing</li><li>Rigging</li><li>Animation</li><li>Lighting</li><li>VFX</li></ul></div>
<div class="stage"><h3>Post-Production</h3><ul><li>Compositing</li><li>Editing</li><li>Rendering</li></ul></div>
</div></div></section>
<section class="block"><div class="wrap">
<div class="sec-head"><h2>Production flow</h2></div>
<ol class="flow">
<li><h3>Negotiation</h3><p>We are expert in animated cartoon series, feature films, short animation clips, and more.</p></li>
<li><h3>Planning</h3><p>From planning, budgeting to scheduling, we have you covered! A production team will be dedicated exclusively for your project.</p></li>
<li><h3>Production</h3><p>Now it's time for the pure fun creative processes, where your imagination will come to life. Uh oh! Got new ideas or any adjustments? No worries, tell us!</p></li>
<li><h3>Delivery</h3><p>Your satisfaction is our priority. We strive to produce the highest quality animation.</p></li>
</ol></div></section>
<section class="block"><div class="wrap sec-head" style="margin-bottom:0">
<h2>For business/collaboration proposal, contact us!</h2>
<div class="actions" style="margin-top:0"><a class="btn" href="{u('', '#contact')}">Contact us</a><a class="btn btn-ghost" href="{u('production')}">View our portfolio</a></div></div></section>
"""


def body_brands():
    return f"""
{page_hero("Mirayi Original Works",
 "Mirayi Animation Studio retains outstanding creative talents, in-depth hands-on experiences, resources and state-of-the-art technology and craftsmanship in creating and co-producing first-rate entertainment – predominantly animated cartoon series and films for local and international distribution and audience.",
 extra=prod_subnav("mirayibrand"))}
<section class="block"><div class="wrap">
{portfolio(filters=False, kinds="ip")}
</div></section>
{contact_cta("Interested in co-producing? Talk to us.")}
"""


def body_production():
    return f"""
{page_hero("Production Portfolio", "Please send us the email to request for the showreel!", extra=prod_subnav("production"))}
<section class="block"><div class="wrap">
{portfolio(filters=True)}
</div></section>
{contact_cta("Need a showreel or a quote? Get in touch.")}
"""


def body_series():
    return f"""
{page_hero("Mirayi Services",
 "Mirayi has collaborated with numerous clients from all around the world. We are specialized in 3D cartoon series and animated feature films. In Mirayi, we provide full-fledged 3D animation services. From your pre-production needs, 3D modeling, rigging, animation work, VFX, to post-production editing; We have you covered !",
 extra=prod_subnav("seriesandfilms"))}
<section class="block"><div class="wrap">
{portfolio(filters=False, kinds="service", cats="series,film")}
</div></section>
{contact_cta()}
"""


def body_game():
    return f"""
{page_hero("Game Animation &amp; Art Services",
 "Mirayi brings decades of high-end broadcast animation experience directly into the game development pipeline.<br><br>We are a 50-person studio bridging the gap between narrative artistry and real-time technical requirements. Whether you need emotional in-engine cutscenes, responsive gameplay cycles, or optimized character rigs, our team delivers assets that are story-driven and engine-ready.",
 extra=prod_subnav("gameproduction"))}
<section class="block"><div class="wrap">
<img class="photo" src="{wix('c08280_3eeb71cc3c3a4df99bfa04cdf2acf893~mv2.jpg', 1400, 612)}" alt="Game environment concept art by Mirayi" width="1400" height="612" style="aspect-ratio:1400/612">
</div></section>
<section class="block"><div class="wrap"><div class="svc-list">
<div class="svc-row"><h3>Cinematics &amp; Cutscenes</h3><p>We translate complex narratives into compelling visual experiences. We handle the full spectrum of production, from pre-rendered marketing trailers to real-time, in-engine story sequences (Unreal/Unity), ensuring high-fidelity acting and emotional impact.</p></div>
<div class="svc-row"><h3>Gameplay Animation</h3><p>Animation that feels good to play. We create grounded, impactful motion for player characters, enemies, and creatures. Our focus is on weight, timing, and readability for combat actions, traversal cycles, and interactive reactions.</p></div>
<div class="svc-row"><h3>Assets &amp; Rigging</h3><p>Technical foundation meets artistic vision. We provide clean, optimized mesh topology suitable for modern game engines. Our technical team builds robust, animator-friendly control rigs designed for complex performances and efficient pipelines.</p></div>
</div></div></section>
<section class="block"><div class="wrap sec-head" style="margin-bottom:0">
<h2>Please contact us for the showreels</h2><a class="btn" href="{u('', '#contact')}">Contact us</a></div></section>
"""


def body_tv():
    return f"""
{page_hero("TV Commercials",
 f'Besides producing cartoon series and animated feature films, Mirayi also produces animation clips for TV commercial purposes. If you need animation clips for your brand marketing, please do not hesitate to <a href="{u("", "#contact")}">contact us</a> !',
 extra=prod_subnav("tvcommercials"))}
<section class="block"><div class="wrap">
{portfolio(filters=False, kinds="service", cats="commercial")}
</div></section>
"""


VISDEV = [
    ("c08280_d64f79a3498b43988a8da2bf2882df6f~mv2_d_7155_2659_s_4_2.jpg", 324, 120),
    ("0e22db_ea6e967ebcee421abbb8368e47866bcc~mv2_d_7089_3508_s_4_2.jpg", 324, 160),
    ("0e22db_fbd332e8365940a6b226893fe12006df~mv2_d_7087_4134_s_4_2.jpg", 324, 189),
    ("c08280_e1ff1423429e4e39b4cf2c182cf54217~mv2_d_7425_3234_s_4_2.jpg", 324, 141),
    ("0e22db_f1012b4059f84580974bb2197b47ccb6~mv2.jpg", 324, 182),
    ("0e22db_fb0bbee0748f480492f944bafc5adeb4~mv2_d_5493_3535_s_4_2.jpg", 324, 209),
    ("0e22db_f6b6f97610934b4fa2580f047b0222f4~mv2_d_8442_6945_s_4_2.jpg", 324, 267),
    ("0e22db_cf434096ed4c4eccb2b22aaac4df9646~mv2_d_4000_1400_s_2.jpg", 324, 113),
    ("0e22db_e7c45adbde5b425bb698a8d467750674~mv2.jpg", 324, 527),
    ("0e22db_92624376df2e4bfdb4952eba31acbbee~mv2_d_14983_5702_s_3_2.jpg", 324, 123),
    ("0e22db_8de2511f5d754f0a9cb66f125f58a2a3~mv2.jpg", 324, 207),
    ("0e22db_d5f8c354fa87415cab04b30a20cf94e8~mv2.jpg", 324, 203),
    ("0e22db_259ca3f7851f41d0a26eb03cbaaadc7d~mv2.jpg", 324, 213),
    ("0e22db_63d675c7ade04048aedbcdecf9dd1a43~mv2.jpg", 324, 450),
    ("0e22db_3fec0feb3c9f4b019d4b44c87ff91aee~mv2_d_7087_4134_s_4_2.jpg", 324, 189),
    ("0e22db_8ded72209acb4ce4ac4d430ebfe026c8~mv2_d_7087_5551_s_4_2.jpg", 324, 254),
    ("0e22db_7ff8c4dc6513470cb6fa8625272ab8bb~mv2_d_7087_4134_s_4_2.jpg", 324, 189),
    ("0e22db_9d3ea7213b1445c599e36cafa34d7fb5~mv2_d_7087_4134_s_4_2.jpg", 324, 189),
]


def body_visdev():
    imgs = "".join(
        f'<img src="{wix(i, w * 2, h * 2)}" alt="Mirayi concept art and visual development, image {n}" width="{w}" height="{h}" loading="lazy" decoding="async">'
        for n, (i, w, h) in enumerate(VISDEV, 1))
    return f"""
{page_hero("Visual Development",
 "Back-to-basics with 2D illustration: Concept Art, essence of Animation Production.<br>State-of-the-Art production: Enliven illustrations through 3D modeling.",
 extra=prod_subnav("visualdevelopment"))}
<section class="block"><div class="wrap">
<div class="gallery">{imgs}</div>
<div class="gallery-cta">
<a href="https://mirayi.artstation.com/" target="_blank" rel="noopener"><img src="{wix('0e22db_c3c1b12eaee648b2ad904079c6b97468~mv2.png', 150, 148)}" alt="ArtStation" width="56" height="56" loading="lazy"></a>
<div><h2>Want to see more?</h2><p style="color:var(--paper-dim);margin-top:6px">Check out our gallery on <a href="https://mirayi.artstation.com/" target="_blank" rel="noopener">ArtStation</a>!</p></div>
</div></div></section>
"""


POSTS = load_posts()
GUIDES = load_guides()


def load_lang_pages(lang):
    out = []
    d = LANG_DIRS[lang]
    for f in (sorted(d.glob("*.md")) if d.is_dir() else []):
        fm, body = split_front(f.read_text(encoding="utf-8"))
        pub = iso(fm.get("published") or TODAY)
        img = fm.get("image") or "c08280_97853ac24bf54b97a6738ef0a0de4944~mv2.jpg"
        w, h = dims_of(img, fm.get("image_w"), fm.get("image_h"))
        out.append(dict(slug=f.stem, h1=fm.get("title", f.stem), title=fm.get("seo_title") or fm.get("title", f.stem),
                        desc=fm.get("description", ""), keywords=fm.get("keywords", ""), intro=fm.get("intro", ""),
                        img=(img, w, h), published=pub, modified=iso(fm.get("modified") or pub), faq=fm.get("faq") or [],
                        subnav=bool(fm.get("subnav")), portfolio=bool(fm.get("portfolio")) or bool(fm.get("portfolio_kinds")),
                        kinds=fm.get("portfolio_kinds") or "", cats=fm.get("portfolio_cats") or "",
                        filters=bool(fm.get("portfolio_filters")), limit=int(fm.get("portfolio_limit") or 0),
                        gallery=fm.get("gallery") or "", active=fm.get("active") or "who", md=body))
    return out


def make_tr_body(g):
    def body():
        extra = prod_subnav_tr(g["slug"]) if g["subnav"] else ""
        intro = "<br>".join(E(x) for x in g["intro"].split("\n")) if g["intro"] else ""
        port = (f'<section class="block"><div class="wrap">{portfolio(limit=g["limit"], filters=g["filters"], kinds=g["kinds"], cats=g["cats"])}</div></section>'
                if g["portfolio"] else "")
        gal = ""
        if g["gallery"] == "visdev":
            imgs = "".join(
                f'<img src="{wix(i, w * 2, h * 2)}" alt="{T()['vis_alt']} {n}" width="{w}" height="{h}" loading="lazy" decoding="async">'
                for n, (i, w, h) in enumerate(VISDEV, 1))
            gal = (f'<section class="block"><div class="wrap"><div class="gallery">{imgs}</div>'
                   f'<div class="gallery-cta"><a href="https://mirayi.artstation.com/" target="_blank" rel="noopener">'
                   f'<img src="{wix("0e22db_c3c1b12eaee648b2ad904079c6b97468~mv2.png", 150, 148)}" alt="ArtStation" width="56" height="56" loading="lazy"></a>'
                   f'<div><h2>{T()["vis_more"]}</h2><p style="color:var(--paper-dim);margin-top:6px">{T()["vis_p"]}</p></div></div></div></section>')
        prose = (f'<section class="block"><div class="wrap"><div class="prose" style="max-width:780px;margin:0 auto">{md_to_html(g["md"])}</div></div></section>'
                 if g["md"].strip() else "")
        faq = ""
        if g["faq"]:
            items = "".join(f'<details><summary>{E(x["q"])}</summary><p>{E(x["a"])}</p></details>' for x in g["faq"])
            faq = (f'<section class="block alt"><div class="wrap"><div class="sec-head"><h2>{T()["faq_h"]}</h2></div>'
                   f'<div class="faq">{items}</div></div></section>')
        return f"""
{page_hero(E(g['h1']), intro, extra=extra)}
{port}{gal}{prose}
{faq}
{contact_cta_tr()}
"""
    return body


def tr_ld(g):
    ld = []
    if g["faq"]:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": x["q"], "acceptedAnswer": {"@type": "Answer", "text": x["a"]}} for x in g["faq"]]})
    return ld


def body_home_tr():
    Z = HOME_L[LANG]
    t = T()
    logos = "".join(
        f'<div class="client"><img src="{wix(c["logo"], 240, 120)}" alt="{E(c["name"])}" loading="lazy" decoding="async" width="120" height="60"></div>'
        for c in HOME["clients"])
    slides = "".join(
        (f'<img class="slide on" src="{wix(sl["image"], 1600, 900)}" alt="{E(sl.get("alt", ""))}" width="1600" height="900" fetchpriority="high">'
         if n == 0 else
         f'<img class="slide" data-src="{wix(sl["image"], 1600, 900)}" alt="{E(sl.get("alt", ""))}" width="1600" height="900">')
        for n, sl in enumerate(HOME["hero_slides"]))
    global HERO_PRELOAD
    HERO_PRELOAD = wix(HOME["hero_slides"][0]["image"], 1600, 900)

    def panel(title, intro, items):
        lis = "".join(f'<li><a href="{lu(t)}">{E(n)}</a></li>' for n, t in items)
        return f'<div class="svc-panel"><h3>{E(title)}</h3><p>{E(intro)}</p><ul>{lis}</ul></div>'

    return f"""
<section class="hero-slider" aria-roledescription="carousel" aria-label="{t['hero_aria']}">
{slides}
<div class="hero-text"><h1>{E(Z['hero_title'])}</h1>
<p class="lead">{E(Z['hero_lead'])}</p>
<p class="sr">{E(Z['hero_sr'])}</p></div>
<button class="hs-arrow prev" type="button" aria-label="{t['prev']}">&#8249;</button><button class="hs-arrow next" type="button" aria-label="{t['next']}">&#8250;</button>
<div class="hs-dots"></div></section>

<section class="block"><div class="wrap">
<div class="sec-head"><h2>{t["h_clients"]}</h2><p>{E(Z['clients_intro'])}</p></div>
<div class="clients">{logos}</div>
</div></section>

<section class="block svc-sec"><div class="wrap">
<div class="sec-head"><h2>{t["h_services"]}</h2><p>{E(Z['services_intro'])}</p></div>
<div class="svc-split">
{panel(t['panels'][0][0], Z['game_intro'], t['panels'][0][1])}
{panel(t['panels'][1][0], Z['anim_intro'], t['panels'][1][1])}
</div></div></section>

<section class="block" id="work"><div class="wrap">
<div class="sec-head"><h2>{t["h_work"]}</h2><p>{E(Z['work_intro'])}</p></div>
{portfolio(limit=12, filters=True)}
<p style="margin-top:26px"><a href="{lu('production')}">{t["all_work"]}</a></p>
</div></section>

<section class="block alt"><div class="wrap two-col">
<div>
<img class="photo" src="{wix(HOME["story_image"], 733, 399)}" alt="{t['story_alt']}" width="733" height="399" loading="lazy">
<div class="badges">{"".join(f'<span class="badge">{b}</span>' for b in t["badges"])}</div>
</div>
<div class="story-copy">
<div class="year">{E(HOME["story_year"])}</div>
<h3>{E(Z['story_heading_1'])}</h3>
{paras(Z['story_text_1'])}
<h3>{E(Z['story_heading_2'])}</h3>
{paras(Z['story_text_2'])}
<p><a href="{lu('whoweare')}">{t["more_about"]}</a></p>
</div></div></section>

<section class="block alt"><div class="wrap"><div class="sec-head"><h2>{t["h_quote"]}</h2></div>
<blockquote class="quote"><p>“{E(Z['testimonial_quote'])}”</p><cite>{E(Z['testimonial_by'])}</cite></blockquote></div></section>

<section class="block"><div class="wrap"><div class="inc">
<div><h2>{E(Z['rebate_title'])}</h2>
{paras(Z['rebate_text'])}
<p><a href="{lu('fimi-cash-rebate-animation')}">{t["fimi_link"]}</a> &middot; <a href="{lu('animation-outsourcing-malaysia')}">{t["outs_link"]}</a></p>
<div class="logos">
<img src="{wix('7c4f43_86a92f7dc5054b2397a19f15f692620b~mv2.png', 172, 170)}" alt="FINAS" width="86" height="85" loading="lazy">
<img src="{wix('7c4f43_6a1047bfa1904aba94a4aea1b3ce6351~mv2.png', 254, 94)}" alt="MDEC" width="127" height="47" loading="lazy">
<img src="{wix('7c4f43_54ad31da47944267b8539420c00a7fe9~mv2.png', 200, 150)}" alt="MSC Malaysia" width="100" height="75" loading="lazy">
</div></div>
<div class="pct">30%<small>{t["pct"]}</small></div>
</div></div></section>

{contact_section()}
"""


def make_guide_body(g):
    def body():
        faq = ""
        if g["faq"]:
            items = "".join(f'<details><summary>{E(x["q"])}</summary><p>{E(x["a"])}</p></details>' for x in g["faq"])
            faq = (f'<section class="block alt"><div class="wrap"><div class="sec-head"><h2>Frequently asked questions</h2></div>'
                   f'<div class="faq">{items}</div></div></section>')
        return f"""
{page_hero(E(g['h1']), E(g['intro']), crumbs=[("Home", ""), (g['h1'], None)])}
<section class="block"><div class="wrap"><div class="prose" style="max-width:780px;margin:0 auto">{md_to_html(g['md'])}</div></div></section>
{faq}
{"" if g.get("legal") else contact_cta("Have a project in mind? Send us your brief.")}
"""
    return body


def guide_ld(g):
    if g.get("legal"):
        return []
    ld = [{"@context": "https://schema.org", "@type": "Article", "headline": g["h1"], "datePublished": g["published"],
           "dateModified": g["modified"], "image": absu(*g["img"]), "mainEntityOfPage": f"{SITE}/{g['slug']}",
           "author": {"@type": "Organization", "name": "Mirayi Sdn Bhd"},
           "publisher": {"@type": "Organization", "name": "Mirayi Sdn Bhd", "logo": {"@type": "ImageObject", "url": absu(LOGO_ID)}}}]
    if g["faq"]:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": x["q"], "acceptedAnswer": {"@type": "Answer", "text": x["a"]}} for x in g["faq"]]})
    return ld


def make_post_body(post):
    def body():
        others = "".join(
            f'<a href="{u("post/" + o["slug"])}">{E(o["h1"])}</a>' for o in POSTS if o["slug"] != post["slug"])
        i, w, h = post["img"]
        return f"""
<article class="article"><div class="wrap">
<div class="crumbs"><a href="{u('blog')}">All posts</a></div>
<h1>{E(post['h1'])}</h1>
<p class="meta">{E(post['author'])} · <time datetime="{post['published'][:10]}">{post['date']}</time> · {post['read']}</p>
<div class="prose" style="max-width:none">{md_to_html(post['md'])}</div>
<aside class="recent"><h2>Recent posts</h2>{others}<a href="{u('blog')}">See all</a></aside>
</div></article>
{contact_cta("Have a project in mind? Let's talk.")}
"""
    return body


def body_blog():
    cards = "".join(
        f"""<a class="post-card" href="{u('post/' + p['slug'])}">
<img src="{wix(p['img'][0], 800, 600)}" alt="{E(p['h1'])}" width="800" height="600" loading="lazy" style="object-fit:cover">
<h2>{E(p['h1'])}</h2><p>{E(p['excerpt'])}</p>
<div class="meta">{E(p['author'])} · {p['date']} · {p['read']}</div></a>"""
        for p in POSTS)
    return f"""
{page_hero("Animation insights &amp; industry tips", "Tips, trends, and behind-the-scenes stories from the animation industry—crafted for game producers, filmmakers, and creative directors worldwide.")}
<section class="block"><div class="wrap"><div class="posts">{cards}</div></div></section>
"""


def body_join():
    J = load_json("jobs.json")
    intro = "<br>".join(E(x) for x in J["intro"].split("\n"))
    jobs = ""
    for x in J["positions"]:
        text = E(x["text"]).replace("hr@mirayi.my", '<a href="mailto:hr@mirayi.my">hr@mirayi.my</a>')
        cls = "btn btn-ghost" if x.get("secondary") else "btn"
        btn = (f'<a class="{cls}" href="{E(x["link"])}" target="_blank" rel="noopener">{E(x.get("button") or "Apply now")}</a>'
               if x.get("link") else "")
        jobs += f'<div class="job"><div><h3>{E(x["title"])}</h3><p>{text}</p></div>{btn}</div>\n'
    return f"""
{page_hero(E(J["heading"]), intro)}
<section class="block"><div class="wrap">
<img class="photo" src="{wix('c08280_203cb469198a45968df9a3e6efcddf06f000.jpg', 1916, 808)}" alt="Join the Mirayi team" width="1916" height="808" style="aspect-ratio:1916/808;margin-bottom:56px">
<div class="sec-head"><h2>{E(J.get("positions_heading") or "Open positions")}</h2></div>
{jobs}</div></section>
"""


def body_contact():
    return f"""
{page_hero("Contact Mirayi", "Tell us about your project. We reply to every enquiry, usually within one to two working days.", crumbs=[("Home", ""), ("Contact", None)])}
<section class="block alt"><div class="wrap"><div class="sec-head"><h2>What to include in your brief</h2></div>
<ul class="checklist"><li>What you want made: game cinematic, series, commercial, assets or rigging.</li>
<li>Length or number of episodes, and a style reference or sample if you have one.</li>
<li>Which production steps you need, and your delivery date and format.</li>
<li>Scripts, storyboards or designs, if they exist. Ask us about the <a href="{u('fimi-cash-rebate-animation')}">FIMI 30% cash rebate</a> if your project may qualify.</li></ul></div></section>
{contact_section()}
"""


# ---------------------------------------------------------------- structured data

ORG = {
    "@context": "https://schema.org", "@type": "Organization", "name": "Mirayi Sdn Bhd", "alternateName": "Mirayi",
    "url": SITE, "foundingDate": "2005",
    "logo": absu(LOGO_ID),
    "description": "Malaysian 3D animation and IP development studio serving game, TV series and commercial clients in the U.S., Europe and Asia.",
    "sameAs": [h for _, h in SOCIAL],
    "address": {"@type": "PostalAddress", "addressRegion": SETTINGS.get("region", ""), "addressCountry": "MY"},
    **({"email": SETTINGS["public_email"]} if SETTINGS.get("public_email") else {}),
    **({"telephone": SETTINGS["phone"]} if SETTINGS.get("phone") else {}),
    **({"contactPoint": {"@type": "ContactPoint", "contactType": "sales", "areaServed": ["US", "EU", "Asia"],
                         **({"email": SETTINGS["public_email"]} if SETTINGS.get("public_email") else {}),
                         **({"telephone": SETTINGS["phone"]} if SETTINGS.get("phone") else {})}}
       if (SETTINGS.get("public_email") or SETTINGS.get("phone")) else {}),
    "areaServed": ["United States", "Europe", "Asia"],
    "knowsLanguage": ["en", "zh"],
    "knowsAbout": ["3D animation", "Game cinematics", "Animated TV series", "TV commercials", "Visual development",
                   "Animation outsourcing", "IP development", "Rigging", "Game assets"],
    "hasOfferCatalog": {"@type": "OfferCatalog", "name": "Animation services", "itemListElement": [
        {"@type": "Offer", "itemOffered": {"@type": "Service", "name": n}} for n in
        ["Game cinematic", "Cutscene animation", "Game assets", "Rigging", "Cartoon series production", "TV commercial",
         "Animated movie production", "IP development", "Visual development and concept art"]]},
}
ORG_L = {l: dict(ORG, **{"description": UI[l]["org_desc"], "inLanguage": META[l]["html"],
                         "knowsLanguage": ["en", "zh"]}) for l in LANGS}
WEBSITE_L = {l: {"@context": "https://schema.org", "@type": "WebSite", "name": META[l]["site_name"], "url": SITE + "/" + l + "/",
                 "inLanguage": META[l]["html"], "publisher": {"@type": "Organization", "name": "Mirayi Sdn Bhd"}} for l in LANGS}
WEBSITE = {"@context": "https://schema.org", "@type": "WebSite", "name": "Mirayi", "url": SITE,
           "publisher": {"@type": "Organization", "name": "Mirayi Sdn Bhd"}}


def article_ld(p):
    i, w, h = p["img"]
    return {
        "@context": "https://schema.org", "@type": "BlogPosting", "headline": p["h1"],
        "datePublished": p["published"], "dateModified": p["modified"],
        "author": {"@type": "Person", "name": p["author"]},
        "image": absu(i, w, h),
        "mainEntityOfPage": f"{SITE}/post/{p['slug']}",
        "publisher": {"@type": "Organization", "name": "Mirayi Sdn Bhd"},
    }


PAGES = [
    dict(path="", active="home", portfolio=True, body=body_home,
         title="3D Animation Outsourcing for Games, Series & Commercials | Mirayi", og_title="Mirayi Game & Animation Studio",
         desc="Mirayi delivers high-quality 3D animation for games, TV series, and commercials. Trusted by studios in the U.S., Europe, and Asia since 2005.",
         keywords="top animation studios, top asian animation studios, best 3d animation, top animation studios in south east asia, animation companies, 3d animation studio in malaysia, animation company in malaysia, south east asia animation studios, 3d animation",
         og_img=("c08280_97853ac24bf54b97a6738ef0a0de4944~mv2.jpg", 2000, 1126), jsonld=[ORG, WEBSITE]),
    dict(path="whoweare", active="who", body=body_whoweare,
         title="About Mirayi | Global 3D Animation & IP Development Studio",
         desc="Discover Mirayi, a Malaysian 3D animation studio serving the U.S., Europe, and Asia. Since 2005, delivering cinematic animation for games, TV, and commercials.",
         keywords="top animation studios, top asian animation studios, best 3d animation, top animation studios in malaysia, animation companies, 3d animation studio in malaysia , animation company in malaysia, animation studio malaysia, malaysia animation company",
         og_img=("0cc356_d0325ce9600e45efaa4064ee73109363~mv2.jpg", 1080, 810)),
    dict(path="ourbusiness", active="who", body=body_ourbusiness, title="Mirayi | Our Game & Animation Services",
         desc="Mirayi Sdn Bhd is a premier animation studio in Malaysia, offering expert services in game cinematics, cartoon series creation, animation production, and game asset modeling. From stunning visuals to engaging storytelling, we deliver world-class animation solutions tailored to your needs.",
         keywords="3D animation, Malaysia Animation studios, top 3D animation studio, animation outsourcing company, malaysia animation outsourcing companies",
         og_img=OG_SERVICES),
    # NOTE: the title and description below keep the original spelling ("Oringinal", "Proviving") on purpose,
    # so the indexed snippet is unchanged. Fixing the typos is safe if you prefer.
    dict(path="mirayibrand", active="brands", portfolio=True, body=body_brands, title="Mirayi | Mirayi Game & Oringinal IP",
         desc="Mirayi Animation Studio is passionate in Proviving Game & Animation services and creating fresh and heartwarming stories to all our audiences around the world.",
         keywords=KW_PROD, og_img=("c08280_d0b53444d92e4abca9e6c8f33c5458d0~mv2.jpg", 2500, 1277)),
    dict(path="production", active="prod", portfolio=True, body=body_production,
         title="3D Animation Portfolio | Game Cinematics, TV Series & Commercials",
         desc="Explore Mirayi’s portfolio of game cinematics, TV series, commercials, and feature film animation. Trusted by international studios worldwide.",
         keywords=KW_PROD, og_img=("c08280_4b3803cc048e4524bbbe1ebac660d5db~mv2.jpg", 2500, 1121)),
    dict(path="seriesandfilms", active="prod", portfolio=True, body=body_series, title="TV Series Animation Production | Mirayi",
         desc="Mirayi produces TV series animation for broadcasters and streaming platforms in the U.S., Europe, and Asia. High-quality, deadline-driven, and budget-friendly.",
         keywords=KW_PROD, og_img=OG_SERVICES),
    dict(path="gameproduction", active="prod", body=body_game, title="Game Animation Studio | Mirayi",
         desc="Game cinematic , Game cutscene , in game animation, game assets , rigging", keywords=KW_PROD, og_img=OG_SERVICES),
    dict(path="tvcommercials", active="prod", portfolio=True, body=body_tv, title="Commercial Animation Studio | Mirayi",
         desc="Impactful animated commercials for brands in the U.S., Europe, and Asia. Mirayi delivers cinematic quality with a marketing edge.",
         keywords=KW_PROD, og_img=OG_SERVICES),
    dict(path="visualdevelopment", active="prod", body=body_visdev, title="Mirayi | Visual Development . Concept Art",
         desc="We provided Visual development for Game and Animation , Develop IP and Movie.", keywords=KW_BLOG, og_img=OG_SERVICES),
    dict(path="blog", active="blog", body=body_blog, title="Animation Insights & Industry Tips | Mirayi Blog",
         desc="Tips, trends, and behind-the-scenes stories from the animation industry—crafted for game producers, filmmakers, and creative directors worldwide.",
         keywords=KW_BLOG, og_img=("c08280_822ba7b0d5544a279577de49f9806912~mv2.jpg", 2500, 1091)),
    dict(path="contact", active="contact", body=body_contact, title="Contact Mirayi | Request a Quote for 3D Animation",
         desc="Request a quote for game cinematics, TV series, commercial or feature animation. Email, phone, WhatsApp, Lark and WeChat. Mirayi, Selangor, Malaysia.",
         keywords="contact animation studio, request animation quote, animation outsourcing quote, Mirayi contact", og_img=OG_SERVICES,
         jsonld=[{"@context": "https://schema.org", "@type": "ContactPage", "name": "Contact Mirayi", "url": SITE + "/contact",
                  "mainEntity": {"@type": "Organization", "name": "Mirayi Sdn Bhd"}}]),
    dict(path="join-with-us", active="join", body=body_join, title="Mirayi | Join with us | Malaysia Animation Studio",
         desc="We are zealous about our creative and dynamic force where success is relentless.",
         keywords="animation career, jobs in animation, 3d animation jobs, animation internships, animation jobs for freshers, jobs for animators, animation job openings, animator jobs",
         og_img=OG_SERVICES),
]

for _s in load_json("seo.json")["pages"]:
    _path = "" if _s["path"] == "/" else _s["path"].strip("/")
    for _pg in PAGES:
        if _pg["path"] == _path:
            for _k, _f in (("title", "title"), ("desc", "description"), ("keywords", "keywords")):
                if _s.get(_f) is not None and str(_s[_f]).strip():
                    _pg[_k] = _s[_f]

_TR_OG = ("c08280_97853ac24bf54b97a6738ef0a0de4944~mv2.jpg", 2000, 1126)
for _l in LANGS:
    if _l in HOME_L:
        _h = HOME_L[_l]
        PAGES.append(dict(path=_l, lang=_l, active="home", portfolio=True, body=body_home_tr, title=_h["seo_title"],
                          desc=_h["seo_description"], keywords=_h.get("seo_keywords", ""), og_img=_TR_OG,
                          og_title=_h["seo_title"], jsonld=[ORG_L[_l], WEBSITE_L[_l]]))
    for _z in load_lang_pages(_l):
        PAGES.append(dict(path=_l + "/" + _z["slug"], lang=_l, active="fimi" if _z["slug"] == "fimi-cash-rebate-animation" else _z["active"], portfolio=_z["portfolio"], body=make_tr_body(_z),
                          title=_z["title"], desc=_z["desc"], keywords=_z["keywords"], og_img=_z["img"], crumb=_z["h1"],
                          jsonld=tr_ld(_z)))

for _g in GUIDES:
    PAGES.append(dict(
        crumb=_g["h1"], path=_g["slug"], active="fimi" if _g["slug"] == "fimi-cash-rebate-animation" else "who", body=make_guide_body(_g), title=_g["title"], desc=_g["desc"],
        keywords=_g["keywords"], og_type="website" if _g.get("legal") else "article", og_img=_g["img"],
        article=None if _g.get("legal") else dict(author="Mirayi", published=_g["published"], modified=_g["modified"]),
        jsonld=guide_ld(_g)))

for _p in POSTS:
    PAGES.append(dict(
        path="post/" + _p["slug"], active="blog", body=make_post_body(_p), title=_p["title"], desc=_p["meta_desc"],
        og_desc=_p["og_desc"], og_type="article", og_img=_p["img"],
        article=dict(author=_p["author"], published=_p["published"], modified=_p["modified"]),
        jsonld=[article_ld(_p)]))


# ---------------------------------------------------------------- static files

def llms_txt():
    ip = [w["title"] for w in load_json("works.json")["works"] if w.get("kind") == "ip"]
    pages = [("About Mirayi", "whoweare"), ("Our business and services", "ourbusiness"), ("Our original IP", "mirayibrand"),
             ("Production portfolio", "production"), ("Animated series and feature film", "seriesandfilms"),
             ("Game animation services", "gameproduction"), ("TV commercial animation", "tvcommercials"),
             ("Visual development and concept art", "visualdevelopment"), ("Blog", "blog"), ("Careers", "join-with-us")]
    lines = ["# Mirayi Sdn Bhd (Mirayi Animation Studio)", "",
             "> Malaysian 3D animation and IP development studio, founded in 2005. Mirayi produces game cinematics, "
             "animated TV series, feature-film animation and TV commercials for clients in the U.S., Europe and Asia, and "
             "develops its own original animated IP. MSC Malaysia status; licensed by FINAS. Eligible projects can use the "
             "Film in Malaysia Incentive (FIMI) 30% cash rebate.", "",
             "Original IP: " + ", ".join(ip) + ".", "", "## Pages", ""]
    lines += [f"- [{n}]({SITE}/{p}): {next((x['description'] for x in load_json('seo.json')['pages'] if x['path'] == p), '')}".rstrip(": ")
              for n, p in pages]
    for _l in LANGS:
        trp = [p for p in PAGES if p.get("lang") == _l]
        if trp:
            lines += ["", UI[_l]["llms_h"], "", UI[_l]["llms_note"], ""]
            lines += [f"- [{p['crumb'] if p.get('crumb') else UI[_l]['crumb_home']}]({page_url(p['path'])}): {p['desc']}" for p in trp]
    lines += ["", "## Guides", ""] + [f"- [{g['h1']}]({SITE}/{g['slug']}): {g['desc']}" for g in GUIDES]
    lines += ["", "## Posts", ""] + [f"- [{p['h1']}]({SITE}/post/{p['slug']}): {p['meta_desc']}" for p in POSTS]
    lines += ["", "## Contact", "", f"- Business and collaboration enquiries: {SITE}/#contact"]
    if SETTINGS.get("public_email"):
        lines.append(f"- Email: {SETTINGS['public_email']}")
    if SETTINGS.get("phone"):
        lines.append(f"- Phone / WhatsApp: {SETTINGS['phone']}")
    if SETTINGS.get("region"):
        lines.append(f"- Location: {SETTINGS['region']}, Malaysia")
    return "\n".join(lines) + "\n"


def write_static():
    urls = []
    for p in PAGES:
        loc = page_url(p["path"])
        mod = p["article"]["modified"][:10] if p.get("article") else TODAY
        alts = "".join(f'<xhtml:link rel="alternate" hreflang="{hl}" href="{href}"/>' for hl, href in alt_links(p))
        urls.append(f"  <url><loc>{loc}</loc><lastmod>{mod}</lastmod>{alts}</url>")
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(urls) + "\n</urlset>\n", encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /api/\n\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")
    (ROOT / "llms.txt").write_text(llms_txt(), encoding="utf-8")
    (ROOT / "_redirects").write_text(
        "# Old Wix URLs that no longer have their own page -> nearest new page (permanent 301)\n"
        "/jobs /join-with-us 301\n"
        "/join-with-us-1 /join-with-us 301\n"
        "/search /blog 301\n"
        "/profile/* /blog 301\n"
        "/blog/categories/* /blog 301\n"
        "/blog-categories/* /blog 301\n", encoding="utf-8")
    (ROOT / "_headers").write_text(
        "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n"
        "/admin/*\n  X-Robots-Tag: noindex\n  Cache-Control: no-store\n" + "".join(f"/{l}/*\n  Content-Language: {META[l]['header']}\n" for l in LANGS) + "/assets/site.js\n  Cache-Control: public, max-age=3600\n/assets/portfolio.js\n  Cache-Control: public, max-age=3600\n/assets/style.css\n  Cache-Control: public, max-age=3600\n/assets/config.js\n  Cache-Control: no-cache\n/assets/works.js\n  Cache-Control: no-cache\n/assets/img/*\n  Cache-Control: public, max-age=31536000, immutable\n",
        encoding="utf-8")


def write_404():
    global DEPTH, LANG
    DEPTH = 0
    LANG = "en"
    body = f"""<section class="page-hero"><div class="wrap"><h1>Page not found</h1>
<p>That page has moved or no longer exists.</p>
<div class="actions"><a class="btn" href="{u()}">Go to the homepage</a><a class="btn btn-ghost" href="{u('production')}">See our work</a></div></div></section>"""
    page = dict(path="404", title="Page not found | Mirayi", desc="Page not found.", og_img=("c08280_97853ac24bf54b97a6738ef0a0de4944~mv2.jpg", 2000, 1126))
    doc = f"""<!doctype html>
<html lang="en"><head>
{head(page)}
<meta name="robots" content="noindex">
</head><body>
{header(None, "404")}
<main id="main">{body}</main>
{footer()}
<script src="{a('site.js')}" defer></script>
</body></html>
"""
    (OUT / "404.html").write_text(doc, encoding="utf-8")


def write_works():
    """content/works.json -> assets/works.js (read by the portfolio on the page)."""
    out = []
    for w in load_json("works.json")["works"]:
        src = w.get("img", "")
        mid = media_id(src)
        if mid and not local_file(mid):
            img = mid                                  # still on the old host: portfolio.js builds the URL
        elif mid:
            img = "/assets/img/" + local_file(mid).name
        else:
            img = src if src.startswith("http") else "/" + src.lstrip("/")
        ww, hh = dims_of(src if not mid else src, w.get("w"), w.get("h"))
        if w.get("w") and w.get("h"):
            ww, hh = w["w"], w["h"]
        else:
            ww, hh = 250, round(250 * hh / ww)
        item = {"t": w["title"], "kind": w.get("kind", "service"), "cat": w.get("cat", "series"),
                "type": w.get("type", ""), "img": img, "w": ww, "h": hh}
        if w.get("video"):
            item["video"] = w["video"]
        if w.get("note"):
            item["note"] = w["note"]
        for src_k, dst_k in (("title_zh", "tz"), ("type_zh", "xz"), ("note_zh", "nz"), ("video_cn", "vz"),
                             ("title_ko", "tk"), ("type_ko", "xk"), ("note_ko", "nk"), ("title_ja", "tj"), ("type_ja", "xj"), ("note_ja", "nj")):
            if w.get(src_k):
                item[dst_k] = w[src_k]
        out.append(item)
    txt = ("/* GENERATED by _tools/build.py from content/works.json. Edit works in /admin (or content/works.json), not here. */\n"
           "window.MIRAYI_WORKS = " + json.dumps(out, ensure_ascii=False, indent=1) + ";\n")
    (ROOT / "assets" / "works.js").write_text(txt, encoding="utf-8")
    cfg = ("/* GENERATED from content/settings.json by _tools/build.py */\n"
           "window.MIRAYI = " + json.dumps({"localImages": False, "formEndpoint": SETTINGS.get("form_endpoint", ""),
                                            "contactEmail": SETTINGS.get("contact_email", "")}, indent=2) + ";\n")
    (ROOT / "assets" / "config.js").write_text(cfg, encoding="utf-8")
    return [x["img"] for x in out]


WORK_IMGS = []


def validate_ids():
    ids = {i for i in WORK_IMGS if not i.startswith(("/", "http"))}
    bad = sorted(i for i in (USED_IDS | ids) if not ID_RE.match(i))
    if bad:
        print("WARNING: image ids that do not look like Wix media ids:")
        for b in bad:
            print("   ", b)
    return len(USED_IDS | ids), bad


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    optimize_images()
    WORK_IMGS = write_works()
    for p in PAGES:
        render(p)
    if not PREVIEW:
        write_static()
    write_404()
    n, bad = validate_ids()
    print(f"built {len(PAGES)} pages + 404 into {OUT} ({n} distinct images referenced, {len(bad)} suspicious ids)")
