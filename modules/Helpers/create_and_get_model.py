import json
import os
from modules.Helpers.LogHelpers import LogHelpers
from modules.Helpers.create_and_get_bot_settings import get_bot_settings
from modules.Model import Model
from modules.Logger import Logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.Helpers.Helpers import Helpers


def create_and_get_model(helper: "Helpers", file_handler, model_path=""):
    log_level = helper.config.get("Logging", "model_log_level", fallback="INFO")
    logger = Logger("Model Logger", "model_log.log", log_level, file_handler)
    log_helper = LogHelpers()
    log_helper.debug(logger, "model_path:", model_path)

    # Get the BotSettings
    bot_settings = get_bot_settings(helper, logger)
    bot_settings.print_settings()

    if not model_path:
        model_path = bot_settings.model_path
        if not model_path:
            e_msg = "Error. model_path is empty. Please provide the path to your model."
            log_helper.error(logger, e_msg)
            raise RuntimeError(e_msg)

    return Model(
        model_path,
        helper,
        bot_settings,
        file_handler,
        logger,
    )
