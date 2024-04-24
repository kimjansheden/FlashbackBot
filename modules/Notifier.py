from abc import ABC, abstractmethod
from typing import Any, List

from modules.Logger import Logger
from .Helpers.Helpers import Helpers

# Interface
class Notifier(ABC):
    def __init__(self, helper: Helpers) -> None:
        self.helper = helper
        self.config = self.helper.config
        
        # Sets common logger for all notifiers. Override in each notifier if needed
        self.log_level = self.config["Logging"]["notifier_log_level"]
        self.logger = Logger("Notifier Logger", "notifier_log.log", self.log_level)

    @abstractmethod
    def send_notification(self, method, flag, message=None):
        pass

    @abstractmethod
    def get_notifications(self, rejects_and_accepts=True) -> (tuple[List[str], List[str]] | Any | list[Any]):
        pass

    @abstractmethod
    def delete_notification(self, action_id):
        pass
