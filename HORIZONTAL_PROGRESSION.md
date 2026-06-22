# HORISONTELL PROGRESSION: material, komponenter, transmutation och skills

En framtidsvision för hur utrustning får långsiktigt syfte och identitet — så att
man *bygger på och uppgraderar* snarare än byter ut, och så att så mycket som
möjligt i spelet (en fälld best, en malmåder, en ädelsten) har en mening. Plus
ett RuneScape-inspirerat lager av icke-combat-skills som binder ihop allt.

**Status:** designskiss, framtida spår. INGET av detta byggs nu. Det här fångar
filosofin och systemen medvetet, så idén inte tappas och så att de byggs i rätt
ordning på en grund som står stilla — efter att världen har innehåll och spel-
testning faktiskt visat att utrustning känns slit-och-släng. Skissen är inte en
byggorder; den är en kompass.

## Filosofin: horisontell, inte vertikal

Vertikal progression (WoW i sin sämsta form): ett nytt item gör det förra
irrelevant; du byter ut, det gamla skrotas, kraften är en stege där varje pinne
raderar den förra. Icke-combat-system är grunda — gör item, klar.

Horisontell progression (det du är ute efter, RuneScape i sin bästa form): saker
har långvarigt syfte. Du *bygger på* det du har. Ett vapen följer med dig och
växer. Skills är djupa, sammanflätade, och belönar resan — inte bara taket. Din
utrustning blir *din*, inte en av N fasta drops.

Tre principer styr resten av dokumentet:

1. **Allt har ett syfte.** Den fällda björnens päls, malmådern, ädelstenen, det
   gamla vapnet du skulle ha skrotat — allt är en *insats* i något. Dagens
   junk-loot (rat_pelt, bone_dust) ska bli material, inte bara guld-foder.
2. **Bygg på, byt inte ut.** Uppgradera, sockla, transmutera. Färre drops, men
   varje drop betyder mer och lever längre.
3. **Identitet i utrustningen.** Ett vapen = material-bas + det du socklat + det
   du transmuterat. Två spelare med "samma" vapen bär ändå inte samma vapen.

## Dina tre system

### 1. Materialnivåer av samma vapen (RuneScape-stegen, smalare)

Samma vapentyp i flera material som skiljer sig i grundstyrka. Inte RS:s fulla
bronze→iron→steel→mithril→adamant→rune, men en smalare stege — säg 3–4 steg per
vapentyp. En "greataxe" finns som t.ex. iron / steel / mithril / rune, där varje
är samma vapen men starkare bas.

- **Mest data.** En vapen-mall (greataxe) × en material-modifierare (tier +
  bas-bonus + ev. level/skill-krav). Skadetyp och kategori ärvs från mallen.
- Ger igenkänning (du vet vad en greataxe är) och en tydlig stege *inom* en typ.
- Kan i princip skeppas som ren loot/butik-data utan något skill-system — men
  blir *meningsfullt* först när man kan smida dem själv (se Smithing nedan).
- Förhåller sig rent till `WEAPONS.md`: `category` och `damage_type` lever kvar;
  material är ett nytt fält ovanpå.

### 2. Komponenter / sockets (ädelsten-handtaget)

En iron greataxe med sapphire-handtag ger +frost. Ett vapen (eller en geardel)
är inte längre ett fast föremål utan en **bas + socklar** där man sätter
komponenter (ädelstenar, runor) som modifierar attribut.

- **Riktigt system.** Det ändrar item-modellen: item = bas + en lista socklade
  komponenter. Men grunden finns till hälften redan: equipment-systemets
  `stat_modifiers` (EQUIPMENT.md) är *exakt* vad en socklad ädelsten är — en
  modifierar-källa. En sockel är en modifierare med en plats.
- **Och elementdelen är redan mekaniskt möjlig.** Multi-komponent-skadan
  (DAMAGE.md) gör redan att en attack kan bära flera skadekomponenter med olika
  `damage_type`, var och en löst mot resistanser. En "+frost"-ädelsten lägger
  helt enkelt till en frost-komponent på basattacken — precis som element-
  talangerna redan gör. Skademotorn behöver alltså inte ändras; det som saknas är
  *sockel-lagret* som låter spelaren bygga de komponenterna på sin gear.
- **Sockeltyper ger placering mening:** ett vapen kan ha en "haft"-sockel för
  skade-/element-stenar; rustning en "foder"-sockel för resist-stenar. Det gör
  socklandet till ett val, inte bara fler slots.
- **Förenas med "fasta items" (LOOT.md):** LOOT.md slog fast fasta drops, inga
  slumpade affixar (RuneScape, inte Diablo). Det HÅLLER om ädelstenarna också är
  fasta föremål — du hittar en fast sapphire, socklar en fast +frost. Slumpen
  ligger inte i dropens stats, utan i *vilken kombination du bygger*. Det är
  faktiskt djupare än Diablos affix-lotteri och helt förenligt med beslutet.

### 3. Transmutation / uppgradering (consecration mace → unholy, +1 tier)

Att ta ett item och *förvandla* det med ett rare-material: en consecration mace
+ ett särskilt rare-item → en unholy mace, +1 tier, bytt attribut (holy →
shadow/unholy). Vapnet följer med dig och *utvecklas* i stället för att skrotas.

- **Riktigt system.** Item-state-mutation + recept (vad + vad → vad). Det rör
  hur tier/skadetyp/attribut ändras på ett befintligt item.
- **Löser exakt problemet du namngav.** Din consecration mace blev mäktig och
  skulle annars bli obsolet — med transmutation evolverar den i stället. Det är
  den renaste formen av "bygg på, byt inte ut".
- Naturligt skill-gated (hög Enchanting krävs för att transmutera) så det är en
  belöning, inte en gratis-knapp.

## Mitt tillägg: skill-väven som binder ihop allt

Du sa att RS-skills är kul och att WoW missar med grunda icke-combat-system. Jag
håller med, och nyckeln är att skills ska vara **djupa** (långa kurvor, många
unlocks på vägen — inte bara ett tak), **sammanflätade** (en skill matar en
annan) och **frikopplade från combat-level** (du kan mina mithril vid Mining 30
oavsett din strids-level). Det är den väven WoW saknar.

Förslag på en liten men äkta väv — gathering matar production matar combat:

**Gathering (förvandlar världen och kills till insatser):**

| Skill | Källa | Ger | "Allt har syfte"-payoff |
|---|---|---|---|
| **Mining** | malmådror i zoner | malm → tackor | nya noder i världen att besöka |
| **Skinning / Harvest** | fällda bestar | pälsar, huggtänder, hudar | junk-drops blir material |
| *(ev.)* Woodcutting | träd | hafts till bågar/stavar | — |

**Production (gör och förfinar gear):**

| Skill | Tar | Gör | Hem för |
|---|---|---|---|
| **Smithing** | tackor | material-tier-vapen & rustning | system #1 (materialstegen) |
| **Enchanting** | ädelstenar, runor, rare-material | socklar, runor, transmutation | system #2 + #3 |

Loopen blir den RS-känsla du gillar: *döda bestar + mina → material → smida en
bas → enchanta/sockla för identitet → transmutera för att låta den växa.* Varje
led har syfte: björnpälsen, malmådern, ädelstensdropen, det gamla vapnet.

**Hur skills levlar:** XP av att göra aktiviteten (mina = Mining-XP; smida =
Smithing-XP), egen nivå per skill, **unlocks på många nivåer** (kan bearbeta
mithril vid Smithing X; kan sockla sapphire vid Enchanting Y; kan transmutera
vid Enchanting Z). Det är djupet WoW saknar — en resa, inte bara ett tak. En ny
progressionsaxel vid sidan av combat-level.

**Salvage (valfri men tematiskt stark):** att plocka isär oönskad gear till
material. Då är även loot du inte använder aldrig bortkastad — den blir insats.
Förstärker "allt har syfte" och dämpar drop-treadmillen.

## Genom-tråden: identitet och längre livslängd

Allt ovan tjänar samma sak. Ett vapen = **material-bas** (vad det är) +
**socklar** (vad du byggt i det) + **transmutation** (hur det vuxit). Det blir
*ditt*. Och eftersom du uppgraderar i stället för att byta ut kan drop-frekvensen
sänkas och varje drop bli mer meningsfull — färre items, mer identitet, längre
liv per item. Exakt den "relativt stora identiteten i utrustningen" du ville ha.

## Vad som är gratis, billigt och dyrt

Ärlig kostnadsbild mot nuvarande motor:

- **Redan på plats (substrat finns):** multi-komponent-skada (element-stenar
  behöver ingen ny skademotor), `stat_modifiers` (en socklad sten ÄR en
  modifierare), stackbara consumables (material-stacks har ett substrat),
  fasta-items-beslutet (förenligt med fasta ädelstenar).
- **Billigt (mest data):** materialnivåer (#1) — vapen-mall × material.
- **Dyrt (riktig motor + ny state):** sockel-lagret på items (#2), transmutation
  + recept (#3), och hela skill-väven (ny progressionsaxel, XP/nivå per skill,
  noder i världen, save/load-utökning).

## Slicing — om/när detta tas av hyllan

Minimal-först, så det aldrig blir allt-eller-inget. Var och en är en äkta
commitment och spelbar för sig:

1. **Materialnivåer + en enkel Smithing-skill.** Billigast, och bevisar
   filosofin: junk + tackor → en uppgradering du *gjorde*, plus en icke-combat-
   axel att levla. Rör inte item-modellen (inga socklar än). Det här ensamt
   svarar på "items känns slit-och-släng" och kan vara hela v1 om du nöjer dig.
2. **Sockels + Enchanting (komponenter).** Ändrar item-modellen; lutar sig mot
   `stat_modifiers` + multi-komponent-skada som redan finns. Ger identitet.
3. **Transmutation.** Mest komplext (item-mutation + recept). Får vapen att växa.
4. **Resten av gathering-väven** (Mining-noder, Skinning, ev. Woodcutting,
   Salvage) breddas in efter hand.

## Ärlig scope-varning (läs denna)

Det här är en **andra pelare** i spelet, i samma storleksordning som hela
combat-systemet vi byggt. Det är inte "ett system till" — det är ett helt nytt
spel-lager. Tre konsekvenser:

- **Bygg det inte nu.** Vi är mitt i att befolka zon 2. Spelet har en spelbar
  zon och noll art. Att börja riva i item-modellen nu vore att lägga en pelare
  på ett halvmöblerat hus.
- **Du vet inte än om du behöver det.** Poängen är att lösa "items blir
  irrelevanta för snabbt" — men det har du inte mätt än, du har en zon. Spela
  genom flera zoner först; då vet du om utrustning känns slit-och-släng, och
  *vilken* slice som löser det (kanske räcker materialnivåer; kanske vill du ha
  hela väven). Bygg det uppmätta behovet, inte alla tre på spekulation.
- **Samma disciplin som hittills.** Du sköt balanstuning och vägrade nerfa
  klasser mitt i bygget. Samma princip, fast starkare här: det här är ett mycket
  större åtagande. Det hör hemma efter att världen lever och du spelat den.

## Beroenden och risker

- **Sockels rör vapen-modellen**, som idag är orörd av equipment-systemet
  (medvetet). Att sockla vapen är den största enskilda motor-ändringen.
- **`stat_modifiers` är substratet för stenar** — bra återbruk, men verifiera att
  en sockel-källa kan matas in i `effective_stat`-aggregeringen utan
  special-fall.
- **Element-stenar lutar på multi-komponent-skadan** — redan möjlig, men en sten
  som lägger till en skadekomponent på basattacken måste gå genom samma väg som
  element-talangerna, inte en ny.
- **Skill-XP/nivåer är en ny progressionsaxel** → ny state, save/load-utökning,
  ny UI-yta (skill-panel). Inte trivialt.
- **Balans-risk:** crafting + transmutation kan trivialisera loot (gör din egen
  BiS) om det inte gate:as av skill-nivå + sällsynta material. Skill-gating är
  försvaret.

## Öppna frågor (att besluta när detta tas upp)

- Hur smal ska materialstegen vara? (3 eller 4 steg per vapentyp?)
- Hur många sockeltyper, och hur många socklar per item-slot?
- Är transmutation enkelriktad (holy → unholy permanent) eller reversibel?
- Hur många skills i väven v1 — bara Smithing + Enchanting, eller direkt med
  Mining/Skinning som matar dem?
- Ska skills ha unlocks utöver "kan bearbeta högre material" — t.ex. passiva
  bonusar, recept, effektivitet? (WoW-fällan är att de bara höjer ett tak.)

## Utanför även denna vision (åtminstone nu)

- Player housing / egna verkstäder, handel mellan spelare (single-player).
- Slumpade affixar (vi håller fasta items; identitet kommer från kombination).
- Set-bonusar (kandidat, men separat från detta).
