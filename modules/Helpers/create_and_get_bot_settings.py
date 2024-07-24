import os
from modules.Helpers.BotSettings.BotSettingsConfig import BotSettingsConfig
from modules.Helpers.BotSettings.BotSettingsFirebase import BotSettingsFirebase

from typing import TYPE_CHECKING

from modules.Helpers.LogHelpers import LogHelpers

if TYPE_CHECKING:
    from modules.Helpers.Helpers import Helpers
    from modules.Logger import Logger


def get_bot_settings(helper: "Helpers", logger: "Logger"):
    log_helper = LogHelpers()
    # Determine where to get the settings from
    botsettings_from = os.getenv("BOTSETTINGS_FROM", "CONFIG")
    use_default_botsettings = os.getenv("BOTSETTINGS_USE_DEFAULT_SETTINGS") == "True"
    log_helper.debug(logger, f"Getting botsettings from: {botsettings_from}")
    log_helper.debug(logger, f"Use default botsettings: {use_default_botsettings}")

    if botsettings_from == "CONFIG":
        botsettings = BotSettingsConfig(helper)
    elif botsettings_from == "FIREBASE":
        botsettings = BotSettingsFirebase(logger)
    else:
        log_helper.debug(
            logger,
            f"Unknown botsettings source: {botsettings_from}. Falling back to CONFIG.",
        )
        botsettings = BotSettingsConfig(helper)

    # Load the values
    if use_default_botsettings:
        botsettings.load_default_settings()
    else:
        botsettings.load_settings()

    return botsettings
