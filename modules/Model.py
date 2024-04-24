from datetime import datetime
import os
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig
import torch
from torch import Tensor
from modules.Helpers.FileHandler import FileHandler

from modules.Logger import Logger
from .RewardSpecificTokenLogitsProcessor import RewardSpecificTokenLogitsProcessor
from .Helpers.Helpers import Helpers
import re


class Model:
    def __init__(
        self,
        pretrained_model_name_or_path,
        helper: Helpers,
        max_tokens: int,
        special_tokens,
        file_handler: FileHandler,
        logger: Logger | None = None,
    ):
        """Load model and tokenizer"""
        self.helper = helper
        self.config = self.helper.config
        self.log_level = self.config["Logging"]["model_log_level"]
        if logger:
            # Use the provided Logger
            self.logger = logger
        else:
            # Create a default Model Logger
            self.logger = Logger(
                "Model Logger", "model_log.log", self.log_level, file_handler
            )
        self.path_to_model = pretrained_model_name_or_path
        self.max_tokens = max_tokens
        self.special_tokens = special_tokens
        self.device = (
            torch.device("mps")
            if torch.backends.mps.is_available()
            else torch.device("cpu")
        )
        self.logger.debug(f"Model Device: {self.device}")
        try:
            self.model_config = AutoConfig.from_pretrained(self.path_to_model)
            self.tokenizer = AutoTokenizer.from_pretrained(self.path_to_model)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.path_to_model, config=self.model_config
            ).to(self.device)
        except OSError as e:
            e_short = str(e).split('\n')[0]  # Extract first row of the error message
            error_message = f"Error loading model: {e_short}\nMake sure you have specified a valid path to your model."
            self.logger.error(error_message)
            raise ValueError(error_message) from None
        self.file_handler = file_handler
        self.script_dir = self.helper.file_helper.get_base_path(
            os.path.abspath(__file__), 2
        )
        self.posts_dir = os.path.join(self.script_dir, "posts")

        # Create instance of custom LogitsProcessor with words we want to encourage the model to use
        reward_tokens = [
            token for token in os.getenv("REWARD_TOKENS", "").split(",") if token
        ]
        self.logits_processor = RewardSpecificTokenLogitsProcessor(
            self.tokenizer, reward_tokens, 5.0
        )

        # In case we need to remove specific unwanted phrases from the inferred answer
        self.unwanted_phrases = os.getenv("UNWANTED_PHRASES", "").split(",")
        self.unwanted_phrases_literal = os.getenv("UNWANTED_PHRASES_LITERAL", "").split(
            ","
        )

    def generate_answer(self, post: dict) -> str:
        full_context, post_text = self._prepare_context(post)

        max_attempts = 5
        attempts = 0

        self._prepare_tokens()

        # Initial context includes the full context
        current_context = full_context

        # TEST
        # current_context = post_text

        # Formatted like training input – works badly
        # full_context = f"Username: {username}\nQuoted User: {quoted_user}\nQuoted Text: {quoted_text}\nPost Text: {post_text}"

        while attempts < max_attempts:
            input_ids, attention_mask, input_length = self._get_valid_input_ids(
                current_context, post_text
            )

            # Generate output from model
            output = self._generate_answer(input_ids, attention_mask, input_length)

            # Decode output to text and clean it
            cleaned_dataset = self._clean_dataset(output, input_ids)

            if not self._wrong_generation(cleaned_dataset, [self.unwanted_phrases]):
                # If the output is good, break the loop and return it
                break
            attempts += 1
            self.logger.debug(
                f"Unwanted pattern detected, regenerating... (attempt {attempts} of {max_attempts})"
            )

            # After 1-4 failed attempts, use only post_text for generation
            if attempts >= 1 and attempts < max_attempts:
                current_context = post_text

        if attempts == max_attempts:
            error_message = (
                f"Max attempts reached. Last generated text: {cleaned_dataset}"
            )
            self.logger.debug(error_message)
            raise RuntimeError(error_message)

        # Log conversation
        self._log_conversation(full_context, cleaned_dataset)

        return cleaned_dataset

    def _prepare_tokens(self):
        """
        Updates the model's token embeddings with special tokens.

        This method first updates the tokenizer with special tokens and resizes
        the model's token embeddings to accommodate the new tokens.

        Note:
            - Ensure that `self.special_tokens` is populated with the correct tokens before calling this method.
            - This method should be used during the initialization or update phases of the model where
            special tokens need to be integrated into the tokenizer.
        """
        # Update model's token embeddings with the special tokens
        # self.tokenizer.add_tokens(new_tokens=special_tokens) # Switch to this one if special_tokens behaves weirdly
        # self.tokenizer.add_tokens(new_tokens=special_tokens, special_tokens=True)
        # self.model.resize_token_embeddings(len(self.tokenizer))

        # Print token ID for each special token being used
        for token in self.special_tokens:
            token_id = self.tokenizer.convert_tokens_to_ids(token)
            self.logger.debug(f"Token: {token}, Token ID: {token_id}")

    def _log_conversation(self, full_context: str, cleaned_dataset: str) -> None:
        """
        Logs a conversation to a text file. The log includes timestamps, input data, and model output.

        This function constructs a path to a 'conversation_log.txt' file within a directory specified by 'self.posts_dir'.
        It ensures the file exists and then appends a formatted log entry with the current time, the input context (forum post),
        the output from the model (cleaned dataset), and a separator for readability.

        Parameters:
        - full_context (str): The full text of the forum post being processed.
        - cleaned_dataset (str): The output from the model after processing the input forum post.

        Returns:
        - None
        """
        conversation_path = os.path.join(self.posts_dir, "conversation_log.txt")
        self.helper.file_helper.create_file_if_not_exist(conversation_path, "")
        self.file_handler.write(
            conversation_path,
            mode="a",
            data=f"Time: {datetime.now()}\n\nInput Forum Post: {full_context}\n\nModel Output: {cleaned_dataset}\n{'-' * 50}\n\n",
        )

    def _clean_dataset(self, output: Tensor, input_ids: Tensor) -> str:
        """
        Processes the given output tensor by decoding it using a tokenizer, cleaning it up, 
        and removing unwanted phrases, including special tokens.

        The method first decodes the output tensor to text, starting from the position that matches the length of the input tensor.
        It trims the raw decoded text according to a specific pattern, and performs corrections like merging split parentheses.
        Unwanted phrases and special tokens are then removed, with options for escaping special characters and case insensitivity.

        Parameters:
            output (Tensor): The output tensor to be processed.
            input_ids (Tensor): The tensor representing input IDs used to align the start position for decoding.

        Returns:
            str: The cleaned and processed text after all transformations.
        """
        raw_output_text = self.tokenizer.decode(
            output[0][len(input_ids[0]) :], skip_special_tokens=True
        )

        self.logger.paranoid(f"raw_output_text before cleaning: {raw_output_text}")

        # Cut output for certain pattern
        cleaned_output_text = self.helper.trim_output(
            raw_output_text, pattern=r"\.\.\.+"
        )

        self.logger.paranoid(
            "cleaned_output_text after trim_output():", cleaned_output_text
        )

        # Further clean the output (merge parentheses that were split during tokenization, etc.)
        cleaned_output_text = self.helper.correct_output(cleaned_output_text)
        self.logger.paranoid(
            "cleaned_output_text after correct_output():", cleaned_output_text
        )

        self.logger.debug(f"unwanted_phrases: {self.unwanted_phrases}")
        self.logger.debug(f"unwanted_phrases_literal: {self.unwanted_phrases_literal}")

        # Add the special tokens to the list of unwanted phrases we want to cut off from the generated answer
        # Note: We might have to handle spaces before and after these phrases too
        for token in self.special_tokens:
            self.unwanted_phrases_literal.append(token)

        # Clean with special characters intact
        cleaned_dataset = self.helper.remove_unwanted_phrases(
            cleaned_output_text, self.unwanted_phrases, self.logger
        )

        # Clean with treating special characters literal
        cleaned_dataset = self.helper.remove_unwanted_phrases(
            cleaned_dataset,
            self.unwanted_phrases_literal,
            self.logger,
            escape=True,
            no_caps=True,
        )

        self.logger.paranoid(
            "cleaned_dataset after remove_unwanted_phrases():", cleaned_dataset
        )

        return cleaned_dataset

    def _generate_answer(
        self, input_ids: Tensor, attention_mask: Tensor, input_length: int
    ) -> Tensor:
        """
        Generates an answer based on the provided input IDs and attention mask.

        This method utilizes the internal model to generate text outputs by configuring the generation process with various parameters such as temperature, sampling preference, token constraints, and more, which are fetched from the configuration file.

        Parameters:
            input_ids (Tensor): The input tensor containing token IDs to be fed into the model.
            attention_mask (Tensor): The binary tensor indicating the position of valid tokens and padding in 'input_ids'.
            input_length (int): The length of the input sequence.

        Returns:
            Tensor: The tensor containing the generated token IDs from the model.

        """
        output: Tensor = self.model.generate(
            input_ids,
            attention_mask=attention_mask,
            max_new_tokens=self._calc_max_new_tokens(input_length),
            temperature=self.helper.config.getfloat("Model", "temperature"),
            do_sample=self.helper.config.getboolean("Model", "do_sample"),
            top_k=self.helper.config.getint("Model", "top_k"),
            top_p=self.helper.config.getfloat("Model", "top_p"),
            repetition_penalty=self.helper.config.getfloat(
                "Model", "repetition_penalty"
            ),
            no_repeat_ngram_size=self.helper.config.getint(
                "Model", "no_repeat_ngram_size"
            ),
            logits_processor=[self.logits_processor],
        )
        self.logger.paranoid("output: ", output)
        return output

    def _get_valid_input_ids(
        self, current_context: str, post_text: str
    ) -> tuple[Tensor, Tensor, int]:
        """
        Continuously encodes and validates the context until a valid context is obtained.
        A context is deemed valid based on a set of internal validation criteria related to its length and content.

        Parameters:
            current_context (str): The initial context text to encode.
            post_text (str): Additional text used for validating the context.

        Returns:
            tuple[Tensor, Tensor, int]: A tuple containing the `input_ids` and `attention_mask` as tensors, and the `input_length` as an integer.
        """
        valid_context = False
        while not valid_context:
            input_ids, attention_mask, input_length = self._encode_context(
                current_context
            )
            valid_context, current_context = self._validate_context(
                input_length, current_context, post_text
            )

        # Test for padding
        if 0 in input_ids[0].tolist():
            self.logger.debug("There is padding in the input_ids.")
        else:
            self.logger.debug("There is no padding in the input_ids.")

        # Additional logging
        self.logger.paranoid("input_ids: ", input_ids)
        self.logger.paranoid("attention_mask:", attention_mask)
        return input_ids, attention_mask, input_length

    def _validate_context(
        self, input_length: int, current_context: str, post_text: str
    ):
        """
        Validates the context length to ensure that the model can generate a response without exceeding its token limit.

        This method checks if the number of new tokens that can be generated (based on the input length) meets a minimum required number
        of new tokens. If the current context with the maximum new tokens is insufficient, it attempts to reset the context using only
        the post_text. If the post_text is still too large, it truncates the post_text to fit within the model's maximum token limit.

        Parameters:
            input_length (int): The current length of the input in tokens.
            current_context (str): The current context being used for the model's input.
            post_text (str): The post text that might be used as a new context if the current one is too long.

        Returns:
            tuple:
                - A boolean indicating whether the current context is valid (True) or not (False).
                - The modified or unmodified current_context based on validation.
        """
        minimum_new_tokens = self.helper.config.getint(
            "Model", "minimum_new_tokens", fallback=75
        )
        # Calculate the number of tokens that can be generated without exceeding the model's context limit
        max_new_tokens = self._calc_max_new_tokens(input_length)
        self.logger.debug("max_new_tokens:", max_new_tokens)

        # If max new tokens is less than minimum new tokens, fail this round and do it over with context as post_text
        if max_new_tokens < minimum_new_tokens:
            # If the post is still too large even after resetting the context to just the post_text,
            # truncate post_text to a manageable size that ensures the model can generate a response
            # without exceeding max_tokens. This keeps the most relevant part of the post.
            if current_context == post_text:
                self.logger.info(
                    "Post is too large, truncating to fit model's constraints."
                )
                # Adjust value for truncation_length as needed. This length aims to
                # balance between keeping enough context for a meaningful response and not exceeding model limits.
                truncation_length = self.max_tokens - minimum_new_tokens - 20
                post_text = post_text[:truncation_length]
                current_context = post_text
            else:
                current_context = post_text
                self.logger.info(
                    "Context is too big to generate any meaningful answer. Restarting using post only as input"
                )

            return False, current_context
        # If max new tokens is greater than or equal to minimum new tokens, the current context is good
        else:
            return True, current_context

    def _calc_max_new_tokens(self, input_length: int):
        return self.max_tokens - input_length

    def _encode_context(self, current_context: str):
        """
        Encodes the given text context into model-compatible input formats.

        This method encodes the text using a tokenizer configured to work on the specified device. It handles the creation of attention masks and ensures that the encoded input does not exceed the maximum token limit of the model by trimming the input if necessary.

        Parameters:
        - current_context (str): The text context to encode.

        Returns:
        - Tuple[Tensor, Tensor, int]: A tuple containing the encoded input IDs as a Tensor, the corresponding attention mask as a Tensor, and the length of the input sequence as an integer.
        """
        self.logger.debug("current_context:", current_context)

        # Encoding of indata with tokenizer
        input_ids: Tensor = self.tokenizer.encode(
            current_context, return_tensors="pt"
        ).to(self.device)
        input_length: int = input_ids.shape[1]  # The length of the input_ids

        # Create attention mask
        attention_mask: Tensor = torch.ones_like(input_ids)

        # If the initial input exceeds the model's context limit, trim the input
        if input_length > self.max_tokens:
            # Calculate the number of tokens to trim from input
            num_tokens_to_trim = input_length - self.max_tokens

            # Trim input_ids and attention_mask to fit the model's context size
            input_ids = input_ids[:, num_tokens_to_trim:]
            attention_mask = attention_mask[:, num_tokens_to_trim:]
            input_length = input_ids.shape[1]  # Update input_length after trimming

        return input_ids, attention_mask, input_length

    def _prepare_context(self, post: dict | str):
        """
        Prepares a context string from a given post, which can be either a dictionary with specific keys
        or a plain string. This function is used to format the post information into a structured string
        that includes special tokens to distinguish different parts of the context.

        Parameters:
        - post (dict | str): A post to be formatted. If a dictionary, it must contain keys 'unique_id',
        'username', 'post', and a 'quote' dictionary with 'quoted_user' and 'quoted_post'.

        Returns:
        - tuple: A tuple containing the full context string and the post text. The full context string
        includes user, quoted user, and post data with special formatting tokens.

        Raises:
        - ValueError: If 'post' is not a dictionary with the required structure or a plain string.
        """
        if isinstance(post, dict) and all(
            key in post for key in ["unique_id", "username", "post", "quote"]
        ):
            unique_id = post["unique_id"]
            username = post["username"]
            post_text = post["post"]
            quoted_user = post["quote"]["quoted_user"]
            quoted_text = " ".join(post["quote"]["quoted_post"])

            # Combine all information into a string or a format that the model can understand
            # Add special tokens around the different parts of the context
            full_context = f"[USER] {username}\n[QUOTED_USER] {quoted_user}\n[QUOTE_START] {quoted_text} [QUOTE_END]\n[POST_START] {post_text} [POST_END]"
        elif isinstance(post, str):
            full_context = post
        else:
            raise ValueError(
                "post_input must be either a dict with specific structure or a plain string."
            )

        return full_context, post_text

    def _wrong_generation(self, text: str, unwanted_patterns_list: list) -> bool:
        """Check if the generated text contains unwanted patterns or phrases indicating a poorly generated response or is invalid."""
        # Check for unwanted patterns
        for list in unwanted_patterns_list:
            for pattern in list:
                if re.search(pattern, text):
                    self.logger.debug(
                        f"Unwanted pattern found: {pattern} in text: {text}"
                    )
                    return True

        # Check for a single word
        if self._is_single_word(text):
            self.logger.debug(f"Single word detected in text: {text}")
            return True

        return False

    def _is_single_word(self, text: str) -> bool:
        """Check if the text is a single word."""
        # Print the received text
        self.logger.debug(f"Received text for word check: '{text}'")

        # Split the text by spaces and count the words
        words = text.split()

        self.logger.paranoid(f"Words: {words}")
        self.logger.paranoid(f"Number of words: {len(words)}")

        return len(words) <= 1
