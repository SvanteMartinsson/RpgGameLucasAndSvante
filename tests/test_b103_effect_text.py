"""B103: every effect type in the data renders as computed, human text.

The guard test walks actions.json + talents.json: every effect type found must
be registered in RENDERED_EFFECT_TYPES, and no rendered line may leak a raw
identifier (underscores / the bare type name). Future content that adds a new
effect type without a renderer fails here — the gap can never reappear.
"""

import unittest

from rpg_game.core.data_loader import load_content
from rpg_game.presentation.talent_text import (
    RENDERED_EFFECT_TYPES,
    describe_effect,
    talent_rank_lines,
)


def _all_data_effects(content):
    for action in content.actions.values():
        for effect in action.effects:
            yield f"action {action.id}", effect
    for node in content.talents.values():
        for effect in node.effects:
            yield f"talent {node.id}", effect


class EffectTextGuardTest(unittest.TestCase):
    """The lock: data may not contain an effect type without a renderer."""

    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def test_every_effect_type_in_data_has_a_renderer(self):
        missing = {effect.type for _, effect in _all_data_effects(self.content)
                   if effect.type not in RENDERED_EFFECT_TYPES}
        self.assertFalse(
            missing,
            f"effect types without a registered renderer: {sorted(missing)} — "
            "add a describe_effect branch AND list the type in RENDERED_EFFECT_TYPES",
        )

    def test_no_rendered_line_leaks_a_raw_identifier(self):
        for source, effect in _all_data_effects(self.content):
            text = describe_effect(effect)
            self.assertNotEqual(text, effect.type, f"{source}: bare type leaked")
            self.assertNotIn("_", text, f"{source}: raw identifier in {text!r}")

    def test_rank_lines_use_the_same_renderer(self):
        """B90 rank rows go through describe_effect too — no raw ids there."""
        for node in self.content.talents.values():
            for line in talent_rank_lines(self.content, node):
                self.assertNotIn("_mod", line, f"{node.id}: {line!r}")
                self.assertNotIn("elemental", line, f"{node.id}: {line!r}")


class EffectTextComputedTest(unittest.TestCase):
    """The playtest finds: Combustion and Flametongue/Rimeblade, computed."""

    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _talent(self, name):
        return next(n for n in self.content.talents.values() if n.name == name)

    def test_combustion_reads_as_fire_damage_vs_burning(self):
        node = self._talent("Combustion")
        self.assertEqual(describe_effect(node.effects[0]),
                         "Fire damage +20% vs burning targets")

    def test_combustion_rank_lines_scale_the_percent(self):
        node = self._talent("Combustion")
        lines = talent_rank_lines(self.content, node)
        self.assertIn("+20%", lines[0])
        self.assertNotIn("+20%", lines[-1])   # top rank computed, not repeated

    def test_flametongue_reads_as_flat_fire_on_attacks(self):
        node = self._talent("Flametongue")
        self.assertEqual(describe_effect(node.effects[0]),
                         "+4 fire damage on attacks")

    def test_virulence_states_tick_and_duration(self):
        node = self._talent("Virulence")
        self.assertEqual(describe_effect(node.effects[0]),
                         "your poison effects tick +2 damage and last +1 round")

    def test_rage_states_trigger_and_stacking(self):
        node = self._talent("Rage")
        self.assertEqual(describe_effect(node.effects[0]),
                         "when hit: +3 damage for 3 rounds (self), stacks up to 5")


if __name__ == "__main__":
    unittest.main()
