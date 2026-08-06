import json
import base64
import gzip
import zlib
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from duan_app import config, documents, fetcher, validation
from duan_app.config import load_sites_config
from duan_app.crawl_service import process_site
from duan_app.domain import Candidate, Site, SiteResult
from duan_app.parsing.engine import (
    has_body_locator,
    has_invalid_duan_value,
    has_result_keyword,
    is_strict_segment,
    iter_issue_focus_texts,
    iter_issue_segments,
    iter_search_texts,
    score_segment,
    table_signature_count,
    title_in_segment,
    trim_segment,
    values_in_segment,
)
from duan_app.parsing.profiles import load_site_profiles
from duan_app.parsing.profiles import stable_site_id
from duan_app.persistence import outputs
from duan_app.selection import (
    candidate_window,
    candidate_window_issue_reasons,
    candidate_conflict_issue_reasons,
    ordered_candidate_groups,
    pick_nearest_candidate,
    strict_candidate_window_required,
    values_for_cache_issue,
)
from duan_app.text_utils import (
    compact_line,
    decode_bytes,
    decompress_bytes,
    html_to_text,
    number_to_int,
    strip_hidden_html_blocks,
)


ROOT = Path(__file__).parents[2]


def make_candidate(issue: int, value: str, position: int, order: int = 0) -> Candidate:
    return Candidate(issue, str(issue), value, "测试站", "202期 [绝杀一段] 杀 [2段] 开 准", 100, order, position)


def make_result(site: Site, matches: list[Candidate], fail_line: str | None = None) -> SiteResult:
    return SiteResult(1, site, matches, fail_line, "OK" if matches else "MISS")


def test_config_loads_aliases_and_rejects_duplicate_identity(tmp_path: Path) -> None:
    valid_path = tmp_path / "valid.json"
    valid_path.write_text(
        json.dumps(
            [
                {"name": "甲", "url": "https://example.test/topic/1.html", "region": "尾部", "retry": 3},
                {"name": "乙", "url": "https://example.test/read.php?tid=2", "pick": "上"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    sites = load_sites_config(valid_path)
    assert [site.pick for site in sites] == ["bottom", "top"]
    assert sites[0].retry == 3
    assert config.topic_key_from_url(sites[0].url) == "1"
    assert config.topic_key_from_url(sites[1].url) is None
    assert config.normalize_pick("未知") == "未知"

    duplicate_cases = [
        ([{"name": "甲", "url": "https://a.test", "pick": "top"}, {"name": "甲", "url": "https://b.test", "pick": "top"}], "目录名重复"),
        ([{"name": "甲", "url": "https://a.test/topic/1.html", "pick": "top"}, {"name": "乙", "url": "https://b.test/topic/1.html", "pick": "top"}], "topic 重复"),
        ([{"name": "甲", "url": "https://a.test", "pick": "side"}], "pick 只能"),
        ([{"name": "甲", "url": "https://a.test", "pick": "top", "retry": "x"}], "retry 必须"),
    ]
    for payload, expected in duplicate_cases:
        path = tmp_path / f"{len(list(tmp_path.iterdir()))}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(ValueError, match=expected):
            load_sites_config(path)

    canonical_duplicate = [
        {"name": "甲", "url": "HTTPS://EXAMPLE.TEST:443/read.php?tid=1", "pick": "top"},
        {"name": "乙", "url": "https://example.test/read.php?tid=1", "pick": "top"},
    ]
    canonical_path = tmp_path / "canonical-duplicate.json"
    canonical_path.write_text(json.dumps(canonical_duplicate, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="URL 重复"):
        load_sites_config(canonical_path)


def test_config_default_paths_and_profile_fail_closed(tmp_path: Path) -> None:
    missing_sites = tmp_path / "missing-sites.json"
    sites = load_sites_config(missing_sites)
    assert len(sites) == len(config.DEFAULT_SITES)
    assert missing_sites.exists()
    result_dir = config.default_result_dir(tmp_path)
    failure_dir = config.default_failure_result_dir(tmp_path)
    assert result_dir.exists()
    assert failure_dir.exists()
    assert config.resolve_failure_path(None, failure_dir, "202") == failure_dir / "202期-段-失败.txt"
    assert config.resolve_failure_path("C:/elsewhere/result.txt", failure_dir, "202") == failure_dir / "result.txt"

    formal_sites = load_sites_config(ROOT / "sites.json")
    payload = json.loads((ROOT / "site_profiles.json").read_text(encoding="utf-8-sig"))
    payload["sites"][0]["name_anchors"] = []
    profile_path = tmp_path / "profiles.json"
    profile_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="名称锚点"):
        load_site_profiles(profile_path, formal_sites)


def test_engine_strict_parsing_and_boundaries() -> None:
    valid = "202期 [绝杀一段] 杀 [2段] 开 准"
    invalid = "202期 [绝杀一段] 杀 [8段] 开 准"
    assert has_result_keyword(valid)
    assert has_body_locator(valid)
    assert values_in_segment(valid) == ["2段"]
    assert has_invalid_duan_value(invalid)
    assert values_in_segment(invalid) == []
    assert is_strict_segment(valid)
    assert not is_strict_segment("202期 绝杀一段 2段")
    assert values_in_segment("202期 [绝杀一段] 杀 [2段][3段] 开 准") == ["2段"]
    assert is_strict_segment("202期 [绝杀一段] 杀 [2段][3段] 开 准")
    assert values_in_segment("202期 [1,2,3,4,5,6段]", allow_multi_duan=True) == ["7段"]
    assert values_in_segment("202期 [1,2段]", allow_multi_duan=True) == ["1段", "2段"]
    assert values_in_segment("202期 [绝杀一段] 222段", allow_repeated_duan=True) == ["2段"]
    assert has_invalid_duan_value("没有目标数据") is False
    assert table_signature_count("1段: 01 02 03") == 1
    assert trim_segment(valid + " 1段 2段", 220) == valid
    assert title_in_segment("202期【目标站】[绝杀一段] 杀 [2段] 开 准", "回退") == "目标站"
    assert title_in_segment("202期 杀 [2段] 开 准", "回退") == "回退"
    assert score_segment(valid, ["2段"]) > 0
    assert list(iter_issue_segments("202期 [绝杀一段] 杀 [2段] 开 准\n201期 [绝杀一段] 杀 [3段] 开 准", {201}))[0][0] == 201
    assert list(iter_issue_focus_texts("202期 [绝杀一段] 杀 [2段] 开 准", {202}))
    assert list(iter_search_texts("<p>202期</p><script>旧数据</script>")) == ["202期"]


def test_profile_contract_checks_all_identity_fields(tmp_path: Path) -> None:
    site = Site("甲", "https://example.test/topic/1.html", "top")
    base = {
        "name": site.name,
        "url": site.url,
        "pick": site.pick,
        "site_id": stable_site_id(site),
        "name_anchors": [site.name],
        "candidate_window": 3,
        "record_id_required": False,
    }
    valid_path = tmp_path / "valid-profile.json"
    valid_path.write_text(json.dumps({"sites": [base]}, ensure_ascii=False), encoding="utf-8")
    assert load_site_profiles(valid_path, [site])[site.name]["site_id"] == base["site_id"]

    cases = [
        ("url", "URL 不一致"),
        ("site_id", "稳定 ID 不一致"),
        ("candidate_window", "候选窗口不一致"),
        ("record_id_required", "文章 ID 边界不一致"),
    ]
    for field, expected in cases:
        payload = dict(base)
        payload[field] = "wrong" if field != "candidate_window" else 4
        path = tmp_path / f"{field}.json"
        path.write_text(json.dumps({"sites": [payload]}, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(ValueError, match=expected):
            load_site_profiles(path, [site])

    duplicate = {"sites": [base, dict(base)]}
    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text(json.dumps(duplicate, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="目录名重复"):
        load_site_profiles(duplicate_path, [site])


def encoded(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def article_payload(record_id: str = "target", name: str = "目标站") -> str:
    record = {
        "id": record_id,
        "authorNickname": name,
        "title": encoded("202期 [绝杀一段] 目标标题"),
        "html": encoded("202期 [绝杀一段] 杀 [2段] 开 准"),
        "formSections": [{"type": "mainarticle", "name": "主栏目"}],
    }
    return json.dumps({"data": [record]}, ensure_ascii=False)


def test_selection_direction_groups_and_conflict_rules() -> None:
    candidates = [
        make_candidate(202, "2段", 10),
        make_candidate(202, "2段", 10, 1),
        make_candidate(201, "3段", 20),
        make_candidate(200, "4段", 30),
        make_candidate(199, "5段", 40),
    ]
    assert pick_nearest_candidate([], "top") is None
    assert pick_nearest_candidate(candidates, "top").issue == 202
    assert pick_nearest_candidate(candidates, "bottom").issue == 199
    assert len(ordered_candidate_groups(candidates, "top")) == 4
    assert len(ordered_candidate_groups(candidates, "bottom")) == 4
    assert values_for_cache_issue(candidates, 202, "top") == ["2段"]
    assert values_for_cache_issue(candidates, 198, "top") == []
    assert candidate_window(candidates, "top") == candidates[:3]
    assert candidate_window(candidates, "bottom") == candidates[-3:]
    assert strict_candidate_window_required([make_candidate(202, "2段", 1)]) is False
    assert strict_candidate_window_required([make_candidate(202, "2段", 1), make_candidate(202, "3段", 2)]) is True
    assert candidate_conflict_issue_reasons(candidates, {202}) == {}
    conflict = candidates + [make_candidate(202, "7段", 11)]
    assert candidate_conflict_issue_reasons(conflict, {202}) == {202: "同一期高可信候选冲突[2段、7段]"}
    assert candidate_window_issue_reasons(candidates, {198}, "top")[198].startswith("顶部最新")
    assert candidate_window_issue_reasons([], {202}, "top") == {}


def test_validation_reason_matrix_and_source_diagnostics() -> None:
    state = validation.new_issue_state()
    assert validation.reason_from_issue_state(state) == "无期数"
    state["issue"] = True
    assert validation.reason_from_issue_state(state) == "无定位"
    state["locator"] = True
    assert validation.reason_from_issue_state(state) == "无结果词"
    state["table"] = True
    assert validation.reason_from_issue_state(state) == "段位表"
    state["keyword"] = True
    assert validation.reason_from_issue_state(state) == "无开字"
    state["open"] = True
    assert validation.reason_from_issue_state(state) == "无对错"
    state["status"] = True
    assert validation.reason_from_issue_state(state) == "表干扰"
    state["invalid"] = True
    assert validation.reason_from_issue_state(state) == "段数越界"
    state["invalid"] = False
    assert validation.reason_from_issue_state(state) == "表干扰"
    state["table"] = False
    assert validation.reason_from_issue_state(state) == "无段数"
    state["value"] = True
    assert validation.reason_from_issue_state(state) == "数量错"
    state["single"] = True
    assert validation.reason_from_issue_state(state) == "不合规"

    site = Site("测试站", "https://example.test", "top")
    reasons = validation.diagnose_issue_reasons(["202期 [绝杀一段] 杀 [2段] 开 准"], {202}, site)
    assert 202 in reasons
    assert validation.summarize_issue_reasons({202: "无段数"}, {202}) == "无段数"
    assert "202期" in validation.summarize_issue_reasons({202: "无段数", 201: "无期数"}, {201, 202})
    assert validation.explicit_failure_reason(" ；无期数； ") == "无期数"
    assert validation.explicit_failure_reason(None) == "未找到符合严格规则的结果"
    assert validation.source_failure_reason(["帖子不存在"], []) == "帖子不存在"
    assert validation.source_failure_reason([], ["/api/proxy/a 404"]) == "接口404不存在"
    assert validation.source_failure_reason([], ["/api/proxy/a 403"]) == "接口403拒绝访问"
    assert validation.issue_numbers_in_documents(["202期、201期"] ) == {201, 202}


def test_outputs_format_failures_and_cache_isolation(tmp_path: Path) -> None:
    site = Site("测试站", "https://example.test/topic/123.html", "top")
    candidate = make_candidate(202, "2段", 1)
    success = make_result(site, [candidate])
    partial = SiteResult(2, site, [candidate], None, "OK", {201: "无期数"})
    failure = make_result(site, [], "202期 测试站 https://example.test 无期数")
    success_lines, fail_lines, counts = outputs.build_output_lines([success, partial, failure, None], {201, 202}, 3)
    assert "2段 测试站" in success_lines[0]
    assert len(fail_lines) == 3
    assert all(
        field in fail_lines[-1]
        for field in ("方向: top", "期数: 201、202", "阶段: 指定期数校验", "原因:")
    )
    assert "位置:" not in fail_lines[-1]
    assert "实际期数:" not in fail_lines[-1]
    assert counts == {"2段": 2}
    assert outputs.count_output_lines([success, partial, failure], {201, 202}) == (2, 3)
    assert outputs.build_ranking_lines({}) == ["", "排行", "合计 0条"]
    assert outputs.build_ranking_lines({"2段": 2, "1段": 2})[3].startswith("第1名")
    assert outputs.default_name_from_url(site.url) == "example_topic_123"
    assert outputs.default_name_from_url("https://example.test/read.php?tid=8") == "example_tid_8"
    assert outputs.failure_reason_from_line("202期 x 打开失败[超时]") == "超时"
    assert outputs.failure_reason_from_line("202期 x 解析失败：x") == "解析失败"
    assert outputs.failure_reason_from_line("202期 x 最新3组内无指定期数") == "方向范围外"
    assert outputs.failure_reason_from_line(
        "失败 x https://x.test 方向:bottom 位置:尾部最新3个有效候选 期数:215期 "
        "实际期数:212期、213期、214期 阶段:校验 "
        "原因:尾部最新3个有效候选期数为[212期、213期、214期]，不含指定215期"
    ) == "方向范围外"
    assert outputs.failure_reason_from_line(
        "失败 x https://x.test 方向:top 位置:目标URL 期数:215期 实际期数:未读取 "
        "阶段:校验 原因:抓取内容中未发现指定期数"
    ) == "指定期数缺失"
    assert outputs.failure_reason_from_line("202期 x 接口404不存在") == "接口404不存在"
    assert outputs.is_network_retry_reason("HTTP 502")
    assert outputs.build_failure_stats_lines([])[-1] == "无失败"
    path = tmp_path / "out.txt"
    outputs.safe_write_text(path, "内容")
    assert path.read_text(encoding="utf-8-sig") == "内容"
    failure_path = tmp_path / "failure.txt"
    outputs.write_result_files(path, failure_path, ["2段 测试站"], ["202期 测试站 无期数"], {"2段": 1})
    assert failure_path.exists()
    outputs.write_result_files(path, failure_path, ["2段 测试站"], [], {"2段": 1})
    assert not failure_path.exists()


def test_failure_txt_uses_compact_blocks_and_category_stats(tmp_path: Path) -> None:
    failure_path = tmp_path / "216期-段-失败.txt"
    first = (
        "失败 站点甲 https://a.test/topic/1.html 方向: bottom 期数: 216 "
        "阶段: 指定期数校验 原因: 216期不是最后一条专属历史边界行"
    )
    second = (
        "失败 站点乙 https://b.test/topic/2.html 方向: bottom 期数: 216 "
        "阶段: 指定期数校验 原因: 216期不是最后一条专属历史边界行"
    )

    outputs.write_result_files(
        tmp_path / "success.txt",
        failure_path,
        [],
        [first, second],
        {},
    )

    assert failure_path.read_text(encoding="utf-8-sig").splitlines() == [
        first,
        "",
        second,
        "",
        "失败分类统计",
        "方向范围外 2条",
    ]


def test_failure_txt_line_contains_direction_location_period_and_specific_reason() -> None:
    site = Site("边界站", "https://example.test/topic/528.html", "bottom")

    line = outputs.format_failure_line(
        site,
        {215},
        stage="校验",
        location="尾部最新3个有效候选",
        reason="尾部最新3个有效候选期数为[212期、213期、214期]，不含指定215期",
        actual_issues=[212, 213, 214],
    )

    assert line == (
        "失败 边界站 https://example.test/topic/528.html 方向:bottom "
        "位置:尾部最新3个有效候选 期数:215期 实际期数:212期、213期、214期 "
        "阶段:校验 原因:尾部最新3个有效候选期数为[212期、213期、214期]，不含指定215期"
    )


def test_process_site_reports_actual_bottom_window_in_failure_txt(monkeypatch: pytest.MonkeyPatch) -> None:
    import duan_app.crawl_service as service

    site = Site("边界站", "https://example.test/topic/528.html", "bottom")
    candidates = [
        make_candidate(212, "2段", 10),
        make_candidate(213, "3段", 20),
        make_candidate(214, "4段", 30),
    ]
    monkeypatch.setattr(service, "collect_documents", lambda *args, **kwargs: (["正文"], []))
    monkeypatch.setattr(service, "collect_candidates", lambda *args, **kwargs: candidates)

    result = process_site(1, site, 5, True, {215}, "215")

    assert result.fail_line is not None
    assert "方向:bottom" in result.fail_line
    assert "位置:尾部最新3个有效候选" in result.fail_line
    assert "期数:215期" in result.fail_line
    assert "实际期数:212期、213期、214期" in result.fail_line
    assert "原因:尾部最新3个有效候选期数为[212期、213期、214期]，不含指定215期" in result.fail_line
    assert "不合规" not in result.fail_line


def test_outputs_error_matrix_and_slow_memory(tmp_path: Path) -> None:
    assert outputs.parse_issue_range("094-096, 100")[0] == [94, 95, 96, 100]
    with pytest.raises(ValueError, match="不能为空"):
        outputs.parse_issue_range("")
    with pytest.raises(ValueError, match="格式不对"):
        outputs.parse_issue_range("abc")
    assert outputs.duan_sort_value("无段") == 999
    assert outputs.format_progress_line(0, 0, 0, 0, 1.25, Site("甲", "https://a.test", "top")).startswith("[进度 0/0 0%")

    assert outputs.classify_open_error(HTTPError("https://a.test", 404, "missing", {}, None)) == "HTTP 404"
    assert outputs.classify_open_error(outputs.CurlFetchError(60, "certificate verify failed")) == "SSL握手失败"
    assert outputs.classify_open_error(outputs.CurlFetchError(1, "returned error: 502")) == "HTTP 502"
    assert outputs.classify_open_error(outputs.CurlFetchError(1, "connection refused")) == "curl连接失败"
    assert outputs.classify_open_error(TimeoutError("超时")) == "超时"
    assert outputs.classify_open_error(URLError("timed out")) == "超时"
    assert outputs.classify_open_error(OSError(10054, "reset")) == "远端断开"
    assert outputs.classify_open_error(OSError("权限不足")) == "访问被拦截"
    assert outputs.classify_open_error(RuntimeError("SSL error")) == "SSL握手失败"
    assert outputs.classify_open_error(RuntimeError("other")) == "未知打开失败"

    reason_lines = [
        ("候选冲突", "候选冲突"),
        ("近10期缓存冲突", "近10期缓存历史冲突"),
        ("最近 2 期不符", "期数不符"),
        ("帖子不存在", "帖子不存在"),
        ("脚本加载失败", "脚本加载失败"),
        ("202期无定位", "无定位"),
        ("202期无结果词", "无结果词"),
        ("202期无开字", "无开字"),
        ("202期无对错", "无对错"),
        ("202期段数越界", "段数越界"),
        ("202期表干扰", "表干扰"),
        ("202期无段数", "无段数"),
        ("202期数量错", "数量错"),
        ("202期不合规", "不合规"),
    ]
    for line, expected in reason_lines:
        assert outputs.failure_reason_from_line(line) == expected
    assert outputs.failure_reason_from_line("202期未知内容") == "未分类失败[202期未知内容]"
    assert outputs.build_failure_stats([line for line, _ in reason_lines])

    memory_path = tmp_path / "slow.json"
    memory_path.write_text("[]", encoding="utf-8")
    assert outputs.load_slow_site_memory(memory_path) == {}
    site = Site("慢站", "https://slow.test", "top")
    assert outputs.is_slow_site(site, {site.url: {"fail_streak": "bad"}}) is False
    outputs.update_slow_site_memory(
        memory_path,
        [
            make_result(site, [make_candidate(202, "2段", 1)]),
            SiteResult(2, site, [], "202期 慢站 打开失败[超时]", "MISS"),
            None,
        ],
    )
    assert json.loads(memory_path.read_text(encoding="utf-8-sig"))[site.url]["fail_streak"] == 1


def test_text_utils_encoding_and_compression_edges() -> None:
    assert html_to_text("<div>正文</div><script>旧</script>") == "正文"
    assert strip_hidden_html_blocks("<style>旧</style>正文").strip() == "正文"
    assert compact_line("a" * 20, 10).endswith("...")
    assert [number_to_int(value) for value in ("十", "十一", "二十", "二十三")] == [10, 11, 20, 23]
    assert number_to_int("无") is None
    assert decode_bytes("中文".encode("gb18030"), None) == "中文"
    gzip_bytes = gzip.compress("正文".encode("utf-8"))
    assert decompress_bytes(gzip_bytes, {"Content-Encoding": "gzip"}) == "正文".encode("utf-8")
    zlib_bytes = zlib.compress("正文".encode("utf-8"))
    assert decompress_bytes(zlib_bytes, {"Content-Encoding": "deflate"}) == "正文".encode("utf-8")
    assert html_to_text("<p>跨行</p>") == "跨行"


def test_fetcher_helpers_and_documents_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    assert fetcher.is_placeholder_document("")
    assert fetcher.is_placeholder_document("OK")
    assert not fetcher.is_placeholder_document("正文")
    assert "_=" in fetcher.cache_busted_url("https://example.test")
    assert "&_=" in fetcher.cache_busted_url("https://example.test?a=1")
    assert fetcher.build_ssl_contexts(True) == [None]
    assert fetcher.build_ssl_contexts(False)
    assert documents.should_fetch_script("https://example.test/upload/script/x.js", "https://example.test/a")
    assert documents.should_fetch_script("https://xia01.cosds.ahsccn.com/upload/script/x.js", "https://example.test/a")
    assert not documents.should_fetch_script("https://evil.test/x.js", "https://example.test/a")
    assert documents.should_fetch_frame("https://example.test/main/bbs/x", "https://example.test/a")
    assert not documents.should_fetch_frame("https://evil.test/main/bbs/x", "https://example.test/a")
    listing = '<a href="topic/1.html">202期【逍遥浪子】绝杀一段☆实力见证</a>'
    assert documents.xiaoyao_detail_urls(listing, "https://example.test/home", {202}) == ["https://example.test/topic/1.html"]

    calls: list[str] = []

    def fake_page(*args: object) -> str:
        calls.append("page")
        return '<html><script src="/script.js"></script><iframe src="/main/bbs/frame"></iframe>202期 [绝杀一段] 杀 [2段] 开 准</html>'

    def fake_text(url: str, *args: object) -> str:
        calls.append(url)
        if url.endswith("script.js"):
            return "201期 [绝杀一段] 杀 [3段] 开 准"
        return "200期 [绝杀一段] 杀 [4段] 开 准"

    result, errors = documents.collect_documents(
        "https://example.test/topic/1.html",
        5,
        True,
        fetch_page_text_fn=fake_page,
        fetch_text_fn=fake_text,
    )
    assert len(result) == 3
    assert errors == []
    assert calls[0] == "page"


def test_dynamic_document_api_and_legacy_fallback_paths() -> None:
    api_url = "https://example.test/api"
    manager_url = "https://example.test/article/manager/target?url=x"
    docs, errors = documents.collect_documents(
        manager_url,
        5,
        True,
        api_url=api_url,
        site_name="目标站",
        pick="top",
        fetch_text_fn=lambda *args: article_payload(),
    )
    assert len(docs) == 1
    assert errors == []

    bad_manager_docs, bad_manager_errors = documents.collect_documents(
        manager_url,
        5,
        True,
        api_url=api_url,
        site_name="目标站",
        pick="top",
        fetch_text_fn=lambda *args: (_ for _ in ()).throw(RuntimeError("blocked")),
    )
    assert bad_manager_docs == []
    assert len(bad_manager_errors) == 1

    admin_url = "https://example.test/article/admin/target?url=x"
    calls: list[str] = []

    def legacy_fetch(url: str, *args: object) -> str:
        calls.append(url)
        if "manager-articles" in url:
            raise HTTPError(url, 404, "missing", {}, None)
        return article_payload()

    admin_docs, admin_errors = documents.collect_documents(
        admin_url,
        5,
        True,
        fetch_text_fn=legacy_fetch,
        site_name="目标站",
        pick="top",
    )
    assert len(admin_docs) == 1
    assert len(admin_errors) == 1
    assert any("admin-articles" in url for url in calls)

    assert documents.documents_have_strict_context([], {202}, "目标站", "top") is False
    assert documents.documents_have_strict_context(["202期 [绝杀一段] 杀 [2段] 开 准"], {202}, "目标站", "top") is True


def test_process_site_success_failure_network_and_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    import duan_app.crawl_service as service

    site = Site("测试站", "https://example.test", "top")
    candidate = make_candidate(202, "2段", 1)
    monkeypatch.setattr(service, "collect_documents", lambda *args, **kwargs: (["正文"], []))
    monkeypatch.setattr(service, "collect_candidates", lambda *args, **kwargs: [candidate])
    monkeypatch.setattr(service, "find_matches_from_candidates", lambda *args, **kwargs: [candidate])
    result = process_site(1, site, 5, True, {202}, "202")
    assert result.matches == [candidate]
    assert result.fail_line is None

    monkeypatch.setattr(service, "collect_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(service, "find_matches_from_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(service, "diagnose_issue_reasons", lambda *args, **kwargs: {202: "无期数"})
    failed = process_site(1, site, 5, True, {202}, "202")
    assert failed.fail_line and "原因:抓取内容中未发现指定期数" in failed.fail_line
    assert "方向:top" in failed.fail_line
    assert "位置:" in failed.fail_line
    assert "期数:202期" in failed.fail_line
    assert failed.cache_record is not None
    assert failed.cache_record["status"] == "error"

    def raise_http(*args: object, **kwargs: object) -> object:
        raise HTTPError("https://example.test", 503, "down", {}, None)

    monkeypatch.setattr(service, "collect_documents", raise_http)
    opened = process_site(1, site, 5, True, {202}, "202")
    assert opened.fail_line and "HTTP 503" in opened.fail_line
    assert "位置:目标URL" in opened.fail_line
    assert "实际期数:未读取" in opened.fail_line
    assert "阶段:抓取" in opened.fail_line

    monkeypatch.setattr(service, "collect_documents", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad")))
    parsed = process_site(1, site, 5, True, {202}, "202")
    assert parsed.fail_line and "解析失败" in parsed.fail_line
    assert "方向:top" in parsed.fail_line
    assert "阶段:解析" in parsed.fail_line

    confirmed_site = Site("测试站", "https://example.test", "top", confirm=True)
    calls = {"count": 0}

    def alternating_matches(*args: object, **kwargs: object) -> list[Candidate]:
        calls["count"] += 1
        return [candidate] if calls["count"] == 1 else [make_candidate(202, "7段", 1)]

    monkeypatch.setattr(service, "collect_documents", lambda *args, **kwargs: (["正文"], []))
    monkeypatch.setattr(service, "collect_candidates", lambda *args, **kwargs: [candidate])
    monkeypatch.setattr(service, "find_matches_from_candidates", alternating_matches)
    conflict = process_site(1, confirmed_site, 5, True, {202}, "202")
    assert conflict.fail_line and "二次确认结果冲突" in conflict.fail_line
    assert "位置:目标期首次结果与二次抓取结果" in conflict.fail_line
    assert "阶段:二次确认" in conflict.fail_line
