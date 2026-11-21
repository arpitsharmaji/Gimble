"""Public, crawlable SEO pages, robots.txt and sitemap.xml.

The app itself is a single-page app on #/ routes, which search engines cannot index as separate pages. These server-rendered
pages (real URLs, real HTML, own title/description/canonical/structured data) are what can rank. They link into the app.
Individual partner profiles are deliberately NOT public or in the sitemap (privacy and safety).
"""
import json
from pathlib import Path
from datetime import date
from html import escape
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse, Response, JSONResponse, RedirectResponse
from .config import settings
from .seo_content import PAGES, CITIES, CTA

router = APIRouter(include_in_schema=False)
TODAY = date.today().isoformat()
CACHE = {"Cache-Control": "public, max-age=3600"}


def base() -> str:
    return settings.PUBLIC_URL


def enabled_cities() -> list[str]:
    want = [c.strip().lower() for c in settings.SEO_CITIES.split(",") if c.strip()]
    return [c for c in CITIES if c in want] if want else list(CITIES)


def _jsonld(*objs: dict) -> str:
    # "</" is escaped so the data can never close the script tag
    scripts = []
    for obj in objs:
        json_data = json.dumps(obj, ensure_ascii=False)
        json_data = json_data.replace("</", "<\\/")
        scripts.append(
            f'<script type="application/ld+json">{json_data}</script>'
        )
    return "".join(scripts)


def _org() -> dict:
    return {"@context": "https://schema.org", "@type": "Organization", "name": "Gimble", "url": base() + "/",
            "logo": base() + "/logo.png",
            "description": "Marketplace for friendly, public, non-sexual companionship. Adults 18+ only."}


def _faq_ld(faqs) -> dict:
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]}


def _crumbs(items) -> dict:
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": base() + p} for i, (n, p) in enumerate(items)]}


def _blocks(parts) -> str:
    """Section content: '*' = bullet, '#' = numbered step, otherwise a paragraph."""
    out, mode, buf = [], "", []
    def flush():
        nonlocal buf, mode
        if buf:
            tag = "ul" if mode == "*" else "ol"
            out.append(f"<{tag}>" + "".join(f"<li>{escape(x)}</li>" for x in buf) + f"</{tag}>")
        buf, mode = [], ""
    for p in parts:
        if p[:1] in "*#":
            if mode and mode != p[0]:
                flush()
            mode = p[0]; buf.append(p[1:])
        else:
            flush(); out.append(f"<p>{escape(p)}</p>")
    flush()
    return "".join(out)


CSS = ("*{box-sizing:border-box}body{margin:0;background:#0d0b18;color:#e9e4f2;font:17px/1.65 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}"
       "a{color:#b79cff}header,footer{max-width:860px;margin:0 auto;padding:18px 20px}header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px}"
       "header a.brand{font-weight:800;font-size:1.3rem;color:#fff;text-decoration:none}main{max-width:860px;margin:0 auto;padding:8px 20px 40px}"
       "h1{font-size:clamp(1.7rem,4.5vw,2.5rem);line-height:1.2;margin:.4em 0}h2{font-size:1.35rem;margin:1.6em 0 .4em}li{margin:.3em 0}"
       ".cta{display:inline-block;background:#6a3dff;color:#fff;text-decoration:none;font-weight:700;padding:13px 22px;border-radius:12px;margin:10px 0}"
       ".box{background:#16132a;border:1px solid #2b2650;border-radius:14px;padding:6px 20px 14px;margin:22px 0}.crumb{font-size:.9rem;color:#a99fc4}"
       "nav.links a{margin-right:14px;white-space:nowrap}.small{font-size:.9rem;color:#a99fc4}")


def _page(path: str, title: str, desc: str, h1: str, body: str, kw=(), ld=()) -> HTMLResponse:
    url = base() + path
    links = "".join(f'<a href="/{s}">{escape(p["nav"])}</a>' for s, p in PAGES.items())
    html = f"""<!doctype html><html lang="en-IN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">{f'<meta name="keywords" content="{escape(", ".join(kw))}">' if kw else ''}
<meta name="robots" content="index,follow,max-image-preview:large"><link rel="canonical" href="{url}">
<link rel="alternate" hreflang="en-IN" href="{url}"><link rel="alternate" hreflang="x-default" href="{url}">
<meta property="og:type" content="website"><meta property="og:site_name" content="Gimble"><meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}"><meta property="og:url" content="{url}"><meta property="og:image" content="{base()}/icons/icon-512.png">
<meta name="twitter:card" content="summary"><meta name="theme-color" content="#0d0b18">
<link rel="icon" type="image/png" href="/icons/favicon-32.png"><style>{CSS}</style>{_jsonld(_org(), *ld)}</head><body>
<header><a class="brand" href="/">gimble</a><a class="cta" href="{CTA}">Browse companions</a></header>
<main><p class="crumb"><a href="/">Home</a> › <a href="/guides">Guides</a></p><h1>{escape(h1)}</h1>{body}
<div class="box"><h2>Ready to meet someone friendly?</h2><p>Friendly, public, non-sexual company. Adults 18+ only. Emergency? Call 112.</p><a class="cta" href="{CTA}">Browse companions</a></div></main>
<footer><nav class="links" aria-label="Guides">{links}<a href="/faq">FAQ</a></nav>
<p class="small">© Gimble · Gimble is not a dating or escort service. Sexual services are banned.</p></footer></body></html>"""
    return HTMLResponse(html, headers=CACHE)


def _faq_html(faqs) -> str:
    return "<h2>Frequently asked questions</h2>" + "".join(f"<h3>{escape(q)}</h3><p>{escape(a)}</p>" for q, a in faqs)


def _related(slugs) -> str:
    items = "".join(f'<li><a href="/{s}">{escape(PAGES[s]["h1"])}</a></li>' for s in slugs if s in PAGES)
    return f"<h2>Related guides</h2><ul>{items}</ul>" if items else ""


@router.get("/")
def home():
    """The app shell, with absolute canonical / social URLs filled in from PUBLIC_URL."""
    f = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    return HTMLResponse(f.read_text(encoding="utf-8").replace("__SITE__", base()), headers={"Cache-Control": "no-cache"})


@router.get("/index.html")
def index_redirect():
    return RedirectResponse("/", status_code=301)


@router.get("/robots.txt")
def robots():
    return PlainTextResponse(f"User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /uploads/\nDisallow: /upi-qr.png\n\nSitemap: {base()}/sitemap.xml\n", headers=CACHE)


@router.get("/sitemap.xml")
def sitemap():
    paths = ["/", "/guides", "/faq"] + [f"/{s}" for s in PAGES] + [f"/companions/{c}" for c in enabled_cities()]
    body = "".join(f"<url><loc>{escape(base() + p)}</loc><lastmod>{TODAY}</lastmod></url>" for p in paths)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>',
                    media_type="application/xml", headers=CACHE)


@router.get("/guides")
def guides():
    items = "".join(f'<li><a href="/{s}"><b>{escape(p["h1"])}</b></a><br><span class="small">{escape(p["desc"])}</span></li>' for s, p in PAGES.items())
    cities = "".join(f'<li><a href="/companions/{c}">Hire a companion in {escape(CITIES[c][0])}</a></li>' for c in enabled_cities())
    body = f"<p>Plain-English guides to hiring a companion, renting a friend, meeting new people and staying safe.</p><ul>{items}</ul><h2>By city</h2><ul>{cities}</ul>"
    return _page("/guides", "Guides: Hire a Companion, Rent a Friend & Meet New People | Gimble",
                 "Guides to hiring a companion, renting a friend, bringing a plus-one to events, meeting new people and staying safe. By Gimble.",
                 "Guides to companions, friendship and safe meet-ups", body,
                 ld=[_crumbs([("Home", "/"), ("Guides", "/guides")])])


@router.get("/faq")
def faq():
    seen, faqs = set(), []
    for p in PAGES.values():
        for q, a in p["faqs"]:
            if q not in seen:
                seen.add(q); faqs.append((q, a))
    return _page("/faq", "Gimble FAQ: Hiring a Companion, Safety, Payments | Gimble",
                 "Answers to common questions about hiring a companion, renting a friend, safety, payments and who can use Gimble.",
                 "Frequently asked questions", _faq_html(faqs), ld=[_faq_ld(faqs), _crumbs([("Home", "/"), ("FAQ", "/faq")])])


@router.get("/companions/{city}")
def city_page(city: str):
    if city not in enabled_cities():
        return JSONResponse({"detail": "Not found"}, status_code=404)
    name, areas = CITIES[city]
    faqs = [(f"How do I hire a companion in {name}?", f"Browse partner profiles, send a booking request with the activity, time and a public place in {name}, and pay through Gimble once the partner accepts. A Gimble membership is needed to send requests."),
            (f"Where should I meet in {name}?", f"Choose a busy public place, for example {', '.join(areas[:3])}. Gimble requires meet-ups to be in public places."),
            (f"Is Gimble a dating or escort service in {name}?", "No. Gimble is for friendly, public, non-sexual company. Sexual services are banned."),
            ("Who can use Gimble?", "Adults aged 18 and over.")]
    body = (f"<p>Looking for friendly company in {escape(name)}? On Gimble you can hire a companion for a coffee, a film, a workout, a walk, a dinner or an event. "
            f"Plans are time-limited, held in public places and paid for through the platform. Availability varies by area, so browse to see who is currently listed near you.</p>"
            f"<h2>Popular public places to meet in {escape(name)}</h2><ul>{''.join(f'<li>{escape(a)}</li>' for a in areas)}</ul>"
            f"<h2>Plans people book</h2><ul><li>Coffee and conversation</li><li>A film or concert buddy</li><li>A gym, run or yoga partner</li><li>Exploring the city</li><li>A plus-one for a wedding or event</li></ul>"
            f"<h2>How it works</h2><ol><li>Browse profiles and choose someone.</li><li>Send a request with the activity, time and a public location.</li><li>Pay through Gimble once they accept, then meet.</li></ol>"
            + _faq_html(faqs) + _related(["hire-a-companion", "rent-a-friend", "safe-meeting-tips"]))
    return _page(f"/companions/{city}", f"Hire a Companion in {name}: Safe, Public Plans | Gimble",
                 f"Hire a companion in {name} for coffee, films, workouts or events. Friendly, public, non-sexual company with admin-approved profiles. 18+ only.",
                 f"Hire a companion in {name}", body, kw=[f"hire a companion in {name}", f"rent a friend in {name}", f"companion in {name}", f"friend on rent {name}"],
                 ld=[_faq_ld(faqs), _crumbs([("Home", "/"), ("Guides", "/guides"), (name, f"/companions/{city}")])])


def _make(slug):
    def view():
        p = PAGES[slug]
        body = f"<p>{escape(p['intro'])}</p>" + "".join(f"<h2>{escape(h)}</h2>{_blocks(parts)}" for h, parts in p["sections"]) + _faq_html(p["faqs"]) + _related(p["related"])
        return _page(f"/{slug}", p["title"], p["desc"], p["h1"], body, kw=p["kw"],
                     ld=[_faq_ld(p["faqs"]), _crumbs([("Home", "/"), ("Guides", "/guides"), (p["nav"], f"/{slug}")])])
    view.__name__ = "seo_" + slug.replace("-", "_")
    return view


for _slug in PAGES:
    router.add_api_route(f"/{_slug}", _make(_slug), methods=["GET"], include_in_schema=False)
