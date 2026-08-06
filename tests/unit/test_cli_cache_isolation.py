from pathlib import Path

import duan_app.cli as cli
from duan_app.domain import Candidate, Site, SiteResult


def make_success_result() -> SiteResult:
    site = Site("实时站", "https://example.test/live", "bottom")
    match = Candidate(
        215,
        "215",
        "3段",
        site.name,
        "215期[绝杀一段][3段]开:0000中",
        100,
        0,
        0,
        source_url=site.url,
        document_type="page",
        block_id="body",
        anchor=site.name,
    )
    return SiteResult(
        1,
        site,
        [match],
        None,
        "OK",
        cache_record={
            "name": site.name,
            "url": site.url,
            "pick": site.pick,
            "status": "ok",
            "period_count": 1,
            "sequence": [{"period": 215, "values": ["3段"]}],
        },
    )


def patch_single_site_run(monkeypatch, tmp_path: Path, result: SiteResult, events: list[str]) -> list[str]:
    site = result.site
    sites_path = tmp_path / "sites.json"
    sites_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(cli, "load_sites_config", lambda _path: [site])
    monkeypatch.setattr(cli, "load_site_profiles", lambda *_args: None)
    monkeypatch.setattr(cli, "load_slow_site_memory", lambda _path: {})
    monkeypatch.setattr(cli, "process_site", lambda *_args: result)
    monkeypatch.setattr(cli, "update_slow_site_memory", lambda *_args: events.append("health"))

    output_lines: list[str] = []

    def fake_write_result_files(_success, _fail, success_lines, failure_lines, _ranking):
        events.append("outputs")
        output_lines.extend(success_lines)
        output_lines.extend(failure_lines)

    monkeypatch.setattr(cli, "write_result_files", fake_write_result_files)
    return output_lines


def test_cache_conflict_cannot_change_realtime_output_and_runs_after_outputs(
    monkeypatch, tmp_path: Path
) -> None:
    result = make_success_result()
    events: list[str] = []
    output_lines = patch_single_site_run(monkeypatch, tmp_path, result, events)

    def fake_write_cache(*_args, **_kwargs):
        events.append("cache")
        return {
            "site_count": 1,
            "full_10_count": 0,
            "audit_count": 0,
            "error_count": 0,
            "conflicts": [{"name": result.site.name, "url": result.site.url}],
        }

    monkeypatch.setattr(cli, "write_recent_cache_file", fake_write_cache)

    exit_code = cli.main(
        [
            "-i",
            "215",
            "--sites",
            str(tmp_path / "sites.json"),
            "--success",
            str(tmp_path / "success.txt"),
            "--fail",
            str(tmp_path / "failure.txt"),
        ]
    )

    assert exit_code == 0
    assert output_lines == ["3段 实时站"]
    assert events == ["outputs", "health", "cache"]


def test_cache_write_failure_keeps_realtime_output_and_reports_failure(
    monkeypatch, tmp_path: Path
) -> None:
    result = make_success_result()
    events: list[str] = []
    output_lines = patch_single_site_run(monkeypatch, tmp_path, result, events)

    def fail_cache(*_args, **_kwargs):
        events.append("cache")
        raise OSError("测试失败")

    monkeypatch.setattr(cli, "write_recent_cache_file", fail_cache)

    exit_code = cli.main(
        [
            "-i",
            "215",
            "--sites",
            str(tmp_path / "sites.json"),
            "--success",
            str(tmp_path / "success.txt"),
            "--fail",
            str(tmp_path / "failure.txt"),
        ]
    )

    assert exit_code == 1
    assert output_lines == ["3段 实时站"]
    assert events == ["outputs", "health", "cache"]


def test_invalid_issue_returns_input_error(capsys) -> None:
    assert cli.main(["-i", "not-an-issue"]) == 2
    assert "输入错误：" in capsys.readouterr().err


def test_site_config_error_returns_input_error(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(cli, "load_sites_config", lambda _path: (_ for _ in ()).throw(ValueError("bad config")))

    assert cli.main(["-i", "215", "--sites", str(tmp_path / "sites.json")]) == 2
    assert "输入错误：bad config" in capsys.readouterr().err
