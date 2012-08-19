import unittest
import gcode_optimise
from gcode_parse import parse_file

def test_equal_commands(tc, a, b):
    for ca,cb in zip(a,b):
        tc.assertEqual(ca, cb, "Commands (%s) & (%s) should be equal" % (ca,cb))
    tc.assertEqual(len(a),len(b), "Commands %d %d should have equal lengths" % (len(a),len(b)))

class TestGcodeOptimiser(unittest.TestCase):

    def _simplify_commands(self, threshold):
        # test data is 10mm line w/1mm deviation
        commands = parse_file("testdata/deviate_1mm.ngc")
        old_moves = [c for c in commands if c["name"]=="G1"]
        not_moves = [c for c in commands if c["name"]!="G1"]
        commands = list(gcode_optimise.simplify_movements(commands, threshold))
        new_moves = [c for c in commands if c["name"]=="G1"]
        new_not_moves = [c for c in commands if c["name"]!="G1"]
        test_equal_commands(self, not_moves, new_not_moves)
        return old_moves, new_moves

    def test_simplify_lines(self):
        """ In this test the line should be simplifed to a
        straight one """
        old_moves, new_moves = self._simplify_commands(1.1)
        self.assertTrue(len(new_moves)<len(old_moves),
                   "Simplification should have shortened move length from %d" % len(new_moves))
        self.assertEqual(old_moves[0], new_moves[0], "First commands should stay same")
        self.assertEqual(old_moves[-1], new_moves[-1], "Last commands should stay same")

    def test_nosimplify_lines(self):
        """ In this test the line should not be simplifed """
        old_moves, new_moves = self._simplify_commands(0.9)
        self.assertEqual(old_moves, new_moves, "0.9mm threshold should cause no simplification of movements")

if __name__ == '__main__':
    unittest.main()
