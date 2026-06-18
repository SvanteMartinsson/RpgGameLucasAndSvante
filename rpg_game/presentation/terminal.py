from __future__ import annotations

from rpg_game.core import combat
from rpg_game.core.game import GameEngine


SAVE_PATH = "savegame.json"


def main() -> None:
    engine = GameEngine()
    print("Welcome to Svantrenish RPG!")

    while True:
        choice = prompt_menu(
            "Main menu:",
            [
                ("1", "new", "New game"),
                ("2", "load", "Load game"),
                ("q", "quit", "Quit"),
            ],
        )
        if choice == "new":
            name = input("What is your name? ").strip() or "Hero"
            class_id = prompt_class(engine)
            engine.start_new_game(name, class_id)
            print(f"Welcome, {engine.player.name} the {engine.content.classes[class_id].name}.")
            run_game_loop(engine)
            return
        if choice == "load":
            result = engine.load(SAVE_PATH)
            print(result.message)
            if result.success:
                run_game_loop(engine)
                return
            continue  # missing/corrupt file: back to the start menu
        if choice == "quit":
            print("Goodbye.")
            return


def run_game_loop(engine: GameEngine) -> None:
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
            ("equip", "Equip weapon"),
            ("talents", "Talents"),
            ("skills", "Skills"),
            ("save", "Save game"),
        ]
        if engine.available_tournaments():
            menu.append(("tournaments", "Tournaments"))
        if place.has_store:
            menu.append(("rest", "Rest"))
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
        elif action == "equip":
            handle_equip_weapon(engine)
        elif action == "talents":
            handle_talents(engine)
        elif action == "skills":
            handle_skills(engine)
        elif action == "tournaments":
            handle_tournaments(engine)
        elif action == "save":
            print(engine.save(SAVE_PATH).message)
        elif action == "rest":
            print(engine.rest().message)
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


def prompt_quantity(prompt: str, maximum: int) -> int:
    while True:
        answer = input(f"{prompt} (1-{maximum}, default 1): ").strip()
        if answer == "":
            return 1
        if answer.isdigit() and 1 <= int(answer) <= maximum:
            return int(answer)
        print(f"Enter a number between 1 and {maximum}.")


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
    print(f"Weapon: {weapon.name} (+{weapon.damage_bonus}, tier {weapon.tier})")
    print(f"Total damage: {total_damage}")
    print(f"Armor: {player.armor}")
    print(f"Speed: {player.speed}")
    print(f"Crit chance: {player.crit_chance}%")
    print(f"Talent points: {player.talent_points}")
    print(f"Gold: {player.gold}")


def show_inventory(engine: GameEngine) -> None:
    player = engine.player
    weapon = engine.content.weapons[player.equipped_weapon_id]
    print()
    print("Inventory")
    print(f"Equipped weapon: {weapon.name} (+{weapon.damage_bonus} damage)")
    print("Owned weapons:")
    for owned in engine.owned_weapons():
        equipped = " (equipped)" if owned.id == player.equipped_weapon_id else ""
        print(
            f"- {owned.name} (+{owned.damage_bonus} {owned.damage_type}, tier {owned.tier})"
            f"{weapon_level_requirement_text(engine, owned)}{equipped}"
        )
    print(f"Gold: {player.gold}")
    if not player.inventory.consumables:
        print("Items: none")
        return

    print("Items:")
    for item_id, count in sorted(player.inventory.consumables.items()):
        item = engine.content.items[item_id]
        print(f"- {item.name} ({item.kind}): {count}")


def handle_travel(engine: GameEngine) -> None:
    connections = engine.available_connections()
    if not connections:
        print("There is nowhere to travel from here.")
        return

    options = []
    for index, connection in enumerate(connections, start=1):
        destination = engine.content.places[connection.to]
        label = f"{destination.name} ({connection.travel}, {connection.distance_km_approx} km)"
        options.append((str(index), destination.id, label))
    options.append(("b", "back", "Back"))

    destination_id = prompt_menu("Where do you want to travel?", options, allow_label=False)
    if destination_id == "back":
        return
    print(engine.travel(destination_id))


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
        if status == "reflect":
            amount = f"{effect.multiplier}x Power" if effect.scale == "power" else str(effect.magnitude)
            return f"reflect {amount} {effect.damage_type} for {effect.duration} rounds ({where})"
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
        print_talent_tree(engine)

        if player.talent_points <= 0:
            print("You have no talent points to spend.")
            return
        purchasable = engine.available_talents()
        if not purchasable:
            print("No talents are available to learn right now.")
            return

        options = [(str(index), node.id, node.name) for index, node in enumerate(purchasable, start=1)]
        options.append(("b", "back", "Back"))

        choice = prompt_menu("Spend a talent point on which node?", options, allow_label=False)
        if choice == "back":
            return
        try:
            print(engine.allocate_talent(choice))
        except ValueError as error:
            print(f"Cannot learn that talent: {error}")


def print_talent_tree(engine: GameEngine) -> None:
    player = engine.player
    class_nodes = sorted(
        (node for node in engine.content.talents.values() if node.class_id == player.player_class),
        key=lambda node: (node.branch, node.order),
    )
    available_ids = {node.id for node in engine.available_talents()}

    current_branch = None
    for node in class_nodes:
        if node.branch != current_branch:
            current_branch = node.branch
            print(f"-- {node.branch} --")
        if node.id in player.learned_talent_ids:
            status = "[LEARNED] "
        elif node.id in available_ids:
            status = "[CAN LEARN]"
        else:
            status = "[LOCKED]  "
        print(
            f"  {status} {node.name} [{node.branch} t{node.order}] - "
            f"{describe_talent(engine, node)}{talent_prereq_text(engine, node)}"
        )


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
            label = f"{mark} {skill.name} - {skill_cost_text(skill)}{skill_requirement_text(engine, skill)}"
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


# --- Combat --------------------------------------------------------------


def format_statuses(actor) -> list[str]:
    labels = []
    for status in actor.active_statuses:
        name = status.tag or status.type
        if status.stacks > 1:
            name = f"{name} x{status.stacks}"
        labels.append(name)
    return labels


def status_suffix(engine: GameEngine, actor, charging_action_id: str = "") -> str:
    labels = format_statuses(actor)
    if charging_action_id:
        action = engine.content.actions.get(charging_action_id)
        labels.append(f"CHARGING {action.name if action else charging_action_id}!")
    return f" | {', '.join(labels)}" if labels else ""


def print_combat_status(engine: GameEngine, enemy) -> None:
    player = engine.player
    print()
    print(
        f"You: HP {player.hp}/{player.max_hp} | Mana {player.mana}/{player.max_mana}"
        f"{status_suffix(engine, player)}"
    )
    for line in enemy_status_lines(engine, enemy):
        print(line)


def enemy_status_lines(engine: GameEngine, enemy) -> list[str]:
    lines = [
        f"{enemy.name}: HP {enemy.hp}/{enemy.max_hp}"
        f"{status_suffix(engine, enemy, enemy.charging_action_id)}"
    ]
    if enemy.identified:
        skill_names = [
            engine.content.actions[action_id].name
            for action_id in enemy.action_ids
            if action_id in engine.content.actions
        ]
        tags = ", ".join(sorted(enemy.tags)) if enemy.tags else "none"
        lines.append(f"Level {enemy.level} | Power {enemy.damage} | Armor {enemy.armor} | Speed {enemy.speed}")
        lines.append(f"Tags: {tags}")
        lines.append(f"Skills: {', '.join(skill_names) if skill_names else 'none'}")
    return lines


def print_enemy_reveal(reveal) -> None:
    print("Identify")
    print(f"{reveal.name} | Level {reveal.level}")
    print(f"Power {reveal.power} | Armor {reveal.armor} | Speed {reveal.speed}")
    resistances = ", ".join(f"{key} {value:g}x" for key, value in sorted(reveal.resistances.items()))
    print(f"Resistances: {resistances if resistances else 'none'}")
    print(f"Tags: {', '.join(reveal.tags) if reveal.tags else 'none'}")
    print(f"Skills: {', '.join(reveal.skills) if reveal.skills else 'none'}")


def handle_explore(engine: GameEngine) -> None:
    enemy = engine.create_encounter()
    if enemy is None:
        print("This place is safe. There are no enemies here.")
        return

    print(f"You encounter a {enemy.name}.")
    while enemy.is_alive and engine.player.is_alive:
        print_combat_status(engine, enemy)
        kind, payload = choose_combat_command(engine, enemy)
        if kind == "flee":
            result = engine.attempt_flee(enemy)
        else:
            result = engine.run_combat_turn(enemy, payload)
        for event in result.events:
            print(event)
        if result.enemy_reveal is not None:
            print_enemy_reveal(result.enemy_reveal)
        if result.outcome == "fled":
            return
        if result.outcome in {"victory", "defeat"}:
            resolve_pending_stat_choices(engine)
            return


def handle_tournaments(engine: GameEngine) -> None:
    available = engine.available_tournaments()
    if not available:
        print("There are no tournaments here.")
        return

    options = []
    for index, tournament in enumerate(available, start=1):
        completed = " [CLEARED]" if tournament.id in engine.player.completed_tournament_ids else ""
        reward = tournament_reward_text(engine, tournament)
        options.append(
            (
                str(index),
                tournament.id,
                f"{tournament.name} ({tournament.rank}, {len(tournament.opponent_ids)} fights) - {reward}{completed}",
            )
        )
    options.append(("b", "back", "Back"))

    choice = prompt_menu("Enter which tournament?", options, allow_label=False)
    if choice == "back":
        return
    start = engine.start_tournament(choice)
    print(start.message)
    if not start.success or start.tournament is None:
        return
    run_tournament(engine, start.tournament)


def tournament_reward_text(engine: GameEngine, tournament) -> str:
    reward_bits = []
    if tournament.reward.gold:
        reward_bits.append(f"{tournament.reward.gold} gold")
    for item_id in tournament.reward.item_ids:
        if item_id in engine.content.weapons:
            reward_bits.append(engine.content.weapons[item_id].name)
        elif item_id in engine.content.items:
            reward_bits.append(engine.content.items[item_id].name)
    return "reward: " + (", ".join(reward_bits) if reward_bits else "none")


def run_tournament(engine: GameEngine, tournament) -> None:
    print(tournament.description)
    for index, _enemy_id in enumerate(tournament.opponent_ids):
        enemy = engine.create_tournament_opponent(tournament, index)
        print()
        print(f"Round {index + 1}/{len(tournament.opponent_ids)}: {enemy.name}")
        while enemy.is_alive and engine.player.is_alive:
            print_combat_status(engine, enemy)
            payload = choose_tournament_combat_command(engine, enemy)
            result = engine.run_combat_turn(enemy, payload)
            for event in result.events:
                print(event)
            if result.enemy_reveal is not None:
                print_enemy_reveal(result.enemy_reveal)
            if result.outcome == "blocked":
                continue
            if result.outcome == "defeat":
                print(f"You were eliminated from {tournament.name}.")
                resolve_pending_stat_choices(engine)
                return
            if result.outcome == "victory":
                break

    reward = engine.complete_tournament(tournament)
    print(reward.message)
    resolve_pending_stat_choices(engine)


def choose_tournament_combat_command(engine: GameEngine, enemy) -> str:
    while True:
        command = prompt_menu(
            "Choose action:",
            [
                ("1", "attack", "Attack (rolls style)"),
                ("2", "skill", "Skill"),
                ("3", "item", "Item"),
                ("4", "swap", "Swap weapon"),
                ("5", "identify", "Identify"),
            ],
        )
        if command == "attack":
            return "attack"
        if command == "skill":
            action_id = choose_skill(engine)
            if action_id:
                return action_id
        if command == "item":
            item_id = choose_combat_item(engine)
            if item_id:
                return f"item:{item_id}"
        if command == "swap":
            weapon_id = choose_swap_weapon(engine)
            if weapon_id:
                return f"swap:{weapon_id}"
        if command == "identify":
            return "identify"


def choose_combat_command(engine: GameEngine, enemy) -> tuple[str, str]:
    while True:
        command = prompt_menu(
            "Choose action:",
            [
                ("1", "attack", "Attack (rolls style)"),
                ("2", "skill", "Skill"),
                ("3", "item", "Item"),
                ("4", "swap", "Swap weapon"),
                ("5", "identify", "Identify"),
                ("6", "flee", "Flee"),
            ],
        )
        if command == "attack":
            return ("turn", "attack")
        elif command == "skill":
            action_id = choose_skill(engine)
            if action_id:
                return ("turn", action_id)
        elif command == "item":
            item_id = choose_combat_item(engine)
            if item_id:
                return ("turn", f"item:{item_id}")
        elif command == "swap":
            weapon_id = choose_swap_weapon(engine)
            if weapon_id:
                return ("turn", f"swap:{weapon_id}")
        elif command == "identify":
            return ("turn", "identify")
        elif command == "flee":
            return ("flee", "")

def choose_skill(engine: GameEngine) -> str | None:
    skills = engine.equipped_skills()
    if not skills:
        print("You have no skills equipped. Equip some from the main menu (Skills).")
        return None

    while True:
        options = []
        weapon = engine.content.weapons[engine.player.equipped_weapon_id]
        for index, skill in enumerate(skills, start=1):
            label = (
                f"{skill.name} - {skill_cost_text(skill)}"
                f"{skill_requirement_text(engine, skill)}{skill_readiness_text(engine, skill)}"
            )
            options.append((str(index), skill.id, label))
        options.append(("b", "back", "Back"))

        choice = prompt_menu("Use which skill?", options, allow_label=False)
        if choice == "back":
            return None
        action = engine.content.actions[choice]
        reason = combat.blocked_action_reason(engine.player, action, weapon=weapon)
        if reason:
            print(reason)
            continue  # reprompt without spending the round
        return choice


def skill_readiness_text(engine: GameEngine, action) -> str:
    weapon = engine.content.weapons[engine.player.equipped_weapon_id]
    reason = combat.blocked_action_reason(engine.player, action, weapon=weapon)
    return f" [NOT READY: {reason}]" if reason else ""


def skill_requirement_text(engine: GameEngine, action) -> str:
    if not action.requires_weapon_category:
        return ""
    weapon = engine.content.weapons[engine.player.equipped_weapon_id]
    text = f", requires {action.requires_weapon_category}"
    if weapon.category != action.requires_weapon_category:
        text += f" [NO {action.requires_weapon_category.upper()} WEAPON]"
    return text


def choose_combat_item(engine: GameEngine) -> str | None:
    usable = [
        (item_id, count)
        for item_id, count in sorted(engine.player.inventory.consumables.items())
        if engine.content.items[item_id].kind == "consumable"
    ]
    if not usable:
        print("You have no usable consumables.")
        return None

    options = []
    for index, (item_id, count) in enumerate(usable, start=1):
        item = engine.content.items[item_id]
        options.append((str(index), item_id, f"{item.name} x{count} - {item_effect_text(item)}"))
    options.append(("b", "back", "Back"))

    choice = prompt_menu("Use which item?", options, allow_label=False)
    return None if choice == "back" else choice


def choose_swap_weapon(engine: GameEngine) -> str | None:
    player = engine.player
    options = []
    for index, weapon in enumerate(engine.owned_weapons(), start=1):
        equipped = " (equipped)" if weapon.id == player.equipped_weapon_id else ""
        options.append(
            (
                str(index),
                weapon.id,
                f"{weapon.name} (+{weapon.damage_bonus} {weapon.damage_type}, tier {weapon.tier})"
                f"{weapon_level_requirement_text(engine, weapon)}{equipped}",
            )
        )
    options.append(("b", "back", "Back"))

    choice = prompt_menu("Swap to which weapon?", options, allow_label=False)
    if choice == "back":
        return None
    if choice == player.equipped_weapon_id:
        print("That weapon is already equipped.")
        return None
    return choice


def handle_equip_weapon(engine: GameEngine) -> None:
    player = engine.player
    weapons = engine.owned_weapons()
    if not weapons:
        print("You own no weapons.")
        return

    options = []
    print()
    print(f"Equip weapon (current: {engine.content.weapons[player.equipped_weapon_id].name})")
    for index, weapon in enumerate(weapons, start=1):
        equipped = " (equipped)" if weapon.id == player.equipped_weapon_id else ""
        options.append(
            (
                str(index),
                weapon.id,
                f"{weapon.name} (+{weapon.damage_bonus} {weapon.damage_type}, tier {weapon.tier})"
                f"{weapon_level_requirement_text(engine, weapon)}{equipped}",
            )
        )
    options.append(("b", "back", "Back"))

    choice = prompt_menu("Equip which weapon?", options, allow_label=False)
    if choice == "back":
        return
    if choice == player.equipped_weapon_id:
        print("That weapon is already equipped.")
        return

    weapon = engine.content.weapons[choice]
    # Reuse the combat weapon-swap path so level requirements are enforced.
    action = combat.create_weapon_swap_action(weapon)
    result = combat.resolve_action(player, player, action, engine.rng, weapon=weapon)
    if result.blocked:
        for event in result.events:
            print(event)
    else:
        print(f"Equipped {weapon.name}.")


def weapon_level_requirement_text(engine: GameEngine, weapon) -> str:
    required_level = combat.weapon_required_level(weapon)
    text = f" - requires level {required_level}"
    if engine.player.level < required_level:
        text += " [LEVEL TOO LOW]"
    return text


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
    while True:
        print()
        print(f"Store | Gold: {engine.player.gold}")
        choice = prompt_menu(
            "Store:",
            [
                ("1", "buy", "Buy"),
                ("2", "sell", "Sell"),
                ("b", "back", "Back"),
            ],
        )
        if choice == "buy":
            handle_buy(engine)
        elif choice == "sell":
            handle_sell(engine)
        else:
            return


def handle_buy(engine: GameEngine) -> None:
    entries = engine.store_entries()
    if not entries:
        print("There is nothing for sale here.")
        return

    options = []
    print()
    print(f"Buy | Gold: {engine.player.gold}")
    for index, entry in enumerate(entries, start=1):
        print(f"{index}: {entry.name} ({entry.kind}) - {entry.price} gold, {entry.description}")
        options.append((str(index), entry.id, entry.name))
    options.append(("b", "back", "Back"))

    item_id = prompt_menu("What do you want to buy?", options)
    if item_id == "back":
        return

    chosen = next(entry for entry in entries if entry.id == item_id)
    if chosen.kind == "consumable" and chosen.price > 0:
        affordable = engine.player.gold // chosen.price
        if affordable < 1:
            print(engine.buy_item(item_id).message)  # reports not enough gold
            return
        quantity = prompt_quantity("How many?", affordable)
        bought = 0
        for _ in range(quantity):
            result = engine.buy_item(item_id)
            if not result.success:
                print(result.message)
                break
            bought += 1
        if bought:
            print(f"Bought {bought}x {chosen.name}.")
        return

    print(engine.buy_item(item_id).message)


def handle_sell(engine: GameEngine) -> None:
    entries = engine.sellable_entries()
    if not entries:
        print("You have nothing to sell (junk and unequipped weapons only).")
        return

    options = []
    print()
    print(f"Sell | Gold: {engine.player.gold}")
    for index, entry in enumerate(entries, start=1):
        count = f" x{entry.count}" if entry.kind == "junk" and entry.count > 1 else ""
        print(f"{index}: {entry.name} ({entry.kind}){count} - sells for {entry.value} gold")
        options.append((str(index), entry.id, entry.name))
    options.append(("b", "back", "Back"))

    item_id = prompt_menu("What do you want to sell?", options, allow_label=False)
    if item_id == "back":
        return

    chosen = next(entry for entry in entries if entry.id == item_id)
    if chosen.kind == "junk" and chosen.count > 1:
        quantity = prompt_quantity("How many?", chosen.count)
        gold_before = engine.player.gold
        sold = 0
        for _ in range(quantity):
            result = engine.sell_item(item_id)
            if not result.success:
                print(result.message)
                break
            sold += 1
        if sold:
            print(f"Sold {sold}x {chosen.name} for {engine.player.gold - gold_before} gold.")
        return

    print(engine.sell_item(item_id).message)


def item_effect_text(item) -> str:
    bits = []
    if item.heal_amount:
        bits.append(f"heals {item.heal_amount} HP")
    if item.mana_amount:
        bits.append(f"restores {item.mana_amount} mana")
    if item.cures:
        bits.append("cures " + ", ".join(item.cures))
    return ", ".join(bits) if bits else "no effect"


def handle_use_item(engine: GameEngine) -> None:
    usable = [
        (item_id, count)
        for item_id, count in sorted(engine.player.inventory.consumables.items())
        if engine.content.items[item_id].kind == "consumable"
    ]
    if not usable:
        print("You have no usable consumables.")
        return

    options = []
    print()
    print("Use item")
    for index, (item_id, count) in enumerate(usable, start=1):
        item = engine.content.items[item_id]
        print(f"{index}: {item.name} x{count} - {item_effect_text(item)}")
        options.append((str(index), item.id, item.name))
    options.append(("b", "back", "Back"))

    item_id = prompt_menu("Which item do you want to use?", options)
    if item_id == "back":
        return
    result = engine.use_consumable(item_id)
    print(result.message)
