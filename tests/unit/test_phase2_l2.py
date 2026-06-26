from app.phase2_l2 import L2Scorer

class FakeDB: pass

def test_score_batch():
    s = L2Scorer(FakeDB())
    msgs = [{'role':'user','content':'failed 500'},{'role':'user','content':'ok'}]
    results = s.score_batch(msgs)
    assert len(results) == 2

def test_filter_valuable():
    s = L2Scorer(FakeDB())
    msgs = [{'role':'user','content':'hi'}]
    f = s.filter_valuable(msgs)
    assert isinstance(f, list)
