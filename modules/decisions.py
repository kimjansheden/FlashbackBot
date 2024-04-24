from modules.Helpers.FileHandler import FileHandler
from modules.Helpers.LocalFileHandler import LocalFileHandler
from modules.Logger import Logger
from .Helpers.Helpers import Helpers
import json
import random
import os


class Decisions:
    """
    Manages and makes decisions on unread posts or messages by applying specific rules and conditions.
    """

    def __init__(
        self,
        helper: Helpers,
        decisions_json_path=None,
        unread_posts_json_path=None,
        file_handler: FileHandler = LocalFileHandler(),
    ) -> None:
        # Load modules
        self.helper = helper
        self.config = self.helper.config
        self.file_handler = file_handler

        # Load paths
        # Get the full path to the directory where the script is located
        self.script_dir = self.helper.file_helper.get_base_path(
            os.path.abspath(__file__), 2
        )
        self.posts_dir = os.path.join(self.script_dir, "posts")
        if decisions_json_path is None:
            self.decisions_json_path = os.path.join(self.posts_dir, "decisions.json")
        else:
            self.decisions_json_path = decisions_json_path
        if unread_posts_json_path is None:
            self.unread_posts_json_path = os.path.join(
                self.posts_dir, "unread_posts.json"
            )
        else:
            self.unread_posts_json_path = unread_posts_json_path
        self.pending_posts_json_path = os.path.join(self.posts_dir, "pending.json")

        # LOAD NECESSARY VARIABLES
        # Get the username from the config file
        self.username = os.getenv("USERNAME")

        # Read the existing decisions from file (restoring the state)
        self.decisions = self.helper.file_helper.read_json_file(
            self.decisions_json_path
        )
        # Check if 24 hours have passed since the bot last received an answer
        self.has_been_24_h_since_response_to_bot = (
            self.helper.check_if_min_interval_since_response()
        )
        self.new_answers = False
        self.num_new_answers = 0
        self.log_level = self.config["Logging"]["act_log_level"]
        self.logger = Logger(
            "Actions Logger", "act_log.log", self.log_level, file_handler=file_handler
        )

    def decide(self, unread_posts: dict, test_mode=False):
        """The bot reads and makes decisions on unread posts.

        This method processes unread posts to determine if and how the bot should respond. It considers various conditions such as if the bot itself has been quoted.

        Args:
            unread_posts (dict): Dictionary containing posts that the bot has not yet read and decided on.

        Returns:
            dict: A dictionary of posts the bot has decided to act upon. This may include modifications to the details of the posts to reflect decision criteria (e.g., flattening quoted users into a single string).

        Notes:
            The method does not change the overall structure of each post in the dictionary but may modify or add details to represent decisions. For instance, it may adjust the list of quoted users to a single string, but the key and basic structure of each post remain the same.
        """

        # Restore vars
        self.new_answers = False
        self.num_new_answers = 0

        self.logger.debug("Taking Decisions ...")

        self.logger.info(f"Bot is taking decision on {len(unread_posts)} new posts.")

        # Assert if bot has got an answer
        self.check_for_answers(unread_posts)

        # If bot has got no new answers, and no one has answered in more than 24 hours, and there aren't already decisions waiting to be acted on: pick a random post to answer to a random post
        self.eval_and_pick_random_post(unread_posts)

        # Save the decisions to file and clear the unread posts file, because now they are read
        if not test_mode:
            self.helper.file_helper.update_json_file(
                self.decisions_json_path, self.decisions
            )
            self.file_handler.write(self.unread_posts_json_path, mode="w", data="")

        decisions_json = json.dumps(self.decisions, indent=4, ensure_ascii=False)
        self.logger.debug(
            f"Bot has decided to answer {len(self.decisions)} posts. These are:\n\n{decisions_json}"
        )
        self.logger.paranoid(f"Bot's username is: {self.username}")

        return self.decisions

    def check_for_answers(self, unread_posts):
        for index, id in enumerate(unread_posts, start=1):
            self.logger.debug(f"Deciding on unread post number {index} with ID {id}.")
            # Extract quoted users and posts
            current_post = unread_posts[id]
            quoted_users = current_post["quote"]["quoted_user"]
            quoted_posts = current_post["quote"]["quoted_post"]

            # Check if any of the quoted users is the bot
            for quoted_user, quoted_post in zip(quoted_users, quoted_posts):
                if quoted_user == self.username:
                    self.logger.info("The bot has got an answer.")
                    # Add the current post to self.decisions
                    self.decisions[id] = current_post

                    # Overwrite the recently added post's lists of quoted users and quoted posts to the single user and post we have singled out in the current iteration
                    self._single_out_quoted_user_and_quoted_post(
                        id, quoted_user, quoted_post
                    )
                    self.helper.save_time_of_last_response()
                    self.new_answers = True
                    self.num_new_answers += 1

        if self.new_answers:
            self.logger.info(f"{self.num_new_answers} new answers.")
        else:
            self.logger.info("No new answers.")

    def eval_and_pick_random_post(self, unread_posts):
        """Evaluates the necessary conditions and picks a random post to answer if appropriate.

        This method decides whether the bot should pick a random post to answer based on the following conditions:
        1. The bot has not received any new answers.
        2. It has been more than 24 hours since the bot last received an answer.
        3. There are no pending decisions in the queue.

        Args:
            unread_posts (dict): A dictionary containing the unread posts for the bot to consider.

        Returns:
            None: The method updates the instance variable `self.decisions` if a random post is picked.
        """
        pending = self.helper.file_helper.read_json_file(self.pending_posts_json_path)
        if len(self.decisions) > 0:
            self.logger.info(
                "The bot has already taken decisions and will proceed to act upon them."
            )
            return

        self.logger.info("No one new has answered the bot.")
        if self.has_been_24_h_since_response_to_bot:
            self.logger.info(
                "And it's been more than 24 hours since the bot received an answer."
            )
            if len(pending) > 0:
                self.logger.info(
                    "But there are still posts pending, so the bot is not deciding on a random post to answer right now."
                )
            elif len(unread_posts) > 0:
                self.logger.info(
                    "The bot is therefore deciding on a random post to answer."
                )

                # Filter out the bot's own posts
                eligible_posts = {
                    post_id: post
                    for post_id, post in unread_posts.items()
                    if post["username"] != self.username
                }

                if not eligible_posts:
                    self.logger.info(
                        "No eligible posts to answer (only the bot's own)."
                    )
                    return

                # Pick a random post from the eligible posts
                random_id = random.choice(list(eligible_posts.keys()))

                # Extract quoted users
                chosen_post = eligible_posts[random_id]
                quoted_users = chosen_post["quote"]["quoted_user"]

                # Flatten out quoted users to one single string
                flattened_quoted_users = ", ".join(quoted_users)

                # Replace the list of quoted users in the chosen post with the flattened string
                chosen_post["quote"]["quoted_user"] = flattened_quoted_users

                # Add the chosen post to decisions
                self.decisions[random_id] = chosen_post
        else:
            self.logger.info(
                "But there hasn't been 24 hours yet since the bot last got an answer, so the bot is not taking any new decisions right now."
            )

    def _single_out_quoted_user_and_quoted_post(self, id, quoted_user, quoted_post):
        # Overwrite the selected post's lists of quoted users and quoted posts to the single user and post we have singled out in the current iteration
        self.decisions[id]["quote"]["quoted_user"] = quoted_user
        self.decisions[id]["quote"]["quoted_post"] = [quoted_post]
