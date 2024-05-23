from abc import ABC, abstractmethod
from typing import Any, List

from modules.Helpers.FileHandler import FileHandler
from modules.Helpers.LocalFileHandler import LocalFileHandler
from modules.Logger import Logger
from .Helpers.Helpers import Helpers

# Interface
class Notifier(ABC):
    def __init__(self, helper: Helpers, file_handler: FileHandler = LocalFileHandler()) -> None:
        self.helper = helper
        self.config = self.helper.config
        
        # Sets common logger for all notifiers. Override in each notifier if needed
        self.log_level = self.config["Logging"]["notifier_log_level"]
        self.logger = Logger("Notifier Logger", "notifier_log.log", self.log_level, file_handler)

    @abstractmethod
    def send_notification(self, method, flag, message=None):
        pass

    @abstractmethod
    def get_notifications(self, rejects_and_accepts=True) -> (tuple[List[str], List[str]] | Any | list[Any]):
        pass

    @abstractmethod
    def delete_notification(self, action_id):
        pass

    @abstractmethod
    def check_for_updates(self, **kwargs):
        """Checks for updates and differences between the notifier and the bot and acts accordingly.
        Provide kwargs as needed, e.g. filters.
        """
        pass
