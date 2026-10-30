"""Run: .venv/bin/python -m tests.test_chronicle_agent"""
from stages.chronicle_agent import awaiting, check_film_plan, excerpt_ok, parse_json_lines, year_errors


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


def test_year_errors_flag_unsourced_years():
    film = {"shots": [{"id": "S01", "year": [1601, 1817]}],
            "chronology": {"layers": [{"area": "core", "from": 1714, "to": None}], "eras": [{"code": "01", "from": 1500}]}}
    errs = year_errors(film, {1714, 1817, 2026})
    assert any("1601" in e for e in errs) and any("1500" in e for e in errs) and len(errs) == 2


def test_film_plan_bars_must_tile_sections():
    plan = {"sections": [{"id": "intro", "bars": 4}, {"id": "verse", "bars": 2}]}
    basemap = {"places": [{"id": "wada"}], "areas": []}
    shot = lambda i, sec, b: {"id": i, "section": sec, "bars": b, "view": {"at": "wada"}, "caption": {"en": {"text": "Short line"}}}
    ok = {"shots": [shot("S01", "intro", 2), shot("S02", "intro", 2), shot("S03", "verse", 2)], "areas": []}
    assert check_film_plan(ok, plan, basemap) == []
    short = {"shots": [shot("S01", "intro", 2), shot("S02", "verse", 2)], "areas": []}
    assert any("intro" in e for e in check_film_plan(short, plan, basemap))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
