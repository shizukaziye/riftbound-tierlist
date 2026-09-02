# Riftbound Tier List Maker

Live: https://shizukaziye.github.io/riftbound-tierlist/

Build tier lists for Riftbound cards. Search any card by name, collector code,
tag (champion, region) or rules text, see its picture at all times, and drag it
into a tier. Share a link that rebuilds the list anywhere, or export a PNG.

## Features

- Every card in the game (all sets), baked from Riot's public gallery API and
  refreshed weekly by a GitHub Action.
- Text search with type, domain, set and rarity filters. Reprints and showcase
  alt arts collapse into one entry unless "all printings" is on.
- Big preview pane shows the hovered or tapped card with its stats and text.
- Drag and drop, click-to-add to the highlighted tier, keyboard (arrows, Enter,
  digits 1–9 for tier N), and a per-card move/remove menu that also works on
  touch screens.
- Rename, recolor, reorder, add and delete tiers.
- Saves in the browser, named lists under Load, share links (deflate + base64
  in the URL hash, no server), JSON export/import, PNG download.

## Data

`scripts/build_cards.py` writes `data/cards.json` from
`content.publishing.riotgames.com` (channel `riftbound_website`, list
`riftbound_gallery_cards`). Card images are hotlinked from Riot's Sanity CDN;
the PNG export draws from `cdn.piltoverarchive.com`, which sends CORS headers.

```bash
python3 scripts/build_cards.py
```

Riftbound is a trademark of Riot Games. This is a fan tool and is not endorsed
by Riot Games.
