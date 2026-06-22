# coding: utf-8
from __future__ import annotations, unicode_literals

import json

import pytest
from helper.molecule import get_vars, infra_hosts

testinfra_hosts = infra_hosts(host_name="instance")


# --- helpers ---------------------------------------------------------------

def _onboarding(get_vars):
    return get_vars.get("home_assistant_onboarding", {}) or {}


def _home(get_vars):
    return get_vars.get("home_assistant_user", {}).get("home", "/opt/home-assistant")


# --- base install ----------------------------------------------------------

@pytest.mark.parametrize("dirs", [
    "/opt/home-assistant",
])
def test_directories(host, dirs):
    d = host.file(dirs)
    assert d.is_directory


def test_files(host, get_vars):
    """
    """
    distribution = host.system_info.distribution
    home = _home(get_vars)

    files = [
        f"{home}/bin/hass",
        f"{home}/bin/uv",          # bundled with recent Home Assistant releases
    ]
    if distribution != "artix":
        files.append("/etc/default/home-assistant")

    print(files)

    for _file in files:
        assert host.file(_file).is_file


def test_user(host, get_vars):
    """
    """
    ha_user = get_vars.get("home_assistant_user", {})
    user = ha_user.get("owner", "home-assistant")
    group = ha_user.get("group", "home-assistant")
    home = ha_user.get("home", "/opt/home-assistant")

    assert host.group(group).exists
    assert host.user(user).exists
    assert group in host.user(user).groups
    assert host.user(user).home == home


def test_service(host):
    service = host.service("home-assistant")
    print(service)
    assert service.is_running
    assert service.is_enabled


def test_open_port(host):
    """
    """
    listen_address = "0.0.0.0:8123"

    service = host.socket(f"tcp://{listen_address}")
    assert service.is_listening


# --- headless onboarding (configured scenario) -----------------------------

def test_onboarding_storage(host, get_vars):
    """The owner/auth/onboarding storage files must be seeded."""
    onboarding = _onboarding(get_vars)
    if not onboarding.get("enabled"):
        pytest.skip("onboarding not enabled")

    home = _home(get_vars)
    for name in ("auth", "auth_provider.homeassistant", "onboarding"):
        assert host.file(f"{home}/.storage/{name}").is_file, f".storage/{name} missing"


def test_onboarding_owner(host, get_vars):
    """The configured owner must exist in the auth store as is_owner."""
    onboarding = _onboarding(get_vars)
    if not onboarding.get("enabled"):
        pytest.skip("onboarding not enabled")

    home = _home(get_vars)
    username = onboarding.get("owner", {}).get("username")

    auth = json.loads(host.file(f"{home}/.storage/auth").content_string)
    assert any(u.get("is_owner") for u in auth["data"]["users"]), \
        "no is_owner user in auth store"
    assert any(c["data"].get("username") == username for c in auth["data"]["credentials"]), \
        f"no homeassistant credential for username {username!r}"


def test_onboarding_done(host, get_vars):
    """All onboarding steps must be marked done so the wizard is skipped."""
    onboarding = _onboarding(get_vars)
    if not onboarding.get("enabled"):
        pytest.skip("onboarding not enabled")

    home = _home(get_vars)
    data = json.loads(host.file(f"{home}/.storage/onboarding").content_string)
    assert "user" in data["data"]["done"]
    assert "core_config" in data["data"]["done"]


def test_access_token(host, get_vars):
    """When enabled, the long-lived access token file must exist (mode 0600)."""
    onboarding = _onboarding(get_vars)
    access_token = onboarding.get("access_token", {})
    if not (onboarding.get("enabled") and access_token.get("enabled")):
        pytest.skip("access token not enabled")

    home = _home(get_vars)
    dest = access_token.get("dest", f"{home}/.ansible_access_token")

    f = host.file(dest)
    assert f.is_file
    assert f.mode == 0o600
    # a JWT has exactly three base64url segments separated by dots
    assert f.content_string.count(".") == 2


def test_location_in_configuration(host, get_vars):
    """Location/units must end up in the homeassistant: block of the config."""
    onboarding = _onboarding(get_vars)
    location = onboarding.get("location", {})
    if not location:
        pytest.skip("no location configured")

    home = _home(get_vars)
    content = host.file(f"{home}/configuration.yaml").content_string
    assert "homeassistant:" in content
    if location.get("time_zone"):
        assert location["time_zone"] in content
