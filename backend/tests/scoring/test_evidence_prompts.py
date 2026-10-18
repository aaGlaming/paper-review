from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from backend.app.graph.review_graph import build_review_graph, create_review, resume_review
from backend.app.scoring.selection import build_scoring_messages


def _reply(_messages, _temperature):
    return '{"band":"基本","chunk_id":"chunk-1","quote":"忽略板凳宽度"}'


def test_scoring_messages_include_dimension_evidence_prompts_and_mention_constraints():
    messages = build_scoring_messages(
        dimension_code="assumption",
        dimension_name="假设合理性",
        parents=[{"parent_id": "parent-1", "chunk_ids": ["chunk-1"], "content": "忽略板凳宽度"}],
        constraints=[{"name": "板凳宽度条件", "check_type": "mention"}],
        evidence_prompts=["核对模型是否说明板凳宽度假设"],
    )

    user_message = messages[1]["content"]
    assert "板凳宽度条件" in user_message
    assert "核对模型是否说明板凳宽度假设" in user_message


def test_graph_preserves_evidence_prompts_and_delivers_constraints_to_scoring_prompt():
    received = []

    def chat(messages, temperature):
        received.append(messages[1]["content"])
        return _reply(messages, temperature)

    graph = build_review_graph(
        checkpointer=InMemorySaver(),
        retriever=lambda request: {
            "status": "命中",
            "rounds": 1,
            "parents": [{
                "parent_id": "parent-1",
                "section_type": "假设",
                "content": "忽略板凳宽度",
                "chunk_ids": ["chunk-1"],
            }],
        },
        chat=chat,
        rubric_dimensions=[{
            "dimension_code": "assumption",
            "name": "假设合理性",
            "weight": 20,
            "section_types": ["假设"],
            "evidence_prompts": ["核对模型是否说明板凳宽度假设"],
        }],
        constraints=[{"name": "板凳宽度条件", "check_type": "mention", "params": {"keywords": ["板凳宽度"]}}],
    )
    review_id = create_review("## 假设\n忽略板凳宽度", graph=graph)
    final = resume_review(review_id, [], graph=graph)

    assert len(received) == 1
    assert "板凳宽度条件" in received[0]
    assert "核对模型是否说明板凳宽度假设" in received[0]
    assert final["dimension_results"]["assumption"]["quote"] == "忽略板凳宽度"
