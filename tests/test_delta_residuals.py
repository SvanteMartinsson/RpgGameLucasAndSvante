"""Known Δ0/Δ−2 residual tagging in the delta-curve tool (2026-07-12).

Locks that the frozen baseline is well-formed (every check name parses to a real
zone + class + gate type), that every frozen check gets a specific reason tag,
and that classify_gates separates a NEW regression from the accepted residuals
so a real regression can never drown in the 92.
"""

import unittest

from rpg_game.tools import delta_curve as dc


class FrozenBaselineShapeTests(unittest.TestCase):
    GATE_PREFIXES = ("Δ0 neutral", "Δ0 floor", "Δ0 TTK", "Δ0 cost",
                     "Δ+3", "Δ−2", "Δ−4")

    def test_baseline_size_matches_the_captured_snapshot(self):
        # 42 Δ0 + 19 Δ−2 + 14 Δ+3 + 13 Δ−4 + 4 DEFAULT, N=120==N=200.
        self.assertEqual(len(dc.KNOWN_RESIDUAL_CHECKS), 92)

    def test_every_frozen_check_parses_to_a_real_zone_and_class(self):
        for name in dc.KNOWN_RESIDUAL_CHECKS:
            if name.startswith("DEFAULT") or name.startswith("OPTIMIZED"):
                self.assertIn(name.split()[-1], dc.CLASSES, name)
                continue
            self.assertTrue(any(name.startswith(p) for p in self.GATE_PREFIXES), name)
            head, _, cls = name.partition("/")
            self.assertTrue(cls, name)
            self.assertIn(cls, dc.CLASSES, name)
            self.assertIn(head.split()[-1], dc.ZONES, name)

    def test_every_frozen_check_gets_a_specific_reason(self):
        for name in dc.KNOWN_RESIDUAL_CHECKS:
            reason = dc.residual_reason(name)
            self.assertTrue(reason.strip(), name)
            self.assertNotEqual(reason, "prep-2026-07-12 residual", name)


class ClassifyGatesTests(unittest.TestCase):
    def test_the_whole_frozen_baseline_classifies_as_known(self):
        gates = [f"FAIL  {n}: detail" for n in dc.KNOWN_RESIDUAL_CHECKS]
        known, new = dc.classify_gates(gates)
        self.assertEqual(len(known), 92)
        self.assertEqual(new, [])   # a clean run reports zero new fails

    def test_a_regression_not_in_the_baseline_surfaces_as_new(self):
        frozen = sorted(dc.KNOWN_RESIDUAL_CHECKS)[0]
        # cainos Δ0 is NOT frozen (mild corridor, passes) -> a good stand-in for
        # a genuinely new on-level regression.
        regression = "Δ0 neutral cainos/fighter"
        self.assertNotIn(regression, dc.KNOWN_RESIDUAL_CHECKS)
        gates = [f"FAIL  {frozen}: d", f"FAIL  {regression}: d",
                 "PASS  Δ0 neutral cainos/tank: fine"]
        known, new = dc.classify_gates(gates)
        self.assertEqual([n for n, _ in known], [frozen])
        self.assertEqual(new, [regression])

    def test_pass_lines_are_ignored(self):
        self.assertEqual(dc.classify_gates(["PASS  Δ0 neutral cainos/tank: ok"]),
                         ([], []))

    def test_reason_tags_by_band(self):
        self.assertIn("floor", dc.residual_reason("Δ0 floor grave_heath/mage"))
        self.assertIn("durable", dc.residual_reason("Δ0 neutral mork_skog/tank"))
        self.assertIn("delta2", dc.residual_reason("Δ−2 grave_heath/mage"))
        self.assertIn("plus3", dc.residual_reason("Δ+3 cainos/fighter"))
        self.assertIn("delta4", dc.residual_reason("Δ−4 mork_skog/tank"))
        self.assertIn("default", dc.residual_reason("DEFAULT ≥ median−15pp mage"))


if __name__ == "__main__":
    unittest.main()
