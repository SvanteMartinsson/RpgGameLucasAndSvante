# Geografi-förslag: area-levelband + resekostnad (HALT — förslag, ingen data ändrad)

Metod: band stiger med BFS-gångavstånd från närmaste stad. Stadsnära = zonens
ingångslevel, bortre = zonens topp (bandbredd 2). Resekostnad = summan av
per-tile encounter-rate längs hemvägen från areans BORTERSTA tile, dämpad av
B104-cooldownen (~4 tiles rörelse à 4.5 tiles/s).

## cainos (zonband L1–5)
| area | gångavst. stad (mitt; min–max) | föreslaget band | hemresa (tiles) | E[encounters] rå | E[enc] m. B104 | roster |
|---|---|---|---|---|---|---|
| cainos_stag_west | 21 (0–65) | **L2–4** | 65 | 3.7 | 2.9 | wild_stag |
| cainos_stag_south | 33 (0–78) | **L3–5** | 78 | 4.1 | 3.3 | wild_stag |
| cainos_undead_east | 20 (0–71) | **L2–4** | 71 | 3.7 | 3.0 | undead |
| cainos_generalists | 11 (0–65) | **L1–3** | 65 | 3.7 | 2.9 | wild_dog, giant_rat, giant_spider, goblin_scrapper |
| cainos_undead_north | 30 (7–52) | **L3–5** | 52 | 2.6 | 2.1 | undead |

## mork_skog (zonband L4–9)
| area | gångavst. stad (mitt; min–max) | föreslaget band | hemresa (tiles) | E[encounters] rå | E[enc] m. B104 | roster |
|---|---|---|---|---|---|---|
| skog_beast_north | 14 (0–56) | **L5–7** | 56 | 2.8 | 2.3 | razortusk_boar, dire_wolf, cave_bear |
| skog_goblin_west | 7 (0–43) | **L4–6** | 43 | 2.0 | 1.6 | goblin_raider, cave_bear |
| skog_plant_south | 18 (0–54) | **L6–8** | 54 | 2.8 | 2.3 | thornling, goblin_shaman, strangling_vine |
| skog_deep_east | 25 (0–38) | **L7–9** | 38 | 1.8 | 1.5 | treant, broodmother_spider, strangling_vine |

## cursed_mire (zonband L5–10)
| area | gångavst. stad (mitt; min–max) | föreslaget band | hemresa (tiles) | E[encounters] rå | E[enc] m. B104 | roster |
|---|---|---|---|---|---|---|
| mire_leech_all | 28 (0–56) | **L8–10** | 56 | 3.2 | 2.6 | bog_leech |
| mire_spirits | 15 (0–46) | **L5–7** | 46 | 2.3 | 1.9 | bog_wraith, witchlight |
| mire_tar_east | 13 (0–52) | **L5–7** | 52 | 3.0 | 2.4 | tar_beast, mire_lurker |
| mire_hag_bog | 17 (3–32) | **L6–8** | 32 | 1.8 | 1.4 | bog_hag |
| mire_crab_coast_north | 14 (4–52) | **L5–7** | 52 | 2.7 | 2.2 | mutated_mudcrab |
| mire_crab_coast_east | 26 (8–52) | **L8–10** | 52 | 2.7 | 2.2 | mutated_mudcrab |

## grave_heath (zonband L6–12)
| area | gångavst. stad (mitt; min–max) | föreslaget band | hemresa (tiles) | E[encounters] rå | E[enc] m. B104 | roster |
|---|---|---|---|---|---|---|
| heath_entry_northwest | 9 (0–65) | **L6–8** | 65 | 3.4 | 2.8 | undead, undead_priest, rotting_fiend |
| heath_ghoul_west | 31 (0–56) | **L8–10** | 56 | 3.2 | 2.6 | ghoul, grave_hound |
| heath_worg_column | 33 (0–65) | **L8–10** | 65 | 3.4 | 2.8 | shade, hollow_worg |
| heath_elite_east | 26 (0–81) | **L8–10** | 81 | 4.7 | 3.7 | undead_priest, skeleton_warrior, cursed_wight |
| heath_palegate | 32 (0–69) | **L8–10** | 69 | 3.7 | 3.0 | shade, hollow_worg |
| heath_ghoul_south | 50 (7–85) | **L10–12** | 85 | 5.0 | 3.9 | ghoul, grave_hound |
| heath_northeast_pocket | 46 (8–79) | **L10–12** | 79 | 4.6 | 3.6 | undead_priest, rotting_fiend |
