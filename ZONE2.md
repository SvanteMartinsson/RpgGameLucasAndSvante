# ZONE2: Vildmarken i väster (tier 2)

Spelets första expansion från en spelbar zon till två. Designprincipen är din:
**öppen värld, fri vandring, ingen achievement-låsning.** Man går västerut och
det blir farligare; zonen är inte anpassad för låglevlade och det är meningen.
Du *kan* gå dit på level 3 — du kommer troligen dö, och det är ditt val.

Det här bygger nästan helt på data som redan finns: `world.json` har redan
`danger_tier 2`-platser i väster, och `ENEMIES.md`/`LOOT.md` har redan
arketyperna och loot-modellen utstakade. Vi öppnar och fyller — vi uppfinner
inte.

## Vad som redan finns (och varför zonen nästan är gratis)

Din värld klustrar sig redan i två naturliga zoner:

**Kärnzonen (öster, tier 0–1, level ~1–5)** — där du spelar nu. Hordanita
(burg_5, hub/respawn/mana), Gaste, Yeblegali (tier 0, trygga), och en svärm
tier-1-byar med `giant_rat` + `undead`.

**Västra vildmarken (tier 2, redan i datan, oöppnad)** — sju platser, alla
`danger_tier 2` med `undead` + `cave_bear`:

| id | Namn | Typ | Butik | Notis |
|---|---|---|---|---|
| `burg_146` | Rotequero | town | ✓ | fäste, marknad — naturlig zon-hub |
| `burg_67` | Fongorinos | town | ✓ | marknad |
| `burg_379` | Condillosca | village | | |
| `burg_235` | Jinosa | village | | gränsby mot kärnan |
| `burg_200` | Estables | camp | | jaktläger "at the edge of the wilds" |
| `burg_219` | Tierva | camp | | jaktläger |
| `burg_320` | Parguillas | camp | | jaktläger |

Och de binds redan ihop med kärnan genom **två långa vägar** — den naturliga
gränsen mellan zonerna:
- **Gaste (burg_160) → Jinosa (burg_235)**: 56px, den längsta sträckan i hela
  världen. Detta är huvudporten västerut.
- **Fongorinos (burg_67) → Parguillas (burg_320)**: 48px, en sydlig rutt.

Det betyder att "vandra till en annan zon och testa din tur" redan är inbyggt i
geografin. Gränsen är avstånd, inte en låst dörr — exakt det du ville.

## Hur man når zonen (ditt val: fri vandring)

Ingen achievement-låsning, ingen nyckel. Idag är världen gated till kärnzonens
spelbara platser; **vi flyttar den gränsen så de västra vägarna blir
gångbara.** Konkret:

- De gated edges som idag blockerar med "more to come"-text (i `core_zone.json`)
  öppnas mot väster: Gaste→Jinosa och Fongorinos→Parguillas blir passerbara.
- Inget annat hindrar dig. Du går västerut, encounter-frekvensen och fiendernas
  level stiger, och du klarar dig eller inte.
- **En mjuk signal, inte en spärr:** en rad text när man passerar gränsen
  ("Vägen västerut känns ödsligare. Få vänder tillbaka oskadda.") — en varning,
  ingen vägg. Ren flavor, valfri.

Rotequero (burg_146) blir zonens hub: den har butik och ligger i hjärtat av
västklustret, en naturlig plats att vila och handla mellan strider. Värt att ge
den `respawn: true` så man inte slungas hela vägen till Hordanita vid död djupt
i väster — annars blir dödsstraffet i praktiken "förlora 10 minuters vandring",
vilket är hårdare än vi designade. (Beslut: ge zon-2 en egen respawn-punkt.)

## Lore: Förfallets gräns

Världen berättar detta själv genom sin data. Öster (kärnan) binds ihop av
`road` — bebott, sammanvävt land. Väster binds av `trail`, glesare, och har tre
`camp`-platser uttryckligen beskrivna som *"a hunting camp at the edge of the
wilds"* (Estables, Tierva, Parguillas). Mitt i sitter två *befästa* towns med
marknad (Rotequero, Fongorinos) — de står kvar för att de är befästa. Och hela
väster bär `undead` + `cave_bear` i sina pooler: de döda och bestarna har tagit
landet.

> **Förfallets gräns (the Edge of the Wilds).** Detta var en gång bördig mark.
> Rotequeros och Fongorinos murar minns en tid då de skyddade handel, inte
> överlevnad. Men något kröp ur de djupa skogarna och de glömda gravfälten: de
> döda reste sig, bestarna växte sig stora och orädda, och kärren längst i väster
> drog till sig något kallt och drunknat. Jaktlägren är de sista mänskliga
> fästena — och de som inte hann fly blev själva *något annat*. Folk i öster
> talar om väster med sänkt röst. Få vänder tillbaka oskadda.

## Tuffare OCH nya teman

Båda: högre nivå *och* ny variation — och medvetet bruten holy-dominans, så ett
enda holy-vapen inte sveper hela zonen som det svepte kärnan.

**Tuffare:** zonens vilda fiender spawnar i ett högre level-band (~5–10 mot
kärnans 1–5). VIKTIGT: detta får inte höja kärnans `undead`/`cave_bear` — banden
hör till *regionen*, inte enbart fiendetypen (se STEG 0 i bygget).

**Tre under-teman efter djup** (region per tile-x finns redan via
`wild_region_at`), som tillsammans täcker hela skade-/resistansmatrisen:

| Under-tema (djup) | Fiende | Roll (arketyp) | Skadeprofil | Status |
|---|---|---|---|---|
| **Gravfälten** (kant) | `undead` | grunt | holy ×2 svag | finns |
| | `undead_priest` | healer | holy ×2 svag | finns |
| **Vildskogen** (mitten) | `cave_bear` | bruiser | physical lätt tålig | finns |
| | `dire_wolf` | bruiser (snabb) | physical, **ej** holy-svag | NY (data) |
| | `wild_boar` | bruiser (charge) | physical | NY (data) |
| | `treant` | bruiser (tålig) | **fire ×2 svag**, frost-tålig | NY (data) |
| **Kärret** (djupast) | `mutated_mudcrab` | grunt/bruiser | **fire-tålig** | NY (data) |
| | `bog_wraith` | caster | **frost ×2 svag** | NY (data) |

Skadematrisen blir komplett: holy biter på gravfälten, fire på treant, frost på
bog-wraith; mudcrab står emot fire; bestarna är neutrala physical. Inget enda
vapen dominerar — man byter verktyg efter fiende.

**Rare miniboss — `hollow_worg`.** En sällsynt, betydligt svårare encounter: en
människa från väster som gravfältens förfall förvandlade permanent till en best.
Ingen transformations-mekanik behövs — den *är* bara en mäktig bruiser med
miniboss-stats. Lore-mässigt binder den ihop allt: väster tog inte bara folkets
land, det tog folket. Låg spawn-vikt, hög belöning.

De nya fienderna är **data, inte motor** — de återanvänder de befintliga
arketyperna (bruiser, caster, healer) och effektvokabulären ur `ENEMIES.md`,
plus `resistances`-fältet som redan finns (undead har holy ×2). Inga nya
mekanik, bara nya rader i `enemies.json`. (En verklig swarm/pack vore en
motorändring och ligger utanför zonen — `ENEMIES.md` flaggar den som blockerad
tills striden stödjer >1 fiende.)

## Loot-profil (höjd, inte bara mer)

`LOOT.md` har redan loot-only-vapnen tier 3–6 och `rare_table_access` på
arketyperna. Zon 2 är där de högre tierna faktiskt ska droppa:

- Zon-2-fienderna (priest, acolyte, bear, de nya bruisrarna) har
  `rare_table_access` → de når tier 4–5-bandet (Consecrated Maul, Venomfang,
  Gravewarden Blade, Pyre Scepter). Det är belöningen för att överleva väster.
- **Equipment-gear i det högre tier-bandet:** nu när slot-systemet finns ska
  zon 2 droppa tier 3–5 armor och ringar (de starkare modifierarna), inte bara
  vapen. Det ger en anledning att grinda väster utöver vapnet.
- Kärnzonen behåller sin låg-tier-profil oförändrad — kontrasten *är*
  progressionen.

> Notis om kraftspiken vi såg: din Fighter svepte kärnzonen med en
> turnerings-mace. I väster, med fiender level 5–10 och egna resistanser, biter
> inte ett enda högtier-vapen lika lätt — zonen är delvis ett svar på just den
> trivialiseringen. Men den verkliga lösningen på svårighet är **tuning**, som
> vi medvetet skjuter till ett samlat pass. Zon 2 ska byggas, inte balanseras.

## Vad som är data och vad som (ev.) är motor

**Rent data (huvuddelen):**
- Öppna de gated edges västerut (`core_zone.json`).
- Höjda level-ranges på zon-2-fiendernas encounter-poster.
- Två nya fiende-rader i `enemies.json` (återanvänder arketyper).
- `rare_table_access` + loot-tabeller på zon-2-fienderna; tier 3–5 gear/vapen i
  drop-poolen.
- Zonens platser pekar redan på rätt `encounters`/`danger_tier` i `world.json`.

**Möjlig liten motor-touch (verifiera, bygg inte blint):**
- Respawn-punkt för zon 2 (Rotequero) om respawn idag är hårdkodad till
  Hordanita. STEG 0: kolla hur respawn väljs; om det redan läser `respawn: true`
  per plats är det data, annars en liten ändring.
- Encounter-pooler/level-ranges *per väg* (inte bara per plats) om vägarna ska
  ha egen fara — `OVERWORLD.md` beskriver redan detta som framtida
  `connection.encounters`. Kan skjutas; platsbaserade encounters räcker för v1
  av zonen.

## Byggordning

**Steg 1 — Öppna gränsen. KLART (commit d078f2b).** De västra vägarna gångbara;
Rotequero (`burg_146`) blev respawn-punkt (ren data — respawn läser
`respawn: true` per plats); region per tile-x via `wild_region_at`. Spelaren kan
nu vandra till väster.

**Steg 2 — Befolka väster.** Slicas efter under-tema, var och en spelbar:
- **2a Vildskogen + level-band**: STEG 0 om regionalt level-band, sedan
  `dire_wolf`, `wild_boar`, `treant` (data) i västpoolen vid det högre bandet.
  Bryter holy-dominansen direkt (neutrala bestar + fire-svag treant).
- **2b Kärret**: `mutated_mudcrab` (fire-tålig) + `bog_wraith` (frost-svag caster)
  i en djup-väster-ficka. Fullbordar skadematrisen.
- **2c Hollow Worg**: rare miniboss-encounter, låg spawn-vikt, hög belöning.

**Steg 3 — Loot-höjd.** `rare_table_access` + tier 3–5 vapen/gear i
zon-2-drops (data).

Varje steg/del är spelbar och testbar för sig.

## Utanför denna zon (medvetet)

- **Svårighetstuning** — fiendeskada/HP/turneringsbelöning. Eget samlat pass.
- **Per-väg-encounters** (`connection.encounters`) — framtida, `OVERWORLD.md`.
- **Swarm/pack-strid** (>1 fiende) — motorändring, blockerad enligt `ENEMIES.md`.
- **Art/tiles** — kommer efter att världen är befolkad och tunad.
- **Resten av de 21 platserna** — zon 3+ öppnas på samma sätt senare.