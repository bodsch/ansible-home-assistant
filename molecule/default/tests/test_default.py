# coding: utf-8
from __future__ import annotations, unicode_literals

import json

import pytest
from helper.molecule import get_vars, infra_hosts

testinfra_hosts = infra_hosts(host_name="instance")


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
    home = get_vars.get("home_assistant_user", {}).get("home", "/opt/home-assistant")

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
