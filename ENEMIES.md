# ENEMIES: arketyper och AI

Fiendernas djup. Bygger på `COMBAT_DESIGN.md`:s arketyper och använder samma
motor och effektvokabulär som klasserna (`CLASSES.md`). Kopplas till
`world.json`:s encounter-pooler och `danger_tier`.

**Status:** byggt och testat. AI-regler, telegraph, healer, bruiser och caster
finns i Python-porten och konfigureras i `enemies.json`.

## Princip: fiender är entiteter precis som spelare

En fiende går genom samma handling→effekt→resolver-pipeline som spelaren och
bär samma fält: hp, power, armor, **speed**, **mana**, resistances, tags,
samt en lista **skills** ur den befintliga vokabulären. Det enda som skiljer
en fiende från en spelare är att en **AI väljer dess handling** istället för
en meny. Inga nya effekttyper behövs — bara ett beslutssystem.

## Motorfunktioner

- **AI-regelsystem** — varje fiende har en ordnad `ai`-lista av regler
  `{ condition, action }`. Resolvern utvärderar uppifrån; första regeln vars
  villkor är sant och vars action är *ready* (av cooldown + nog mana) fyrar.
  Matchar ingen regel: **uniformt slumpval** bland fiendens ready
  icke-telegraf-actions. AI:n väljer aldrig en action som inte är ready.
- **telegraph** — en action kan vara tvåfas: när den väljs *laddas* den och
  annonseras ("X laddar Y"), gör ingen skada den rundan, och *släpps* nästa
  runda. Dör fienden under laddningsrundan fyrar den aldrig. Ger spelaren en
  runda att tanka, fly eller bursta.

Villkorsvokabulär (litet, generiskt, utbyggbart):

- `self_hp_below: X` (procent)
- `target_hp_below: X`
- `skill_ready: skill_id`
- `self_has_status: tag` / `target_has_status: tag`
- `always` (fallback-regel)

## Arketyp: Healer

Fantasin: håll dig vid liv genom att överhela spelaren. **Pusslet:** bursta
ner den innan den hinner heala — eller hindra healen.

- Skills: en heal (instant_heal self) + en svag attack.
- AI: `self_hp_below: 50 + skill_ready: heal → heal`; annars `always → attack`.
- Lågt-till-måttligt hp så burst är möjligt; annars out-healar den dig.

## Arketyp: Bruiser

Fantasin: hög skada, långsam. **Pusslet:** mitigera eller dö; snabba klasser
agerar före och kan bursta/kontrollera den.

- Skills: en tung attack (hög multiplier) + basattack.
- Låg speed (agerar sent), hög power, hög hp, ofta `beast`-tag.
- AI: mest tung attack; ingen finess behövs — hotet är skadan.

## Arketyp: Caster

Fantasin: bräcklig men telegraferar en stor nuke. **Pusslet:** när du ser
laddningen, välj — tanka den, fly, eller döda castern innan den släpps.

- Skills: en telegraferad nuke (hög fire/frost-skada) + en svag bolt.
- AI: `skill_ready: nuke → telegraf nuke`; annars `always → bolt`.
- Lågt hp; hög speed så laddningen ofta hinner före spelarens drag (men en
  ännu snabbare Rogue kan agera före och avbryta genom att döda).

## Konkreta fiender

Återanvänd de tre befintliga där det passar; lägg till två nya för healer och
caster. Grunts (giant_rat, undead) behåller sin enkla roll — alla fiender
behöver inte vara arketyper.

**Auktoritativ data: `enemies.json`. Denna tabell är en läsbar spegling.** Roll
härleds ur AI/actions (finns inte som fält i datan). Resistans ×>1.0 = svag mot,
×<1.0 = tålig.

### Core- och vildmarksfiender

| id | Namn | Roll | Speed | Resistances / tags | Notis |
|---|---|---|---:|---|---|
| `giant_rat` | Giant Rat | grunt | 8 | `beast` | introfiende, basattack |
| `undead` | Undead | grunt | 6 | holy ×2.0; poison-immun; `undead` | tidig undead |
| `cave_bear` | Cave Bear | **bruiser** | 6 | physical lätt tålig; `beast` | tung attack |
| `undead_priest` | Undead Priest | **healer** | 9 | holy ×2.0; `undead` | healar sig själv |
| `plague_acolyte` | Plague Acolyte | **caster** | 14 | poison-tålig | telegraferar nuke |
| `dire_wolf` | Dire Wolf | grunt | 12 | `beast` | wolf_bite; zon-2 rar (lvl 5-10) |
| `wild_boar` | Wild Boar | grunt | 8 | `beast` | boar_charge; zon-2 rar (lvl 5-10) |
| `treant` | Treant | **bruiser** | 3 | fire ×2.0; frost ×0.5; `beast, plant` | mkt långsam treant_slam; zon-2 rar |
| `mutated_mudcrab` | Mutated Mudcrab | grunt | 6 | fire ×0.5; `beast` | crab_claw; zon-2 rar (lvl 5-10) |
| `bog_wraith` | Bog Wraith | **caster** | 14 | frost ×2.0; `undead, spirit` | wraith_hex + wraith_bolt; zon-2 rar |
| `tar_beast` | Tar Beast | **bruiser** | 4 | fire ×1.5; `beast, ooze` | self-regen + ensnare + maul; zon-2 rar |
| `hollow_worg` | Hollow Worg | grunt | 8 | physical ×0.9; `beast, cursed` | pounce + bite; lvl 8 rar top-band-miniboss |

Startvärden för stats/skadetal sätts i `enemies.json` och tunas där.
*Placering:* dire_wolf/wild_boar/treant/mudcrab/bog_wraith/tar_beast/hollow_worg
mappas nu in i 4-zon-rostern nedan (B42) — se den för aktuell pool.

## 4-zon-roster (B42)

Vildmarken är indelad i fyra zoner: `ground_theme` (tile-band) → `wild_region`
→ platsens `encounters`-pool. Roll = stat-budget + AI (**trash / standard /
elite / mini-boss**), inte ett datafält. **Svag mot** härleds ur `traits`
(`core/traits.py`): step +3 = ×2.0, +2 = ×1.5, +1 = ×1.25, −1 = ×0.65,
IMMUNE = ×0. (NY) = ny fiende; (infälld) = befintlig fiende inplacerad i zonen.

### CAINOS — start (`burg_54`-poolen, L1–6, ingen rare)
Mjuk introzon: djur, vermin, goblins.

| id | Roll | Traits | Svag mot |
|---|---|---|---|
| `wild_dog` | trash | beast | fire ×2 · poison ×1.25 |
| `goblin_scrapper` | trash | — | neutral |
| `giant_spider` | standard | vermin | fire ×1.25 (poison-tålig) |
| `wild_stag` | standard | beast | fire ×2 · poison ×1.25 |
| `giant_rat` | trash | beast | fire ×2 |
| `undead` | standard | undead | holy ×2 · poison-immun |

### MÖRK SKOG — skog (`burg_146`-poolen, L4–9, rare: `strangling_vine`)
Djur, växter, spindlar, goblins.

| id | Roll | Traits | Svag mot |
|---|---|---|---|
| `goblin_raider` (NY) | standard | — | neutral |
| `thornling` (NY) | trash | plant | fire ×2 |
| `razortusk_boar` (NY) | standard | beast | fire ×2 · poison ×1.25 |
| `cave_bear` (infälld) | bruiser | beast | fire ×2 |
| `dire_wolf` (infälld) | standard | beast | fire ×2 |
| `treant` (infälld) | bruiser | plant | fire ×2 |
| `broodmother_spider` (NY) | elite | vermin | fire ×1.25 |
| `goblin_shaman` (NY) | elite caster | cursed | holy ×1.5 · phys ×0.65 |
| `strangling_vine` (NY, rare) | elite | plant | fire ×2 |

### CURSED MIRE — träsk (`burg_320`-poolen, L5–10, rare: `bog_hag`)
Träsk, ooze, spöken.

| id | Roll | Traits | Svag mot |
|---|---|---|---|
| `bog_leech` | trash | swamp | frost ×2 |
| `mire_lurker` | standard | swamp | frost ×2 |
| `rotting_fiend` | standard | undead | holy ×2 · poison-immun |
| `mutated_mudcrab` (infälld) | bruiser | beast,swamp | frost ×2 |
| `tar_beast` (infälld) | bruiser | swamp | frost ×2 |
| `bog_wraith` (infälld) | caster | undead,swamp | frost ×2 · holy ×2 |
| `witchlight` | elite caster | spirit | holy ×1.5 · phys ×0.65 |
| `bog_hag` (rare) | elite caster | cursed | holy ×1.5 · phys ×0.65 |

### GRAVE HEATH — hed (`burg_121`-poolen, L6–12, rare: `cursed_wight` mini-boss)
Död, odöda, spöken.

| id | Roll | Traits | Svag mot |
|---|---|---|---|
| `skeleton_warrior` | elite | undead | holy ×2 · poison-immun |
| `ghoul` | standard | undead | holy ×2 · poison-immun |
| `grave_hound` | standard | beast,cursed | fire ×2 · holy ×1.5 |
| `undead` (infälld) | standard | undead | holy ×2 · poison-immun |
| `undead_priest` (infälld) | healer | undead | holy ×2 |
| `shade` | elite | spirit,undead | holy ×2 · phys ×0.65 |
| `hollow_worg` (infälld) | bruiser | beast,cursed | fire ×2 · holy ×1.5 |
| `cursed_wight` (rare) | mini-boss | undead,cursed | holy ×2 · poison-immun |

**Designnot — physical-resistenta specialister:** spirit/cursed-fiender (shade,
witchlight, goblin_shaman, bog_hag, cursed_wight, grave_hound) tål fysisk skada
(×0.65). En ren melee-bruiser (fighter) ska ta ett icke-fysiskt vapen (holy/magi,
t.ex. `consecrated_maul`) eller lämna dem åt rogue/caster. Avsiktlig "ta rätt
verktyg"-design — sim: fighter ~20 %, rogue 60–100 %, cleric 100 % mot shade/wight.

**Loot (differentierad):** trash ger salvage (`bone_dust`/`tattered_cloth`/
`rat_pelt`/`iron_scrap`) + lesser-pots; standard ger tier 1–2 gear; elit/caster
har `rare_table_access` + ett signatur-`unique_table`-item (tier 3–4). Låg-level
wild capas mot top-tier rares (`rare_table_tier_cap`).

### Arena-duellanter (turneringsmotståndare)

Platsbundna turneringsmotståndare (`arena_*`), inte vildmarkspooler. De flesta är
raka människo-attackare med en signaturskill → `grunt`; bara de med ren spell-
telegraf märks `caster`.

| id | Namn | Roll | Speed | Resistances / tags | Notis |
|---|---|---|---:|---|---|
| `arena_ralla_quickstep` | Ralla Quickstep | grunt | 13 | `human, duelist` | snabb basattackare (lvl 1) |
| `arena_borin_shieldhand` | Borin Shieldhand | grunt | 7 | `human, guard` | block + normal (lvl 1) |
| `arena_mira_candlewick` | Mira Candlewick | **caster** | 10 | fire ×0.8; frost ×1.25; `human, mage` | ignite-DoT + firebolt (lvl 2) |
| `arena_tomas_reed` | Tomas Reed | grunt | 9 | `human, swordsman` | basattackare (lvl 2) |
| `arena_selka_bowyer` | Selka Bowyer | grunt | 12 | `human, archer` | aimed_shot (lvl 3) |
| `arena_ivar_grim` | Ivar Grim | grunt | 8 | physical ×0.95; `human, veteran` | taunt + sunder (lvl 3) |
| `arena_nalia_frostveil` | Nalia Frostveil | **caster** | 11 | fire ×1.25; frost ×0.75; `human, mage` | frostbolt (lvl 4) |
| `arena_orren_blackbell` | Orren Blackbell | grunt | 13 | poison ×0.75; `human, rogue` | backstab + riposte (lvl 4) |
| `arena_ser_kaela_voss` | Ser Kaela Voss | grunt | 10 | physical ×0.9; `human, knight` | counter + sunder (lvl 5) |
| `arena_lord_maren_dusk` | Lord Maren Dusk | grunt | 12 | physical ×0.9; `human, champion` | combo + counter (lvl 6) |

## Koppling till world.json

Overworld-zonerna kartläggs i `maps/core_zone.json`: `ground_themes` sätter
tile-bandet (cainos x≤82 · mork_skog x83–158 · cursed_mire x≥159 · grave_heath
y≥100) och `wild_regions` pekar varje band mot **en plats vars `encounters`-pool
styr zonen**: cainos→`burg_54` (default), mork_skog→`burg_146`, cursed_mire→
`burg_320`, grave_heath→`burg_121`. Zon-nivåbandet sätts som `level_min/level_max`
på den platsen (överstyr fiendens egna band vid roll). Den tuffaste per zon ligger
som `rare_encounter` (+`rare_chance`). Menyresans övriga platser behåller sina
egna småpooler. (Senare kan `derive_world.py` tilldela roller per tier — inte nu.)

## Invarianter att låsa i test

- **Healer**: när dess hp < 50% och heal är ready healar den (attackerar
  inte); heal cappas vid max_hp; återanvänder instant_heal.
- **Caster-telegraf**: laddningsrundan gör 0 skada och annonseras; nuken
  släpps nästa runda; dödas castern under laddning fyrar nuken aldrig.
- **Bruiser**: en snabbare spelare agerar före (speed-ordning); tung attack
  gör sin angivna skada.
- **AI-gating**: AI:n väljer aldrig en action som är på cooldown eller saknar
  mana; fallback är uniformt slumpval bland ready actions.
- **AI-prioritet**: första matchande, ready regeln fyrar; lägre regler hoppas
  över.
- **Regression**: alla 49 tidigare tester gröna; giant_rat/undead fungerar
  som förut.

## Byggordning (historik)

1. Bygg AI-regelsystemet + telegraph (motor). Validera med **Healer** (en
   arketyp som rör båda: regelprioritet + heal). Grön + commit.
2. Lägg till **Bruiser** och **Caster** som data (+ ev. telegraf-finputs).
   Grön + commit.

Båda stegen är genomförda.

## Utanför denna slice

- **Swarm** — kräver flera samtidiga motståndare; blockerad tills striden
  stödjer >1 fiende (egen, större combat-ändring).
- **Interrupt** — explicit spelar-action som avbryter en telegraf (utöver att
  döda castern). Kandidat-refinement senare.
- Multi-target och AoE.
