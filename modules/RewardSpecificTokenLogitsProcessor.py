from transformers import LogitsProcessor
import torch

class RewardSpecificTokenLogitsProcessor(LogitsProcessor):
    def __init__(self, tokenizer, reward_tokens, reward_value):
        super().__init__()
        self.tokenizer = tokenizer
        # Convert each token in the reward_tokens list to its token ID
        self.reward_token_ids = [tokenizer.encode(token, add_special_tokens=False)[0] for token in reward_tokens]
        self.reward_value = reward_value  # The value to increase logits for these tokens

    def __call__(self, input_ids, scores):
        # For each token ID in reward_token_ids, increase its logits across all positions
        for token_id in self.reward_token_ids:
            # Create a mask for the entire vocabulary and apply the reward mask to scores
            reward_mask_full_vocab = torch.zeros(scores.shape[1], device=scores.device)
            reward_mask_full_vocab[token_id] = self.reward_value
            scores += reward_mask_full_vocab

        return scores