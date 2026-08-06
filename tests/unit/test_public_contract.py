from pathlib import Path

import duan_crawler as crawler


PUBLIC_NAMES = {
    "ArticleDocumentList",
    "ArticleRecordError",
    "Candidate",
    "CANDIDATE_WINDOW_LIMIT",
    "FULLWIDTH_DIGITS",
    "ISSUE_RE",
    "Site",
    "SiteResult",
    "WENJIN_DUAN_RE",
    "candidate_conflict_issue_reasons",
    "collect_candidates",
    "collect_documents",
    "compact_line",
    "fetch_page_text",
    "fetch_text",
    "find_matches_from_candidates",
    "has_result_keyword",
    "is_strict_segment",
    "iter_issue_segments",
    "iter_search_texts",
    "load_sites_config",
    "normalize_pick",
    "normalize_text",
    "render_page_text",
    "score_segment",
    "scoped_candidates",
    "site_section_anchor_terms",
    "values_in_segment",
}


def test_external_tool_public_contract_is_available() -> None:
    missing = sorted(name for name in PUBLIC_NAMES if not hasattr(crawler, name))
    assert missing == []


def test_formal_sites_are_unique_and_loadable() -> None:
    sites = crawler.load_sites_config(Path(__file__).parents[2] / "sites.json")
    names = [site.name for site in sites]
    urls = [site.url for site in sites]

    assert len(sites) == 150
    assert len(names) == len(set(names))
    assert len(urls) == len(set(urls))


def test_cli_help_remains_compatible() -> None:
    parser = crawler.build_parser()
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert {"-i", "--issues", "--workers", "--recent-cache", "--no-recent-cache"} <= option_strings
