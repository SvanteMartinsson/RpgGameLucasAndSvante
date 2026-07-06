# worldgen — engångs-/regen-verktyg för overworlden

Skript som **genererar eller retuscherar** kart- och tile-assets. De är inte en
del av spelet i drift (`rpg_game/core` och presentationen läser bara de
incheckade resultatfilerna) — de körs manuellt, **från repo-roten**, när världen
eller dess tilesets ska byggas om.

## ⚠️ Determinism-varning (läs före regen)

`regenerate_overworld.py` shufflar prop-/vegetations-placering ur en **delad
seedad rp-ström**. En regen kan därför flytta till synes orelaterad dekor över
hela kartan (det har bitit oss förr: en busk-fix flyttade dekor i andra zoner).
Regenerera bara när det är avsikten, granska diffen på `overworld.tmx` som en
HELHET, och committa aldrig en regen ihop med en orelaterad ändring.

## Skripten

| Skript | Gör |
|---|---|
| `overworld_layout.py` | Parametrisk 240×208-layout (#3): zon-band, kust, seam, flod/sjö, broar härledda ur stads-rutter. Importeras av `regenerate_overworld`. |
| `regenerate_overworld.py` | Målar layouten till `rpg_game/data/maps/overworld.tmx` (terräng, vatten, props, gravar). Huvud-regen. |
| `extend_verralda.py` | Historisk söder-expansion (Verralda-heden) av kartan. |
| `generate_water_autotiles.py` | Bygger vatten-autotile-arket ur bastexturer. |
| `crispen_water.py` | Skärper vatten-/bro-tilesens pixelkanter (ingen mjuk skalning). |
| `recolor_themes.py` | Genererar per-zon-färgade tema-ark (grass/stone/props/plant) ur cainos-originalen. |
| `unify_overworld_theme.py` | Historisk tema-unifiering av TMX-referenser. |

*`generate_bridge_halfdecks.py` raderades i B61 — noll referenser i kod/tester
(halv-däcks-arket den byggde är incheckat och används direkt).*

## Körning

```sh
# från repo-roten (skripten öppnar rpg_game/data/... relativt cwd)
python3 rpg_game/tools/worldgen/regenerate_overworld.py
```

Verifiera efter en regen: `python3 -m unittest discover -s tests` (reachability-,
vatten- och zon-testerna fångar en trasig karta).
