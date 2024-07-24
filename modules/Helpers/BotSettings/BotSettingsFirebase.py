import json
import os
from typing import TYPE_CHECKING
from dotenv import load_dotenv
from modules.Helpers.BotSettings.BotSettings import BotSettings
import firebase_admin
from firebase_admin import credentials, firestore

if TYPE_CHECKING:
    from modules.Helpers.Helpers import Helpers
    from modules.Logger import Logger


class BotSettingsFirebase(BotSettings):
    def __init__(self, logger: "Logger"):
        super().__init__()

        self.logger = logger

        # Initialize Firebase Admin SDK
        load_dotenv()
        cred_path = os.getenv("FIREBASE_ADMIN_JSON_PATH", "")
        self.logger.debug(f"Using Firebase credential path: {cred_path}")
        cred = credentials.Certificate(cred_path)

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.get_app()

        # Firestore client
        self.db = firestore.client()

    def fetch_bot_settings(self, user_id: str):
        try:
            doc_ref = self.db.collection("postHistory").document(user_id)
            self.logger.debug(f"Fetching document for user_id: {user_id}")
            self.logger.debug(f"Document reference: {doc_ref.path}")

            # Get the document with document_id=user_id
            doc = doc_ref.get()

            # If the document exists, the snapshot's exists value will be True
            if doc.exists:
                self.logger.debug("Document exists")
                data = doc.to_dict()
                if data and "botSettings" in data:
                    self.logger.debug(
                        f"Fetched botSettings: {json.dumps(data['botSettings'], indent=4)}"
                    )
                    return data["botSettings"]
                else:
                    raise ValueError("No botSettings found in document.")
            else:
                raise ValueError("Document does not exist")
        except ValueError as e:
            self.logger.error(f"ValueError fetching bot settings: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Error fetching bot settings: {e}")
            return {}

    def load_settings(self):
        # Fetch user bot settings
        firebase_uid = os.getenv("FIREBASE_UID", "")
        self.logger.debug(f"Using FIREBASE_UID: {firebase_uid}")
        fetched_bot_settings = self.fetch_bot_settings(firebase_uid)

        # Assign fetched settings to instance variables
        self.minimum_new_tokens = fetched_bot_settings.get("minimum_new_tokens", 75)
        self.temperature = float(fetched_bot_settings.get("temperature", 0.5))
        self.do_sample = fetched_bot_settings.get("do_sample", True)
        self.top_k = fetched_bot_settings.get("top_k", 40)
        self.top_p = float(fetched_bot_settings.get("top_p", 0.7))
        self.repetition_penalty = float(
            fetched_bot_settings.get("repetition_penalty", 2.0)
        )
        self.no_repeat_ngram_size = fetched_bot_settings.get("no_repeat_ngram_size", 2)
        self.model_path = fetched_bot_settings.get("model_path", "")
        self.max_tokens = fetched_bot_settings.get("max_tokens", 256)
        self.reward_tokens = [
            token.strip() for token in fetched_bot_settings.get("reward_tokens", "")
        ]
        self.special_tokens = [
            token.strip() for token in fetched_bot_settings.get("special_tokens", "")
        ]
