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
  src "tcg" when the print comes from TCGplayer's feed (image is a TCGplayer
     product photo; u is the full URL, no Sanity params)  pm 1 = promo print
  v  print class for variants (Alt Art / Overnumbered / Signature / Token / Promo);
     for those r is set to v and br keeps the underlying card's rarity
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
          "RAD": "Radiance", "OPP": "Organized Play Promos",
          "SGN": "Secret Garden", "PR": "Promos"}


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


TCG_GROUPS = {24344: "OGN", 24439: "OGS", 24519: "SFD", 24560: "UNL", 24698: "VEN",
              24343: "PR", 24528: "OPP", 24552: "JDG", 24797: "SGN"}
DENOM_SET = {"298": "OGN", "024": "OGS", "221": "SFD", "219": "UNL", "166": "VEN",
             "006": "VEN", "003": "SGN"}
TCG_IMG = "https://tcgplayer-cdn.tcgplayer.com/product/{id}_in_1000x1000.jpg"


def tcg_extra(cards):
    """Prints TCGplayer sells that Riot's gallery omits: promo alt arts,
    rune variants, Secret Garden promos. Same-number promos (foil stamp on
    the base art) and oversized cards are skipped."""
    have = {c["c"] for c in cards}
    by_code = {c["c"]: c for c in cards}
    out, seen = [], set()
    for gid, ab in TCG_GROUPS.items():
        try:
            rows = fetch(f"https://tcgcsv.com/tcgplayer/89/{gid}/products").get("results") or []
        except Exception as e:
            print(f"tcg group {ab} failed: {e}")
            continue
        for p in rows:
            ext = {x["name"]: x["value"] for x in p.get("extendedData") or []}
            n = (ext.get("Number") or "").replace(" ", "")
            m = re.match(r"^(SP|R)?(\d+)([a-z*]?)/?(\d{3})?$", n)
            if not m or "//" in n or "Oversized" in p["name"]:
                continue
            pre, num, suf, den = m.groups()
            st = ab if ab in ("OGN", "OGS", "SFD", "UNL", "VEN") else DENOM_SET.get(den or "", ab)
            if pre == "SP":
                st = "VEN"
            if pre == "R" and ab == "OPP":
                st = "VEN" if "(Vendetta)" in p["name"] else "OPP"
            code = f"{st}-{pre or ''}{num}{suf}"
            if ab == "JDG":
                code += "j"
            if code in have or code in seen:
                continue
            if not suf and pre != "R" and ab in ("OPP", "PR"):
                continue                      # same-number promo of a base card
            name = re.sub(r"\s*\((Alternate Art|R\d+[a-z]?|Vendetta|GG EZ)\)\s*$", "", p["name"]).strip()
            base = by_code.get(f"{st}-{pre or ''}{num}")
            if not base:                      # runes share text across sets
                base = next((c for c in cards if c["n"] == name and c.get("t") == "Rune"
                             and not c.get("v")), None)
            tcg_r = ext.get("Rarity") or ""
            card = {"c": code, "n": name, "s": st, "u": TCG_IMG.format(id=p["productId"]), "src": "tcg"}
            if base:
                for k in ("t", "r", "d", "e", "m", "p", "x", "g", "o", "mb"):
                    if k in base:
                        card[k] = base[k]
            else:
                ctype = (ext.get("Card Type") or "").replace("Champion ", "")
                card["t"] = "Unit" if "Unit" in ctype else ctype
                card["r"] = tcg_r if tcg_r in RARITY_OK else ""
                card["d"] = [d for d in (ext.get("Domain") or "").split(";") if d]
                for src, dst in (("Energy Cost", "e"), ("Might", "m"), ("Power Cost", "p")):
                    v = str(ext.get(src) or "")
                    if v and not (v == "0" and card["t"] not in ("Unit", "Spell", "Gear")):
                        card[dst] = v
                card["x"] = plain(ext.get("Description") or "")
                tags = [t.strip() for t in (ext.get("Tag") or "").split(";") if t.strip()]
                if tags:
                    card["g"] = tags
                if card["t"] == "Battlefield":
                    card["o"] = "l"
            if pre == "R":
                card.setdefault("t", "Rune")
                card.setdefault("r", "Common")
                card.setdefault("d", [name.split()[0]] if name.endswith("Rune") else [])
                variant = {"": "", "a": "Alt Art", "b": "Promo", "c": "Promo"}.get(suf, "Alt Art")
            elif suf:
                variant = "Signature" if suf == "*" else "Alt Art"
            else:
                variant = "Promo"
            if variant:
                card["v"] = variant
            if tcg_r == "Promo":
                card["pm"] = 1
            out.append(card)
            seen.add(code)
        time.sleep(0.3)
    print(f"TCGplayer extras: {len(out)}")
    return out


RARITY_OK = {"Common", "Uncommon", "Rare", "Epic"}


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
        # Print class from the code, because Riot's rarity label is not
        # consistent for variants (Showcase in OGN/SFD, Rare/Epic in UNL/VEN).
        m = re.match(r"^[A-Z]+-(\d+)([a-z*]?)$", code)
        denom = (c.get("publicCode") or "").split("/")[1:]
        denom = int(denom[0]) if denom and denom[0].isdigit() else 0
        variant = ""
        if m and m.group(2) == "*":
            variant = "Signature"
        elif m and denom and int(m.group(1)) > denom:
            variant = "Overnumbered"
        elif m and m.group(2) == "a" or re.match(r"^[A-Z]+-SP\d", code):
            variant = "Alt Art"
        elif re.match(r"^[A-Z]+-T\d", code):
            variant = "Token"
        elif re.match(r"^[A-Z]+-R\d", code):
            variant = "Promo"
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
        if variant:
            card["v"] = variant
        cards.append(card)

    cards.extend(tcg_extra(cards))

    # Base rarity for variants: the base print of the same card when it
    # exists, else Riot's label unless that label is just "Showcase".
    def gkey(c):
        return "|".join([c["n"], c["t"], c.get("x", ""), str(c.get("e", "")),
                         str(c.get("m", "")), str(c.get("p", "")), ",".join(c["d"])])
    base_r = {}
    for c in cards:
        if not c.get("v"):
            base_r.setdefault(gkey(c), c["r"])
    for c in cards:
        if c.get("v"):
            br = base_r.get(gkey(c)) or (c["r"] if c["r"] != "Showcase" else "")
            if br:
                c["br"] = br        # true rarity of the underlying card
            c["r"] = c["v"]         # class shown in filters: Alt Art / Overnumbered / Signature

    if unknown:
        print("unhandled fields:", sorted(unknown))
    cards.sort(key=lambda c: (c["s"], c["c"]))
    if len(cards) < 1000:
        raise SystemExit(f"only {len(cards)} cards; refusing to write")
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"updated": time.strftime("%Y-%m-%d"),
           "sets": [{"i": k, "n": SET_EN.get(k, k)} for k in sorted(set(c["s"] for c in cards))],
           "cards": cards}
    (OUT / "cards.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                                    encoding="utf-8")
    from collections import Counter
    print(f"wrote {len(cards)} cards; sets {dict(Counter(c['s'] for c in cards))}")
    print("types", dict(Counter(c['t'] for c in cards)))
    print("rarity", dict(Counter(c['r'] for c in cards)))
    print("variants w/o base rarity:", [c['c'] for c in cards if c.get('v') and not c.get('br')])
    print("SP cards:", [(c['c'], c['n']) for c in cards if '-SP' in c['c']])


if __name__ == "__main__":
    main()
