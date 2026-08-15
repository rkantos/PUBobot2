# -*- coding: utf-8 -*-
import os
from types import SimpleNamespace
from pathlib import Path
from importlib.machinery import SourceFileLoader


# Load config.cfg if it exists
config_path = Path(__file__).resolve().parent.parent / "config.cfg"

if config_path.exists():
    try:
        cfg = SourceFileLoader("cfg", str(config_path)).load_module()
    except Exception as e:
        print("Failed to load config.cfg file!")
        raise e
else:
    print("config.cfg not found, using environment variables.")
    cfg = SimpleNamespace()


# Environment variables override config.cfg values
CONFIG_VARS = [
    "DC_BOT_TOKEN",
    "DC_CLIENT_ID",
    "DC_CLIENT_SECRET",
    "DC_INVITE_LINK",
    "DC_OWNER_ID",
    "DB_URI",
    "DB_CAPATH",
    "LOG_LEVEL",
    "COMMANDS_URL",
    "HELP",
    "STATUS",
]

for name in CONFIG_VARS:
    value = os.environ.get(name)

    if value is not None:
        setattr(cfg, name, value)


# Required configuration
for name in ["DC_BOT_TOKEN", "DB_URI"]:
    if not getattr(cfg, name, ""):
        raise RuntimeError(
            f"Required configuration '{name}' is not set "
            "in config.cfg or Railway environment variables."
        )


with open(Path(__file__).resolve().parent.parent / ".version", "r") as f:
    __version__ = f.read()
