from backend.app.chat import answering, retrieval


def test_extract_review_id_matches_32_hex_and_lowercases():
    assert retrieval.extract_review_id("ABCDEF0123456789ABCDEF0123456789") == "abcdef0123456789abcdef0123456789"


def test_extract_review_id_rejects_wrong_length_and_hex_substrings():
    assert retrieval.extract_review_id("a" * 33) is None
    assert retrieval.extract_review_id("a" * 31) is None
    assert retrieval.extract_review_id("x" + "a" * 32 + "f") is None
    assert retrieval.extract_review_id("a" * 31 + "g") is None


def test_extract_review_id_matches_id_in_chinese_question():
    expected = "c50ee35713d6446d835b50d30caf9e5c"
    assert retrieval.extract_review_id(f"记录 {expected} 的维度为什么这样判断？") == expected


def test_answer_question_direct_mode_only_includes_target_review(monkeypatch):
    target = "c" * 32
    other = "d" * 32
    direct = [
        {"review_id": target, "dimension_code": f"dim{i}", "content": f"目标 {i}", "citable": True}
        for i in range(5)
    ] + [{"review_id": target, "dimension_code": "record_summary", "content": "概览", "citable": False}]
    monkeypatch.setattr(answering.records, "load_record_blocks", lambda *a, **k: direct)
    captured = {}

    def chat_fn(messages):
        captured["prompt"] = messages[1]["content"]
        return "回答"

    result = answering.answer_question(
        None, session_row=None, question=f"记录 {target} 的情况", contest_id="c1",
        search_fn=lambda *a, **k: [{"review_id": other, "dimension_code": "x", "content": "其他"}],
        chat_fn=chat_fn,
    )
    assert result["notes"]["mode"] == "record"
    assert result["notes"]["retrieved"] == 6
    assert result["notes"]["direct"] == 6
    assert other not in captured["prompt"]


def test_answer_question_direct_mode_calls_chat_once(monkeypatch):
    target = "b" * 32
    monkeypatch.setattr(answering.records, "load_record_blocks", lambda *a, **k: [
        {"review_id": target, "dimension_code": "assumption", "content": "记录", "citable": True}
    ])
    calls = []
    result = answering.answer_question(
        None, session_row=None, question=f"记录 {target}", contest_id="c1",
        chat_fn=lambda messages: calls.append(messages) or "回答",
    )
    assert result["notes"]["mode"] == "record"
    assert len(calls) == 1


def test_answer_question_missing_direct_record_does_not_call_model(monkeypatch):
    monkeypatch.setattr(answering.records, "load_record_blocks", lambda *a, **k: [])
    calls = []
    result = answering.answer_question(
        None, session_row=None, question=f"记录 {'e' * 32} 内容", contest_id="c1",
        chat_fn=lambda messages: calls.append(messages),
    )
    assert result["content"] == answering.RECORD_NOT_FOUND_CONTENT
    assert result["refs"] == []
    assert result["notes"]["mode"] == "record_missing"
    assert result["notes"]["model_called"] is False
    assert calls == []


def test_validate_citations_rejects_non_citable_overview():
    review_id = "a" * 32
    cleaned, refs, rejected, _ = answering.validate_citations(
        f"[review_id={review_id} dim=record_summary]",
        [{"review_id": review_id, "dimension_code": "record_summary", "citable": False}],
    )
    assert "record_summary" not in cleaned
    assert refs == []
    assert rejected == [{"review_id": review_id, "dimension_code": "record_summary"}]
