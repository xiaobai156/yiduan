import duan_crawler as crawler


def candidate(issue: int, value: str, position: int, order: int = 0) -> crawler.Candidate:
    return crawler.Candidate(issue, str(issue), value, "站点", "片段", 100, order, position)


def test_top_and_bottom_use_page_position() -> None:
    candidates = [
        candidate(202, "2段", 10),
        candidate(201, "3段", 20),
        candidate(200, "4段", 30),
        candidate(199, "5段", 40),
    ]

    top, top_reason = crawler.scoped_candidates(candidates, {202}, "top")
    bottom, bottom_reason = crawler.scoped_candidates(candidates, {199}, "bottom")

    assert top_reason == ""
    assert [item.issue for item in top] == [202, 201, 200]
    assert bottom_reason == ""
    assert [item.issue for item in bottom] == [201, 200, 199]


def test_conflicting_values_for_same_issue_fail_closed() -> None:
    site = crawler.Site("冲突站", "https://example.test", "top")
    candidates = [candidate(202, "2段", 10), candidate(202, "7段", 11)]

    matches = crawler.find_matches_from_candidates(candidates, {202}, site)
    reasons = crawler.candidate_conflict_issue_reasons(candidates, {202})

    assert matches == []
    assert reasons == {202: "同一期高可信候选冲突[2段、7段]"}
