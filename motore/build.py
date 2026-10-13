#!/usr/bin/env python3
"""Markdown -> presentazione HTML (un solo file, font inclusi).

Uso:
    python3 build.py ../sapienza/sapienza.md            # genera sapienza.html accanto al .md
    python3 build.py ../sapienza/sapienza.md --serve    # anteprima live su http://localhost:8000
    python3 build.py ../sapienza/sapienza.md --pdf      # genera anche il PDF (serve google-chrome)
    python3 build.py talk.md --theme printproof --out /tmp/prova.html   # prova un altro tema

Il tema si sceglie nel .md con <!-- theme: nome --> (cartella themes/nome/).

Sintassi del .md: vedi README.md in questa cartella.
"""
import base64, html, http.server, os, re, shutil, subprocess, sys, threading, time
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
DEFAULT_THEME = "carta"
MIME = {".ttf": "font/ttf", ".otf": "font/otf", ".woff2": "font/woff2", ".woff": "font/woff",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
        ".svg": "image/svg+xml", ".gif": "image/gif"}
LABELS = {"spoiler": "spoiler", "problema": "problema", "soluzione": "soluzione"}

# ---------------------------------------------------------------- inline

CAPS_WORD = r"[A-ZÀÈÉÌÒÙ][A-ZÀÈÉÌÒÙ'’]*"
CAPS_RUN = re.compile(rf"(?<![\w/])({CAPS_WORD}(?:[ ]+{CAPS_WORD})*)(?![\w/])")


def caps(text):
    """Evidenzia le parole in MAIUSCOLO (almeno una parola da 4+ lettere: KDE o PDF no, ANSIA sì)."""
    def repl(m):
        run = m.group(1)
        if any(len(re.sub(r"['’]", "", w)) >= 4 for w in run.split()):
            return f'<span class="caps">{run}</span>'
        return run
    return CAPS_RUN.sub(repl, text)


def inline(text):
    keep = []

    def stash(s):
        keep.append(s)
        return f"\x00{len(keep) - 1}\x00"

    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{m.group(1)}</code>"), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  lambda m: stash(f'<a href="{m.group(2)}">{m.group(1)}</a>'), text)
    text = re.sub(r"\[([^\]]+)\]", lambda m: stash(f'<span class="todo">[{m.group(1)}]</span>'), text)
    text = caps(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], text)


# ---------------------------------------------------------------- blocchi

def paragraph(s, step):
    st = f' data-step="{step}"' if step else ""
    m = re.match(r"^(\w+):\s+(.*)$", s)
    if m and m.group(1).lower() in LABELS:
        kind = LABELS[m.group(1).lower()]
        return f'<p class="lab"{st}><span class="chip {kind}">{html.escape(m.group(1))}</span> {inline(m.group(2))}</p>'
    if s.startswith("(") and s.endswith(")"):
        return f'<p class="aside"{st}>{inline(s)}</p>'
    if s.endswith(":"):
        return f'<p class="lead"{st}>{inline(s)}</p>'
    return f"<p{st}>{inline(s)}</p>"


def section_title(text):
    words = text.split(" ", 1)
    if len(words) == 2 and words[0].upper() == "COME":
        return f'<span class="come">{html.escape(words[0])}</span> {html.escape(words[1])}'
    return html.escape(text)


def image_aspect(path):
    """larghezza/altezza di un PNG o JPEG leggendo solo l'intestazione (niente dipendenze)."""
    try:
        with open(path, "rb") as f:
            head = f.read(26)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return int.from_bytes(head[16:20], "big") / int.from_bytes(head[20:24], "big")
            if head[:2] == b"\xff\xd8":
                f.seek(2)
                while True:
                    marker, size = f.read(2), int.from_bytes(f.read(2), "big")
                    if marker[0] != 0xFF:
                        break
                    if marker[1] in (0xC0, 0xC1, 0xC2):
                        f.read(1)
                        h, w = int.from_bytes(f.read(2), "big"), int.from_bytes(f.read(2), "big")
                        return w / h
                    f.seek(size - 2, 1)
    except Exception:
        pass
    return 1.0


def parse(md, base=Path(".")):
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)  # i commenti non finiscono nelle slide
    chunks = re.split(r"^\s*---\s*$", md, flags=re.M)
    slides, section, num = [], None, 0
    for chunk in chunks:
        lines = chunk.strip("\n").splitlines()
        if not any(l.strip() for l in lines):
            continue
        out, notes, classes, step, in_list = [], [], [], 0, False
        figs, aspects = [], []
        kicker = None
        opener = None
        for raw in lines:
            s = raw.strip()
            if notes or s.lower().startswith("note:"):
                notes.append(s[5:].strip() if not notes else s)
                continue
            if not s:
                continue
            if s.startswith("{.") and s.endswith("}"):  # {.classe} -> classe CSS sulla slide
                classes += s[2:-1].replace(".", " ").split()
                continue
            if s == "--":
                step += 1
                continue
            st = f' data-step="{step}"' if step else ""
            is_li = s.startswith("- ") or s.startswith("* ")
            if in_list and not is_li:
                out.append("</ul>")
                in_list = False
            if s.startswith("# "):
                classes.append("title")
                out.append(f"<h1{st}>{inline(s[2:])}</h1>")
            elif s.startswith("## "):
                num += 1
                section = s[3:].strip()
                opener = section
            elif s.startswith("### "):
                out.append(f"<h3{st}>{inline(s[4:])}</h3>")
            elif is_li:
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append(f"<li{st}>{inline(s[2:])}</li>")
            elif re.match(r"^!\[[^\]]*\]\([^)]+\)$", s):
                alt, src = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", s).groups()
                cap = f"<figcaption>{inline(alt)}</figcaption>" if alt else ""
                figs.append(f'<figure{st}><img src="{html.escape(src)}" alt="{html.escape(alt)}">{cap}</figure>')
                aspects.append(image_aspect(base / src))
            else:
                out.append(paragraph(s, step))
        if in_list:
            out.append("</ul>")
        if figs:  # immagini: accanto al testo, sotto il testo, o da sole
            media = f'<div class="media" data-count="{len(figs)}">' + "".join(figs) + "</div>"
            text_blocks = [b for b in out if not b.startswith("<h3")]
            if not text_blocks:
                classes.append("img-only")
                out = [b for b in out] + [media]
            else:
                if not {"side", "stack"} & set(classes):
                    chars = len(re.sub(r"<[^>]+>", "", "".join(text_blocks)))
                    a = min(aspects)
                    wide = a >= 2 or (a >= 1.45 and chars <= 90)
                    classes.append("stack" if (len(figs) == 1 and wide) or len(figs) > 2 else "side")
                classes.append("has-img")
                out = [f'<div class="txt">{"".join(out)}</div>', media]
        if opener:
            classes.append("opener")
            kicker = (f'<div class="num">{num:02d}</div>'
                      f'<h2>{section_title(opener)}</h2>')
        elif section and "title" not in classes:
            kicker = f'<div class="run"><span class="num">{num:02d}</span> {html.escape(section)}</div>'
        slides.append({"classes": classes, "kicker": kicker, "body": "\n".join(out),
                       "notes": "\n".join(notes), "steps": step, "section": section or "", "num": num})
    return slides


# ---------------------------------------------------------------- output

def inline_urls(css, base):
    """url(file) relativi al CSS -> data URI, così l'html resta un file unico."""
    def repl(m):
        ref = m.group(2)
        if ref.startswith(("data:", "http:", "https:", "#")):
            return m.group(0)
        f = (base / ref).resolve()
        if not f.exists():
            print(f"  attenzione: {f} non trovato")
            return m.group(0)
        mime = MIME.get(f.suffix.lower(), "application/octet-stream")
        return f"url(data:{mime};base64,{base64.b64encode(f.read_bytes()).decode()})"
    return re.sub(r"""url\((['"]?)([^)'"]+)\1\)""", repl, css)


def theme_css(name):
    d = ENGINE / "themes" / name
    if not (d / "theme.css").exists():
        sys.exit(f"tema '{name}' non trovato in {ENGINE / 'themes'}")
    return inline_urls((d / "theme.css").read_text(encoding="utf-8"), d)


def render(md_path, theme=None, out_path=None, stamp=None):
    md_path = Path(md_path).resolve()
    text = md_path.read_text(encoding="utf-8")
    m = re.search(r"<!--\s*theme:\s*([\w-]+)\s*-->", text)
    theme = theme or (m.group(1) if m else DEFAULT_THEME)
    slides = parse(text, md_path.parent)
    title = next((re.sub(r"<[^>]+>", "", re.search(r"<h1[^>]*>(.*?)</h1>", s["body"]).group(1))
                  for s in slides if "title" in s["classes"]), md_path.stem)
    css = (ENGINE / "base.css").read_text(encoding="utf-8") + "\n" + theme_css(theme)
    local_css = md_path.with_name("style.css")  # ritocchi specifici del talk (facoltativo)
    if local_css.exists():
        css += "\n/* style.css del talk */\n" + local_css.read_text(encoding="utf-8")
    js = (ENGINE / "deck.js").read_text(encoding="utf-8")
    total = len(slides)
    parts = []
    for i, s in enumerate(slides, 1):
        cls = " ".join(["slide"] + s["classes"])
        talk = html.escape(title)
        sec = html.escape(s["section"])
        notes = f'<aside class="notes">{html.escape(s["notes"])}</aside>' if s["notes"] else ""
        parts.append(
            f'<section class="{cls}" data-steps="{s["steps"]}" data-n="{i}" data-sec="{s["num"]}">\n'
            f'<div class="deco"></div>\n'
            f'{s["kicker"] or ""}\n<div class="body"><div class="inner">\n{s["body"]}\n</div></div>\n'
            f'<footer><span class="talk">{talk}</span><span class="sec">{sec}</span>'
            f'<span class="page">{i:02d} / {total:02d}</span></footer>{notes}\n</section>')
    out = f"""<!doctype html>
<html lang="it" data-skin="{theme}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="talk-version" content="{html.escape(stamp or '')}">
<title>{html.escape(title)}</title>
<style>
{css}
</style>
</head>
<body>
<div id="deck">
{chr(10).join(parts)}
</div>
<div id="progress"><div></div></div>
<script>
{js}
</script>
</body>
</html>
"""
    html_path = Path(out_path).resolve() if out_path else md_path.with_suffix(".html")
    html_path.write_text(out, encoding="utf-8")
    return html_path, total


def pdf(html_path):
    chrome = next((c for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)), None)
    if not chrome:
        sys.exit("google-chrome/chromium non trovato: niente PDF")
    out = html_path.with_suffix(".pdf")
    subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=8000", f"--print-to-pdf={out}",
                    html_path.as_uri() + "?print"], check=True, capture_output=True)
    return out


def serve(md_path, port=8000, theme=None, out_path=None):
    md_path = Path(md_path).resolve()
    watched = lambda: [md_path, md_path.with_name("style.css"), *ENGINE.glob("*.css"), *ENGINE.glob("*.js"),
                       *ENGINE.glob("themes/**/*.css")]
    stamp = lambda: [p.stat().st_mtime if p.exists() else 0 for p in watched()]

    def loop():
        last = stamp()
        while True:
            time.sleep(0.4)
            now = stamp()
            if now != last:
                last = now
                try:
                    _, n = render(md_path, theme, out_path)
                    print(f"  ricostruito ({n} slide)")
                except Exception as e:  # un errore di battitura non deve fermare l'anteprima
                    print("  errore:", e)

    threading.Thread(target=loop, daemon=True).start()
    os.chdir(Path(out_path).resolve().parent if out_path else md_path.parent)
    handler = lambda *a: http.server.SimpleHTTPRequestHandler(*a)
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    name = Path(out_path).name if out_path else md_path.with_suffix('.html').name
    print(f"Anteprima live: http://localhost:{port}/{name}  (Ctrl+C per uscire)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


def option(name):
    if name in sys.argv:
        i = sys.argv.index(name)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    return None


if __name__ == "__main__":
    theme, out_path, port, stamp = option("--theme"), option("--out"), option("--port"), option("--stamp")
    values = {theme, out_path, port, stamp}
    args = [a for a in sys.argv[1:] if not a.startswith("--") and a not in values]
    if not args:
        sys.exit(__doc__)
    path, n = render(args[0], theme, out_path, stamp)
    print(f"{path}  ({n} slide)")
    if "--pdf" in sys.argv:
        print(pdf(path))
    if "--serve" in sys.argv:
        serve(args[0], int(port or 8000), theme, out_path)
