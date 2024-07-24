from abc import ABC, abstractmethod
import json

from modules.Helpers.BotSettings.DefaultBotSettings import DefaultBotSettings


class BotSettings(ABC):
    def __init__(self):
        self.minimum_new_tokens: int = 0
        self.temperature: float = 0.0
        self.do_sample: bool = True
        self.top_k: int = 0
        self.top_p: float = 0.0
        self.repetition_penalty: float = 0.0
        self.no_repeat_ngram_size: int = 0
        self.model_path: str = ""
        self.max_tokens: int = 0
        self.reward_tokens: list[str] = []
        self.special_tokens: list[str] = []

    # If everything fails we can load this
    def load_default_settings(self):
        default_bot_settings = DefaultBotSettings()
        self.minimum_new_tokens = default_bot_settings.minimum_new_tokens
        self.temperature = default_bot_settings.temperature
        self.do_sample = default_bot_settings.do_sample
        self.top_k = default_bot_settings.top_k
        self.top_p = default_bot_settings.top_p
        self.repetition_penalty = default_bot_settings.repetition_penalty
        self.no_repeat_ngram_size = default_bot_settings.no_repeat_ngram_size
        self.model_path = default_bot_settings.model_path
        self.max_tokens = default_bot_settings.max_tokens
        self.reward_tokens = default_bot_settings.reward_tokens
        self.special_tokens = default_bot_settings.special_tokens

    @abstractmethod
    def load_settings(self):
        pass

    def print_settings(self):
        """Prints all settings."""
        print("Minimum new tokens:", self.minimum_new_tokens)
        print("Temperature:", self.temperature)
        print("Do sample:", self.do_sample)
        print("Top k:", self.top_k)
        print("Top p:", self.top_p)
        print("Repetition penalty:", self.repetition_penalty)
        print("No repeat ngram size:", self.no_repeat_ngram_size)
        print("Model path:", self.model_path)
        print("Max tokens:", self.max_tokens)
        print("Reward tokens:", self.reward_tokens)
        print("Special tokens:", self.special_tokens)

    def to_dict(self):
        return {
            "minimum_new_tokens": self.minimum_new_tokens,
            "temperature": self.temperature,
            "do_sample": self.do_sample,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "repetition_penalty": self.repetition_penalty,
            "no_repeat_ngram_size": self.no_repeat_ngram_size,
            "model_path": self.model_path,
            "max_tokens": self.max_tokens,
            "reward_tokens": self.reward_tokens,
            "special_tokens": self.special_tokens,
        }
    

