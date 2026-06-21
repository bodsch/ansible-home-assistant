# coding: utf-8
from __future__ import annotations, unicode_literals

import pytest
from helper.molecule import get_vars, infra_hosts, local_facts

testinfra_hosts = infra_hosts(host_name="instance")

# --- tests -----------------------------------------------------------------

# _facts = local_facts(host=host, fact="home-assistent")


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
    release = host.system_info.release

    print(f"distribution: {distribution}")
    print(f"release     : {release}")

    install_dir = "/opt/home-assistant"
    defaults_dir = "/etc/default"

    files = []
    files.append(f"{install_dir}/bin/hass")

    if install_dir:
        files.append(f"{install_dir}/bin/uv")
    if defaults_dir and not distribution == "artix":
        files.append(f"{defaults_dir}/home-assistant")

    print(files)

    for _file in files:
        f = host.file(_file)
        assert f.is_file


def test_user(host, get_vars):
    """
    """
    user = get_vars.get("ha_system_user", "home-assistant")
    group = get_vars.get("ha_system_group", "home-assistant")

    assert host.group(group).exists
    assert host.user(user).exists
    assert group in host.user(user).groups
    assert host.user(user).home == "/opt/home-assistant"


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
