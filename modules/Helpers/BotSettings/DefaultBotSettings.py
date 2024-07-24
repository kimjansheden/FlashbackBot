class DefaultBotSettings:
    def __init__(self):
        self.minimum_new_tokens: int = 75
        self.temperature: float = 0.5
        self.do_sample: bool = True
        self.top_k: int = 40
        self.top_p: float = 0.7
        self.repetition_penalty: float = 2.0
        self.no_repeat_ngram_size: int = 2
        self.model_path: str = ""
        self.max_tokens: int = 256
        self.reward_tokens: list[str] = []
        self.special_tokens: list[str] = []

    def get_settings(self) -> dict:
        return {
            "minimum_new_tokens": self.minimum_new_tokens,
            "temperature": self.temperature,
            "do_sample": self.do_sample,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "repetition_penalty": self.repetition_penalty,
            "no_repeat_ngram_size": self.no_repeat_ngram_size,
            "max_tokens": self.max_tokens,
            "reward_tokens": self.reward_tokens,
            "special_tokens": self.special_tokens,
        }
