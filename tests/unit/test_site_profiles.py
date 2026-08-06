import json
from pathlib import Path

import pytest

from duan_app.config import load_sites_config
from duan_app.parsing.profiles import load_site_profiles


ROOT = Path(__file__).parents[2]


def test_every_formal_site_has_one_matching_profile() -> None:
    sites = load_sites_config(ROOT / "sites.json")
    profiles = load_site_profiles(ROOT / "site_profiles.json", sites)

    assert len(profiles) == len(sites) == 150
    assert set(profiles) == {site.name for site in sites}


def test_missing_profile_fails_closed(tmp_path: Path) -> None:
    sites = load_sites_config(ROOT / "sites.json")
    payload = json.loads((ROOT / "site_profiles.json").read_text(encoding="utf-8-sig"))
    payload["sites"] = payload["sites"][:-1]
    path = tmp_path / "site_profiles.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="缺少专属解析档案"):
        load_site_profiles(path, sites)


def test_profile_direction_mismatch_fails_closed(tmp_path: Path) -> None:
    sites = load_sites_config(ROOT / "sites.json")
    payload = json.loads((ROOT / "site_profiles.json").read_text(encoding="utf-8-sig"))
    payload["sites"][0]["pick"] = "bottom" if payload["sites"][0]["pick"] == "top" else "top"
    path = tmp_path / "site_profiles.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="方向不一致"):
        load_site_profiles(path, sites)
