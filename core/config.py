# -*- coding: utf-8 -*-
import os
from importlib.machinery import SourceFileLoader

# Load config.cfg
try:
    cfg = SourceFileLoader('cfg', 'config.cfg').load_module()
except Exception as e:
    print("Failed to load config.cfg file!")
    raise e

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

with open('.version', 'r') as f:
    __version__ = f.read()
