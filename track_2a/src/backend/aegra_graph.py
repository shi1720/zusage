"""Aegra / LangGraph Server entry point.

Aegra (https://github.com/aegra/aegra) loads graphs by file path, so this shim
exposes the interrupt-driven interview graph as a module-level ``graph``.
See ``aegra.json`` and docs/DEPLOYMENT.md § Aegra.

Drive it with any LangGraph SDK client:

    thread = await client.threads.create()
    run = await client.runs.wait(thread["thread_id"], "zusage_interview",
                                 input={"setup": {"language": "de", "occupation_id": "fage_efz", "length": "quick"}})
    # → run["__interrupt__"][0]["value"]["interviewer"] is the first question
    await client.runs.wait(thread["thread_id"], "zusage_interview", command={"resume": "<answer>"})
"""

from zusage.engine.graph import build_interview_graph

graph = build_interview_graph()
