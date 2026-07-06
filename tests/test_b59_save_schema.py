"""B59: save-schema hardening.

Locks the four guarantees: (a) versioned saves lifted through the MIGRATIONS
table, (b) ONE field table drives both serialize and deserialize, (c) load
verifies cross-field invariants with a named error, (d) a new Player field that
is neither in PLAYER_FIELDS nor declared DERIVED fails the coverage test — and
the round-trip test pushes a non-default value through REAL JSON for every
persisted field, so a field serialized-but-not-restored (or vice versa) fails.
"""

import dataclasses
import json
import unittest

from rpg_game.core import persistence
from rpg_game.core.entities import ActiveStatus, Inventory, Player


def _fully_populated_player() -> Player:
    """A Player with a NON-DEFAULT value in every persisted field."""
    return Player(
        name="Rt", player_class="mage", level=7, xp=55, xp_required=210,
        hp=33, max_hp=44, base_damage=9, armor=3, gold=123,
        equipped_weapon_id="emberwand",
        inventory=Inventory(consumables={"hp_potion": 2, "tome_zap": 1}),
        current_place_id="burg_146", respawn_place_id="burg_5",
        owned_weapon_ids=("emberwand", "knife"), owned_gear_ids=("acolyte_charm",),
        equipped_gear={"amulet": "acolyte_charm"},
        mana=17, wisdom=11, speed=6, crit_chance=8, crit_mult=2.5,
        evasion_chance=4, damage_dealt_mod=10, damage_taken_mod=-5,
        equipped_skill_ids=("firebolt", "ignite"), talent_points=2,
        learned_skill_ids=("zap",),
        learned_talent_ids={"mage_t1"}, talent_ranks={"mage_t1": 2},
        resistances={"fire": 0.65},
        active_statuses=[ActiveStatus(type="regen", magnitude=5, duration=2,
                                      tick_timing="round_end", tag="regen")],
        stat_bonuses={"speed": 1},
        applied_status_mods={"poison": {"magnitude": 2}},
        cooldowns={"fireball": 1}, accuracy_mod=-10,
        immunity_tags={"burn"}, tags={"blessed"},
        conditional_damage_mods=[{"predicate": "hp_pct_lte", "threshold": 30}],
        elemental_attack_mods=[{"damage_type": "fire", "magnitude": 2}],
        pending_stat_choices=1, completed_tournament_ids={"hordanita_novice_cup"},
        item_upgrades={"emberwand": "honed"},
        revealed_tiles=bytearray(b"\x0f\xf0"),
        opened_chest_ids=("chest_cainos_1",),                     # B63
        playtime_seconds=4321,                                    # B71
        bestiary_seen={"cave_bear"},                              # B66
        bestiary_identified={"cave_bear"},
        bestiary_kills={"wild_dog": 3},
        defeated_boss_ids={"rotfang"},                            # B65
        overworld_tile=(12, 88),                                  # B74
    )


class FieldTableCoverageTests(unittest.TestCase):
    def test_every_player_field_is_classified(self):
        # A new Player field must be added to PLAYER_FIELDS (persisted) or
        # DERIVED_FIELDS (rebuilt) — anything else fails here, in both directions.
        self.assertEqual(persistence.persisted_field_names(),
                         set(persistence.PLAYER_FIELDS))

    def test_derived_fields_are_real_fields(self):
        all_fields = {f.name for f in dataclasses.fields(Player)}
        self.assertTrue(persistence.DERIVED_FIELDS <= all_fields)


class RoundTripTests(unittest.TestCase):
    def test_every_persisted_field_round_trips_through_real_json(self):
        original = _fully_populated_player()
        raw = json.loads(json.dumps(persistence.serialize_player(original)))
        raw = persistence.migrate_player_data(raw, persistence.SAVE_VERSION)  # no-op at current
        restored = persistence.deserialize_player(raw)
        for name in persistence.PLAYER_FIELDS:
            self.assertEqual(getattr(restored, name), getattr(original, name),
                             f"field {name} did not round-trip")

    def test_serialize_state_stamps_the_current_version(self):
        from rpg_game.core.entities import GameState
        from rpg_game.core.data_loader import load_content
        state = GameState(player=_fully_populated_player(), content=load_content())
        self.assertEqual(persistence.serialize_state(state)["version"], persistence.SAVE_VERSION)


class MigrationTests(unittest.TestCase):
    def test_v1_legacy_respawn_and_wisdom_and_ranks(self):
        legacy = {
            "name": "Old", "player_class": "cleric",
            "last_rest_place_id": "burg_67",       # purchased respawn, legacy key
            "respawn_place_id": "burg_999",        # movement-polluted, must be ignored
            "max_mana": 20,                        # pre-wisdom save
            "learned_talent_ids": ["cleric_t1"],   # pre-B36: no ranks stored
        }
        migrated = persistence.migrate_player_data(legacy, 1)
        player = persistence.deserialize_player(migrated, "burg_5")
        self.assertEqual(player.respawn_place_id, "burg_67")
        self.assertEqual(player.wisdom, 20 // 4)               # MANA_PER_WISDOM = 4
        self.assertEqual(player.talent_ranks, {"cleric_t1": 1})
        self.assertEqual(player.learned_talent_ids, {"cleric_t1"})
        persistence.verify_invariants(player)                  # holds after migration

    def test_unknown_version_fails_with_named_error(self):
        with self.assertRaisesRegex(ValueError, "no migration from save version -3"):
            persistence.migrate_player_data({}, -3)

    def test_future_version_passes_through(self):
        data = {"name": "X"}
        self.assertIs(persistence.migrate_player_data(data, persistence.SAVE_VERSION), data)


class InvariantTests(unittest.TestCase):
    def test_learned_without_rank_is_a_named_error(self):
        player = _fully_populated_player()
        player.learned_talent_ids = {"mage_t1", "ghost_node"}
        with self.assertRaisesRegex(ValueError, "learned_talent_ids"):
            persistence.verify_invariants(player)

    def test_non_positive_rank_is_a_named_error(self):
        player = _fully_populated_player()
        player.talent_ranks = {"mage_t1": 0}
        player.learned_talent_ids = set()
        with self.assertRaisesRegex(ValueError, "non-positive"):
            persistence.verify_invariants(player)

    def test_clean_player_passes(self):
        persistence.verify_invariants(_fully_populated_player())


if __name__ == "__main__":
    unittest.main()
