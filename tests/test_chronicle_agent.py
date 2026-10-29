"""Run: .venv/bin/python -m tests.test_chronicle_agent"""
from stages.chronicle_agent import awaiting, excerpt_ok, parse_json_lines


def test_awaiting_takes_last_status():
    assert awaiting("[research] ok\nstatus: awaiting_claims\n") == "claims"
    assert awaiting("[facts] ok\n[script] status: awaiting_script\n") == "script"
    assert awaiting("[report] done") is None


def test_excerpt_matches_after_folding():
    src = "Pune, city, west-central Maharashtra state,\n western India, at the junction of the Mula and Mutha rivers."
    assert excerpt_ok("at the junction of the  Mula and MUTHA rivers", src)


def test_excerpt_rejects_paraphrase_and_long():
    src = "In 1961 the Panshet Dam collapsed, washing away a substantial part of the old town."
    assert not excerpt_ok("In 1961 the Panshet dam burst", src)
    assert not excerpt_ok(" ".join(["word"] * 31), " ".join(["word"] * 40))
    assert not excerpt_ok("", src)


def test_json_lines_drop_only_bad_lines():
    text = '{"predicate": "river", "value": 1}\n{"predicate": "founded", "value": {"x": 1}\n\n{"predicate": "renamed"},'
    good, bad = parse_json_lines(text)
    assert [g["predicate"] for g in good] == ["river", "renamed"]
    assert len(bad) == 1
    assert parse_json_lines('{"claims": [{"predicate": "river"}]}')[0] == [{"predicate": "river"}]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
