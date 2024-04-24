from modules.Helpers.LogHelpers import LogHelpers
from modules.Model import Model
from modules.Logger import Logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.Helpers.Helpers import Helpers


def create_and_get_model(
    helper: "Helpers", file_handler, model_path = ""
):
    log_level = helper.config.get("Logging", "model_log_level", fallback="INFO")
    logger = Logger("Model Logger", "model_log.log", log_level, file_handler)
    log_helper = LogHelpers()
    log_helper.debug(logger, "model_path:", model_path)

    if not model_path:
        model_path = helper.config.get("Model", "model_path", fallback="")
        if not model_path:
            e_msg = "Error. model_path is empty. Please provide the path to your model."
            log_helper.error(logger, e_msg)
            raise RuntimeError(e_msg)

    max_tokens = helper.config.getint("Model", "max_tokens", fallback=256)
    special_tokens = helper.config.get("Model", "special_tokens", fallback="").split(
        ","
    )
    return Model(
        model_path,
        helper,
        max_tokens,
        special_tokens,
        file_handler,
        logger,
    )
