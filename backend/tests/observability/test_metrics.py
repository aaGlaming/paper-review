"""指标文本必须是 Prometheus 能解析的 exposition，而不只是「包含某个子串」。

断言分两层：
1. 每个族都在（HELP/TYPE 齐全），`_bucket` 带 `+Inf`；
2. 每次 render 的每一行都过朴素解析器（指标名 + 可选标签 + 数值三个部分，
   中间单个空格），且不含科学计数法——`1e-05` 会让 Prometheus 直接报解析错误。
"""

import re

from backend.app.observability import metrics

SAMPLE = re.compile(r"[a-z_]+(?:\{[^}]*\})? [0-9.]+")
QUOTE = chr(34)
BACKSLASH = chr(92)
NEWLINE = chr(10)

FAMILIES = (
    "paper_review_reviews_total",
    "paper_review_llm_calls_total",
    "paper_review_llm_latency_seconds",
    "paper_review_retrieve_parents",
    "paper_review_auth_total",
)
LLM_BOUNDS = ("0.5", "1", "2", "5", "10", "+Inf")
RETRIEVE_BOUNDS = ("1", "2", "3", "4", "+Inf")


def _samples(text):
    return [line for line in text.splitlines() if line and not line.startswith("#")]


def _assert_parseable(text):
    assert text.endswith("\n")
    for line in _samples(text):
        assert SAMPLE.fullmatch(line), line
        assert "e-" not in line.lower() and "e+" not in line.lower(), line
        assert "{}" not in line, line


def _value(text, prefix):
    for line in text.splitlines():
        if line.startswith(prefix):
            return float(line.rsplit(" ", 1)[1])
    return 0.0


def _buckets(text, family, bounds):
    return [_value(text, '%s_bucket{le="%s"}' % (family, bound)) for bound in bounds]


def test_render_always_prints_required_families():
    metrics.reset_metrics_for_tests()
    text = metrics.render()
    for family in FAMILIES:
        assert "# TYPE %s" % family in text
    # 直方图的桶即使一次没观测也要有 +Inf，否则 rate() 算不出来。
    assert 'paper_review_llm_latency_seconds_bucket{le="+Inf"} 0' in text
    assert 'paper_review_retrieve_parents_bucket{le="+Inf"} 0' in text
    # 「完成」有零值基线，避免第一次评审前看板显示「无数据」。
    assert 'paper_review_reviews_total{status="完成"} 0' in text
    _assert_parseable(text)


def test_counter_increments():
    metrics.reset_metrics_for_tests()
    before = _value(metrics.render(), 'paper_review_reviews_total{status="完成"}')
    metrics.inc_reviews("完成")
    after = _value(metrics.render(), 'paper_review_reviews_total{status="完成"}')
    assert after == before + 1


def test_llm_buckets_are_cumulative_and_match_sum_count():
    metrics.reset_metrics_for_tests()
    for elapsed in (0.2, 1.5, 7.0):
        metrics.observe_llm("deepseek-flash", True, elapsed)
    text = metrics.render()
    # 0.2 落在全部桶；1.5 落在 2 及以上；7.0 只落在 10 与 +Inf。
    assert _buckets(text, "paper_review_llm_latency_seconds", LLM_BOUNDS) == [1, 1, 2, 2, 3, 3]
    assert _value(text, "paper_review_llm_latency_seconds_count") == 3
    assert abs(_value(text, "paper_review_llm_latency_seconds_sum") - 8.7) < 1e-6
    _assert_parseable(text)


def test_llm_failure_and_success_are_separate_series():
    metrics.reset_metrics_for_tests()
    metrics.observe_llm("deepseek-flash", True, 0.3)
    metrics.observe_llm("deepseek-flash", False, 0.1)
    text = metrics.render()
    assert 'paper_review_llm_calls_total{model="deepseek-flash",result="ok"} 1' in text
    assert 'paper_review_llm_calls_total{model="deepseek-flash",result="error"} 1' in text
    _assert_parseable(text)


def test_retrieve_parents_histogram():
    metrics.reset_metrics_for_tests()
    metrics.observe_retrieve_parents(0)
    metrics.observe_retrieve_parents(4)
    text = metrics.render()
    assert _buckets(text, "paper_review_retrieve_parents", RETRIEVE_BOUNDS) == [1, 1, 1, 2, 2]
    _assert_parseable(text)


def test_labels_are_minimally_escaped_and_still_parseable():
    metrics.reset_metrics_for_tests()
    status = "a" + QUOTE + "b" + BACKSLASH + "c" + NEWLINE + "d"
    metrics.inc_reviews(status)
    text = metrics.render()
    label = "a" + BACKSLASH + QUOTE + "b" + BACKSLASH + BACKSLASH + "c" + BACKSLASH + "n" + "d"
    assert 'paper_review_reviews_total{status="%s"} 1' % label in text
    # 换行被转义成 \n 后仍是一行，否则整段 exposition 会被截断。
    assert len(_samples(text)) == len(_samples(metrics.render()))
    _assert_parseable(text)


def test_reset_keeps_only_the_seeded_zero_series():
    metrics.inc_reviews("完成")
    metrics.inc_reviews("临时")
    metrics.reset_metrics_for_tests()
    text = metrics.render()
    # 预置的「完成」零值行保留，其它状态在清理后不再出现。
    assert 'paper_review_reviews_total{status="完成"} 0' in text
    assert 'paper_review_reviews_total{status="临时"}' not in text


def test_auth_counter_success_and_failure_tracked_separately():
    # 原断言只验「auth_total 族在文本里」；本版接上 inc_auth 后必须验数值：
    # 成功失败各算各的，互不影响。
    metrics.reset_metrics_for_tests()
    text = metrics.render()
    assert 'paper_review_auth_total{result="success"} 0' in text
    assert 'paper_review_auth_total{result="failure"} 0' in text
    metrics.inc_auth(True)
    metrics.inc_auth(True)
    metrics.inc_auth(False)
    text = metrics.render()
    assert 'paper_review_auth_total{result="success"} 2' in text
    assert 'paper_review_auth_total{result="failure"} 1' in text
    metrics.reset_metrics_for_tests()
    text = metrics.render()
    assert 'paper_review_auth_total{result="success"} 0' in text
    assert 'paper_review_auth_total{result="failure"} 0' in text
    _assert_parseable(text)
