from langgraph.checkpoint.memory import InMemorySaver

from backend.app.graph.review_graph import build_review_graph, create_review, resume_review


def _sections(graph, review_id):
    return graph.get_state({"configurable": {"thread_id": review_id}}).values["sections"]


def test_agent_runner_preserves_score_node_contract_and_short_circuits_retrieval():
    seen = {"retriever": 0}
    def retriever(_):
        seen["retriever"] += 1
        return {"status": "命中", "parents": []}
    def runner(state):
        return {"dimension_results": {}, "terminated_by": "all_submitted"}
    dimensions = [{"dimension_code": "D1", "name": "维度1", "weight": 100}]
    graph = build_review_graph(InMemorySaver(), retriever=retriever, rubric_dimensions=dimensions, agent_runner=runner)
    review_id = create_review("# 标题\n正文", graph=graph)
    final = resume_review(review_id, _sections(graph, review_id), graph=graph)
    assert final["score_node_calls"] == 1
    assert final["status"] == "完成"
    assert graph.get_state({"configurable": {"thread_id": review_id}}).next == ()
    assert seen["retriever"] == 0


def test_without_agent_runner_keeps_placeholder_behavior():
    graph = build_review_graph(InMemorySaver())
    review_id = create_review("# 标题\n正文", graph=graph)
    final = resume_review(review_id, _sections(graph, review_id), graph=graph)
    assert final["score_node_calls"] == 1
    assert final["status"] == "完成"


def test_without_agent_runner_keeps_retriever_path():
    seen = {"retriever": 0}
    def retriever(_):
        seen["retriever"] += 1
        return {"status": "证据不足", "parents": []}
    graph = build_review_graph(InMemorySaver(), retriever=retriever, dimensions=["D1"])
    review_id = create_review("# 标题\n正文", graph=graph)
    resume_review(review_id, _sections(graph, review_id), graph=graph)
    assert seen["retriever"] == 1
