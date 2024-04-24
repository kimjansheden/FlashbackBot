import argparse
import os
import sys
from dotenv import load_dotenv
from CustomArgumentParser import CustomArgumentParser
from bot import FlashbackBot
from modules.Helpers.Helpers import Helpers
from modules.Helpers.create_and_get_file_handler import create_and_get_file_handler
from modules.Helpers.create_and_get_notifier import create_and_get_notifier
from modules.Helpers.create_and_get_model import create_and_get_model


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def parse_args():
    # Create the parser
    parser = CustomArgumentParser(
        description="Start the Flashback Bot with optional modes.",
        usage="%(prog)s [-h] --continuous CONTINUOUS [--test] [--model_path]",
        epilog="Examples:\n  python %(prog)s --continuous true\n  python %(prog)s --continuous false --test --model_path /path/to/model",
    )

    # Add arguments
    parser.add_argument(
        "-c",
        "--continuous",
        type=str2bool,
        required=True,
        help="Run the bot in continuous mode (true/false).",
    )
    parser.add_argument(
        "-t", "--test", action="store_true", help="Optional: Run the bot in test mode."
    )
    parser.add_argument(
        "-m",
        "--model_path",
        type=str,
        help="Optional: Path to the model file. Use this if you want to specify or update the model path in your configuration.",
    )

    # Parse arguments
    args = parser.parse_args()

    return args


def handle_model_path(model_path: str, helper: Helpers, existing_model_path: str):
    if not model_path:
        return
    if existing_model_path:
        while True:
            response = input(
                f"A model path is already set ({existing_model_path}). Do you want to replace it? (Y/n): "
            )
            if response in ["Y", "Yes"]:
                try:
                    helper.config.update_config("Model", {"model_path": model_path})
                    print(
                        f"Model path updated from {existing_model_path} to {model_path}."
                    )
                    break
                except Exception as e:
                    print(f"Failed to update model path. Reason: {e}. \n Exiting.")
                    sys.exit(1)
            elif response.lower() in ["n", "no"]:
                print("Keeping existing model path.")
                break
            else:
                print("Invalid response.")
    else:
        helper.config.update_config("Model", {"model_path": model_path})


# Here we configure how we want to run the bot. But the actual logic of the bot, we don't touch here.
if __name__ == "__main__":
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    args = parse_args()

    # Initialize flags
    continuous_run = args.continuous
    test_mode = args.test
    model_path = args.model_path

    # Load environment variables from .env file so they can be accessed as environment variables
    load_dotenv()
    file_handler = create_and_get_file_handler()
    helper = Helpers(file_handler)
    notifier = create_and_get_notifier(helper)

    existing_model_path = helper.config.get("Model", "model_path")

    handle_model_path(model_path, helper, existing_model_path)

    model = create_and_get_model(helper, file_handler)

    # Initialize the bot
    bot = FlashbackBot(file_handler, helper, notifier, model, [file_handler.cleanup])

    # Set up the environment based on the flags
    if test_mode:
        print("Running in test mode …")

    if continuous_run:
        print("Running in continuous mode …")
        while True:
            file_handler.get_or_refresh_token()
            bot.run(test_mode)
            bot.execute_callbacks()
            bot.random_sleep()
    else:
        print("Running in single execution mode …")
        bot.run(test_mode)
