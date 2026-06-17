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

| id | Namn | Roll | Speed | Resistances / tags | Notis |
|---|---|---|---:|---|---|
| `giant_rat` | Giant Rat | grunt | 8 | `beast` | introfiende, basattack |
| `undead` | Undead | grunt | 6 | holy ×2.0; poison-immun; `undead` | tidig undead |
| `cave_bear` | Cave Bear | **bruiser** | 6 | physical lätt tålig; `beast` | tung attack |
| `undead_priest` | Undead Priest | **healer** | 9 | holy ×2.0; `undead` | healar sig själv |
| `plague_acolyte` | Plague Acolyte | **caster** | 14 | poison-tålig | telegraferar nuke |

Startvärden för stats/skadetal sätts i `enemies.json` och tunas där.

## Koppling till world.json

Lägg de nya fienderna i `enemies.json` och referera dem i lämpliga platsers
`encounters[]` efter `danger_tier`: priest och acolyte hör hemma i tier 2
(periferin), bruisern likaså; grunts i tier 1. (Senare kan `derive_world.py`
tilldela arketyper per tier automatiskt — inte nu.)

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
