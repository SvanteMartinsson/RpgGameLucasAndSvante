# DAMAGE: multikomponent-skada och karaktärsbundna element

Löser två saker från playtesten: (1) elementet "försvann" när man uppgraderade
vapen, för det bodde på vapnet; (2) önskan om dubbla skadetyper + tydligare
output. Kärninsikten: **elementet hör till karaktären (talanger), inte
startvapnet.** Då följer det med över vapenbyten OCH staplar med vapnets egen
typ. Bygger på WEAPONS.md — att `category` och `damage_type` är skilda är exakt
det som gör detta möjligt.

**Status:** design. Detta är det sista stora stridsmekanik-tillägget innan vi
fryser för Pygame.

## Modell: en attack är flera skadekomponenter

Skada blir en lista `[{ amount, damage_type }, …]` istället för ett tal + en typ.

- Varje komponent avräknas mot målet för sig: `resist[type] × amount`; armor
  reducerar ENDAST physical-komponenter (armor_pen gäller per physical-komponent).
- Komponenterna summeras; försvararens mitigation (flat) dras från summan en
  gång; totalen golvas vid 1.
- **Crit** blir en range-förlängare (se egen sektion): vid crit läggs en rollad
  bonus på multiplikatorn, som sedan slår genom på alla komponenter. (Multi-hit
  = separata instanser, var sin roll, som förut.)
- En enkomponents-attack/skill är bara en 1-elementslista → bakåtkompatibelt.

## Attack-profiler: träff% och skade-range

Basattackerna får högre träff på normal/power (power ska inte längre vara ett
50/50 på om man ens träffar) och en **rollad skade-range** istället för en fast
multiplikator, så striderna inte blir statiska. Alla tre överlappar men har
olika golv/tak. (Alla tal tunas i JSON.)

| Attack | Träff% | Skade-range (× (Power+vapen)) | EV (≈) |
|---|---:|---|---:|
| Quick | 90% | 1.0–1.25× | 1.01 |
| Normal | 80% | 1.1–1.4× | 1.00 |
| Power | 70% | 1.25–1.7× | 1.03 |

- Multiplikatorn rullas uniformt i range:n per attack (seedbar rng).
- EV:na ligger nära varann så alla tre är gångbara; power har en liten premie
  för risken + högst tak, quick är det pålitliga golvet, normal mitten.
- Skills behåller sin **fasta** multiplikator (ingen range) — de är medvetna,
  förutsägbara val. (Range på skills kan komma senare.)

## Crit som range-förlängare

Crit slutar vara en fast ×-dubbling och blir en **rollad förlängning av
range:n**. Vid crit (gated av `crit_chance` som förut, inkl. talang-bonusar)
läggs en bonus på multiplikatorn:

```
crit_bonus = uniform(crit_floor, crit_bonus_max)   # rekommenderat 0.25 … 1.0
multiplier += crit_bonus
```

Så en quick attack går från 1.0–1.25 upp till **2.25** som crit-tak (1.25 + 1.0)
— exakt ditt exempel. `crit_floor` (≈0.25) gör att en crit alltid känns som en
crit och höjer både golv och tak på crit-utfallet; sätt 0 om du vill ha den
exakta 0–1-rollen. Bonusen ligger på multiplikatorn, så den slår genom på alla
komponenter och skalar med Power+vapen.

> **Balansflagga:** detta ersätter den fasta `crit_mult = 2.0`. Additiv crit är
> svagare på hög-multiplikator-skills (en Fireball ×2.4 dubblas inte längre) och
> relativt starkare på små attacker — det dämpar crit-klassernas (Rogue/Hunter)
> topp. Håll öga på det i tuning-passet; `crit_bonus_max` är ratten.

## Startvapen blir physical (men behåller kategori)

**Endast `damage_type` ändras till physical. `category` är oförändrad** så
vapen-gatingen funkar precis som förut.

| Klass | Startvapen | category | damage_type |
|---|---|---|---|
| Cleric | Mace | magic *(oförändrad)* | holy → **physical** |
| Mage | Staff | magic *(oförändrad)* | fire → **physical** |
| Tank | Mace | melee | physical *(oförändrad)* |
| Rogue | Dagger | melee | physical *(oförändrad)* |
| Fighter | Sword | melee | physical *(oförändrad)* |
| Hunter | Bow | ranged | physical *(oförändrad)* |

Så Cleric kan fortfarande kasta Smite (magic-gated) från level 1, men basattacker
är physical tills man väljer ett element. **Loot-vapen behåller sina element** —
en funnen Consecrated Maul är fortfarande holy. Det är bara *startvapnens*
element som tas bort, så man föds inte acklimatiserad; man väljer eller hittar
sitt element.

> Detta revideras medvetet från det tidigare "staff = fire är korrekt"-beslutet.
> Kastarens element flyttar från startvapnet till talanger/skills.

## Element via talanger (karaktärsbundet, persistent)

En element-mod är en **passiv talang** som lägger en komponent på dina
quick/normal/power-attacker: `amount = round_half_up(multiplier × mod_value)` av
sin typ. Den **följer med över vapenbyten** (sitter på dig) och **staplar med
vapnets egen typ** — det är den dubbla modifiern. Gäller ENDAST basattacker;
skills behåller sin egen typ.

Nya tidiga noder (kräver grenens tier-1-nod → "tidig, inte steg 1"):

| Klass | Gren | Ny nod | Effekt | Krav |
|---|---|---|---|---|
| Cleric | Ljus | Sanctified Strikes (passiv) | +holy-komponent på basattacker (mod_value ~4) | Smite |
| Mage | Pyromancer | Flametongue (passiv) | +fire på basattacker | Firebolt |
| Mage | Cryomancer | Rimeblade (passiv) | +frost på basattacker | Frostbolt |

Martial-klasser (Fighter/Rogue/Tank/Hunter) förblir physical och får ingen
element-mod i v1 (kan läggas till senare). `mod_value` tunas i JSON.

Exempel — Cleric, Power 10, physical mace +0, Sanctified Strikes (+4 holy), mot
Undead (holy 2×):
- Quick (×1): `10 physical + 4 holy` → 10 + 8 = 18, "(holy super effective)".
- Power (×2): `20 physical + 8 holy` → 20 + 16 = 36.

## Output: bryt ut komponenter + flagga effektivitet

`Pelle's Quick attack dealt 10 physical + 8 holy (holy super effective) to Undead.`

- Visa varje komponent: belopp + typ.
- Effektivitet per komponent: `resist > 1.0` → "super effective"; `resist < 1.0`
  → "resisted". Datan finns redan (Identify visar resistenser).
- HP/total uppdateras som förut.

## Resolutionsordning (basattack)

1. Träffrull (attackens träff% ± accuracy_mod). Miss → ingen skada.
2. Rulla multiplikator uniformt i attackens range.
3. Crit-rull (`crit_chance`). Vid crit: `multiplier += uniform(crit_floor,
   crit_bonus_max)`.
4. Per komponent: `amount = round_half_up(multiplier × källvärde)`; `resist`
   → `armor` (endast physical, minus armor_pen).
5. Summera komponenterna → `mitigation` (flat, på summan) → `max(1, total)`.

Skills: hoppa över steg 2 (fast multiplikator), men crit (steg 3) gäller även dem.

## Invarianter att låsa i test

- **Range**: med seedad rng landar varje attack-typ inom sin range; lo/hi
  respekteras; seed → känt utfall.
- **Träff%**: power/normal/quick använder de nya värdena (70/80/90),
  modifierade av accuracy_mod.
- **Crit**: vid forcerad crit läggs `uniform(crit_floor, crit_bonus_max)` på
  multiplikatorn (inte en fast ×2); utan crit oförändrad; quick-crit kan nå
  taket 2.25×. Multi-hit rullar crit per instans.
- **Multikomponent**: varje komponent avräknas mot sin egen resistens; endast
  physical-komponenten reduceras av armor; samma rullade multiplikator + crit
  slår på alla komponenter.
- **Element-talang**: lägger en komponent av sin typ på basattacker, skalar med
  multiplikatorn, kvarstår över vapenbyten, staplar med vapnets typ; påverkar
  INTE skills.
- **Output**: varje komponent + rätt effektivitetsflagga; crit markeras; total
  golvas vid 1.
- **Startvapen**: `category` oförändrad (gating funkar); endast `damage_type`
  → physical.
- **Skills**: fast multiplikator (ingen range), men crit gäller.
- Regression: övriga tester gröna (uppdatera de som låste fasta basattack-tal,
  Cleric/Mage basattack-typ, och `crit_mult` ×2).

## Byggordning

1. **Multikomponent + output + startvapen**: skada som komponentlista,
   per-komponent-resolution, effektivitets-output; startvapnens `damage_type`
   → physical (`category` orörd). Commit: "Add multi-component damage with
   per-type resolution and effectiveness output".
2. **Attack-profiler + crit-range**: nya träff% (90/80/70) + rollade
   skade-ranges på quick/normal/power; crit blir additiv range-förlängare
   (ersätter `crit_mult` ×2). Commit: "Add rolled attack ranges and crit
   range-extension".
3. **Element-talanger**: nya noder (Cleric Sanctified Strikes; Mage Flametongue
   / Rimeblade). Commit: "Add character-bound elemental attack talents".

## Utanför denna slice

- Element-mods för martial-klasser (senare polish).
- Skill-skadetyp-konvertering, fler element, set-effekter.
- Efter denna slice fryser vi mekaniken: sedan tuning, sedan Pygame.
