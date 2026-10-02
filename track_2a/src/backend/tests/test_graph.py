"""The Aegra / LangGraph-Server graph pauses for answers via interrupt()."""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from zusage.config import Settings
from zusage.engine.brain import OfflineBrain
from zusage.engine.graph import build_interview_graph, build_turn_graph


def test_interrupt_driven_interview(kb):
    graph = build_interview_graph(kb, OfflineBrain(), Settings(offline=True), checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "t"}}
    out = graph.invoke({"setup": {"language": "fr", "occupation_id": "automech_efz", "length": "quick",
                                  "candidate": {"first_name": "Chloé"}}}, cfg)
    asked = 0
    while "__interrupt__" in out:
        asked += 1
        out = graph.invoke(Command(resume="Par exemple, j'ai réparé le vélo de ma voisine, puis j'ai appris la patience."), cfg)
        assert asked < 20
    assert asked >= 5 and out["state"]["report"]["overall"] > 0
    assert out["transcript"][0]["text"].startswith("Bonjour")


def test_turn_graph_finishes_with_report(kb):
    from zusage.engine import core

    graph = build_turn_graph(kb, OfflineBrain(), Settings(offline=True))
    state = core.start(kb, OfflineBrain(), {"language": "de", "occupation_id": "logistik_eba", "length": "quick"})
    while not state.get("done"):
        state = graph.invoke({"state": state, "answer": "Zum Beispiel helfe ich im Lager meines Onkels."})["state"]
    assert state["report"] is not None
