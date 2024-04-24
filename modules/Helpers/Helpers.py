import io
import re
import os
import logging
from datetime import timedelta, datetime, timezone
import random
from modules.Helpers.CustomConfigParser import CustomConfigParser
from modules.Helpers.FileHandler import FileHandler
from modules.Helpers.FileHelpers import FileHelpers
from modules.Helpers.LogHelpers import LogHelpers

from modules.Logger import Logger


class Helpers:
    def __init__(self, file_handler: FileHandler):
        self.file_handler = file_handler
        self.file_helper = FileHelpers(self.file_handler)
        self.log_helper = LogHelpers()

        # Get the full path to the dir where the script is running from
        self.script_dir = self.file_helper.get_base_path(os.path.abspath(__file__), 3)
        self.modules_dir = os.path.join(self.script_dir, "modules")
        self.helpers_dir = os.path.join(self.script_dir, "helpers")

        # Load the needed variables
        self.min_interval_minutes = 60 * 24
        self.time_of_last_post = "time_of_last_post"
        self.time_of_last_response = "time_of_last_response"

        # Read the configuration file. Create if missing
        self.config_file_path = os.path.join(self.script_dir, "config.ini")
        self.config = CustomConfigParser(file_handler, self.config_file_path)
        self.create_config()

    def trim_output(self, text, pattern=r"\.\.+"):
        """
        Trims the text at the first occurrence of the specified pattern.

        Args:
            text (str): The text to be trimmed.
            pattern (str): The regex pattern to trim at. Default is ".." or "...".

        Returns:
            str: The trimmed text.
        """

        # Find the first occurrence of the specified pattern in the text
        match = re.search(pattern, text)

        # Cut the text at the first occurrence
        if match:
            return text[: match.start() + len(match.group())]
        else:
            return text

    def correct_output(self, text):
        """
        Corrects common formatting issues in the text.

        Args:
            text (str): The text to be corrected.

        Returns:
            str: The corrected text.
        """

        # Remove spaces inside parentheses
        corrected_text = text.replace("( ", "(").replace(" )", ")")

        # Replace spaces after parentheses if they are followed by punctuation marks
        pattern = r"\) ([\.,;:])"
        subst = r")\1"
        corrected_text = re.sub(pattern, subst, corrected_text)

        # Remove spaces before colons
        corrected_text = corrected_text.replace(" :", ":")

        # Remove spaces before semicolons
        corrected_text = corrected_text.replace(" ;", ";")

        # Remove spaces in URLs
        corrected_text = corrected_text.replace("/ www", "/www")

        # Remove before and after slashes
        corrected_text = corrected_text.replace(" / ", "/")

        # Remove spaces around hyphens in URLs
        pattern = r"http(.+?) - "
        subst = "http\\1-"
        corrected_text = re.sub(pattern, subst, corrected_text)

        # Remove spaces around quotation marks
        corrected_text = corrected_text.replace('" ', '"').replace(' "', '"')

        # Remove leading ". " if present
        if corrected_text.startswith(". "):
            corrected_text = corrected_text[2:]

        # Remove spaces before and after hyphens if there are numbers around the hyphen
        corrected_text = re.sub(r"(\d) - (\d)", r"\1-\2", corrected_text)

        # Split text into words
        words = corrected_text.split()

        # Check if the last word is repeated
        if len(words) > 1 and all(word == words[-1] for word in words[-2:]):
            # Find the position where the repetition starts
            for i in range(len(words) - 2, -1, -1):
                if words[i] != words[-1]:
                    # Keep the text up to the position where repetition starts
                    corrected_text = " ".join(words[: i + 1])
                    break

        return corrected_text

    def remove_unwanted_phrases(
        self,
        text: str,
        unwanted_patterns: list,
        logger: Logger,
        escape=False,
        no_caps=False,
        dotall=False,
    ) -> str:
        """
        Removes specified unwanted phrases or patterns from the given text using regular expressions.

        Parameters:
        - text (str): The original text from which unwanted phrases or patterns should be removed.
        - unwanted_patterns (list of str): A list of phrases or regex patterns that should be removed from the text.
        - escape (bool): If True, escapes brackets in the patterns.
        - no_caps (bool): If True, makes the search case-insensitive.
        - dotall (bool): If True, allows '.' to match any character including newline.

        Returns:
        - str: The text with unwanted phrases or patterns removed.

        Example:
        >>> unwanted_patterns = ["Gå till inlägget", r"Ursprungligen postat av \S+ "]
        >>> text = "Här är en text. Gå till inlägget för mer information. Ursprungligen postat av foo något viktigt."
        >>> remove_unwanted_phrases(text, unwanted_patterns)
        'Här är en text.  för mer information. något viktigt.'
        """
        flags = 0
        if no_caps:
            flags |= re.IGNORECASE
        if dotall:
            flags |= re.DOTALL
        for pattern in unwanted_patterns:
            if escape:
                # pattern = pattern.replace("[", "\[").replace("]", "\]")
                pattern = re.escape(pattern)

            case_handling = (
                "with case sensitivity" if not no_caps else "without case sensitivity"
            )
            dotall_handling = "with dotall" if dotall else "without dotall"
            logger.debug(
                f"Removing '{pattern}' from '{text}' {case_handling} {dotall_handling}"
            )

            original_text = text
            text = re.sub(pattern, "", text, flags=flags)
            if text != original_text:
                logger.debug(f"Pattern '{pattern}' matched and altered the text.")
        return text

    def create_config(self):
        """
        Creates or reads the configuration file.
        Initializes the configuration settings.
        """
        # Check if the config file exists.
        # print("config_file_path:", self.config_file_path)
        if not self.file_handler.exists(self.config_file_path):
            # If it doesn't exist, create a new config file
            config = self.config
            config["LaunchAgent"] = {"exists": "False"}
            config["Time"] = {
                self.time_of_last_post: "None",
                self.time_of_last_response: "None",
                "scrape_timeout_time": "30",
                "random_sleep_time_min": "1",
                "random_sleep_time_max": "10",
                "random_sleep_time_off": "False"
            }
            config["Misc"] = {"post_lock": "False"}
            config["Logging"] = {
                "act_log_level": "INFO",
                "actions_taken_log_level": "INFO",
                "scraper_log_level": "INFO",
                "decisions_log_level": "INFO",
                "post_log_level": "INFO",
                "model_log_level": "INFO",
                "notifier_log_level": "INFO",
                "s3_fh_log_level": "INFO",
                "local_fh_log_level": "INFO",
                "dbx_fh_log_level": "INFO",
            }
            config["Model"] = {
                "minimum_new_tokens": "75",
                "temperature": "0.5",
                "do_sample": "True",
                "top_k": "40",
                "top_p": "0.7",
                "repetition_penalty": "2.0",
                "no_repeat_ngram_size": "2",
                "model_path": "path/to/your/model",
                "max_tokens": "256",
                "special_tokens": "[USER], [QUOTED_USER], [QUOTE_START], [QUOTE_END], [POST_START], [POST_END]"
            }
            # Add more user agents separated by " || " in your config file as needed
            config["Scraper"] = {
                "user_agents": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 || Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"
            }

            # Convert config to a string and write using the file handler
            config_str = io.StringIO()
            config.write(config_str)
            config_str.seek(0)  # Rewind the buffer to the beginning
            self.file_handler.write(self.config_file_path, config_str.read())

        config_content = self.file_handler.read(self.config_file_path)
        # print("Read config content:", config_content)
        if isinstance(config_content, str):
            config_str = io.StringIO(config_content)
        else:
            raise TypeError("Expected config_content to be a string, but got a different type. This indicates a critical error in file handling.")
        config_str.seek(0)
        self.config.read_file(
            config_str
        )  # Use read_file instead of read to load from a string buffer

    def update_config(self, title: str, key_value: dict):
        """
        Updates the configuration file with new key-value pairs under a given title
        without overwriting other keys in the same section.

        Args:
            title (str): The section title in the configuration file.
            key_value (dict): Dictionary containing key-value pairs to update.
        """
        self.config.update_config(title, key_value)

    def logging_decorator(self, func):
        """
        Decorator for enhancing functions with logging capabilities.
        When a function is decorated with this decorator, log entries will be created
        at the beginning and the end of the function execution, indicating which function
        is being executed.

        Args:
            func (function): The function to be decorated.

        Returns:
            function: A new function that wraps the original function, adding logging
            before and after its execution.

        Example:
            @logging_decorator
            def my_function(arg1, arg2):
                # function body
                pass

        When `my_function` is called, log entries will be created indicating that
        `my_function` has started and finished execution.
        """

        def wrapper(*args, **kwargs):
            logging.info(f"Starting function: {func.__name__}")
            result = func(*args, **kwargs)
            logging.info(f"Finished function: {func.__name__}")
            return result

        return wrapper

    def create_logger(self, logger_name, file_name):
        """
        Creates and initializes a logger.

        Args:
            logger_name (str): The name of the logger.
            file_name (str): The name of the log file.

        Example:
            self.logger = self.helper.create_logger("Decisions Logger", "decisions_log.log")

        Returns:
            Logger: The initialized logger.
        """
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        log_path = os.path.join(self.script_dir, file_name)
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.info(f"{logger_name} initialized and working.")
        return logger

    def change_log_level(self, logger_name, log_level):
        """
        Changes the log level of a logger.

        Args:
            logger_name (str): The name of the logger.
            log_level (str): The new log level.
        """
        # Check if the log level is valid
        Logger.check_valid_log_level(log_level)

        # Update the log level in the configuration file
        self.update_config("Logging", {logger_name: log_level})

    def save_time_of_last_post(self, time_of_post):
        """
        Saves the current time the post was posted as the time of the last post.
        """
        # Check if time_of_post is a string or a datetime object
        if isinstance(time_of_post, str):
            # If it is a string, use it directly
            current_time_str = time_of_post
        elif hasattr(time_of_post, "strftime"):
            # If it is a datetime object, format it to a string
            current_time_str = time_of_post.strftime("%Y-%m-%d %H:%M:%S")
        else:
            # Raise an error if time_of_post is neither a string nor a datetime object
            raise ValueError("time_of_post must be a string or a datetime object")

        self.update_config("Time", {self.time_of_last_post: current_time_str})

    def load_time_of_last_post(self):
        """
        Loads the time of the last answer the bot has posted from the configuration file.

        Returns:
            datetime: The time of the last post, or None if not available.
        """
        try:
            # Get the time string from the config file
            last_time_str = self.config["Time"][self.time_of_last_post].strip()

            # Convert the string format into datetime format
            last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
            return last_time
        except Exception as e:
            # print(f"Exception: {e}\n\nAssuming the bot has never posted any messages previously.")
            return None

    def save_time_of_last_response(self):
        """
        Saves the current time as the time of the last answer.
        """
        current_time = datetime.now(timezone.utc).astimezone(None)

        # Convert the datetime format into string format
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        self.update_config("Time", {self.time_of_last_response: current_time_str})

    def load_time_of_last_response(self):
        """
        Loads the time of the last answer the bot has received from the configuration file.

        Returns:
            datetime: The time of the last answer, or None if not available.
        """
        try:
            # Get the time string from the config file
            last_time_str = self.config["Time"][self.time_of_last_response].strip()

            # Convert the string format into datetime format
            last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
            return last_time
        except Exception as e:
            # print(f"Exception: {e}\n\nAssuming the bot has never got any answers previously.")
            return None

    def check_if_min_interval_since_response(self, min_interval_minutes=-1):
        """
        Checks if a minimum interval has passed since the last response.

        Args:
            min_interval_minutes (int): The minimum interval in minutes. If no value is given, defaults to "self.min_interval_minutes".

        Returns:
            bool: True if the minimum interval has passed, False otherwise.
        """
        # If no custom interval is passed, use the default
        if min_interval_minutes == -1:
            min_interval_minutes = self.min_interval_minutes

        last_answer_time = self.load_time_of_last_response()

        if last_answer_time is None:
            return True  # Because then we assume the bot has not got any answers yet.
        min_interval = timedelta(minutes=min_interval_minutes)
        current_time = datetime.now()

        # If the difference between now and last_answer_time is greater than min_interval (24 h), then more than 24 hours have passed since the bot last received an answer
        return (current_time - last_answer_time) >= min_interval

    def has_posted_less_than_5_times_in_last_24_hours(self, history_path, logger: Logger):
        # Read the data from post_history.json
        history = self.file_helper.read_json_file(history_path)

        num_posts_in_last_24_hours = 0

        # Get the current time
        current_time = datetime.now()

        # Iterate through the history
        for action_id, action in history.items():
            try:
                # Extract and convert the time of the bot post to a datetime object
                time_of_post_str = action.get("time_of_post", "")
                if time_of_post_str:
                    time_of_post = datetime.strptime(
                        time_of_post_str, "%Y-%m-%d %H:%M:%S"
                    )

                    # Check if this post was within the last 24 hours
                    if (
                        current_time - timedelta(hours=24)
                        <= time_of_post
                        <= current_time
                    ):
                        num_posts_in_last_24_hours += 1

            except Exception as e:
                print(f"Error when going through post history: {e}")

        # Return True if the bot has posted less than 5 times in the last 24 hours
        has_posted_less_than_5_times_in_last_24_hours = num_posts_in_last_24_hours < 5
        print(
            f"Bot has posted less than 5 times in the last 24 hours? {has_posted_less_than_5_times_in_last_24_hours}"
        )
        return has_posted_less_than_5_times_in_last_24_hours

    def task_in_progress(self, status_data):
        current_time = datetime.now()

        # Check if another instance is already waiting
        if status_data and "waiting_until" in status_data:
            waiting_until = datetime.fromisoformat(status_data["waiting_until"])
            if current_time < waiting_until:
                print("Another instance is already waiting")
                return True  # Another instance is already waiting
            else:
                print("No other instance is already waiting")
                return False
        else:
            print("No 'waiting_until' found in post_status.json")

    def done_waiting(self, post_status, logger: Logger):
        status_data = self.file_helper.read_json_file(post_status)

        logger.info("Checking if done waiting")

        # Check the time elapsed since the last post
        time_of_last_post = self.load_time_of_last_post()

        if time_of_last_post is None:
            # If there is no last post time (first time running), allow posting
            logger.info(
                "This is the first time the bot is running; no last post time was found"
            )
            return True

        current_time = datetime.now()
        time_elapsed_since_last_post = current_time - time_of_last_post

        # If 2 hours have passed since the last post, allow posting
        if time_elapsed_since_last_post >= timedelta(hours=2):
            logger.info("More than 2 hours have passed since the bot's last post")
            return True
        else:
            logger.info("Less than 2 hours have passed since the bot's last post")

            # Check if there is a waiting time and if it's passed
            if status_data and "waiting_until" in status_data:
                try:
                    waiting_until = datetime.fromisoformat(status_data["waiting_until"])
                    if current_time >= waiting_until:
                        logger.info("And the wait time has passed")
                        return True  # We are done waiting; wait time has passed
                    else:
                        time_remaining = waiting_until - current_time
                        logger.info(
                            f"And the wait time has not yet passed. Time remaining: {time_remaining} min"
                        )
                        return False  # We are not done waiting; wait time has not yet passed
                except ValueError:
                    logger.debug("Invalid date format in status file.")
            else:
                logger.debug("No 'waiting_until' found in post_status.json")

            # Calculate a new random wait time between 5 minutes and 2 hours and update the status file with the new time when the waiting is done
            random_wait_time = timedelta(minutes=random.randint(5, 120))
            logger.info(f"Bot will wait {random_wait_time} minutes until it posts")
            waiting_until = current_time + random_wait_time
            self.file_helper.update_json_file(
                post_status, {"waiting_until": waiting_until.isoformat()}
            )
            return False
