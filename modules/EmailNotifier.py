from .Helpers.Helpers import Helpers
from .Notifier import Notifier
class EmailNotifier(Notifier):
    def __init__(self, helper: Helpers) -> None:
        super().__init__(helper)