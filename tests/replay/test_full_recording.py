import json
from pathlib import Path

import duan_app.crawl_service as crawl_service
import duan_app.documents as documents
import duan_app.fetcher as fetcher
from duan_app.config import load_sites_config
from verification.record_replay_parity import ResponseStore, run_sites, serialize_results


ROOT = Path(__file__).parents[2]


def test_all_sites_match_the_frozen_real_response_contract(monkeypatch) -> None:
    fixture = ROOT / "tests" / "fixtures" / "full-replay"
    store = ResponseStore(fixture, record=False)
    def replay_fetch(url, timeout, verify_ssl):
        return store.replay_call("fetch", url, fetcher)

    def replay_render(url, timeout, verify_ssl):
        return store.replay_call("render", url, fetcher)
    monkeypatch.setattr(fetcher, "fetch_text", replay_fetch)
    monkeypatch.setattr(documents, "fetch_text", replay_fetch)
    monkeypatch.setattr(documents, "render_page_text", replay_render)
    monkeypatch.setattr(fetcher.time, "sleep", lambda *_args, **_kwargs: None)

    sites = load_sites_config(ROOT / "sites.json")
    actual = json.loads(
        json.dumps(serialize_results(run_sites(crawl_service, sites, 202, 8)), ensure_ascii=False)
    )
    expected = json.loads((fixture / "expected-results.json").read_text(encoding="utf-8"))

    assert len(actual) == len(expected) == 150
    assert [item["site"] for item in actual] == [item["site"] for item in expected]
    unexpected_matches = []
    for current, previous in zip(actual, expected):
        current_matches = [
            (item["issue"], item["value"], item["position"])
            for item in current["matches"]
        ]
        previous_matches = [
            (item["issue"], item["value"], item["position"])
            for item in previous["matches"]
        ]
        unexpected = set(current_matches) - set(previous_matches)
        if unexpected:
            unexpected_matches.append((current["site"]["name"], sorted(unexpected)))
        current_sequence = current["cache_record"]["sequence"]
        assert len(current_sequence) <= 10
        assert len({int(item["period"]) for item in current_sequence}) == len(current_sequence)
        for item in current_sequence:
            assert 0 < int(item["period"])
            assert item["values"]
            assert all(value in {f"{number}段" for number in range(1, 8)} for value in item["values"])
        for match in current["matches"]:
            assert match["source_url"]
            assert match["document_type"] != "unknown"
            assert match["block_id"]
            assert match["anchor"]
    assert not unexpected_matches, "\n".join(map(str, unexpected_matches))
    assert store.usage()["unconsumed"] == {}
