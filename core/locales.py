# -*- coding: utf-8 -*-
import gettext
import os


# Project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Compiled locale directory
LOCALES_DIR = os.path.join(BASE_DIR, "locales", "compiled")

locales = dict()


# Load compiled translations
if os.path.isdir(LOCALES_DIR):
    for locale_name in os.listdir(LOCALES_DIR):
        locale_path = os.path.join(LOCALES_DIR, locale_name)

        # Only process directories
        if not os.path.isdir(locale_path):
            continue

        try:
            t = gettext.translation(
                "all",
                localedir=LOCALES_DIR,
                languages=[locale_name]
            )

            locales[t.gettext("_lang")] = t.gettext

        except FileNotFoundError:
            # Ignore directories that don't contain a compiled
            # translation catalog.
            continue

else:
    print(f"Warning: locale directory not found: {LOCALES_DIR}")


# Add default English translation
t = gettext.NullTranslations()
locales["en"] = t.gettext