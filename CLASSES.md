# CLASSES: konkreta klass-träd

Detta dokument innehåller den *konkreta* per-klass-datan: stats, grenar,
noder, kostnader och effekt-semantik. `COMBAT_DESIGN.md` är ramverket (varför
och hur motorn fungerar); detta är innehållet som hälls in i den.

Alla sex klasser är nu designade. **Cleric** och **Tank** är byggda och
gröna; **Rogue, Fighter, Mage, Hunter** är fullt specificerade men ännu inte
byggda. Vi bygger och bekräftar en klass i taget enligt byggordningen nedan —
varje klass-sektion listar sina egna *nya motorfunktioner* och *invarianter*
så att slicen kan byggas isolerat.

Alla tal är startvärden avsedda att tunas i JSON.

## Status

| Klass | Tillstånd |
|---|---|
| Cleric | byggd, grön |
| Tank | byggd, grön |
| Rogue | designad — ej byggd |
| Fighter | designad — ej byggd |
| Mage | designad — ej byggd |
| Hunter | designad — ej byggd |

## Effektvokabulär (vad motorn har NU)

Detta är vad som faktiskt finns implementerat efter Cleric- och Tank-slicen.
Varje kommande klass-slice utökar listan med sina egna "nya motorfunktioner".

Bas:

- **instant_damage** — direkt skada, bär `damage_type`, skalar från Power
  och/eller multiplier. Går genom resistenser; armor reducerar endast
  `physical`.
- **status: poison/dot** — skada per runda i N rundor via tick-loopen.
  Modell: `{ type, magnitude, duration, tick_timing }`.

Från Cleric-slicen:

- **instant_heal** — läker mål; cappas vid `max_hp` (ingen överhealing).
- **drain** — instant_damage + läk källan en andel av utdelad skada (cappas).
- **status: regen** — heal/runda i N rundor (samma tick-loop som poison).
- **status: debuff** — sänker en namngiven stat medan aktiv; återställs vid
  utgång.
- **status: buff** — som debuff fast positiv.
- **passiv: stat_bonus** — platt påslag på en stat.
- **passiv: applied_status_mod** — ändrar parametrarna på statuseffekter som
  entiteten *applicerar*.

Från Tank-slicen:

- **cooldown-system** — action med `cooldown_rounds`; otillgänglig N rundor;
  speglas i `available_actions`.
- **status: mitigation** — platt reduktion av all inkommande skada.
  Lager: resist → armor (physical) → mitigation (all) → `max(1, …)`.
- **status: reflect** — vid träff på bäraren delas skada tillbaka (flat eller
  Power-skalad). Reflekterad skada triggar aldrig ny reflect.
- **accuracy_mod** (fält) — träffslag använder `clamp(base + accuracy_mod, 0, 100)`.
- **passiv: immunity** — immun mot en tagg (`debuff`, `flee_force`).

## Talang- och upplåsningsregel

- **1 talangpoäng per level up**, utöver det befintliga stat-valet.
- Noder låses upp **linjärt inom en gren** (nod 2 kräver nod 1). Poäng får
  fördelas fritt mellan grenarna.
- Kärnan exponerar `available_talents()` och `allocate_talent(node_id)` —
  presentationen driver valet. **Inget `input()` i kärnan.**
- Aktiva noder blir utrustningsbara skills. **Max 4 utrustade skills** gäller.

## Byggordning (beroende-driven)

Ordningen är inte godtycklig — varje klass lutar sig på mekanik den föregående
inför:

1. **Cleric** ✓ — grundläggande effektvokabulär (heal, drain, dot, buff/debuff).
2. **Tank** ✓ — defensiva hakar (cooldown, mitigation, reflect, immunity).
3. **Rogue** — inför **crit**, **conditional** (execute) och **evasion**.
   `conditional` blir en generisk byggsten som tre senare klasser återanvänder.
4. **Fighter** — återanvänder crit + conditional; inför **armor_pen**,
   **multi-hit** och **stacking buff**.
5. **Mage** — återanvänder conditional; inför **skip_turn** (freeze).
   (Oberoende av Rogue/Fighters offensiva tillägg utöver conditional.)
6. **Hunter** — återanvänder crit (Rogue), armor_pen (Fighter), conditional,
   dot; inför endast **damage_taken_mod** (vulnerability). Sist eftersom den
   ärver mest.

---

## Cleric  *(byggd, grön)*

Resursklassen. Måttlig överlevnad, låg Power, lever på mana och timing. Bär
ett holy-vapen (mace). Grenar: **Ljus** (smite, heal, support) och **Pest**
(poison, drain, curse).

### Basstats

| Stat | Värde |
|---|---:|
| HP / Max HP | 90 |
| Max Mana | 30 |
| Power | 10 |
| Armor | 0 |
| Speed | 10 |
| Startvapen | Mace (holy) |

### Gren: Ljus

| Nod | Typ | Effekt | Mana |
|---|---|---|---:|
| L1 Smite | aktiv | instant_damage, holy, ~1.5× Power | 6 |
| L2 Mend | aktiv | instant_heal self, +25 (cappas) | 8 |
| L3 Devotion | passiv | stat_bonus: +15 max_mana | — |
| L4 Sanctuary | aktiv | status regen self: +8 HP/runda i 3 rundor | 10 |

### Gren: Pest

| Nod | Typ | Effekt | Mana |
|---|---|---|---:|
| P1 Plague Bolt | aktiv | status poison på mål: 6/runda i 3 rundor | 7 |
| P2 Drain | aktiv | drain, holy, ~1.2× Power; läk self 50% | 9 |
| P3 Virulence | passiv | applied_status_mod: egna poisons +1 dur, +2 mag | — |
| P4 Curse | aktiv | status debuff på mål: Power −4 i 3 rundor | 8 |

---

## Tank  *(byggd, grön)*

Mitigeringsklassen. Hög överlevnad, låg Power, liten mana-pool — lutar sig på
cooldowns. Grenar: **Guardian** (aktiv mitigering) och **Sentinel** (sustain,
counter, immunitet).

### Basstats

| Stat | Värde |
|---|---:|
| HP / Max HP | 130 |
| Max Mana | 15 |
| Power | 8 |
| Armor | 4 |
| Speed | 7 |
| Startvapen | Mace (physical) |

### Gren: Guardian

| Nod | Typ | Effekt | Kostnad |
|---|---|---|---|
| G1 Block | aktiv | status mitigation self: −8 all inkommande i 1 runda | cooldown 2 |
| G2 Thorns | aktiv | status reflect self: 3 rundor, 5 skada till den som träffar | 6 mana |
| G3 Bulwark | passiv | stat_bonus: +3 armor, +20 max_hp | — |
| G4 Taunt | aktiv | status debuff på mål: accuracy_mod −20 i 2 rundor | cooldown 3 |

### Gren: Sentinel

| Nod | Typ | Effekt | Kostnad |
|---|---|---|---|
| S1 Iron Stance | aktiv | status regen self: +6 HP/runda i 3 rundor | 6 mana |
| S2 Counter | aktiv | status reflect self: 2 rundor, vid träff 1.0× Power physical | 8 mana |
| S3 Resolve | passiv | immunity mot `debuff` och `flee_force` | — |
| S4 Fortitude | passiv | stat_bonus: +5 armor, +20 max_hp | — |

---

## Rogue  *(designad — ej byggd)*

Burst- och precisionsklassen. Hög speed (agerar först), bräcklig, lever på
crit och att avsluta skadade fiender. Grenar: **Assassin** (crit, execute,
bleed) och **Duelist** (evasion, riposte).

### Basstats

| Stat | Värde |
|---|---:|
| HP / Max HP | 80 |
| Max Mana | 20 |
| Power | 13 |
| Armor | 0 |
| Speed | 16 |
| Crit-chans | 10% (bas) |
| Startvapen | Dagger (physical) |

### Nya motorfunktioner denna slice

- **crit** — `crit_chance` (stat) + global `crit_mult` (start 2.0). instant_damage
  rullar crit; vid crit multipliceras skadan. En attack/buff kan addera
  bonus-crit_chance. (Löser `COMBAT_DESIGN.md`:s öppna fråga: crit bor i
  klass/gear, inte som universell stat för alla.)
- **conditional** — generisk villkorsmodifierare på instant_damage:
  `{ subject: target|self, predicate, mult }`. Här: execute (target hp% ≤ X).
  Återanvänds av Fighter, Mage, Hunter med andra predikat.
- **evasion** — `evasion_chance` (via buff). Inkommande attack rullar evade;
  vid evade tar bäraren 0 skada. Kan trigga `reflect` med `trigger: on_evade`
  (riposte) — en liten utökning av reflects befintliga on-hit-trigger.

### Gren: Assassin

| Nod | Typ | Effekt | Mana |
|---|---|---|---:|
| A1 Backstab | aktiv | instant_damage physical 1.6× Power, +25% crit denna attack | 6 |
| A2 Rupture | aktiv | status dot (physical bleed) på mål: 7/runda i 3 rundor | 7 |
| A3 Lethality | passiv | stat_bonus: +15% crit_chance | — |
| A4 Execute | aktiv | instant_damage physical 1.4× Power; om mål hp% ≤ 30 → ×2.5 (conditional) | 8 |

### Gren: Duelist

| Nod | Typ | Effekt | Mana |
|---|---|---|---:|
| D1 Evasion | aktiv | status buff self: +40% evasion_chance i 2 rundor | 6 |
| D2 Riposte | aktiv | status reflect self (trigger: on_evade): 3 rundor, slå tillbaka 1.0× Power | 7 |
| D3 Finesse | passiv | stat_bonus: +4 Power, +2 Speed | — |
| D4 Deadly Precision | aktiv | status buff self: +30% crit_chance i 3 rundor | 7 |

### Invarianter att låsa i test

- **crit**: vid forcerad crit-roll multipliceras skadan med exakt `crit_mult`;
  utan crit oförändrad. Backstabs +25% adderas korrekt till bas-crit_chance.
- **Execute**: mot mål med hp% ≤ 30 blir skadan ×2.5; vid hp% > 30 normal.
- **Lethality/Deadly Precision**: crit_chance höjs med rätt belopp, kvarstår
  rätt tid (buffen löper ut).
- **Evasion**: en attack mot bäraren med aktiv evasion missar enligt
  evasion_chance och gör då 0 skada.
- **Riposte**: vid *evade* slår bäraren tillbaka 1.0× Power; ingen riposte
  vid träff eller utan buff; reflekterad skada triggar inte ny reflect.
- **Rupture**: bleed tickar 7/runda i 3 rundor via tick-loopen.
- **Regression**: alla tidigare tester gröna.

---

## Fighter  *(designad — ej byggd)*

Råskadeklassen, aggressiv. Grenar: **Berserker** (rage, lifesteal, lågt-HP-
skalning) och **Weaponmaster** (crit, armor pen, combo). Återanvänder crit och
conditional från Rogue.

### Basstats

| Stat | Värde |
|---|---:|
| HP / Max HP | 100 |
| Max Mana | 20 |
| Power | 15 |
| Armor | 0 |
| Speed | 11 |
| Crit-chans | 5% (bas) |
| Startvapen | Sword (physical) |

### Nya motorfunktioner denna slice

- **armor_pen** — skade-property: `effektiv_armor = max(0, armor − pen)` före
  physical-mitigering.
- **multi-hit** — `hits: N` på instant_damage: producerar N separata
  skadeinstanser (varje rullar crit för sig).
- **stacking buff** — buff med `max_stacks`; varje applicering lägger en stack;
  stackarna ger additiv effekt och löper ut tillsammans.

### Gren: Berserker

| Nod | Typ | Effekt | Mana |
|---|---|---|---:|
| B1 Frenzy | aktiv | drain physical 1.5× Power, läk self 30% | 6 |
| B2 Rage | passiv | vid skada (on_damaged): +3 Power (stacking buff, max 5 stacks) | — |
| B3 Bloodlust | passiv | conditional: medan eget hp% ≤ 40 → +30% utdelad skada | — |
| B4 Reckless | aktiv | status buff self: +50% utdelad skada OCH +25% tagen skada i 3 rundor | 7 |

### Gren: Weaponmaster

| Nod | Typ | Effekt | Mana |
|---|---|---|---:|
| W1 Precision | aktiv | instant_damage physical 1.4× Power, +35% crit denna attack | 6 |
| W2 Sunder | aktiv | instant_damage physical 1.3× Power, armor_pen 6 | 6 |
| W3 Mastery | passiv | stat_bonus: +6 Power | — |
| W4 Combo | aktiv | multi-hit: 2× 0.8× Power physical | 8 |

### Invarianter att låsa i test

- **armor_pen**: Sunder mot mål med armor 6 ignorerar exakt 6 armor (min 1 går
  fortfarande igenom).
- **multi-hit**: Combo producerar exakt 2 skadeinstanser; varje rullar crit
  oberoende.
- **Rage stacking**: efter 3 träffar +9 Power; capped vid +15 (5 stacks);
  löper ut korrekt.
- **Bloodlust**: vid eget hp% ≤ 40 är utdelad skada +30%; över 40 normal.
- **Reckless**: utdelad skada +50% och tagen skada +25% medan aktiv; båda
  upphör vid utgång.
- **Regression**: alla tidigare tester gröna.

---

## Mage  *(designad — ej byggd)*

Elementär burst- och kontrollklass, mana-tung, bräcklig. Grenar: **Pyromancer**
(fire, burn-DoT, burst) och **Cryomancer** (frost, freeze, kontroll).
Återanvänder conditional från Rogue.

### Basstats

| Stat | Värde |
|---|---:|
| HP / Max HP | 75 |
| Max Mana | 40 |
| Power | 12 |
| Armor | 0 |
| Speed | 9 |
| Startvapen | Staff (fire) |

### Nya motorfunktioner denna slice

- **skip_turn** — status som får bäraren att tappa sin nästa handling (freeze).
  En flagga statusen sätter; konsumeras vid turordningen.
- (conditional återanvänds med nytt predikat: "målet har status X".)

### Gren: Pyromancer

| Nod | Typ | Effekt | Mana |
|---|---|---|---:|
| Y1 Firebolt | aktiv | instant_damage fire 1.6× Power | 6 |
| Y2 Ignite | aktiv | status dot (fire burn) på mål: 8/runda i 3 rundor | 7 |
| Y3 Combustion | passiv | conditional: +20% fire-skada mot mål med burn aktiv | — |
| Y4 Fireball | aktiv | instant_damage fire 2.4× Power (burst) | 14 |

### Gren: Cryomancer

| Nod | Typ | Effekt | Mana |
|---|---|---|---:|
| C1 Frostbolt | aktiv | instant_damage frost 1.4× Power + debuff: mål Speed −4 i 2 rundor | 7 |
| C2 Freeze | aktiv | skip_turn på mål: tappar sin nästa handling | 12 (cooldown 3) |
| C3 Frostbite | passiv | conditional: +25% frost-skada mot frusna/chillade mål | — |
| C4 Ice Lance | aktiv | instant_damage frost 1.5× Power; om mål fruset → ×2 (conditional) | 9 |

### Invarianter att låsa i test

- **skip_turn**: ett fruset mål hoppar över exakt en handling, agerar sedan
  normalt igen.
- **Freeze cooldown**: kan inte kedjas — otillgänglig under cooldown.
- **Combustion/Frostbite**: bonusen gäller endast när målets status matchar
  predikatet; annars normal skada.
- **Ice Lance**: ×2 endast mot fruset mål.
- **Frostbolt-chill**: Speed −4 i 2 rundor, återställs.
- **Regression**: alla tidigare tester gröna.

---

## Hunter  *(designad — ej byggd)*

Svaghetsutnyttjande precisions- och kontrollklass. Grenar: **Marksman**
(precision, vulnerability, armor pen) och **Trapper** (snaror, gift, svaghets-
bonus). Ärver mest — crit (Rogue), armor_pen (Fighter), conditional, dot.

### Basstats

| Stat | Värde |
|---|---:|
| HP / Max HP | 85 |
| Max Mana | 25 |
| Power | 13 |
| Armor | 1 |
| Speed | 13 |
| Crit-chans | 8% (bas) |
| Startvapen | Bow (physical) |

### Nya motorfunktioner denna slice

- **damage_taken_mod** (vulnerability) — debuff som höjer *all* skada målet tar
  med X% under N rundor. (Enda nya tillägget; allt annat återanvänds.)

### Gren: Marksman

| Nod | Typ | Effekt | Mana |
|---|---|---|---:|
| M1 Aimed Shot | aktiv | instant_damage physical 1.7× Power, hög träffsäkerhet | 6 |
| M2 Hunter's Mark | aktiv | debuff damage_taken_mod: mål tar +25% all skada i 3 rundor | 7 |
| M3 Precision | passiv | stat_bonus: +20% crit_chance | — |
| M4 Piercing Shot | aktiv | instant_damage physical 1.5× Power, armor_pen 8 | 7 |

### Gren: Trapper

| Nod | Typ | Effekt | Mana |
|---|---|---|---:|
| T1 Snare | aktiv | debuff: mål Speed −6 och accuracy_mod −10 i 2 rundor | 6 |
| T2 Venom Trap | aktiv | status dot (poison) på mål: 9/runda i 3 rundor | 7 |
| T3 Exploit Weakness | passiv | conditional: +30% skada när skadetypen matchar målets svaghet (resist > 1.0) | — |
| T4 Beast Slayer | passiv | conditional: +25% skada mot mål med taggen `beast` | — |

### Invarianter att låsa i test

- **Hunter's Mark**: medan aktiv tar målet +25% från alla källor; upphör vid
  utgång.
- **Piercing Shot**: armor_pen 8 mot mål med armor 8 ignorerar all armor (min 1).
- **Exploit Weakness**: +30% endast när skadetypen träffar en svaghet
  (resist > 1.0); annars normal.
- **Beast Slayer**: +25% endast mot mål taggade `beast`.
- **Snare**: Speed −6 och accuracy_mod −10 i 2 rundor, återställs.
- **Regression**: alla tidigare tester gröna.

---

## Main/secondary (påminnelse)

Combo-modellen från `COMBAT_DESIGN.md`: main-klass ger fulla basstats + hela
sitt träd; secondary ger endast **gren A:s tier-1-nod + en passiv** plus en
mindre statmod. Secondary hålls medvetet grunt för att undvika kombinatorisk
balansexplosion. Combo-reglerna byggs som data *efter* att alla sex klasser
står gröna var för sig — det är en egen, senare slice.