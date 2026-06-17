# WEAPONS: vapentyper och skill-gating

Löser det playtesten blottade så fort loot kom in: **skills skalar på bas-Power
och struntar i vapnet**, så ett starkt (ofta off-class) vapen gör basattacker
bättre än hela ens kit — och det fanns ingen vettig koppling mellan vapen och
skill (Aimed Shot med en klubba). Bygger på vapen-ägandet från LOOT-slicen.

**Status:** design.

## Modell

- Varje vapen har en **kategori**: `melee`, `ranged` eller `magic`. Kategorin
  beskriver *hur* man slåss med det, och är skild från `damage_type` (vad för
  element). En Consecrated Maul är `melee` + `holy`; en Staff är `magic` + `fire`.
- **Alla klasser kan bära allt.** Inga klass-restriktioner — rummet för weird
  builds står öppet.
- En skill **gatas "när det är vettigt"** till en kategori: ett bågskott kräver
  `ranged`, en riposte kräver `melee`, en besvärjelse kräver `magic`. Gating
  sitter på *kategori*, inte på klass eller specifik vapentyp.
- En gatad skill **skalar med det utrustade vapnet** (se formel). Så starka
  Hunter-skills kräver en bättre *båge*, inte att man byter till en maul.
- **Basattacker gatas aldrig** — vilket vapen som helst, som nu.

## Vapenkategorier

| Vapen | Kategori | damage_type |
|---|---|---|
| Knife, Dagger, Sword, Axe, Longsword, Mace (physical) | melee | physical |
| Steel Greatsword, Venomfang, Worldsplitter | melee | physical |
| Consecrated Maul, Gravewarden Blade | melee | holy |
| Bow | ranged | physical |
| Mace (holy) | magic | holy |
| Staff | magic | fire |
| Emberwand, Pyre Scepter | magic | fire |
| Rimebrand | magic | frost |

Form-faktorn avgör kategorin (svärd/klubba/blad/dolk/maul = melee; båge =
ranged; stav/spira/wand/heligt fokus = magic); elementet är fristående.

## Skill-klassificering

**Regeln:** en skill som gör skada vilken *bör* skala med vapnet kräver en
kategori OCH skalar med vapnet. Skill behåller sin egen `damage_type`.
Allt annat — dots, buffar, heals, debuffs, kontroll, passiva — har **fast
magnitud, ingen vapenkrav** (så en kastare utan fokus kan fortfarande lägga
dots/kontroll, bara inte sina direkta nukes).

### Gatade + vapenskalade

| Klass | Skill | Kategori |
|---|---|---|
| Tank | Counter (riposte) | melee |
| Rogue | Backstab, Execute, Riposte | melee |
| Fighter | Frenzy, Precision, Sunder, Combo | melee |
| Cleric | Smite, Drain | magic |
| Mage | Firebolt, Fireball, Frostbolt, Ice Lance | magic |
| Hunter | Aimed Shot, Piercing Shot | ranged |

(Frostbolt: skadedelen skalar/gatas; speed-debuff-ridern är fast. Counter/
Riposte: reflect-magnituden skalar med vapnet, kravet är melee.)

### Fria (ingen kategori, fast magnitud)

Alla dots (Plague Bolt, Rupture, Ignite, Venom Trap), heals (Mend, Sanctuary,
Iron Stance), buffar (Evasion, Deadly Precision, Reckless), debuffs/kontroll
(Curse, Taunt, Snare, Hunter's Mark, Freeze), flat reflect (Thorns), och alla
passiva (Devotion, Lethality, Mastery, Combustion, Beast Slayer m.fl.).

> **Beslut att stämma av:** jag gatar bara *direkt vapenskada + ripostes*.
> Det betyder att en kastare utan magiskt fokus ändå kan lägga dots/kontroll
> (delvis funktionell weird build) men inte sina nukes. Vill du istället att
> *alla* besvärjelser kräver ett magiskt fokus, säg till — det är en rad i
> tabellen ovan.

## Skalningsformel

För gatade skadeskills, byt ut `Power` mot `Power + vapnets bonus` — exakt som
basattacker redan räknar:

```
skada = round_half_up( multiplier × (base_power + equipped_weapon_bonus) )
```

…med skillens egen `damage_type`, därefter resistenser/armor som vanligt.
Multiplikatorerna i CLASSES.md står kvar tills vi ser dem i spel.
DoT/buff/heal/debuff-magnituder ändras INTE — de förblir sina fasta tal.

## Gating-beteende

- Saknas rätt kategori-vapen är skillen **otillgänglig**: i skill-menyn visas
  kravet och en markering (t.ex. `Aimed Shot — kräver ranged [INGET RANGED-VAPEN]`),
  och försök att välja den **repromptar utan att förbruka rundan** (samma
  mönster som not-ready).
- Basattacker och fria skills påverkas inte.

## Invarianter att låsa i test

- En gatad skill med rätt vapen: skadan = `multiplier × (Power + vapenbonus)`
  (seedat/forcerat, ingen crit) — bevisa att vapenbonusen ingår.
- Samma skill med fel kategori-vapen: otillgänglig; val förbrukar inte rundan;
  state oförändrat.
- Fri skill (t.ex. Iron Stance, Ignite): användbar oavsett vapen; magnitud
  oförändrad av vapnet.
- Counter/Riposte: reflect-skadan skalar med melee-vapnets bonus; kräver melee.
- Basattack: oförändrad (vilket vapen som helst, skalar som förut).
- Regression: alla tidigare tester gröna.

## Byggordning

1. **Motor + data**: lägg `category` på alla vapen; lägg
   `requires_weapon_category` på de gatade skills enligt tabellen; ändra
   skadeskalningen för gatade skills till att inkludera vapenbonus; inför
   gating (otillgänglig + reprompt) i skill-valet. Lås invarianterna.

(En klass i taget behövs inte här — det är samma mekanik applicerad som data
över alla skills. Men dela gärna i två commits om motorn och databredden blir
stora: först en gatad klass som bevis, sedan resten.)

## Utanför denna slice

- **Junk/rare-tuning** (separat, ren JSON): mer junk-frekvens, sällsyntare
  rares — de föll för lätt i playtesten.
- Vapen-specifika krav (en skill som kräver exakt "bow", inte bara `ranged`).
- Cross-class/secondary-skills och hur de gatas (väntar på combo-slicen).
- Två-händer/sköld, vapen-hastighet, dual wield.
