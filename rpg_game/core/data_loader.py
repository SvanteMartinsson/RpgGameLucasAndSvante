"""Load authored JSON content into typed dataclasses.

This module is the boundary between data files and the runtime game state.
Keep defaults here when adding optional JSON fields so older data remains
loadable during development.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rpg_game.core.entities import (
    BossDef,
    ChestDef,
    Connection,
    ConsumableItem,
    CombatAction,
    EnemyTemplate,
    EquipmentSlot,
    EffectSpec,
    GameContent,
    GearItem,
    Place,
    Position,
    PlayerClass,
    TalentNode,
    Tournament,
    TournamentReward,
    UpgradeMod,
    UpgradeRecipe,
    UpgradeVariant,
    Weapon,
)
from rpg_game.core.equipment import ALLOWED_GEAR_STATS
from rpg_game.core import combat, traits


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_STORE_INVENTORY = ("hp_potion", "sword", "axe", "longsword")


def _read_json(filename: str) -> Any:
    with (DATA_DIR / filename).open(encoding="utf-8") as file:
        return json.load(file)


def _core_zone_store_towns() -> dict[str, bool]:
    """place_id -> has_store, derived from core_zone tier + shop_category (the
    source of truth for a town's rendered cluster). capital/city/town always have
    a trade building; a village only when it has a shop_category."""
    try:
        towns = _read_json("maps/core_zone.json")["towns"]
    except (FileNotFoundError, KeyError):
        return {}
    return {
        t["place_id"]: t.get("tier") in {"capital", "city", "town"}
        or (t.get("tier") == "village" and bool(t.get("shop_category")))
        for t in towns
    }


def _load_upgrade_recipes() -> dict[str, UpgradeRecipe]:
    recipes: dict[str, UpgradeRecipe] = {}
    for item_id, row in _read_json("upgrades.json").items():
        variants = tuple(
            UpgradeVariant(
                id=v["id"],
                name=v["name"],
                description=v.get("description", ""),
                mods=tuple(
                    UpgradeMod(
                        type=m["type"],
                        stat=m.get("stat", ""),
                        damage_type=m.get("damage_type", ""),
                        value=int(m.get("value", 0)),
                    )
                    for m in v.get("mods", ())
                ),
                gold=int(v.get("gold", 0)),
                materials=tuple((mid, int(count)) for mid, count in v.get("materials", {}).items()),
            )
            for v in row.get("variants", ())
        )
        recipes[item_id] = UpgradeRecipe(item_id=item_id, category=row["category"], variants=variants)
    return recipes


def load_content() -> GameContent:
    classes = {
        row["id"]: PlayerClass(
            id=row["id"],
            name=row["name"],
            max_hp=row["max_hp"],
            base_damage=row["base_damage"],
            armor=row["armor"],
            wisdom=row["wisdom"],
            speed=row["speed"],
            crit_chance=row.get("crit_chance", 0),
            starting_weapon_id=row["starting_weapon_id"],
            starting_skill_ids=tuple(row.get("starting_skill_ids", ())),
        )
        for row in _read_json("classes.json")
    }
    for player_class in classes.values():
        if len(player_class.starting_skill_ids) > 4:
            raise ValueError(f"{player_class.id} has more than 4 equipped skills")

    weapons = {
        row["id"]: Weapon(
            id=row["id"],
            name=row["name"],
            damage_bonus=row["damage_bonus"],
            price=row["price"],
            damage_type=row.get("damage_type", "physical"),
            # Tier is derived from damage (single source of truth); any `tier` in
            # JSON is ignored.
            tier=combat.weapon_tier_from_damage(row["damage_bonus"]),
            category=row.get("category", "melee"),
            rarity=row.get("rarity", "common"),
            on_hit=tuple(row.get("on_hit", ())),
        )
        for row in _read_json("weapons.json")
    }

    equipment_slots = {
        row["id"]: EquipmentSlot(
            id=row["id"],
            name=row["name"],
            slot_type=row["slot_type"],
            accepts=row.get("accepts", row["slot_type"]),
            order=row.get("order", 0),
        )
        for row in _read_json("equipment_slots.json")
    }

    gear_items = {
        row["id"]: GearItem(
            id=row["id"],
            name=row["name"],
            slot_type=row["slot_type"],
            tier=row["tier"],
            rarity=row["rarity"],
            level_req=row.get("level_req", max(1, row["tier"] - 2)),
            stat_modifiers={key: int(value) for key, value in row.get("stat_modifiers", {}).items()},
        )
        for row in _read_json("gear.json")
    }

    actions = {
        row["id"]: CombatAction(
            id=row["id"],
            name=row["name"],
            kind=row["kind"],
            hit_chance=row.get("hit_chance", 1.0),
            mana_cost=row.get("mana_cost", 0),
            cooldown_rounds=row.get("cooldown_rounds", 0),
            telegraph=row.get("telegraph", False),
            requires_weapon_category=row.get("requires_weapon_category", ""),
            effects=tuple(
                _effect_from_json(effect)
                for effect in row.get("effects", ())
            ),
        )
        for row in _read_json("actions.json")
    }

    talents = {
        row["id"]: TalentNode(
            id=row["id"],
            class_id=row["class_id"],
            branch=row["branch"],
            order=row["order"],
            name=row["name"],
            node_type=row["node_type"],
            max_rank=row.get("max_rank", 1),
            action_id=row.get("action_id", ""),
            requires=row.get("requires", ""),
            effects=tuple(
                _effect_from_json(effect)
                for effect in row.get("effects", ())
            ),
        )
        for row in _read_json("talents.json")
    }

    tournaments = {
        row["id"]: Tournament(
            id=row["id"],
            name=row["name"],
            place_id=row["place_id"],
            rank=row["rank"],
            description=row["description"],
            opponent_ids=tuple(row["opponent_ids"]),
            reward=TournamentReward(
                gold=row.get("reward", {}).get("gold", 0),
                item_ids=tuple(row.get("reward", {}).get("item_ids", ())),
            ),
            entry_fee=row.get("entry_fee", 0),
            repeatable=row.get("repeatable", False),
        )
        for row in _read_json("tournaments.json")
    }

    items = {
        row["id"]: ConsumableItem(
            id=row["id"],
            name=row["name"],
            kind=row["kind"],
            heal_amount=row.get("heal_amount", 0),
            price=row["price"],
            tier=row.get("tier", 1),
            mana_amount=row.get("mana_amount", 0),
            cures=tuple(row.get("cures", ())),
            teaches=row.get("teaches", ""),
            level_req=row.get("level_req", 1),
            class_req=row.get("class_req", ""),
            weapon_category_req=row.get("weapon_category_req", ""),
        )
        for row in _read_json("items.json")
    }

    enemies = {
        row["id"]: EnemyTemplate(
            id=row["id"],
            name=row["name"],
            level=row["level"],
            max_hp=row["max_hp"],
            damage=row["damage"],
            armor=row["armor"],
            speed=row["speed"],
            traits=tuple(row.get("traits", ())),
            # Resistances are derived from traits (single source of truth); any
            # `resistances` left in JSON is ignored.
            resistances=traits.resistances_from_traits(row.get("traits", ())),
            action_ids=tuple(row.get("action_ids", ("power", "normal", "quick"))),
            xp_reward=row["xp_reward"],
            gold_min=row["gold_min"],
            gold_max=row["gold_max"],
            tags=tuple(row.get("tags", ())),
            mana=row.get("mana", 0),
            ai=tuple(row.get("ai", ())),
            loot_table=tuple(row.get("loot_table", ())),
            unique_table=tuple(row.get("unique_table", ())),
            drop_chance=row.get("drop_chance", 0.0),
            rare_table_access=row.get("rare_table_access", False),
            level_min=row.get("level_min", row["level"]),
            level_max=row.get("level_max", row["level"]),
            boss=row.get("boss", False),
        )
        for row in _read_json("enemies.json")
    }

    rare_loot_table = tuple(_read_json("loot.json").get("rare_table", ()))

    # B67: travel events (validated on parse: outcome chances sum to 1).
    from rpg_game.core.events import parse_events
    travel_event_slot_chance, travel_events = parse_events(_read_json("events.json"))
    upgrade_recipes = _load_upgrade_recipes()

    # B68: alchemy brew recipes.
    from rpg_game.core.alchemy import BrewRecipe
    brew_recipes = {
        row["id"]: BrewRecipe(
            id=row["id"],
            output=row["output"],
            gold=row.get("gold", 0),
            materials=tuple(sorted(row.get("materials", {}).items())),
        )
        for row in _read_json("brews.json")
    }

    # B63: placed world chests (empty dict when the file is absent).
    chests = {
        row["id"]: ChestDef(
            id=row["id"],
            tile=tuple(row["tile"]),
            theme=row.get("theme", "cainos"),
            gold_min=row.get("gold_min", 0),
            gold_max=row.get("gold_max", 0),
            tier_cap=row.get("tier_cap", 3),
            loot_table=tuple(row.get("loot_table", ())),
        )
        for row in _read_json("chests.json")
    }

    # B48: drawn spawn areas + per-region fallbacks (from the zone map config).
    from rpg_game.core.spawns import SpawnArea
    try:
        core_zone = _read_json("maps/core_zone.json")
    except FileNotFoundError:
        core_zone = {}
    spawn_areas = tuple(
        SpawnArea(
            id=row["id"],
            rect=tuple(row["rect"]),
            enemies=tuple((e["id"], int(e["weight"])) for e in row["enemies"]),
            color=tuple(row.get("color", (200, 200, 200))),
            level_min=int(row.get("level_min", 0)),
            level_max=int(row.get("level_max", 0)),
        )
        for row in core_zone.get("spawn_areas", ())
    )
    spawn_fallbacks = {
        place_id: tuple((e["id"], int(e["weight"])) for e in pool)
        for place_id, pool in core_zone.get("spawn_fallbacks", {}).items()
    }

    # B65: zone bosses and their lairs.
    bosses = {
        row["id"]: BossDef(
            id=row["id"],
            enemy_id=row["enemy_id"],
            zone=row.get("zone", ""),
            lair_tile=tuple(row["lair_tile"]),
            requires_defeated=tuple(row.get("requires_defeated", ())),
            reward_gold=row.get("reward_gold", 0),
            reward_item_ids=tuple(row.get("reward_item_ids", ())),
            intro=row.get("intro", ""),
            final=row.get("final", False),
        )
        for row in _read_json("bosses.json")
    }

    world = _read_json("world.json")
    # core_zone is the SINGLE SOURCE for town services: it drives which cluster
    # (and thus which trade building) a town renders, so has_store must derive from
    # it, not the stale hand-set world.json flag. A town has a store iff it renders
    # a trade building — every capital/city/town does, and a village only when it
    # has a shop_category.
    store_towns = _core_zone_store_towns()
    places = {}
    for row in world["places"]:
        position = row["position"]
        connections = tuple(
            Connection(
                to=connection["to"],
                travel=connection["travel"],
                distance_px=connection["distance_px"],
                distance_km_approx=connection["distance_km_approx"],
            )
            for connection in row["connections"]
        )
        places[row["id"]] = Place(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            description=row["description"],
            has_store=store_towns.get(row["id"], row["has_store"]),
            mana_site=row["mana_site"],
            port=row["port"],
            position=Position(x=position["x"], y=position["y"]),
            danger_tier=row["danger_tier"],
            encounters=tuple(row["encounters"]),
            respawn=row["respawn"],
            locked=row["locked"],
            connections=connections,
            store_inventory=tuple(row.get("store_inventory", DEFAULT_STORE_INVENTORY)),
            respawn_place_id=row["id"] if row["respawn"] else world["meta"]["start_place_id"],
            level_min=row.get("level_min", 0),
            level_max=row.get("level_max", 0),
            rare_encounter=row.get("rare_encounter", ""),
            rare_chance=row.get("rare_chance", 0.0),
        )

    _validate_gear(equipment_slots, gear_items)
    _validate_tournaments(tournaments, enemies, places, weapons, items)
    _validate_content_refs(classes, weapons, gear_items, items, actions, talents,
                           enemies, places, rare_loot_table, upgrade_recipes)
    _validate_chests(chests, weapons, gear_items, items)
    _validate_brews(brew_recipes, items)
    _validate_bosses(bosses, enemies, places, weapons, gear_items, items, chests)
    _validate_spawns(spawn_areas, spawn_fallbacks, enemies, places)

    return GameContent(
        start_place_id=world["meta"]["start_place_id"],
        classes=classes,
        weapons=weapons,
        equipment_slots=equipment_slots,
        gear_items=gear_items,
        items=items,
        actions=actions,
        talents=talents,
        tournaments=tournaments,
        enemies=enemies,
        places=places,
        rare_loot_table=rare_loot_table,
        travel_event_slot_chance=travel_event_slot_chance,
        travel_events=travel_events,
        upgrade_recipes=upgrade_recipes,
        chests=chests,
        brew_recipes=brew_recipes,
        bosses=bosses,
        spawn_areas=spawn_areas,
        spawn_fallbacks=spawn_fallbacks,
    )


def _validate_gear(equipment_slots, gear_items) -> None:
    accepted_types = {slot.accepts for slot in equipment_slots.values() if slot.slot_type != "weapon"}
    for gear in gear_items.values():
        if gear.slot_type not in accepted_types:
            raise ValueError(f"{gear.id} uses unknown slot_type {gear.slot_type}")
        invalid_stats = set(gear.stat_modifiers) - ALLOWED_GEAR_STATS
        if invalid_stats:
            raise ValueError(f"{gear.id} has unsupported stats: {', '.join(sorted(invalid_stats))}")


def _validate_tournaments(tournaments, enemies, places, weapons, items) -> None:
    for tournament in tournaments.values():
        if tournament.place_id not in places:
            raise ValueError(f"{tournament.id} references unknown place {tournament.place_id}")
        for enemy_id in tournament.opponent_ids:
            if enemy_id not in enemies:
                raise ValueError(f"{tournament.id} references unknown opponent {enemy_id}")
        for item_id in tournament.reward.item_ids:
            if item_id not in weapons and item_id not in items:
                raise ValueError(f"{tournament.id} references unknown reward {item_id}")


def _validate_brews(brew_recipes, items) -> None:
    """B68: brew outputs must be real consumables; materials real items."""
    for recipe in brew_recipes.values():
        output = items.get(recipe.output)
        if output is None or output.kind != "consumable":
            raise ValueError(f"brew {recipe.id} outputs unknown/non-consumable {recipe.output}")
        for material_id, count in recipe.materials:
            if material_id not in items:
                raise ValueError(f"brew {recipe.id} references unknown material {material_id}")
            if count < 1:
                raise ValueError(f"brew {recipe.id} has a non-positive count for {material_id}")


def _validate_chests(chests, weapons, gear_items, items) -> None:
    """B63: every chest loot entry must resolve (same fail-fast policy as B54)."""
    for chest in chests.values():
        if not chest.loot_table:
            raise ValueError(f"chest {chest.id} has an empty loot table")
        for entry in chest.loot_table:
            item_id = entry.get("item_id")
            if item_id not in weapons and item_id not in gear_items and item_id not in items:
                raise ValueError(f"chest {chest.id} references unknown item {item_id}")


def _validate_bosses(bosses, enemies, places, weapons, gear_items, items, chests) -> None:
    """B65: boss defs must resolve, boss enemies must never sit in a wild pool
    (a boss only spawns via its lair), and lair tiles must not collide."""
    boss_enemy_ids = {enemy.id for enemy in enemies.values() if enemy.boss}
    for boss in bosses.values():
        enemy = enemies.get(boss.enemy_id)
        if enemy is None:
            raise ValueError(f"boss {boss.id} references unknown enemy {boss.enemy_id}")
        if not enemy.boss:
            raise ValueError(f"boss {boss.id} enemy {boss.enemy_id} is not boss-flagged")
        for required_id in boss.requires_defeated:
            if required_id not in bosses:
                raise ValueError(f"boss {boss.id} requires unknown boss {required_id}")
        for item_id in boss.reward_item_ids:
            if item_id not in weapons and item_id not in gear_items and item_id not in items:
                raise ValueError(f"boss {boss.id} rewards unknown item {item_id}")
    placed_enemy_ids = {boss.enemy_id for boss in bosses.values()}
    for orphan in sorted(boss_enemy_ids - placed_enemy_ids):
        raise ValueError(f"boss enemy {orphan} has no lair in bosses.json")
    for place in places.values():
        for enemy_id in place.encounters:
            if enemy_id in boss_enemy_ids:
                raise ValueError(f"boss enemy {enemy_id} must not be in {place.id}'s wild pool")
    lair_tiles = [boss.lair_tile for boss in bosses.values()]
    if len(set(lair_tiles)) != len(lair_tiles):
        raise ValueError("two bosses share a lair tile")
    chest_tiles = {chest.tile for chest in chests.values()}
    for boss in bosses.values():
        if boss.lair_tile in chest_tiles:
            raise ValueError(f"boss {boss.id} lair collides with a chest tile")


def _validate_spawns(spawn_areas, spawn_fallbacks, enemies, places) -> None:
    """B48: every spawn-area/fallback reference must resolve; weights positive;
    rects sane; bosses may never enter a spawn pool (they only live in lairs)."""
    seen_ids = set()
    for area in spawn_areas:
        if area.id in seen_ids:
            raise ValueError(f"duplicate spawn area id {area.id}")
        seen_ids.add(area.id)
        x0, y0, x1, y1 = area.rect
        if not (0 <= x0 <= x1 and 0 <= y0 <= y1):
            raise ValueError(f"spawn area {area.id} has a malformed rect {area.rect}")
        if not area.enemies:
            raise ValueError(f"spawn area {area.id} has an empty pool")
        for enemy_id, weight in area.enemies:
            enemy = enemies.get(enemy_id)
            if enemy is None:
                raise ValueError(f"spawn area {area.id} references unknown enemy {enemy_id}")
            if enemy.boss:
                raise ValueError(f"boss enemy {enemy_id} must not be in spawn area {area.id}")
            if weight <= 0:
                raise ValueError(f"spawn area {area.id} has a non-positive weight for {enemy_id}")
    for place_id, pool in spawn_fallbacks.items():
        if place_id not in places:
            raise ValueError(f"spawn fallback references unknown place {place_id}")
        if not pool:
            raise ValueError(f"spawn fallback for {place_id} is empty")
        for enemy_id, weight in pool:
            enemy = enemies.get(enemy_id)
            if enemy is None:
                raise ValueError(f"spawn fallback {place_id} references unknown enemy {enemy_id}")
            if enemy.boss:
                raise ValueError(f"boss enemy {enemy_id} must not be in spawn fallback {place_id}")
            if weight <= 0:
                raise ValueError(f"spawn fallback {place_id} has a non-positive weight for {enemy_id}")


def _validate_content_refs(classes, weapons, gear_items, items, actions, talents,
                           enemies, places, rare_loot_table, upgrade_recipes) -> None:
    """B54: every id-reference in content must resolve at load — a typo fails HERE
    with a named error instead of silently dropping a skill or crashing mid-fight.
    (Runtime guards in combat.py stay as harmless defence; they can no longer hide
    bad data.)"""
    def lootable(item_id) -> bool:
        return item_id in weapons or item_id in gear_items or item_id in items

    for cls in classes.values():
        if cls.starting_weapon_id not in weapons:
            raise ValueError(f"class {cls.id} references unknown starting weapon {cls.starting_weapon_id}")
        for skill_id in cls.starting_skill_ids:
            if skill_id not in actions:
                raise ValueError(f"class {cls.id} references unknown starting skill {skill_id}")

    for enemy in enemies.values():
        for action_id in enemy.action_ids:
            if action_id not in actions:
                raise ValueError(f"enemy {enemy.id} references unknown action {action_id}")
        for rule in enemy.ai:
            rule_action = str(rule.get("action", ""))
            if rule_action and rule_action not in actions:
                raise ValueError(f"enemy {enemy.id} ai references unknown action {rule_action}")
        for table_name, table in (("loot_table", enemy.loot_table), ("unique_table", enemy.unique_table)):
            for entry in table:
                if not lootable(entry.get("item_id")):
                    raise ValueError(f"enemy {enemy.id} {table_name} references unknown item {entry.get('item_id')}")

    for entry in rare_loot_table:
        if not lootable(entry.get("item_id")):
            raise ValueError(f"rare_table references unknown item {entry.get('item_id')}")

    for item in items.values():
        if item.kind == "tome" and item.teaches not in actions:
            raise ValueError(f"tome {item.id} teaches unknown action {item.teaches}")
        if item.class_req and item.class_req not in classes:
            raise ValueError(f"tome {item.id} requires unknown class {item.class_req}")

    for recipe in upgrade_recipes.values():
        if recipe.item_id not in weapons and recipe.item_id not in gear_items:
            raise ValueError(f"upgrade recipe targets unknown item {recipe.item_id}")
        for variant in recipe.variants:
            for material_id, _count in variant.materials:
                if material_id not in items:
                    raise ValueError(
                        f"upgrade {recipe.item_id}/{variant.id} references unknown material {material_id}")

    for talent in talents.values():
        if talent.class_id not in classes:
            raise ValueError(f"talent {talent.id} references unknown class {talent.class_id}")
        if talent.node_type == "active" and talent.action_id and talent.action_id not in actions:
            raise ValueError(f"talent {talent.id} references unknown action {talent.action_id}")

    for place in places.values():
        for enemy_id in place.encounters:
            if enemy_id not in enemies:
                raise ValueError(f"place {place.id} references unknown encounter {enemy_id}")
        if place.rare_encounter and place.rare_encounter not in enemies:
            raise ValueError(f"place {place.id} references unknown rare encounter {place.rare_encounter}")
        for item_id in place.store_inventory:
            if not lootable(item_id):
                raise ValueError(f"place {place.id} store references unknown item {item_id}")
        for connection in place.connections:
            if connection.to not in places:
                raise ValueError(f"place {place.id} connects to unknown place {connection.to}")


def _effect_from_json(effect: dict[str, Any]) -> EffectSpec:
    return EffectSpec(
        type=effect["type"],
        magnitude=effect.get("magnitude", 0),
        duration=effect.get("duration", 0),
        tick_timing=effect.get("tick_timing", "instant"),
        multiplier=effect.get("multiplier", 1.0),
        multiplier_min=effect.get("multiplier_min", 0.0),
        multiplier_max=effect.get("multiplier_max", 0.0),
        scale=effect.get("scale", "flat"),
        damage_type=effect.get("damage_type", "physical"),
        status_type=effect.get("status_type", ""),
        target=effect.get("target", "enemy"),
        stat=effect.get("stat", ""),
        ratio=effect.get("ratio", 0.0),
        modifies_status_type=effect.get("modifies_status_type", ""),
        mod_magnitude=effect.get("mod_magnitude", 0),
        mod_duration=effect.get("mod_duration", 0),
        tag=effect.get("tag", ""),
        crit_bonus=effect.get("crit_bonus", 0),
        conditional=effect.get("conditional", {}),
        trigger=effect.get("trigger", "on_hit"),
        armor_pen=effect.get("armor_pen", 0),
        hits=effect.get("hits", 1),
        max_stacks=effect.get("max_stacks", 1),
        on_event=effect.get("on_event", ""),
    )
