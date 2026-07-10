# Asset-licenser

Loggbok över tredjeparts- och egengjorda assets i `rpg_game/assets/`.
Nya assets loggas här när de checkas in.

## Ljud — `rpg_game/assets/sounds/` (B69)

Samtliga 16 SFX är egengjorda av Lucas i [ChipTone](https://sfbgames.itch.io/chiptone)
(2026-07-10) och släpps som **CC0** (inga restriktioner; ChipTone-ljud ägs av
skaparen).

| Fil | Händelse i spelet |
| --- | --- |
| `menu_click.wav` | knapptryck i alla menyer |
| `hit_enemy.wav` | spelarens skada landar på fienden |
| `get_hit.wav` | spelaren tar skada |
| `magic_cast.wav` | icke-fysisk skill avfyras (fire/frost/holy/poison/lightning) |
| `physical_cast.wav` | spelarens fysiska skill avfyras (ej basattack) |
| `heal.wav` | heal-effekt från skill |
| `health_pot.wav` | dricka health-potion (även antidote) |
| `mana_pot.wav` | dricka mana-potion |
| `DoT.wav` | DoT tickar vid rundslut (låg volym) |
| `level_up.wav` | level-up |
| `encounter.wav` | strid startar |
| `open_chest.wav` | kista öppnas |
| `brewing.wav` | lyckad alkemi-bryggning |
| `sell.wav` | lyckat butiks-sälj |
| `walk.wav` | spelarsteg (var 2:a tile, låg volym) |
| `die.wav` | spelaren dör/förlorar striden |

## Musik — `rpg_game/assets/sounds/` (B69)

| Fil | Användning | Källa/licens |
| --- | --- | --- |
| `Pixel Heart.ogg` | bakgrundsloop (startar på första skärmen, löper genom overworld + strid) | inlagd av Lucas 2026-07-10 — **bekräfta källa/licens före publik release** |

## Övrigt

- `rpg_game/assets/sprites/`, `buildings/`, `tiles/`, `props/`: projektgenererade
  (AI-genererade/egna) — inga externa licenser.
