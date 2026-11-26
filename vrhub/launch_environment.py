# SPDX-License-Identifier: GPL-3.0-only
"""Keep preview XDG isolation out of normal game launch subprocesses."""
import os

_KEYS = ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME")
_host = None


def capture_host_xdg():
    """Capture the original host environment once, before preview isolation."""
    global _host
    if _host is None:
        _host = {key: os.environ.get(key) for key in _KEYS}


def host_config_home():
    return os.environ.get("XDG_CONFIG_HOME") if _host is None else _host["XDG_CONFIG_HOME"]


def child_environment():
    env = dict(os.environ)
    for key, value in (_host or {}).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return env


def subprocess_kwargs():
    return {} if _host is None else {"env": child_environment()}
