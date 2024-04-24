import re
from typing import List
from pushbullet import Pushbullet

from .Helpers.Helpers import Helpers
from .Notifier import Notifier
import os


class PushbulletNotifier(Notifier):
    def __init__(self, helper: Helpers) -> None:
        """
        Initialize the PushbulletNotifier class.

        :param helper: An instance of the Helpers class.
        """
        super().__init__(helper)

        # Get the full path to the dir where the script is running from
        self.script_dir = self.helper.file_helper.get_base_path(
            os.path.abspath(__file__), 2
        )

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
        self.logger.debug(pushes_list)

        # Filter out messages with the titles 'Accept' and 'Reject' and return them as two lists
        if rejects_and_accepts:
            accepts = []
            rejects = []

            for push in pushes_list:
                # Check if the title is 'Accept' and add to the accepts list
                if push.get("title") == "Accept":
                    accepts.append(push)

                # Check if the title is 'Reject' and add to the rejects list
                elif push.get("title") == "Reject":
                    rejects.append(push)

            accept_ids = self.get_action_ids(accepts)
            reject_ids = self.get_action_ids(rejects)
            return accept_ids, reject_ids

        return pushes_list

    def delete_notification(self, action_id):
        # Here it should connect the action_id with the right iden and then send for deletion
        pushes_list = self.pb.get_pushes()
        idens = []
        pattern = rf"Action ID: {action_id}"
        for push in pushes_list:
            # Check if "body" exists in the dictionary and search for the pattern 'Action ID: [number]'
            if "body" in push:
                match = re.search(pattern, push["body"])
                if match:
                    # Extract the idens
                    # For every action_id there are two pushes: a message and a reject/accept
                    iden = push["iden"]
                    idens.append(iden)

        for iden in idens:
            self.pb.delete_push(iden)

    def get_action_ids(self, pushes_list: list) -> List[str]:
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
