from modules.Helpers.BotSettings.BotSettings import BotSettings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.Helpers.Helpers import Helpers


class BotSettingsConfig(BotSettings):
    def __init__(self, helper: "Helpers"):
        super().__init__()

        self.helper = helper

    def load_settings(self):
        print("self.helper.config:", self.helper.config.sections())
        self.minimum_new_tokens = self.helper.config.getint(
            "Model", "minimum_new_tokens"
        )
        self.temperature = self.helper.config.getfloat("Model", "temperature")
        self.do_sample = self.helper.config.getboolean("Model", "do_sample")
        self.top_k = self.helper.config.getint("Model", "top_k")
        self.top_p = self.helper.config.getfloat("Model", "top_p")
        self.repetition_penalty = self.helper.config.getfloat(
            "Model", "repetition_penalty"
        )
        self.no_repeat_ngram_size = self.helper.config.getint(
            "Model", "no_repeat_ngram_size"
        )
        self.model_path = self.helper.config.get("Model", "model_path")
        self.max_tokens = self.helper.config.getint("Model", "max_tokens", fallback=256)
        self.reward_tokens = self.helper.config.get(
            "Model", "reward_tokens", fallback=""
        ).split(",")
        self.special_tokens = self.helper.config.get(
            "Model", "special_tokens", fallback=""
        ).split(",")
