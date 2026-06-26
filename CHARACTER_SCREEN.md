# CHARACTER_SCREEN

Status: design (ej byggt). Fångar spelarkaraktärens visuella identitet och equip-
/character-skärmen. Ersätter den tidigare paper-doll-tanken och absorberar **B4**
(vapentyp + item-preview). Slot-placering och färgval är ännu utkast — se Öppna
beslut. Layout-referens: `equip_skarm_layout.svg`.

---

## 1. Karaktärs-identitet — den kåpade vandraren

Spelaren är **inte** en traditionell äventyrare. Det är en humanoid i kåpa: hela
ansiktet är mörker med **två lysande ögon**, plus kappan. Mystisk, ansiktslös, på
tema med världens grim/eerie-palett (Verralda-heden, undead, grave_heath,
cursed_mire).

Vi **kastar paper-doll** (lager av rustning/vapen per riktning och animationsruta).
Det blir EN kanonisk look för alla — men det betyder *en design*, inte en stillbild:
figuren animeras. Begränsningen blir identitet i stället för problem: när
karaktären medvetet är ansiktslös finns inget "min nya rustning syns inte"-problem,
för det är hela poängen att du är en skugga ute i världen.

## 2. Tre konst-leveranser (samma design, tre poser)

1. **Overworld** — top-down, 4-riktnings-gångcykel, kåpan fladdrar vid rörelse.
2. **Strid** — sidovy, idle / attack / hurt.
3. **Equip-skärmen** — front, **kåp-öppen** (Dracula-pose), *statisk* illustration.

Tre renderingar av samma figur, inte tre olika figurer. Attacker i striden bärs av
effekt + kåp-rörelse + siffror, inte av ett synligt vapen (vapentyp bor i UI:t, §4).

## 3. Kåp-tier (milestone-uppgradering)

Kåpan är **identitet, inte en loot-slot.** Den byts/uppgraderas vid särskilda
milestones (färg/ornamentik, ev. mörkare/mer detaljerad). Implementeras som en
**sprite-swap av hela figuren per tier** (t.ex. tre kåpor) i alla tre poserna — inte
ett lager-system. Equip-skärmens illustration speglar nuvarande kåp-tier.

## 4. Equip-/character-skärmen

OSRS-känsla, men i stället för en figur påmålad med rustning står den kåpade
gubben i mitten och **håller kåpan öppen**, och utrustnings-slottarna ligger
**anatomiskt på kroppen**. Ikon i slot = utrustat item. Vi renderar aldrig rustning
på figuren — bara ikon-slottar över kåp-öppen-posen. Den mörka kåpan är bakgrunden
slottarna läser mot. Detta ger tillbaka progressions-belöningen ("se din gear på din
gubbe") utan paper-doll-kostnaden.

### Tre zoner
- **Mitten — figur + slottar.** Kåp-öppen-figuren med de tio riktiga slottarna
  (se §5) placerade anatomiskt: head över huvan, amulet vid halsen, chest/legs på
  torson, feet nederst, weapon i ena handen, hands + ring ×3 vid den andra.
  *Slot-placeringen finjusteras* (grov i mocken).
- **Höger — inventory.** Scrollbar lista med **alla** items, rarity-färgad.
- **Vänster — stats-sammanfattning.** Varje stat visas som **totalt + varav från
  utrustning** (t.ex. `Power 24 (+6)`, `Armor 18 (+18)`). Spelaren ser direkt hur
  mycket gear:en bidrar med.

### Interaktion
- **Hover på weapons & armour → stats-tooltip per item** (typ, rarity, tier,
  stat-modifiers). Detta absorberar B4:s item-preview.
- **Klick på slot eller inventory-item → equip / unequip.**
- Vapen visar sin **typ** (category + damage_type) — kritiskt för vapen-beroende
  abilities (kopplar till B3.1).

## 5. Data-grund (mätt i repo)

- Slottar (ur `equipment_slots.json`, exakt dessa tio): **weapon, head, chest,
  hands, legs, feet, amulet, ring_1, ring_2, ring_3**. Ingen cape-/sköld-slot —
  kåpan är identitet, det finns ingen offhand.
- Gear bär `stat_modifiers: dict[str,int]`; vapen bär category/damage_type/tier +
  skadebonus. `WeaponSnapshot` exponerar redan category/damage_type/tier/
  required_level (B4 STEG 0) — gapet var presentation, inte data.
- **Stats-delta** (totalt vs från utrustning) = bas (klass/level) vs summan av
  equipped gears `stat_modifiers` + vapenbonus. Beräknas i kärnan och exponeras i
  snapshot; presentationen ritar bara. Ingen regel-dubblering (PRESENTATION_API).
  STEG 0 vid bygge: mät om effektiv-stat/delta redan finns i snapshot eller måste
  läggas till.

## 6. Relation till backlog & arkitektur

- **Ersätter** paper-doll-planen. **Absorberar B4** — B4 pekar hit (vapentyp +
  preview = den här skärmens hover/slot-vy).
- Del av **fluid-layout-migrationen** (character-skärmen). Bygg equip-skärmen mot
  den fluida layouten, inte fast inzoomad.
- **Fasning:** equip-skärmen kan byggas FÖRE de animerade spritarna — den använder
  en statisk illustration + ikon-slottar och hänger bara på equipment-modellen (som
  finns). De tre animerade poserna är separat, senare konst-arbete.

## 7. Öppna beslut

- Slot-placering på kroppen (finjusteras av Lucas).
- Ögonfärg som accent: cyan (mock) vs bärnsten / blodröd — vad bär "grim" bäst?
- Röd kåp-foder (Dracula-nick) kvar eller ej.
- Kåp-tier: antal tiers + vid vilka milestones de byts.
