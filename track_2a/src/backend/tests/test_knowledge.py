from zusage.knowledge import CRITERIA, LANGS, PHASES


def test_knowledge_base_is_complete(kb):
    assert len(kb.occupations) == 12
    assert set(kb.personas) == {"warm", "structured", "direct"}
    for q in list(kb.questions) + [q for o in kb.occupations.values() for q in o.questions]:
        assert q.phase in PHASES
        assert set(q.targets) <= set(CRITERIA)
        for lang in LANGS:
            assert q.text[lang].strip(), (q.id, lang)


def test_every_occupation_has_company_facts_and_situational_question(kb):
    for occ in kb.occupations.values():
        assert len(occ.company.facts) >= 3
        assert any(q.phase == "situational" for q in occ.questions), occ.id
        assert all(occ.name[lang] for lang in ("de", "fr", "it", "en"))


def test_rubric_has_four_anchors_per_criterion(kb):
    for crit in CRITERIA:
        assert sorted(kb.anchors(crit)) == [1, 2, 3, 4]
        assert kb.criterion_name(crit, "fr")
