import sys, unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from score_primary import run


class TestCheckpoint(unittest.TestCase):
    def test_resumption(self):
        root="qwen/generic"
        requests=[dict(id=str(i),config=root) for i in range(3)]
        seen=[]
        def fail_on_second(c):
            if c["id"]=="1":raise RuntimeError()
            seen.append(c["id"])
            return dict(p=.5)
        def resume(c):
            seen.append(c["id"])
            return dict(p=None)
        with TemporaryDirectory() as tmp:
            dest=Path(tmp)
            with self.assertRaises(RuntimeError):
                run(requests,root,"first",dest,fail_on_second)
            run(requests,root,"first",dest,resume)
            run(requests,root,"first",dest,resume)
            self.assertEqual(seen,["0","1","2"])
            self.assertEqual(len((dest/"qwen__generic.jsonl").read_text().splitlines()),3)
            with self.assertRaises(ValueError):
                run(requests,root,"different",dest,resume)
