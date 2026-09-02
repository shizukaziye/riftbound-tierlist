#!/usr/bin/env python3
"""Bake the Riftbound card catalog from Riot's public gallery API.

Writes data/cards.json: a compact array the page loads once. Fields:
  c  collector code (OGN-001)      n  name
  s  set id                        t  card type (Unit, Spell, ...)
  r  rarity                        d  domains (list)
  e  energy cost                   p  power cost
  m  might                         u  image URL (Sanity CDN)
  x  rules text (plain, effect appended)   a  artist
  mb might bonus (gear)            g  tags (e.g. champion names)
  o  "l" when the card is landscape (battlefields)
"""
import html
import json
import re
import time
import urllib.request
from pathlib import Path

API = ("https://content.publishing.riotgames.com/publishing-content/v2.0/"
       "public/channel/riftbound_website/list/riftbound_gallery_cards"
       "?locale=en_US&from={start}&limit=200")
OUT = Path(__file__).resolve().parent.parent / "data"
UA = "riftbound-tierlist bake (+https://github.com/shizukaziye/riftbound-tierlist)"
SET_EN = {"OGN": "Origins", "OGS": "Origins: Proving Grounds",
          "SFD": "Spiritforged", "UNL": "Unleashed", "VEN": "Vendetta",
          "RAD": "Radiance"}


def fetch(url, tries=4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)


def val(obj, *keys):
    """Walk {'label':..., 'value':{'label':...}} style wrappers."""
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def labels(obj, key):
    lst = val(obj, key) or []
    return [x.get("label") for x in lst if isinstance(x, dict) and x.get("label")]


def plain(htmltext):
    if not htmltext:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", htmltext)
    s = re.sub(r"</p>\s*<p>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def main():
    raw, start, unknown = [], 0, set()
    while True:
        d = fetch(API.format(start=start))
        items = d.get("data") or []
        raw.extend(items)
        total = (d.get("metadata") or {}).get("totalItems") or 0
        start += len(items)
        if not items or start >= total:
            break
        time.sleep(0.3)
    print(f"fetched {len(raw)} cards")

    cards, sets = [], {}
    for c in raw:
        code = (c.get("publicCode") or "").split("/")[0].strip()
        if not code:
            continue
        set_id = str(val(c, "set", "value", "id") or code.split("-")[0]).upper()
        sets.setdefault(set_id, val(c, "set", "value", "label") or set_id)
        for k in c:
            if k not in {"id", "collectorNumber", "name", "set", "cardType",
                         "publicCode", "rarity", "domain", "cardImage",
                         "orientation", "illustrator", "text", "energy",
                         "might", "power", "tags", "effect", "mightBonus"}:
                unknown.add(k)
        card = {
            "c": code,
            "n": c.get("name") or "",
            "s": set_id,
            "t": (labels(c.get("cardType"), "type") or [""])[0],
            "r": val(c, "rarity", "value", "label") or "",
            "d": labels(c.get("domain"), "values"),
            "u": val(c, "cardImage", "url") or "",
        }
        for src, dst in (("energy", "e"), ("might", "m"), ("power", "p")):
            v = val(c, src, "value", "label")
            if v not in (None, ""):
                card[dst] = v
        art = labels(c.get("illustrator"), "values")
        if art:
            card["a"] = art[0]
        text = plain(val(c, "text", "richText", "body"))
        if text:
            card["x"] = text
        effect = plain(val(c, "effect", "richText", "body"))
        if effect:
            card["x"] = (card.get("x", "") + "\n" + effect).strip()
        mb = val(c, "mightBonus", "value", "label")
        if mb not in (None, ""):
            card["mb"] = mb
        tags = val(c, "tags", "tags") or []
        tags = [t for t in tags if isinstance(t, str) and t]
        if tags:
            card["g"] = tags
        if c.get("orientation") == "landscape":
            card["o"] = "l"
        cards.append(card)

    if unknown:
        print("unhandled fields:", sorted(unknown))
    cards.sort(key=lambda c: (c["s"], c["c"]))
    if len(cards) < 1000:
        raise SystemExit(f"only {len(cards)} cards; refusing to write")
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"updated": time.strftime("%Y-%m-%d"),
           "sets": [{"i": k, "n": SET_EN.get(k, v)} for k, v in sorted(sets.items())],
           "cards": cards}
    (OUT / "cards.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                                    encoding="utf-8")
    from collections import Counter
    print(f"wrote {len(cards)} cards; sets {dict(Counter(c['s'] for c in cards))}")
    print("types", dict(Counter(c['t'] for c in cards)))
    print("rarity", dict(Counter(c['r'] for c in cards)))


if __name__ == "__main__":
    main()
