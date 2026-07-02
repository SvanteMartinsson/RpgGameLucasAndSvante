"""B41: on-hit elemental procs carried by weapons.

Locks the new basic-attack hook: a proc weapon applies its status on a hit
(burn/toxin/chill/freeze) or heals the wielder (holy Searing); the resistance
matrix gates status procs (undead shrugs off toxin); only BASIC ATTACKS proc
(skills keep their own authored effects); enemies never proc a player weapon.
"""

import random
import unittest

from rpg_game.core import combat
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine


class ZeroRng(random.Random):
    """random() == 0.0 so every proc-chance and hit-chance clears deterministically."""
    def random(self):
        return 0.0


def _engine(cls, weapon_id, level=10):
    engine = GameEngine(rng=ZeroRng(0))
    engine.start_new_game("Hero", cls)
    engine.player.owned_weapon_ids = (*engine.player.owned_weapon_ids, weapon_id)
    engine.player.equipped_weapon_id = weapon_id
    engine.player.level = level
    return engine


def _attack(engine, enemy_id):
    enemy = engine.content.enemies[enemy_id].create_enemy()
    weapon = engine.content.weapons[engine.player.equipped_weapon_id]
    result = combat.resolve_action(engine.player, enemy,
                                   engine.content.actions["attack"], engine.rng, weapon=weapon)
    return enemy, result


class OnHitDataTests(unittest.TestCase):
    def test_seeded_weapons_carry_matching_procs(self):
        c = load_content()
        expect = {"emberwand": "fire", "pyre_scepter": "fire", "venomfang": "poison",
                  "rimebrand": "frost"}
        for wid, dtype in expect.items():
            procs = c.weapons[wid].on_hit
            self.assertTrue(procs, wid)
            self.assertTrue(any(p.get("damage_type") == dtype for p in procs), wid)
        # holy weapons proc a self-heal, not a target status
        self.assertTrue(any("heal_self" in p for p in c.weapons["consecrated_maul"].on_hit))


class OnHitEffectTests(unittest.TestCase):
    def test_poison_weapon_applies_toxin_to_a_non_immune_target(self):
        enemy, _ = _attack(_engine("rogue", "venomfang"), "giant_rat")
        self.assertTrue(any(s.tag == "poison" for s in enemy.active_statuses))

    def test_poison_is_shrugged_off_by_a_poison_immune_target(self):
        enemy, result = _attack(_engine("rogue", "venomfang"), "undead")  # undead: poison ×0
        self.assertFalse(any(s.tag == "poison" for s in enemy.active_statuses))
        self.assertTrue(any("immune" in e for e in result.events))

    def test_fire_weapon_applies_burn(self):
        enemy, _ = _attack(_engine("mage", "emberwand"), "giant_rat")
        self.assertTrue(any(s.tag == "burn" for s in enemy.active_statuses))

    def test_frost_weapon_can_chill_and_freeze(self):
        enemy, _ = _attack(_engine("mage", "rimebrand"), "giant_rat")
        tags = {s.tag for s in enemy.active_statuses}
        self.assertIn("chill", tags)    # speed debuff
        self.assertIn("freeze", tags)   # skip-turn

    def test_holy_weapon_heals_the_wielder_on_hit(self):
        engine = _engine("fighter", "consecrated_maul")
        engine.player.hp = engine.player.hp - 20
        before = engine.player.hp
        _attack(engine, "undead")
        self.assertGreater(engine.player.hp, before)

    def test_skills_do_not_proc_the_weapon(self):
        # a mage casting firebolt (a skill) must NOT also apply the weapon's burn proc
        engine = _engine("mage", "venomfang")   # poison weapon + a non-base-attack skill
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        weapon = engine.content.weapons["venomfang"]
        firebolt = engine.content.actions["firebolt"]
        combat.resolve_action(engine.player, enemy, firebolt, engine.rng, weapon=weapon)
        self.assertFalse(any(s.tag == "poison" for s in enemy.active_statuses))

    def test_enemy_attacks_never_proc(self):
        # an enemy has no equipped player weapon -> apply_weapon_on_hit is a no-op
        engine = _engine("fighter", "venomfang")
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        result = combat.resolve_action(enemy, engine.player,
                                       engine.content.actions["normal"], engine.rng, weapon=None)
        self.assertFalse(any(s.tag == "poison" for s in engine.player.active_statuses))


if __name__ == "__main__":
    unittest.main()
