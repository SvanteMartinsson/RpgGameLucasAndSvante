from __future__ import annotations

from rpg_game.core.game import GameEngine


def main() -> None:
    engine = GameEngine()
    print("Welcome to Svantrenish RPG!")
    name = input("What is your name? ").strip() or "Hero"
    class_id = prompt_class(engine)
    engine.start_new_game(name, class_id)
    print(f"Welcome, {engine.player.name} the {engine.content.classes[class_id].name}.")

    while True:
        place = engine.current_place()
        print()
        print(f"== {place.name} ==")
        print(place.description)
        print(f"HP: {engine.player.hp}/{engine.player.max_hp} | Gold: {engine.player.gold}")

        menu = [
            ("stats", "Show stats"),
            ("inventory", "Show inventory"),
            ("travel", "Travel"),
            ("explore", "Explore"),
            ("use", "Use item"),
            ("talents", "Talents"),
            ("skills", "Skills"),
        ]
        if place.has_store:
            menu.append(("store", "Store"))
        options = [(str(index), value, label) for index, (value, label) in enumerate(menu, start=1)]
        options.append(("q", "quit", "Quit"))

        action = prompt_menu("What do you want to do?", options)
        if action == "stats":
            show_stats(engine)
        elif action == "inventory":
            show_inventory(engine)
        elif action == "travel":
            handle_travel(engine)
        elif action == "explore":
            handle_explore(engine)
        elif action == "use":
            handle_use_item(engine)
        elif action == "talents":
            handle_talents(engine)
        elif action == "skills":
            handle_skills(engine)
        elif action == "store":
            handle_store(engine)
        elif action == "quit":
            print("Goodbye.")
            return


def prompt_class(engine: GameEngine) -> str:
    options = []
    for index, player_class in enumerate(engine.content.classes.values(), start=1):
        options.append((str(index), player_class.id, player_class.name))
    return prompt_menu("Choose a class:", options)


def prompt_menu(prompt: str, options: list[tuple[str, str, str]], allow_label: bool = True) -> str:
    while True:
        print()
        print(prompt)
        for key, _value, label in options:
            print(f"{key}: {label}")
        answer = input("> ").strip().lower()
        for key, value, label in options:
            accepted = {key.lower(), value.lower()}
            if allow_label:
                accepted.add(label.lower())
            if answer in accepted:
                return value
        print("Invalid input. Please choose one of the listed options.")


def show_stats(engine: GameEngine) -> None:
    player = engine.player
    weapon = engine.content.weapons[player.equipped_weapon_id]
    total_damage = player.base_damage + weapon.damage_bonus
    print()
    print("Stats")
    print(f"Name: {player.name}")
    print(f"Class: {engine.content.classes[player.player_class].name}")
    print(f"Level: {player.level}")
    print(f"XP: {player.xp}/{player.xp_required}")
    print(f"HP: {player.hp}/{player.max_hp}")
    print(f"Mana: {player.mana}/{player.max_mana}")
    print(f"Base damage: {player.base_damage}")
    print(f"Weapon: {weapon.name} (+{weapon.damage_bonus})")
    print(f"Total damage: {total_damage}")
    print(f"Armor: {player.armor}")
    print(f"Speed: {player.speed}")
    print(f"Talent points: {player.talent_points}")
    print(f"Gold: {player.gold}")


def show_inventory(engine: GameEngine) -> None:
    player = engine.player
    weapon = engine.content.weapons[player.equipped_weapon_id]
    print()
    print("Inventory")
    print(f"Equipped weapon: {weapon.name} (+{weapon.damage_bonus} damage)")
    print(f"Gold: {player.gold}")
    if not player.inventory.consumables:
        print("Consumables: none")
        return

    print("Consumables:")
    for item_id, count in sorted(player.inventory.consumables.items()):
        item = engine.content.items[item_id]
        print(f"- {item.name}: {count}")


def handle_travel(engine: GameEngine) -> None:
    connections = engine.available_connections()
    if not connections:
        print("There is nowhere to travel from here.")
        return

    options = []
    print()
    print("Travel")
    for index, connection in enumerate(connections, start=1):
        destination = engine.content.places[connection.to]
        print(
            f"{index}: {destination.id} - {destination.name} "
            f"({connection.travel}, {connection.distance_km_approx} km)"
        )
        options.append((str(index), destination.id, destination.id))
    options.append(("b", "back", "Back"))
    destination_id = prompt_menu("Where do you want to travel? Choose by number or id.", options, allow_label=False)
    if destination_id == "back":
        return
    print(engine.travel(destination_id))


def handle_explore(engine: GameEngine) -> None:
    enemy = engine.create_encounter()
    if enemy is None:
        print("This place is safe. There are no enemies here.")
        return

    print(f"You encounter a {enemy.name}.")
    while enemy.is_alive and engine.player.is_alive:
        print()
        print(f"Your HP: {engine.player.hp}/{engine.player.max_hp}")
        print(f"{enemy.name} HP: {enemy.hp}/{enemy.max_hp}")
        attack_id = prompt_combat_action(engine)
        result = engine.run_combat_turn(enemy, attack_id)
        for event in result.events:
            print(event)
        if result.outcome == "victory":
            resolve_pending_stat_choices(engine)
            return
        if result.outcome == "defeat":
            resolve_pending_stat_choices(engine)
            return


def prompt_combat_action(engine: GameEngine) -> str:
    options = []
    for index, action in enumerate(engine.available_actions(), start=1):
        label = action.name
        if action.mana_cost:
            label += f" ({action.mana_cost} mana)"
        if action.cooldown_rounds:
            label += f" (cooldown {action.cooldown_rounds})"
        options.append((str(index), action.id, label))
    return prompt_menu("Choose action:", options)


# --- Talents -------------------------------------------------------------


def describe_effect(effect) -> str:
    kind = effect.type
    if kind in {"damage", "instant_damage"}:
        base = {"power": "Power", "basic_attack": "weapon", "flat": "flat"}.get(effect.scale, effect.scale)
        hits = f" x{effect.hits} hits" if effect.hits > 1 else ""
        return f"deal {effect.multiplier}x {base} {effect.damage_type} damage{hits}"
    if kind in {"instant_heal", "heal"}:
        return f"heal {effect.magnitude} HP"
    if kind == "drain":
        return f"drain {effect.multiplier}x Power {effect.damage_type}, heal {int(effect.ratio * 100)}% of it"
    if kind == "apply_status":
        status = effect.status_type or effect.damage_type
        where = "self" if effect.target == "self" else "enemy"
        if status in {"buff", "debuff"}:
            sign = "+" if effect.magnitude >= 0 else ""
            return f"{status} {sign}{effect.magnitude} {effect.stat} for {effect.duration} rounds ({where})"
        return f"apply {status} {effect.magnitude} for {effect.duration} rounds ({where})"
    if kind == "stat_bonus":
        return f"+{effect.magnitude} {effect.stat}"
    if kind == "conditional_damage_mod":
        return "conditional damage bonus"
    if kind == "applied_status_mod":
        return f"improve {effect.modifies_status_type} effects"
    if kind == "immunity":
        return f"immunity to {effect.tag}"
    return kind


def skill_cost_text(action) -> str:
    bits = []
    if action.mana_cost:
        bits.append(f"{action.mana_cost} mana")
    if action.cooldown_rounds:
        bits.append(f"cooldown {action.cooldown_rounds}")
    return ", ".join(bits) if bits else "free"


def describe_talent(engine: GameEngine, node) -> str:
    if node.node_type == "active" and node.action_id in engine.content.actions:
        action = engine.content.actions[node.action_id]
        effects = "; ".join(describe_effect(effect) for effect in action.effects) or "active skill"
        return f"Active: {effects} ({skill_cost_text(action)})"
    if node.effects:
        return "Passive: " + "; ".join(describe_effect(effect) for effect in node.effects)
    return node.node_type


def talent_prereq_text(engine: GameEngine, node) -> str:
    if node.order <= 1:
        return " | no prerequisite"
    for candidate in engine.content.talents.values():
        if (
            candidate.class_id == node.class_id
            and candidate.branch == node.branch
            and candidate.order == node.order - 1
        ):
            return f" | requires {candidate.name}"
    return ""


def handle_talents(engine: GameEngine) -> None:
    while True:
        player = engine.player
        print()
        print(f"Talents (points: {player.talent_points})")
        if player.talent_points <= 0:
            print("You have no talent points to spend.")
            return

        nodes = engine.available_talents()
        if not nodes:
            print("No talents are available to learn right now.")
            return

        options = []
        for index, node in enumerate(nodes, start=1):
            label = f"{node.name} [{node.branch} t{node.order}] - {describe_talent(engine, node)}{talent_prereq_text(engine, node)}"
            options.append((str(index), node.id, label))
        options.append(("b", "back", "Back"))

        choice = prompt_menu("Spend a talent point on which node?", options, allow_label=False)
        if choice == "back":
            return
        try:
            print(engine.allocate_talent(choice))
        except ValueError as error:
            print(f"Cannot learn that talent: {error}")


# --- Skills (equip max 4) -----------------------------------------------


def handle_skills(engine: GameEngine) -> None:
    while True:
        player = engine.player
        equipped = set(player.equipped_skill_ids)
        skills = engine.equippable_skills()
        print()
        print(f"Skills (equipped {len(equipped)}/4)")
        if not skills:
            print("You have not unlocked any active skills yet. Learn active talents first.")
            return

        options = []
        for index, skill in enumerate(skills, start=1):
            mark = "[x]" if skill.id in equipped else "[ ]"
            label = f"{mark} {skill.name} - {skill_cost_text(skill)}"
            options.append((str(index), skill.id, label))
        options.append(("b", "back", "Back"))

        choice = prompt_menu("Toggle which skill? (max 4 equipped)", options, allow_label=False)
        if choice == "back":
            return
        try:
            if choice in equipped:
                print(engine.unequip_skill(choice))
            else:
                print(engine.equip_skill(choice))
        except ValueError as error:
            print(f"Cannot change that skill: {error}")


def resolve_pending_stat_choices(engine: GameEngine) -> None:
    leveled = engine.player.pending_stat_choices > 0
    while engine.player.pending_stat_choices > 0:
        print()
        print(f"Level up! You are now level {engine.player.level}.")
        choice = prompt_menu(
            "Choose stat bonus:",
            [
                ("1", "damage", "+5 base damage"),
                ("2", "hp", "+10 max HP"),
            ],
        )
        print(engine.apply_stat_choice(choice))

    if leveled and engine.player.talent_points > 0:
        print(f"You have {engine.player.talent_points} talent point(s) to spend.")
        handle_talents(engine)


def handle_store(engine: GameEngine) -> None:
    entries = engine.store_entries()
    if not entries:
        print("There is no store here.")
        return

    options = []
    print()
    print("Store")
    print(f"Gold: {engine.player.gold}")
    for index, entry in enumerate(entries, start=1):
        print(f"{index}: {entry.name} ({entry.kind}) - {entry.price} gold, {entry.description}")
        options.append((str(index), entry.id, entry.name))
    options.append(("b", "back", "Back"))

    item_id = prompt_menu("What do you want to buy?", options)
    if item_id == "back":
        return
    result = engine.buy_item(item_id)
    print(result.message)


def handle_use_item(engine: GameEngine) -> None:
    consumables = engine.player.inventory.consumables
    if not consumables:
        print("You have no consumables.")
        return

    options = []
    print()
    print("Use item")
    for index, (item_id, count) in enumerate(sorted(consumables.items()), start=1):
        item = engine.content.items[item_id]
        print(f"{index}: {item.name} x{count} - heals {item.heal_amount} HP")
        options.append((str(index), item.id, item.name))
    options.append(("b", "back", "Back"))

    item_id = prompt_menu("Which item do you want to use?", options)
    if item_id == "back":
        return
    result = engine.use_consumable(item_id)
    print(result.message)
