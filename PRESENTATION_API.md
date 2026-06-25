# Presentation API Contract

Det här dokumentet beskriver gränsen som terminal-UI och Pygame-UI:t (battle +
overworld) använder. Målet är att presentationen ska rendera state och skicka
kommandon, inte duplicera spelregler.

## Rendera state

Använd `rpg_game.core.view.build_snapshot(engine)` för read-only rendering.
Snapshoten är immutable dataclasses och innehåller:

- `GameSnapshot.player`: namn, klass, level, XP, HP/mana, damage, armor, speed,
  crit chance, guld, talent points, utrustat vapen och statusar.
- `GameSnapshot.place`: aktuell plats, typ, beskrivning, store-flagga,
  danger tier och om platsen är trygg.
- `GameSnapshot.connections`: grannplatser med id, namn, travel-typ, distans
  och locked-flagga.
- `GameSnapshot.weapons`: ägda vapen med category, damage type, tier,
  required level och om de kan equippas.
- `GameSnapshot.skills`: utrustade skills med kostnader, krav och eventuell
  `blocked_reason`.
- `GameSnapshot.tournaments`: turneringar på aktuell plats med rank,
  opponent-antal, rewards och completed-flagga.

Presentation får läsa snapshoten fritt. Den ska inte mutera snapshoten eller
runtime-dataclasses direkt.

## Mutera state

State ändras via `GameEngine`-metoder:

- `start_new_game(name, class_id)`
- `load(path)` / `save(path)`
- `travel(place_id)`
- `create_encounter()`
- `run_combat_turn(enemy, action_id)`
- `attempt_flee(enemy)`
- `apply_stat_choice(stat)`
- `allocate_talent(node_id)`
- `equip_skill(action_id)` / `unequip_skill(action_id)`
- `buy_item(item_id)` / `sell_item(item_id)`
- `use_consumable(item_id)`
- `rest()`
- `start_tournament(tournament_id)`
- `create_tournament_opponent(tournament, index)`
- `complete_tournament(tournament)`

Presentation ska behandla returvärdena som kontraktet:

- `CombatTurnResult`: outcome, events, HP, XP/gold, pending stat choices, loot
  och Identify-data.
- `ActionResolution`: intern combat-resolution när man medvetet använder
  `combat.resolve_action` för UI-nära handlingar som out-of-combat weapon equip.
- Store, inventory, save/load och rest-resultat har egna strukturer med
  `success`/`outcome` och meddelande.

## Combat-kommandon

Spelaren väljer `"attack"` för basattack. Kärnan rollar quick/normal/power och
returnerar events med den rollade stilen. Presentation ska inte visa eller
skicka quick/normal/power som spelarval.

Tillåtna combat action-id:n från presentation:

- `"attack"`
- `"identify"`
- aktiv skill-id från `engine.equipped_skills()`
- `"item:<item_id>"`
- `"swap:<weapon_id>"`

Om `CombatTurnResult.outcome == "blocked"` ska presentationen visa events och
inte lokalt mutera state.

## Overworld-overlays

Pygame-overworld renderar kartan först och lägger högst en overlay-panel ovanpå.
Panelerna är tillgängliga i overworld, inte i battle:

- `C` / Character: läser stats och ägda vapen från snapshoten; weapon equip går
  via samma weapon-swap action/resolver som övrigt out-of-combat equip.
- `I` / Inventory: visar consumables och junk; consumables använder
  `GameEngine.use_consumable()`, junk är inte klickbart som användbart item.
- `K` / Skills & Talents: skill-loadout använder `equip_skill()` /
  `unequip_skill()`; talent allocation använder `allocate_talent()`.
- `Esc` / System: `save(path)` och quit. Esc stänger också en öppen overlay.

Stadsmenyn får länka till samma overlays för bekvämlighet, men lokala tjänster
som store och rest stannar där platsen erbjuder dem.

## Tournament-kommandon

En turnering är en låst serie strider. Presentationen får erbjuda Back innan
`start_tournament()`, men efter start ska den inte erbjuda flee/abort eller vila
mellan rundorna.

Tillåtna combat action-id:n under en turnering:

- `"attack"`
- `"identify"`
- aktiv skill-id från `engine.equipped_skills()`
- `"item:<item_id>"`
- `"swap:<weapon_id>"`

När alla opponents är besegrade anropar presentationen
`complete_tournament(tournament)`. Slutreward delas ut där, inte per opponent.

## Tuning-simulering

För balansarbete utan manuell playtest:

```sh
python3 -m rpg_game.tools.simulate_balance --trials 100
```

Verktyget skriver CSV-rader med class/enemy, win rate, average turns, HP vid
seger och timeouts. Det använder `rpg_game.core.simulation` och seedad RNG.

## Regler

- `rpg_game/core/` får inte använda `print()` eller `input()`.
- UI får inte implementera egna damage-, XP-, loot- eller cooldown-regler.
- Nya presentationer ska hellre utöka snapshot-kontraktet än läsa många interna
  fält direkt.
