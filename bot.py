from collections.abc import Callable
import time
import os
from typing import Any, TYPE_CHECKING, Optional
import random
from modules.Helpers.FileHandler import FileHandler
from modules.Helpers.Helpers import Helpers
from modules.Logger import Logger
from modules.Notifier import Notifier
from modules.scraper import Scraper
from modules.decisions import Decisions
from modules.act import Act
import json

if TYPE_CHECKING:
    from modules.Model import Model


class FlashbackBot:
    def __init__(
        self,
        file_handler: FileHandler,
        helper: Helpers,
        notifier: Notifier,
        model: "Model",
        callbacks: Optional[list[Callable[..., Any]]] = None,
    ) -> None:
        """
        Initialize the bot with necessary dependencies and optional callbacks.

        Args:
            file_handler: An instance of the chosen file handler, responsible for file operations.
            helper: An instance of Helpers, providing utility functions and configurations.
            notifier: An instance of Notifier, responsible for sending notifications.
            model: An instance of Model, responsible for generating answers.
            callbacks (optional): A list of callback functions to be executed at the end of the bot's operation.
                Callbacks may accept *args and **kwargs if necessary, but it is not mandatory.
                They should be designed according to their specific needs and use cases.

        Usage Example 1:
            def my_cleanup_function(*args, **kwargs):  # Can safely ignore args and kwargs if not needed
                print("Performing custom cleanup...")

            file_handler = create_and_get_file_handler()

            bot = FlashbackBot(file_handler=file_handler, helper=helper, notifier=notifier, callbacks=[my_cleanup_function])
            bot.run()
            bot.execute_callbacks()  # my_cleanup_function will be executed without specific args or kwargs.

        Usage Example 2:
            def my_cleanup_function():
                print("Performing custom cleanup...")

            def log_summary(execution_time: float, result: str):
                print(f"Execution time: {execution_time} seconds, Result: {result}")

            file_handler = create_and_get_file_handler()

            bot = FlashbackBot(file_handler=file_handler, helper=helper, notifier=notifier,
                               callbacks=[my_cleanup_function,
                                          lambda execution_time, result: log_summary(execution_time, result)])

            # Example of running the bot and executing callbacks with arguments
            bot.run()
            bot.execute_callbacks(execution_time=0.52, result="Success")  # Passing specific arguments to the callbacks
        """
        if callbacks is None:
            callbacks = []
        # Initialize Modules
        self.file_handler = file_handler
        self.helper = helper
        self.notifier = notifier
        self.callbacks = callbacks

        print(f"Initializing {self.file_handler.__class__.__name__}")
        self.file_handler.init(self.helper)
        self.scraper = Scraper(self.helper, file_handler=self.file_handler)
        self.decisions = Decisions(self.helper, file_handler=self.file_handler)
        self.actions = Act(self.helper, self.notifier, file_handler=self.file_handler, model=model)
        self.actions_taken_log_level = self.helper.config["Logging"][
            "actions_taken_log_level"
        ]
        self.actions_taken_logger = Logger(
            "Actions Taken Logger",
            "actions_taken_log.log",
            self.actions_taken_log_level,
            file_handler=self.file_handler,
        )

        # Load paths
        self.script_dir = self.helper.file_helper.get_base_path(
            os.path.abspath(__file__), 0
        )
        self.posts_dir = os.path.join(self.script_dir, "posts")
        self.time_of_last_post = self.helper.config["Time"]["time_of_last_post"]

    # ---------------------------------------------------------------
    # DEFINE FUNCTIONS
    # ---------------------------------------------------------------
    def execute_callbacks(self, *args, **kwargs):
        """
        Execute all registered callback functions with the provided arguments.

        Goes through the list of callbacks and executes each one in the order they were added.
        Callbacks that do not need *args and **kwargs can ignore them. This method is flexible enough to handle
        both parameterized and non-parameterized callbacks effectively.
        """
        for callback in self.callbacks:
            callback(
                *args, **kwargs
            )  # Callbacks should handle their argument needs internally

    def get_new_forum_posts(self, test_mode=False) -> dict:
        """1. Check if there are any new posts.
        2. Appends any new posts to the total posts and the unread posts.
        3. Returns the new posts to the bot for its decisions.

        Args:
            test_mode (bool): If True, the function runs in test mode. Defaults to False.

        Returns:
            dict: A dictionary containing the new posts that were not previously scraped. Each key in the dictionary represents a post ID from the forum thread, and each value is another dictionary with details about the post, structured as follows:
                {
                    'unique_id': str - The unique identifier for the post on the forum's server.
                    'username': str - The username of the user who made the post.
                    'quote': {
                        'quoted_user': list[str] - A list of usernames who were quoted in this post.
                        'quoted_post': list[str] - A list of the actual text that was quoted from other posts.
                    },
                    'post': str - The text of the post after quotes have been removed.
                }

                Example:
                {
                    '42349': {
                        'unique_id': 'post12345',
                        'username': 'user123',
                        'quote': {
                            'quoted_user': ['user456'],
                            'quoted_post': ['This is an example of a quoted text.']
                        },
                        'post': 'This is the content of the post, following the quoted text.'
                    }
                }
        """
        return self.scraper.scrape("forum_url", test_mode)

    def decide(self, unread_posts):
        """The bot reads and makes decisions on unread posts.

        Args:
            unread_posts (dict): This is all the posts the bot has not yet read and decided on.

        Returns:
            dict: decisions
        """
        return self.decisions.decide(unread_posts)

    def random_sleep(self):
        """
        Pauses the bot's operation for a random duration between a minimum and maximum time specified in the configuration.

        This function retrieves the minimum and maximum sleep times from the configuration under the "Time" section, with default
        fallback values of 1 and 120 minutes, respectively. If the sleep functionality is disabled in the configuration (controlled
        by the 'random_sleep_time_off' setting), the function will return immediately. Otherwise, it calculates a random sleep
        time within the specified range, converts it to seconds, and suspends execution for that duration.
        """
        min_minutes = self.helper.config.getint(
            "Time", "random_sleep_time_min", fallback=1
        )
        max_minutes = self.helper.config.getint(
            "Time", "random_sleep_time_max", fallback=120
        )
        off = self.helper.config.getboolean(
            "Time", "random_sleep_time_off", fallback=False
        )
        if off:
            return

        # Calculate random sleep time in seconds, because time.sleep() accepts seconds only.
        sleep_time = random.randint(min_minutes * 60, max_minutes * 60)
        print(f"Bot is going to sleep {sleep_time} seconds …")
        time.sleep(sleep_time)

    def run(self, test_mode=False):
        # 1. Watch the forum thread and check for new posts
        if test_mode:
            unread_posts = {}
        else:
            unread_posts = self.get_new_forum_posts(test_mode)

        # 2. Send the unread posts to the decision module and return the decisions.
        decisions = self.decide(unread_posts)

        # 3. Act on the decisions (post, send notifications etc.)
        actions_taken = self.actions.act(decisions)

        # 4. Print and log (## TODO: and notify to the frontend) which actions have been taken by the bot
        if len(actions_taken) > 0:
            self.actions_taken_logger.info(
                json.dumps(actions_taken, indent=4, ensure_ascii=False)
            )
