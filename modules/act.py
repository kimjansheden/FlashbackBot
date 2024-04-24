import json
from modules.Helpers.FileHandler import FileHandler
from modules.Logger import Logger
from .Notifier import Notifier
from .post import Post
from .Model import Model
from .Helpers.Helpers import Helpers

import os


class Act:
    def __init__(
        self,
        helper: Helpers,
        notifier: Notifier,
        file_handler: FileHandler,
        model: Model,
    ) -> None:
        # LOAD MODULES AND CONFIG
        self.helper = helper
        self.notifier = notifier
        self.poster = Post(self.helper, self.notifier, file_handler)
        self.config = self.helper.config
        self.log_level = self.config["Logging"]["act_log_level"]
        self.logger = Logger(
            "Actions Logger", "act_log.log", self.log_level, file_handler=file_handler
        )
        self.file_handler = file_handler

        # LOAD PATHS
        # Get the full path to the dir where the script is running
        self.script_dir = self.helper.file_helper.get_base_path(
            os.path.abspath(__file__), 2
        )

        self.posts_dir = os.path.join(self.script_dir, "posts")
        self.last_action_id_path = os.path.join(self.posts_dir, "last_action_id.txt")
        self.pending_path = os.path.join(self.posts_dir, "pending.json")
        self.decisions_json_path = os.path.join(self.posts_dir, "decisions.json")
        self.post_history_json_path = os.path.join(self.posts_dir, "post_history.json")
        self.post_status_json_path = os.path.join(self.posts_dir, "post_status.json")

        # BUILD THE MODEL
        self.model: Model = model

        # LOAD NECESSARY VARIABLES
        # Load Time
        # Check if 24 hours have passed since the bot last received an answer
        self.has_been_24_h_since_response_to_bot = (
            self.helper.check_if_min_interval_since_response()
        )
        self.can_post_again = None

        # Get the username from the config file
        self.username = os.getenv("USERNAME")

        # Load the decisions file
        self.decisions = self.helper.file_helper.read_json_file(
            self.decisions_json_path
        )

    def post(self, approved_id, approved_post):
        self.can_post_again = self.check_if_allowed_to_post(approved_id)
        # If conditions are passed
        if self.can_post_again[0]:
            self.logger.info(self.can_post_again[1])
            self.logger.info(f"Posting Action ID {approved_id}")
            successful_post = self.poster.post(approved_id, approved_post)
            if successful_post:
                self.logger.info(f"Successfully posted Action ID {approved_id}")
                return True
            else:
                self.logger.info(f"Failed to post Action ID {approved_id}")
                return False
        else:
            self.logger.info(
                f"Bot is not yet allowed to post Action ID {approved_id} due to the following reason(s): {self.can_post_again[1:]}"
            )
            return False

    def notify(self, flag, message, **kwargs):
        """
        Notify based on the given methods and their flags.

        :param kwargs: Dictionary of notification methods and their flags.
                    For example: push=True, email=False
        """

        # Iterate over each key-value pair in kwargs
        # 'action' is the method (e.g., "push", "email") and 'flag' is its value (True or False).
        for action, should_send in kwargs.items():
            # If the flag for this action is True, proceed to send the notification
            if should_send:
                # Using getattr to dynamically get the method from the notifier object based on the action.
                # For example, if action is "push", it fetches the method 'send_push_notification'.
                # That's why it's important to name future methods with the same naming convention as we have done so far.
                method = getattr(self.notifier, f"send_{action}_notification")

                # Call the fetched method
                method(flag=flag, message=message)

    def act(self, decisions=None):
        """The bot takes actions based on the decisions it previously made.

        Actions are:
        1. Send notifications to user, prompting for:
            - accept or decline of generated post
            - new answers the bot has got
            - messages posted on the forum.
        2. Posts message to forum.

        Args:
            decisions (dict): A dictionary containing the decisions the bot has made.
                            Each key is a post ID, and the value is another dictionary with the following structure:

                            {
                                "username": str,  # The username of the person who made the post.

                                "quote": {
                                    "quoted_user": str,  # The username of the person being quoted.

                                    "quoted_post": list,  # A list containing the quoted text.
                                },

                                "post": str  # The text of the post itself.
                            }

            Example:
            {
                "12345": {
                    "username": "Foo",

                    "quote": {
                        "quoted_user": "Goo",

                        "quoted_post": ["Some quoted text here"]
                    },

                    "post": "The post text here"
                },

                "54321": {
                    "username": "Foo-Goo",

                    "quote": {
                        "quoted_user": "Goo-Foo",

                        "quoted_post": ["Another quoted text"]
                    },

                    "post": "Another post text here"
                }
            }

        Returns:
            dict: A dictionary containing the actions that have been taken.
        """
        # The actions the bot has taken: A dict with the key as an id that is being incremented for each new action and the value as a dict with the following structure:
        # "generated_answer": "the generated answer",
        # "reason", "the reason for action"
        actions_taken = {}

        # Create a dictionary to hold all pending posts
        pending_posts = {}

        if decisions is None:
            decisions = {}

        self.logger.debug("Original decisions: " + json.dumps(decisions, indent=4))
        keys_to_remove = []
        len_decisions = len(decisions)

        if len_decisions == 0:
            self.logger.info("Bot is up to speed!")
        else:
            self.logger.info(f"Bot is taking action on {len_decisions} decisions.")

        # Create last_action_id and pending files if they don't exist
        self._initialize_files()

        # Get the last action id
        last_action_id = int(
            self.helper.file_helper.read_file(self.last_action_id_path)
        )

        # Generate an answer from the model
        for post_id, decision in decisions.items():
            try:
                inferred_answer, reason = self.generate_answer(decision)
                unique_post_id = decision["unique_id"]
                last_action_id += 1
                actions_taken[unique_post_id] = {
                    "Action ID:": last_action_id,
                    "generated_answer": inferred_answer,
                    "reason": reason,
                }

                # With the answer successfully generated, the decision is now handled and can be removed
                # First we save the generated answer together with the original post to a temporary holding place in pending.json
                # Save the generated answer and original post to a dict with the last_action_id as key
                pending_posts[last_action_id] = {
                    "original_post": decision,
                    "generated_answer": inferred_answer,
                    "original_post_id": post_id,
                }

                # Add the current decisions for removal
                keys_to_remove.append(post_id)
            except Exception as e:
                self.logger.error(f"Could not generate an answer: {e}")
                return actions_taken

        self.logger.debug("Keys to be removed: " + ", ".join(map(str, keys_to_remove)))

        # Save the dict to pending.json and delete it from decisions
        self._update_files(pending_posts, keys_to_remove, decisions)

        # Write the latest last_action_id to the file so the ids will always be unique.
        self.helper.file_helper.write_file(self.last_action_id_path, last_action_id)

        self.logger.info(
            "Actions taken:" + json.dumps(actions_taken, indent=4, ensure_ascii=False)
        )

        # Here we have generated responses, saved them in pending, and removed the corresponding original posts in decisions.
        # Then comes notify and ask for approval – and they should only read from the latest file in the chain, at this stage pending.json
        try:
            self.ask_for_approval()
        except Exception as e:
            self.logger.info(f"Could not ask for approval: {e}")
            return actions_taken

        # Here we have sent the responses to the frontend, and now we must wait for a response. So if this runs periodically, there will be nothing new to send to the frontend. But we must check every time if there is something to retrieve from the notifier.

        # Get the responses from the frontend (approved and rejected IDs)
        approved_ids, rejected_ids = self.notifier.get_notifications()

        # Now we know which Action IDs have been rejected and which have been accepted.

        # If the user rejects the generated response, we just need to put back the decision in decisions, and the flow will generate a new response in the next round.
        # Also, the old corresponding push must be deleted because the newly generated response will get a new action_id

        # Read the data from pending.json
        pending_posts = self.helper.file_helper.read_json_file(self.pending_path)

        # Handle approved responses
        pending_posts, actions_taken = self._handle_approved_responses(
            actions_taken, pending_posts, approved_ids
        )

        # Handle rejected responses
        pending_posts, actions_taken = self._handle_rejected_responses(
            decisions, actions_taken, pending_posts, rejected_ids
        )

        return actions_taken

    def _handle_rejected_responses(
        self,
        decisions: dict,
        actions_taken: dict,
        pending_posts: dict,
        rejected_ids: list,
    ):
        for rejected_id in rejected_ids:
            if rejected_id not in pending_posts:
                continue
            self.logger.info(f"{rejected_id} has been rejected")
            rejected_post = pending_posts[rejected_id]
            original_post_id = rejected_post["original_post_id"]
            unique_post_id = rejected_post["original_post"]["unique_id"]

            # Check if the original_post_id is NOT already in decisions before adding it back
            if original_post_id not in decisions:
                # Add the post back to decisions.json ONLY if it doesn't already exist
                decisions[original_post_id] = rejected_post["original_post"]
                self.helper.file_helper.update_json_file(
                    self.decisions_json_path, decisions, overwrite=True
                )

            # Remove the post from pending.json
            del pending_posts[rejected_id]
            self.helper.file_helper.update_json_file(
                self.pending_path, pending_posts, overwrite=True
            )

            # Remove the post from pushes
            self.notifier.delete_notification(rejected_id)

            # Add the post to actions_taken
            actions_taken[unique_post_id] = {
                "Action ID:": rejected_id,
                "Action:": "Rejected and sent back for regeneration",
            }
        return pending_posts, actions_taken

    def _handle_approved_responses(
        self, actions_taken: dict, pending_posts: dict, approved_ids: list
    ):
        for approved_id in approved_ids:
            if approved_id in pending_posts:
                approved_post = pending_posts[approved_id]
                original_post_id = approved_post["original_post_id"]
                unique_post_id = approved_post["original_post"]["unique_id"]
                successful_post = self.post(approved_id, approved_post)

                # If a post has been successfully posted, the post has been removed from pending_posts
                if successful_post:
                    # Reload 'pending_posts' from the file to reflect the latest changes
                    pending_posts = self.helper.file_helper.read_json_file(
                        self.pending_path
                    )

                    # Add the post to actions_taken
                    actions_taken[unique_post_id] = {
                        "Action ID:": approved_id,
                        "Action:": "Posted",
                    }

        return pending_posts, actions_taken

    def check_if_allowed_to_post(self, approved_id=None):
        """Determines if the bot is allowed to post again (overall, i.e. at all). So even if we have Accept messages from the user, the following conditions must still be true.

        When we are at this stage, the bot has either generated an answer to an answer it's received, or 24 h have passed since it last received an answer, thus generating an answer to a random post. Or none of that has happened (it could be somewhere in between not having received an answer and 24 h having passed since it last received an answer).

        Either way, those conditions are for GENERATING answers. This function is about determining if the bot is allowed to POST any answers it has generated.

        The following must be true:
            - The bot has posted less than 5 posts within the last 24 hours.
            - There must be a random duration between 5 minutes and 2 hours between the bot’s posts. So, first check when the bot last posted (self.helpers.load_time_of_last_post()). Then check if it has been 2 hours since then. If it has, the bot passes this check. If it has not been 2 hours, a waiting time is randomly determined between 5 minutes and 2 hours. Then, there will be a check once that time has elapsed.
            - Anything else that makes its behavior appear more human?
        """
        self.logger.info("Checking if bot is allowed to post.")
        # Check if bot has posted less than 5 posts within the last 24 hours
        if not self.helper.has_posted_less_than_5_times_in_last_24_hours(
            self.post_history_json_path, self.logger
        ):
            return False, "Bot has already posted 5 times or more in the last 24 hours."

        # Check if 2 h have passed since the bot's last answer. If not, wait a random interval between 5 min-2 h
        if not self.helper.done_waiting(self.post_status_json_path, self.logger):
            return False, "Bot is still waiting."

        # Login the bot to Flashback, either by restoring a previously logged in session or by starting a new one
        if not self.poster.login():
            return False, "Bot failed to log in to Flashback."

        # Finally, check whether another instance is posting right now. If there is an ongoing posting, there is a risk of double posting. Therefore we wait until the lock is open
        post_lock = self.config["Misc"]["post_lock"].lower() == "true"
        if post_lock:
            return (
                False,
                "Posting is locked; another instance is posting right now. Waiting …",
            )

        # Extra check to ensure bot doesn't post the same answer twice. If approved_id is in post_history already, then something is wrong and needs to be fixed
        post_history = self.helper.file_helper.read_json_file(
            self.post_history_json_path
        )
        if approved_id in post_history:
            return (
                False,
                f"ID {approved_id} has already been posted! Something is wrong with the bot.",
            )

        return True, "Bot is allowed to post."

    def generate_answer(self, post: dict):
        """
        Generates an answer to a forum post using an AI model. The method takes a post dictionary as input,
        extracts relevant information, and sends it to the AI model for generating an appropriate response.

        Args:
            post (dict): A dictionary containing details about the forum post. Expected keys are:
                - 'username': The username of the person who made the post.
                - 'post': The text content of the post.
                - 'quote': A dictionary containing quoted information, with keys:
                    - 'quoted_user': The username of the person being quoted.
                    - 'quoted_post': A list of strings representing the quoted text.

        Returns:
            tuple: A tuple containing two elements:
                - inferred_answer (str): The answer generated by the AI model.
                - reason (str): The reason for generating the answer, which can be either "They wrote to the bot." if the bot itself was quoted, or "Random answer." otherwise.

        Example:
            post = {
                'unique_id': '12345'
                'username': 'JohnDoe',
                'post': 'What is the meaning of life?',
                'quote': {
                    'quoted_user': 'JaneDoe',
                    'quoted_post': ['That is a good question.']
                }
            }
            inferred_answer, reason = generate_answer(post)
        """
        quoted_user = post["quote"]["quoted_user"]

        # Determine the reason for the answer
        reason: str = ""
        if quoted_user == self.username:
            reason = "They wrote to the bot."
        else:
            reason = "Random answer."

        # Send this full context to the model to get an inferred answer
        inferred_answer: str = self.model.generate_answer(post)

        return inferred_answer, reason

    def ask_for_approval(self):
        """The bot sends a notification to the user with the answer it has generated. It will then wait for the user's approval."""
        pending_data = self.helper.file_helper.read_json_file(self.pending_path)
        kind = "request_approval"
        message = ""

        # Get pushes and parse them for existing action IDs
        existing_action_ids = {
            push["body"].split("\n")[0].split(": ")[1]
            for push in self.notifier.get_notifications(rejects_and_accepts=False)
            if "body" in push and push["body"].startswith("Action ID")
        }

        self.logger.debug("existing_action_ids:", existing_action_ids)

        for action_id, data in pending_data.items():
            # Check if action_id is already present in pushes
            if action_id in existing_action_ids:
                self.logger.debug(
                    f"Skipping action_id {action_id} as it's already been pushed."
                )
                continue  # Skip this action_id, since it's already been pushed.

            original_username = data["original_post"]["username"]
            quoted_user = data["original_post"]["quote"]["quoted_user"]
            quoted_post = data["original_post"]["quote"]["quoted_post"]
            original_post = data["original_post"]["post"]
            generated_answer = data["generated_answer"]
            message += f"Action ID: {action_id}\nFrom Username: {original_username}\nQuoted User: {quoted_user}\nQuoted Post: {quoted_post}\nOriginal Post: {original_post}\nGenerated Answer: {generated_answer}"
        if message:
            self.notify(flag=kind, message=message, push=True, email=True)

    def _initialize_files(self):
        self.helper.file_helper.create_file_if_not_exist(
            filepath=self.last_action_id_path, what_to_write="0"
        )
        self.helper.file_helper.create_file_if_not_exist(
            filepath=self.pending_path, what_to_write=""
        )

    def _update_files(self, pending_posts, keys_to_remove, decisions):
        success = self.helper.file_helper.update_json_file(
            self.pending_path, pending_posts
        )
        self.logger.paranoid("success:", success)
        self.logger.paranoid("pending_posts:", pending_posts)

        # If the dict is successfully saved to pending.json we can safely delete it from decisions so we don't have to regenerate a new answer every time the script restarts
        if success:
            # Remove the decisions we have generated answers for from the dictionary
            for key in keys_to_remove:
                decisions.pop(key)

            self.logger.debug("Updating decisions.json with:", decisions)
            self.helper.file_helper.update_json_file(
                self.decisions_json_path, decisions, overwrite=True
            )
