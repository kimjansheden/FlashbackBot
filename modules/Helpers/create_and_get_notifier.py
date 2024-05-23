import os

from modules.Helpers.FileHandler import FileHandler
from modules.Helpers.Helpers import Helpers
from modules.Helpers.LocalFileHandler import LocalFileHandler
from modules.PushbulletNotifier import PushbulletNotifier


def create_and_get_notifier(helper: Helpers, file_handler: FileHandler = LocalFileHandler()):
    """Function to create and get notifier.
    
    Returns:
        Notifier: Notifier object.
    """
    # Additional logic can be added here in the future as needed.
    notifier_type = os.getenv("NOTIFIER", "PUSHBULLET")
    if notifier_type == "PUSHBULLET":
        notifier = PushbulletNotifier(helper, file_handler=file_handler)
    else:
        raise ValueError("Notifier type not supported.")
    return notifier