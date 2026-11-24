import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from secondary_contrasts import matched_filler,specificity


class TestSecondary(unittest.TestCase):
    def test_length_and_position(self):
        unused={1:["a b c d e f"],2:["d e f g h i"],3:["before alpha beta after"]}
        p,donors=matched_filler("alpha beta",["one two three","alpha beta","four five"],1,unused,1)
        self.assertEqual(p.split()[3:5],["alpha","beta"])
        self.assertEqual(len(p.split()),7)
        self.assertEqual(donors,[2])
    def test_specificity(self):
        rows=[dict(identity=1,focal=0,weaken=1),dict(identity=0,focal=1,weaken=1),dict(identity=None,focal=0,weaken=0)]
        self.assertEqual(specificity(rows)["mean"],.5)
        self.assertEqual(specificity(rows[:1])["interval95"][1],1)
