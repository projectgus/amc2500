import unittest
import gcode_optimise
from gcode_parse import parse_file

def test_equal_commands(tc, a, b):
    for ca,cb in zip(a,b):
        tc.assertEqual(ca, cb, "Commands (%s) & (%s) should be equal" % (ca,cb))
    tc.assertEqual(len(a),len(b), "Commands %d %d should have equal lengths" % (len(a),len(b)))

class TestGcodeOptimiser(unittest.TestCase):

    def _deviation_commands(self, threshold):
        # test data is 10mm line w/1mm deviation
        commands = parse_file("testdata/deviate_1mm.ngc")
        old_moves = [c for c in commands if c["name"]=="G1"]
        not_moves = [c for c in commands if c["name"]!="G1"]
        optimised = gcode_optimise.optimise(commands, threshold)
        new_moves = [c for c in optimised if c["name"]=="G1"]
        new_not_moves = [c for c in optimised if c["name"]!="G1"]
        test_equal_commands(self, not_moves, new_not_moves) # everything but G1 should commands should be 100% the same
        for new in optimised:
            self.assertTrue(new in commands, "Every optimised command should already exist in old set, including %s" % new)
            self.assertTrue(optimised.index(new) <= commands.index(new), "Optimisation strips commands, so any new command should have index at or before it's position in the old command list (testing %s)" % new)


        return old_moves, new_moves

    def test_deviation_lines(self):
        """ In this test the line should be simplified to a single straight one """
        old_moves, new_moves = self._deviation_commands(1.1)
        self.assertTrue(len(new_moves)<len(old_moves),
                   "Simplification should have shortened move length from %d" % len(new_moves))
        self.assertEqual(old_moves[0], new_moves[0], "First commands should stay same")
        self.assertEqual(old_moves[-1], new_moves[-1], "Last commands should stay same")

    def test_nodeviation_lines(self):
        """ In this test the line should not be simplified for deviation (above threshold) """
        old_moves, new_moves = self._deviation_commands(0.9)
        self.assertEqual(old_moves, new_moves, "0.9mm threshold should cause no simplification of movements")


    def test_drill_optimisation(self):
        commands = list(parse_file("testdata/drill_cycle.ngc"))
        optimised = gcode_optimise.optimise(commands, 100)
        self.assertEqual(len(commands), len(optimised), "Should be same number of commands before/after")
        self.assertNotEqual(commands, optimised, "Optimised drill pass should use different order")
        for c in commands:
            self.assertTrue(c in optimised, "All commands in commands should be in optimised set, including %s" % c)


if __name__ == '__main__':
    unittest.main()
