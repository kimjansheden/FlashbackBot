from datetime import datetime, timezone
import os
from typing import List, Optional
from dotenv import load_dotenv
import dropbox
from dropbox.files import ListFolderResult, Metadata, FileMetadata
from dropbox.exceptions import ApiError
from modules.Helpers.DropboxFileHandler.get_or_refresh_token import (
    get_or_refresh_dropbox_token,
)

from modules.Logger import Logger
from .Helpers.Helpers import Helpers
from .Helpers.LocalFileHandler import LocalFileHandler


def download_files(local_backup_directory: str, from_function_dir=False):
    helper = Helpers(LocalFileHandler())
    script_dir = helper.file_helper.get_base_path(os.path.abspath(__file__), 2)
    log_file = os.path.join(script_dir, "db_backup_log.log")
    log_level = "INFO"
    logger = Logger("Dropbox Backup Logger", log_file, log_level, file_handler)
    helper.log_helper.info(
        logger, f"Attempting to download files to: {local_backup_directory}"
    )

    # Define the Dropbox folder path based on the 'from_function_dir' flag
    folder_path = "/function" if from_function_dir else ""

    # List all files in the Dropbox folder
    try:
        folder_list: Optional[ListFolderResult] = dbx.files_list_folder(
            folder_path, recursive=True
        )
    except ApiError as e:
        helper.log_helper.info(logger, f"Dropbox API Error: {e}")
        return

    if not folder_list:
        helper.log_helper.info(logger, "No files found in the Dropbox folder")
        return
    entries: List[Metadata] = folder_list.entries

    num_local_files, num_local_files_up_to_date, num_calls = download_entries(
        local_backup_directory, helper, logger, folder_path, entries
    )

    helper.log_helper.info(
        logger,
        f"{num_local_files_up_to_date}/{num_local_files} local files were already up to date",
    )
    helper.log_helper.info(logger, f"Number of Dropbox API calls made: {num_calls}")


def download_entries(
    local_backup_directory: str,
    helper: Helpers,
    logger: Logger,
    folder_path: str,
    entries: List[Metadata],
):
    num_local_files = 0
    num_local_files_up_to_date = 0
    num_calls = 0
    for entry in entries:
        if not isinstance(entry, FileMetadata):
            continue
        dropbox_path = entry.path_lower
        local_relative_path = dropbox_path[len(folder_path) :].lstrip("/")
        local_file_path = os.path.join(local_backup_directory, local_relative_path)

        helper.log_helper.debug(logger, f"Dropbox Path: {dropbox_path}")
        helper.log_helper.debug(logger, f"Local File Path: {local_file_path}")

        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

        if os.path.exists(local_file_path):
            num_local_files += 1
            # Ensure local_file_mod_time is offset-aware in UTC
            local_file_mod_time = datetime.fromtimestamp(
                os.path.getmtime(local_file_path), tz=timezone.utc
            )

            # Ensure dropbox_file_mod_time is also considered as offset-aware in UTC
            dropbox_file_mod_time = entry.server_modified.replace(tzinfo=timezone.utc)

            if dropbox_file_mod_time > local_file_mod_time:
                with open(local_file_path, "wb") as f:
                    dbx.files_download_to_file(f.name, entry.path_lower)
                num_calls += 1
                helper.log_helper.info(
                    logger,
                    f"Downloaded {dropbox_path} to {local_file_path} (Dropbox file was newer)",
                )
            else:
                num_local_files_up_to_date += 1
                helper.log_helper.info(
                    logger, f"Skipped {dropbox_path} (local version is up to date)"
                )
        else:
            with open(local_file_path, "wb") as f:
                dbx.files_download_to_file(f.name, entry.path_lower)
            num_calls += 1
            helper.log_helper.info(
                logger,
                f"Downloaded {dropbox_path} to {local_file_path} (local file did not exist)",
            )

    return num_local_files, num_local_files_up_to_date, num_calls


def choose_download_dir(use_backup_dir: bool):
    """Choose the local backup directory based on the 'use_backup_dir' flag.
    If 'use_backup_dir' is True, the download directory will be in the 'backup/from_dropbox' directory.
    Otherwise, the download directory will be in the main directory.


    Args:
        use_backup_dir (bool): Whether to use the backup directory or the main directory.

    Returns:
        str: The local backup directory.
    """
    if use_backup_dir:
        local_backup_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backup"
        )
        local_backup_directory = os.path.join(local_backup_directory, "from_dropbox")
        return local_backup_directory
    else:
        local_backup_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        return local_backup_directory


if __name__ == "__main__":
    load_dotenv()
    os.environ["BASE_PATH"] = "LOCAL"
    # Initialize the Dropbox client with the access token
    dropbox_token = get_or_refresh_dropbox_token()
    dbx = dropbox.Dropbox(dropbox_token)

    file_handler = LocalFileHandler()
    helper = Helpers(file_handler)
    local_backup_directory = choose_download_dir(use_backup_dir=True)
    helper.file_helper.create_directory_if_not_exist(local_backup_directory)
    download_files(local_backup_directory, from_function_dir=True)
