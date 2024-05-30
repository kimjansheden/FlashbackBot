import inspect
import re
from typing import List
from pushbullet import Pushbullet

from modules.Helpers.FileHandler import FileHandler
from modules.Helpers.LocalFileHandler import LocalFileHandler
from modules.Helpers.LogHelpers import LogHelpers

from .Helpers.Helpers import Helpers
from .Notifier import Notifier
import os


class PushbulletNotifier(Notifier):
    def __init__(self, helper: Helpers, test_mode=False, file_handler: FileHandler = LocalFileHandler()) -> None:
        """
        Initialize the PushbulletNotifier class.

        :param helper: An instance of the Helpers class.
        """
        super().__init__(helper, file_handler)

        # Get the full path to the dir where the script is running from
        self.script_dir = self.helper.file_helper.get_base_path(
            os.path.abspath(__file__), 2
        )

        self.posts_dir = os.path.join(self.script_dir, "posts")
        self.pending_path = os.path.join(self.posts_dir, "pending.json")

        # This dictionary maps each flag to its corresponding message
        self.kind = {
            "answer_received": "You have received a new answer.",
            "post_success": "Your post has been posted successfully.",
            "request_approval": "The bot has generated a new post for your approval",
        }
        self.flags = {
            "answer_received": False,
            "post_success": False,
            "request_approval": False,
        }
        self.pb = self.auth_pushbullet()

        self.log_helper = LogHelpers()
        self.test_mode = test_mode

    def set_flag(self, flag, value):
        """
        Set the value of a specific flag in the flags dictionary.

        :param flag: The flag to set.
        :param value: The value to set the flag to.
        """
        self.flags[flag] = value

    def send_notification(self, method, flag, message=None):
        """
        General method for sending notifications based on the flag.

        :param method: The method of notification, e.g., "push" or "email".
        :param flag: The flag indicating the type of notification.
        :param message: Optional message to include in the notification.
        """
        if self.flags[flag]:
            kind = self.kind[flag]
            if method == "push":
                self.logger.info(f"Sending {method} notification … {kind}\n{message}")
                self.pb.push_note(
                    "Notification", message
                )  # Send push notification with PushBullet
            if method == "email":
                self.logger.info(f"Sending {method} notification … {kind}\n{message}")

    def send_push_notification(self, flag, message):
        """
        Send a push notification.

        :param flag: The flag indicating the type of notification.
        :param message: The message to include in the notification.
        """
        self.set_flag(flag, True)
        self.send_notification("push", flag, message)

    def send_email_notification(self, flag, message):
        """
        Send an email notification.

        :param flag: The flag indicating the type of notification.
        :param message: The message to include in the notification.
        """
        self.set_flag(flag, True)
        self.send_notification("email", flag, message)

    def auth_pushbullet(self):
        """
        Authenticate with Pushbullet.
        Create file if missing.

        Returns:
            Pushbullet: A logged in Pushbullet object.
        """

        pb_creds = os.getenv("PB_CREDS")

        self.logger.debug("Current working directory: " + os.getcwd())
        self.logger.debug(f"API Key being sent to Pushbullet: {pb_creds}")
        return Pushbullet(api_key=pb_creds)

    def get_notifications(self, rejects_and_accepts=True):
        pushes_list = self.pb.get_pushes()
        self.logger.debug("pushes_list:", pushes_list)

        # Filter out messages with the titles 'Accept' and 'Reject' and return them as two lists
        if rejects_and_accepts:
            accept_ids, reject_ids = self.get_rejects_and_accepts_ids(pushes_list)
            skip_ids = self.get_skip_ids(pushes_list)
            return accept_ids, reject_ids, skip_ids

        return pushes_list

    def delete_notification(self, action_id):
        # Get the caller's information
        stack = inspect.stack()
        caller = stack[1]  # Index 1 to get the immediate caller
        caller_info = f"{caller.function} at {caller.filename}:{caller.lineno}"
        
        self.log_helper.debug(self.logger, f"Deleting action_id: {action_id} called from {caller_info}")

        # Here it should connect the action_id with the right iden and then send for deletion
        pushes_list = self.pb.get_pushes()
        idens = []
        pattern = rf"Action ID: {action_id}"
        for push in pushes_list:
            # Check if "body" exists in the dictionary and search for the pattern 'Action ID: [number]'
            if "body" in push:
                match = re.search(pattern, push["body"])
                if match:
                    self.log_helper.debug(
                        self.logger, f"Found match for action_id {action_id}"
                    )
                    # Extract the idens
                    # For every action_id there are two pushes: a message and a reject/accept
                    iden = push["iden"]
                    idens.append(iden)

        self.log_helper.debug(self.logger, f"idens: {idens}")
        for iden in idens:
            self.log_helper.debug(self.logger, f"Deleting push with iden: {iden}")
            self.pb.delete_push(iden)

    def get_action_ids(self, pushes_list: list) -> list[str]:
        """
        Extract action IDs from a list of dictionaries representing push notifications.

        Args:
            pushes_list (list): A list of dictionaries, each representing a push notification.
            Example structure:
            [
                {
                    'active': True,
                    'iden': 'abc123',
                    'created': 1234.567,
                    'modified': 1234.567,
                    'type': 'note',
                    'dismissed': False,
                    'direction': 'self',
                    'sender_iden': 'abc123',
                    'sender_email': 'foo@foo.com',
                    'sender_email_normalized': 'foo@foo.com',
                    'sender_name': 'Foo Fooson',
                    'receiver_iden': 'abc123',
                    'receiver_email': 'foo@foo.com',
                    'receiver_email_normalized': 'foo@foo.com',
                    'title': 'Accept',
                    'body': 'Action ID: 4, Response: Accept'
                },
                ...
            ]

        Returns:
            List[str]: A list of action IDs extracted from the 'body' field of the dictionaries.
        """
        action_ids = []
        pattern = r"Action ID: (\d+)"
        for push in pushes_list:
            # Check if "body" exists in the dictionary and search for the pattern 'Action ID: [number]'
            if "body" in push:
                match = re.search(pattern, push["body"])
                if match:
                    # Extract the number and add it to the action_ids list
                    action_id = match.group(1)
                    action_ids.append(action_id)

        return action_ids

    def check_and_update_generated_answer(self, pushes_list: list):
        """Compares generated_answer in pending.json with the Generated Answer in the push body for the respective action_id.

        Args:
            pushes_list (list): List of push dictionaries containing 'body' with action_id and generated_answer.

        Returns:
            None
        """
        self.log_helper.debug(
            self.logger,
            f"Checking for changes in list: {pushes_list}",
            force_print=self.test_mode,
        )
        action_id_pattern = r"Action ID: (\d+)"
        generated_answer_pattern = r"Generated Answer: ([\s\S]*)"
        for push in pushes_list:
            # Check if "body" exists in the dictionary and extract the action_id from the body
            if "body" in push:
                match_action_id = re.search(action_id_pattern, push["body"])
                if match_action_id:
                    # Extract the action_id number and use it to find the Generated Answer in pending
                    action_id = int(match_action_id.group(1))

                    # Check if the Generated Answer exists in the push body and extract it
                    match_generated_answer = re.search(
                        generated_answer_pattern, push["body"], re.MULTILINE
                    )
                    self.log_helper.debug(
                        self.logger,
                        f"match_generated_answer: {match_generated_answer}",
                        force_print=self.test_mode,
                    )

                    if match_generated_answer:
                        generated_answer_notifier = match_generated_answer.group(1)
                        self.log_helper.debug(
                            self.logger,
                            f"generated_answer_notifier: {generated_answer_notifier}",
                            force_print=self.test_mode,
                        )

                    generated_answers_differ = self.compare_generated_answer(
                        action_id, generated_answer_notifier
                    )

                    if generated_answers_differ:
                        self.update_generated_answer(
                            action_id, generated_answer_notifier
                        )
                    else:
                        self.log_helper.debug(
                            self.logger,
                            f"Generated Answer in pending.json does not differ from the one in the push body for the action_id: {action_id}",
                            force_print=self.test_mode
                        )

    def compare_generated_answer(self, action_id: int, generated_answer_notifier: str):
        """Compares generated_answer in pending.json with the Generated Answer in the push body for the respective action_id.
        Returns True if the generated_answer in pending.json is different from the one in the push body.

        Args:
            action_id (int): The action identifier to look up in pending.json.
            generated_answer_notifier (str): The generated answer from the push body to compare.

        Returns:
            bool: True if the answers differ, False otherwise.
        """
        self.log_helper.debug(
            self.logger,
            f"Comparing generated_answer in pending.json with the Generated Answer in the push body for action_id: {action_id}",
            force_print=self.test_mode
        )
        # Read the data from pending.json
        pending_posts = self.helper.file_helper.read_json_file(self.pending_path)
        self.log_helper.debug(self.logger, f"pending_posts path: {self.pending_path}, content: {pending_posts}", force_print=self.test_mode)

        # Make sure action_id is string
        action_id_str = str(action_id)

        # Find the action_id as key in pending_posts and compare the associated Generated Answer with the one fresh from the notifier
        if action_id_str in pending_posts:
            generated_answer_pending = pending_posts[action_id_str]["generated_answer"]
            self.log_helper.debug(
                self.logger,
                f"Comparing generated_answer in pending.json ({generated_answer_pending}) with generated_answer in notifier ({generated_answer_notifier})",
                force_print=self.test_mode
            )
            if generated_answer_pending != generated_answer_notifier:
                self.log_helper.debug(
                    self.logger,
                    f"Generated Answer in pending.json differs from the one in the push body for action_id: {action_id}",
                    force_print=self.test_mode
                )
                return True
            else:
                self.log_helper.debug(
                    self.logger,
                    f"Generated Answer in pending.json is the same as the one in the push body for the action_id: {action_id}",
                    force_print=self.test_mode
                )
                return False
        else:
            self.log_helper.debug(
                self.logger,
                f"action_id {action_id} not found in pending_posts",
                force_print=self.test_mode
            )
            return False

    def update_generated_answer(self, action_id: int, new_generated_answer: str):
        """Updates the generated_answer in pending.json for the given action_id.
        Use this function when there is a divergence between the Generated Answer
        in the bot's pending answers and the Generated Answer in the notifier.
        This means the user has edited the bot's answer and that change must be saved to the bot.

        Args:
            action_id (int): The action identifier for which the generated answer should be updated.
            new_generated_answer (str): The new generated answer to update in pending.json.

        Returns:
            None
        """
        self.log_helper.debug(
            self.logger,
            f"Updating generated_answer in pending.json for the given action_id: {action_id}",
            force_print=self.test_mode
        )

        # Make sure action_id is string
        action_id_str = str(action_id)

        # Read the data from pending.json
        pending_posts = self.helper.file_helper.read_json_file(self.pending_path)
        self.log_helper.debug(
            self.logger,
            f"pending_posts before update: {pending_posts}",
            force_print=self.test_mode,
        )

        # Update the Generated Answer in pending.json; the only time the generated answers would differ is if the user has edited it in the front end. Thus, the notifier version is newer
        pending_posts[action_id_str]["generated_answer"] = new_generated_answer
        self.log_helper.debug(
            self.logger,
            f"pending_posts after update: {pending_posts}", force_print=self.test_mode
        )
        self.helper.file_helper.update_json_file(
            self.pending_path, pending_posts, overwrite=True
        )

    def get_rejects_and_accepts_ids(self, pushes_list: list):
        """
        Processes a list of pushes, separating them into accepts and rejects,
        and performs actions based on their titles.

        Args:
            pushes_list (list): A list of dictionaries where each dictionary
                                represents a push with a "title" key.

        Returns:
            tuple: Two lists containing the IDs of the accepted and rejected pushes.
        """
        accepts_list, rejects_list, _ = self.filter_pushes(pushes_list)

        accept_ids = self.get_action_ids(accepts_list)
        reject_ids = self.get_action_ids(rejects_list)

        return accept_ids, reject_ids

    def get_skip_ids(self, pushes_list: list):
        """
        Processes a list of pushes, separating them into skips,
        and performs actions based on their titles.

        Args:
            pushes_list (list): A list of dictionaries where each dictionary
                                represents a push with a "title" key.

        Returns:
            list: A list containing the IDs of the skipped pushes.
        """
        _, _, skips_lists = self.filter_pushes(pushes_list)

        skip_ids = self.get_action_ids(skips_lists)

        return skip_ids

    def filter_pushes(self, pushes_list: list):
        """
        Filters a list of pushes into three lists: one containing the accepts, one containing the rejects and one containing the skips.

        Args:
            pushes_list (list): A list of dictionaries where each dictionary
                                represents a push with a "title" key.

        Returns:
            tuple: Three lists: one containing the accepts, one containing the rejects and one containing the skips.
        """
        accepts = []
        rejects = []
        skips = []

        for push in pushes_list:
            # Check if the title is 'Accept' and add to the accepts list
            if push.get("title") == "Accept":
                accepts.append(push)

            # Check if the title is 'Reject' and add to the rejects list
            elif push.get("title") == "Reject":
                rejects.append(push)

            # Check if the title is 'Skip' and add to the skips list
            elif push.get("title") == "Skip":
                skips.append(push)

        self.logger.debug("Accepts:", accepts)
        self.logger.debug("Rejects:", rejects)
        self.logger.debug("Skips:", skips)
        return accepts, rejects, skips

    def check_for_updates(self, **kwargs):
        """Check if there are any updates from the front end and update accordingly."""
        self.logger.debug("Checking for updates ...")
        pushes_list: list = self.get_notifications(rejects_and_accepts=False)

        self.logger.debug("Attempting to filter out accepts...")
        accepts_list, _, _ = self.filter_pushes(pushes_list)
        self.logger.debug("Accepts list:", accepts_list)

        self.logger.debug(
            "Attempting to check for any changes ans update pending.json ..."
        )
        self.check_and_update_generated_answer(accepts_list)
