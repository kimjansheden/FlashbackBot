import json
import os
from typing import Dict

from dotenv import load_dotenv

from main import FlashbackBot
from modules.Helpers.DropboxFileHandler.DropboxFileHandler import DropboxFileHandler
from modules.Helpers.Helpers import Helpers
from modules.Helpers.create_and_get_file_handler import create_and_get_file_handler
from modules.Helpers.create_and_get_model import create_and_get_model
from modules.PushbulletNotifier import PushbulletNotifier


def bot_handler(event: Dict, context):
    # Set test_mode based on incoming event data
    test_mode = event.get("test_mode", False)
    message = "Bot execution completed successfully!"

    file_handler = create_and_get_file_handler()
    # Refresh access token if necessary
    file_handler.get_or_refresh_token()

    helper = Helpers(file_handler)
    notifier = PushbulletNotifier(helper)
    load_dotenv()
    model_path = os.getenv("MODEL_PATH", "")
    model = create_and_get_model(helper, file_handler, model_path)
    bot = FlashbackBot(file_handler, helper, notifier, model)
    bot.run(test_mode=test_mode)
    if isinstance(file_handler, DropboxFileHandler):
        file_handler.clear_cache_and_write_to_dropbox()
        file_handler.log_num_calls()
        message += " And all files were successfully written to Dropbox"

    return {"statusCode": 200, "body": json.dumps(message)}
