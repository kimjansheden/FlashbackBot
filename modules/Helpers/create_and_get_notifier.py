import os

from modules.Helpers.Helpers import Helpers
from modules.PushbulletNotifier import PushbulletNotifier


def create_and_get_notifier(helper: Helpers):
    """Function to create and get notifier.
    
    Returns:
        Notifier: Notifier object.
    """
    # Additional logic can be added here in the future as needed.
    notifier_type = os.getenv("NOTIFIER", "PUSHBULLET")
    if notifier_type == "PUSHBULLET":
        notifier = PushbulletNotifier(helper)
    else:
        raise ValueError("Notifier type not supported.")
    return notifier