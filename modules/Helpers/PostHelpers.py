from datetime import datetime
import inspect
import os
from typing import TYPE_CHECKING
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.collection import CollectionReference

if TYPE_CHECKING:
    from modules.Logger import Logger
    from modules.Helpers.Helpers import Helpers


class PostHelpers:
    def __init__(self, helper: "Helpers", logger: "Logger") -> None:
        self.helper = helper
        self.logger = logger

    def move_post_to_history(
        self,
        action_id: str,
        time_of_action,
        pending_path: str,
        history_path: str,
        skip=False,
    ):
        post = self.remove_post_from_pending(
            action_id=action_id, pending_path=pending_path
        )

        if not post:
            return

        # Add the time of the post/skip
        post["time_of_post"] = time_of_action
        if skip:
            post["status"] = "skipped"
        else:
            post["status"] = "posted"

        self._save_history_to_json(history_path, action_id, post)
        self._save_history_to_firestore(action_id, post)

    def remove_post_from_pending(self, pending_path: str, action_id: str):
        # Load the pending posts
        pending_posts = self.helper.file_helper.read_json_file(pending_path)
        self.logger.debug(f"pending_posts loaded from file: {pending_path}")

        # Check if the post exists in pending
        if action_id not in pending_posts:
            self.logger.debug(
                f"remove_post_from_pending: Post with ID {action_id} not found in pending."
            )
            return

        # Extract the post
        post = pending_posts.pop(action_id)

        self.logger.debug(
            f"Post {action_id} removed from pending. Remaining posts: {pending_posts.keys()}"
        )

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

        return post

    def _save_history_to_json(self, history_path: str, action_id: str, post: dict):
        # Load the history
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

    def _save_history_to_firestore(self, action_id: str, post: dict):
        # Initialize Firestore
        cred = credentials.Certificate(os.getenv("FIREBASE_ADMIN_JSON_PATH"))
        try:
            self.logger.debug("Initializing Firestore...")
            firebase_admin.initialize_app(cred)
            self.logger.debug("Firestore initialized successfully.")
        except ValueError as e:
            self.logger.debug(f"ValueError: {e}")
            if "The default Firebase app already exists" in str(e):
                self.logger.debug(
                    "Default Firebase app already exists. Using existing app."
                )
                try:
                    firebase_admin.get_app()
                    self.logger.debug("Firebase app retrieved successfully.")
                except ValueError as e:
                    self.logger.debug(f"ValueError: {e}")
                    raise
                except Exception as e:
                    self.logger.debug(f"Exception: {e}")
                    raise
        db = firestore.client()
        self.logger.debug("Firestore client initialized successfully.")

        if not db:
            class_name = self.__class__.__name__
            current_frame = inspect.currentframe()
            method_name = current_frame.f_code.co_name if current_frame is not None else "Unknown method"
            e_msg = f"An unknown error occurred in {class_name}.{method_name}. Failed to initialize Firestore."
            self.logger.error(e_msg)
            raise ValueError(e_msg)

        user_id = os.getenv("FIREBASE_UID")
        post_data = {
            "action_id": int(action_id),
            "original_post": {
                "unique_id": int(post["original_post"]["unique_id"]),
                "username": post["original_post"]["username"],
                "quote": {
                    "quoted_user": post["original_post"]["quote"]["quoted_user"],
                    "quoted_post": post["original_post"]["quote"]["quoted_post"],
                },
                "post": post["original_post"]["post"],
            },
            "generated_answer": post["generated_answer"],
            "original_post_id": int(post["original_post_id"]),
            "time_of_post": post["time_of_post"],
            "status": post["status"],
        }

        user_doc_ref = db.collection("postHistory").document(user_id)
        posts_collection_ref: CollectionReference = user_doc_ref.collection("posts")
        posts_collection_ref.add(post_data)

        user_doc_ref.set(
            {"lastPostTimestamp": firestore.firestore.SERVER_TIMESTAMP}, merge=True
        )

        self.logger.info(
            f"Post {action_id} moved to Firestore history and time updated successfully."
        )
