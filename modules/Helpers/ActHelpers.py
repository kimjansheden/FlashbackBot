from datetime import datetime
from typing import TYPE_CHECKING

from modules.Helpers.PostHelpers import PostHelpers

if TYPE_CHECKING:
    from modules.act import Act


class ActHelpers:
    def __init__(self, act: "Act"):
        self.act = act
        self.logger = act.logger
        self.helper = act.helper
        self.notifier = act.notifier
        self.decisions_json_path = act.decisions_json_path
        self.pending_path = act.pending_path
        self.skipped_history_json_path = act.skipped_history_json_path
        self.post_helper = PostHelpers(self.helper, self.logger)

    def handle_rejected_responses(
        self,
        decisions: dict,
        actions_taken: dict,
        pending_posts: dict,
        rejected_action_ids: list,
    ):
        for rejected_action_id in rejected_action_ids:
            if rejected_action_id not in pending_posts:
                continue
            self.logger.info(f"{rejected_action_id} has been rejected")
            rejected_post = pending_posts[rejected_action_id]
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
            del pending_posts[rejected_action_id]
            self.helper.file_helper.update_json_file(
                self.pending_path, pending_posts, overwrite=True
            )

            # Remove the post from pushes
            self.notifier.delete_notification(rejected_action_id)

            # Add the post to actions_taken
            actions_taken[unique_post_id] = {
                "Action ID:": rejected_action_id,
                "Action:": "Rejected and sent back for regeneration",
            }
        return pending_posts, actions_taken

    def handle_approved_responses(
        self, actions_taken: dict, pending_posts: dict, approved_action_ids: list
    ):
        for approved_action_id in approved_action_ids:
            if approved_action_id in pending_posts:
                approved_post = pending_posts[approved_action_id]
                original_post_id = approved_post["original_post_id"]
                unique_post_id = approved_post["original_post"]["unique_id"]
                successful_post = self.act.post(approved_action_id, approved_post)

                # If a post has been successfully posted, the post has been removed from pending_posts
                if successful_post:
                    # Reload 'pending_posts' from the file to reflect the latest changes
                    pending_posts = self.helper.file_helper.read_json_file(
                        self.pending_path
                    )

                    # Add the post to actions_taken
                    actions_taken[unique_post_id] = {
                        "Action ID:": approved_action_id,
                        "Action:": "Posted",
                    }

        return pending_posts, actions_taken

    def handle_skipped_responses(
        self,
        actions_taken: dict,
        pending_posts: dict,
        skipped_action_ids: list,
    ):
        for skipped_action_id in skipped_action_ids:
            print("skipped_action_id:", skipped_action_id)
            if skipped_action_id not in pending_posts:
                print("skipped_action_id not in pending_posts")
                continue
            self.logger.info(f"{skipped_action_id} has been skipped")

            skipped_post = pending_posts[skipped_action_id]
            unique_post_id = skipped_post["original_post"]["unique_id"]

            # Add the post to skipped.json
            time_of_skip = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.post_helper.move_post_to_history(
                skipped_action_id,
                time_of_skip,
                self.pending_path,
                self.skipped_history_json_path,
                skip=True,
            )

            # Remove the post from pushes
            self.notifier.delete_notification(skipped_action_id)

            # Add the post to actions_taken
            actions_taken[unique_post_id] = {
                "Action ID:": skipped_action_id,
                "Action:": "Skipped; this post should not be answered.",
            }
        return pending_posts, actions_taken
