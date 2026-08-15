# -*- coding: utf-8 -*-
import os
from types import SimpleNamespace
from pathlib import Path
from importlib.machinery import SourceFileLoader


config_path = Path(__file__).resolve().parent.parent / "config.cfg"


# Load config.cfg if available
if config_path.exists():
    try:
        cfg = SourceFileLoader("cfg", str(config_path)).load_module()
        cfg.USING_CONFIG_FILE = True
    except Exception as e:
        print("Failed to load config.cfg file!")
        raise e
else:
    print("config.cfg not found, using environment variables.")
    cfg = SimpleNamespace()
    cfg.USING_CONFIG_FILE = False


# Defaults used when config.cfg is not available
DEFAULT_CONFIG = {
    "WS_ENABLE": False,
    "LOG_LEVEL": "COMMANDS",
    "COMMANDS_URL": "https://github.com/Leshaka/PUBobot2/blob/main/COMMANDS.md#avaible-commands",
    "HELP": """PUBobot2 is a discord bot for pickup games organisation.
Web interface: <https://pubobot.leshaka.xyz/>.
Commands: https://github.com/Leshaka/PUBobot2/blob/main/COMMANDS.md.
If you need help with the bot feel free to join PUBobot-dev guild: <https://discord.gg/rjNt9nC>.
""",
    "STATUS": "PlussaPlussa",
    "DB_CAPATH": "",
}


# Apply defaults without overwriting config.cfg values
for name, value in DEFAULT_CONFIG.items():
    if not hasattr(cfg, name):
        setattr(cfg, name, value)


# Environment variables override config.cfg/default values
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
    "WS_ENABLE",
]


for name in CONFIG_VARS:
    value = os.environ.get(name)

    if value is not None:
        # Convert boolean environment variables
        if name == "WS_ENABLE":
            value = value.lower() in ("1", "true", "yes", "on")

        setattr(cfg, name, value)


# Required configuration
for name in ["DC_BOT_TOKEN", "DB_URI"]:
    if not getattr(cfg, name, ""):
        raise RuntimeError(
            f"Required configuration '{name}' is not set "
            "in config.cfg or environment variables."
        )


with open(Path(__file__).resolve().parent.parent / ".version", "r") as f:
    __version__ = f.read()