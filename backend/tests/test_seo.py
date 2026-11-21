"""SEO: crawlable pages, sitemap, robots, structured data and noindex on private paths."""
import json, re
from xml.etree import ElementTree as ET
from app.config import settings
from app.seo import PAGES, enabled_cities


def test_robots_and_sitemap(client):
    r = client.get("/robots.txt"); assert r.status_code == 200
    assert "Disallow: /api/" in r.text and "Disallow: /uploads/" in r.text and "Sitemap:" in r.text
    x = client.get("/sitemap.xml"); assert x.status_code == 200
    locs = [e.text for e in ET.fromstring(x.content).iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    for slug in PAGES:
        assert f"{settings.PUBLIC_URL}/{slug}" in locs
    for c in enabled_cities():
        assert f"{settings.PUBLIC_URL}/companions/{c}" in locs
    assert not any("/api/" in u or "partner/" in u for u in locs)      # no private data / individual profiles


def test_every_page_has_seo_basics(client):
    paths = ["/guides", "/faq"] + [f"/{s}" for s in PAGES] + [f"/companions/{c}" for c in enabled_cities()]
    for p in paths:
        r = client.get(p); assert r.status_code == 200, p
        h = r.text
        assert re.search(r"<title>.{10,}</title>", h) and 'name="description"' in h and "<h1>" in h, p
        assert f'<link rel="canonical" href="{settings.PUBLIC_URL}{p}">' in h, p
        for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h):
            json.loads(blob.replace("<\\/", "</"))                      # structured data must be valid JSON


def test_keyword_pages_stay_honest_about_the_policy(client):
    h = client.get("/partner-on-rent").text.lower()
    for kw in ("girlfriend on rent", "boyfriend on rent", "partner on rent"):
        assert kw in h
    assert "do not offer romantic relationships, sexual services, escort services" in h
    assert "money dating" not in client.get("/guides").text.lower()


def test_unknown_city_404_and_home_has_absolute_canonical(client):
    assert client.get("/companions/atlantis").status_code == 404
    home = client.get("/").text
    assert f'<link rel="canonical" href="{settings.PUBLIC_URL}/">' in home and "__SITE__" not in home


def test_private_paths_are_noindex(client):
    assert "noindex" in client.get("/api/nothing-here").headers["x-robots-tag"]
