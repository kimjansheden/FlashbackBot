from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.Logger import Logger
    from modules.Helpers.Helpers import Helpers


class PostHelpers:
    def __init__(self, helper: "Helpers", logger: "Logger") -> None:
        self.helper = helper
        self.logger = logger

    def move_post_to_history(self, action_id, time_of_action, pending_path, history_path, skip=False):
        # Load the pending posts
        pending_posts = self.helper.file_helper.read_json_file(pending_path)
        self.logger.debug(f"pending_posts loaded from file: {pending_path}")

        # Check if the post exists in pending
        if action_id not in pending_posts:
            self.logger.debug(f"Post with ID {action_id} not found in pending.")
            return

        # Extract the post
        post = pending_posts.pop(action_id)

        self.logger.debug(
            f"Post {action_id} removed from pending. Remaining posts: {pending_posts.keys()}"
        )

        # Add the time of the post/skip
        if skip:
            post["time_of_skip"] = time_of_action
        else:
            post["time_of_post"] = time_of_action

        # Save the updated pending posts back to pending.json
        self.logger.debug("Pending posts before update:", pending_posts)
        success = self.helper.file_helper.update_json_file(
            filepath=pending_path, new_data=pending_posts, overwrite=True
        )
        if success:
            self.logger.debug(
                f"Pending posts file {pending_path} updated successfully for post ID {action_id}."
            )
        else:
            self.logger.debug(
                f"Failed to update pending posts file for post ID {action_id}."
            )
        updated_pending_posts = self.helper.file_helper.read_json_file(pending_path)
        self.logger.debug(f"pending_posts loaded from file: {pending_path}")
        self.logger.debug("Pending posts after update:", updated_pending_posts)

        post_history = self.helper.file_helper.read_json_file(history_path)

        # Add the post to the history
        post_history[action_id] = post

        # Save the updated history back to post_history.json
        self.helper.file_helper.update_json_file(
            filepath=history_path, new_data=post_history, overwrite=True
        )

        self.logger.info(
            f"Post {action_id} moved to history and time updated successfully."
        )
