from typing import Any, List
from modules.Helpers.Helpers import Helpers
from modules.Helpers.S3FileHandler import S3FileHandler
from modules.Notifier import Notifier


class S3Notifier(Notifier):
    def __init__(self, helper: Helpers) -> None:
        super().__init__(helper)

        if not isinstance(self.helper.file_handler, S3FileHandler):
            raise RuntimeError("S3FileHandler is required")

    def send_notification(self, method, flag, message=None):
        return super().send_notification(method, flag, message)

    def get_notifications(self, rejects_and_accepts=True) -> tuple[List[str], List[str]] | Any | list[Any]:
        return super().get_notifications(rejects_and_accepts)

    def delete_notification(self, action_id):
        return super().delete_notification(action_id)
