import atexit
from configparser import ConfigParser
from threading import Lock
from typing import Optional, Union
import dropbox
from dropbox.exceptions import ApiError
from dropbox.files import (
    FileMetadata,
)
from modules.Helpers.DropboxFileHandler.DropboxHelpers import (
    DropboxFileAppender,
    DropboxFileReader,
    DropboxFileWriter,
)
from modules.Helpers.DropboxFileHandler.get_or_refresh_token import get_or_refresh_dropbox_token
from modules.Helpers.FileHandler import FileHandler
from modules.Helpers.Helpers import Helpers
from modules.Helpers.LogHelpers import LogHelpers
from modules.Logger import Logger


class DropboxFileHandler(FileHandler):
    def __init__(self, access_token, use_cache=False):
        """
        Initialize the Dropbox client and set the access token.
        :param access_token: The access token to authenticate with Dropbox.
        :param use_cache: Whether to use a cache to store the file contents. Default is False.
        """
        self.log_helper = LogHelpers(exclude_if_in_path=[".log"])
        self.access_token = access_token
        self.__dbx_client = dropbox.Dropbox(self.access_token)

        self.helper: None | Helpers = None
        self.config: None | ConfigParser = None
        self.log_level = None
        self.logger: None | Logger = None

        self.use_cache = use_cache
        self.cache: dict[str, Union[str, bytes]] = {}
        self.lock = Lock()
        self.num_calls = 0

        self.__reader = DropboxFileReader(self)
        self.__writer = DropboxFileWriter(self)
        self.__appender = DropboxFileAppender(self)

        atexit.register(self.log_num_calls)
        atexit.register(self.clear_cache_and_write_to_dropbox)

    def init(self, helper: Helpers):
        """
        Initialize the DropboxFileHandler.
        """
        self.helper = helper
        self.config = self.helper.config
        self.log_level = self.config["Logging"]["dbx_fh_log_level"]
        self.logger = Logger(
            "DropboxFileHandler Logger",
            "dbx_fh_log.log",
            self.log_level,
            file_handler=self,
        )
        self.logger.info(f"DropboxFileHandler initialized with log level {self.log_level}.")

    def get_reader(self):
        return self.__reader

    def get_writer(self):
        return self.__writer

    def get_appender(self):
        return self.__appender

    def get_client(self):
        return self.__dbx_client

    def get_logger(self):
        return self.logger

    def read(self, path: str, mode: str = "r") -> str | bytes:
        """
        Read the content of a file from Dropbox.

        :param path: The path of the file in Dropbox.
        :param mode: The mode in which the file is to be opened. Defaults to 'r' (read).
        :return: The file content as a string or bytes, depending on the file content and the specified mode.
        :raises ValueError: If the `path` is None.
        """
        return self.__reader.read(path, mode)

    def write(self, path: str, data: Union[str, bytes], mode: str = "w"):
        """
        See Super class' docstrings.
        """
        self.__writer.write(path, data, mode)

    def delete(self, path):
        """
        Delete a file from Dropbox.
        """
        try:
            self.__dbx_client.files_delete_v2(path)
            self.num_calls += 1
            self.log_helper.info(
                self.logger, f"File {path} deleted from Dropbox.", path=path
            )
        except ApiError as e:
            self.log_helper.debug(
                self.logger,
                f"Could not delete file {path} from Dropbox: {e}",
                path=path,
            )

    def append_to_dropbox_file(self, path: str, new_content: Union[str, bytes]):
        """
        Append new content to an existing Dropbox file. If the file does not exist,
        it will be created with the new content.

        :param path: The path of the file within Dropbox where the content will be appended.
        :param new_content: The content to be appended to the file. Can be a string or bytes.
        """
        self.__appender.append(path, new_content)

    def exists(self, path: str) -> bool:
        """
        Check if a file exists in Dropbox or in the cache.
        """
        if self.use_cache:
            with self.lock:
                if path in self.cache:
                    self.log_helper.debug(
                        self.logger,
                        f"File {path} found in cache.",
                        path=path,
                    )
                    return True
        try:
            self.__dbx_client.files_get_metadata(path)
            self.num_calls += 1
            self.log_helper.debug(
                self.logger, f"File {path} found in Dropbox.", path=path
            )
            return True
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_not_found():
                self.log_helper.debug(
                    self.logger,
                    f"File {path} not found in Dropbox or cache.",
                    path=path,
                )
                return False
            self.log_helper.debug(
                self.logger,
                f"Could not check if file {path} exists in Dropbox or cache: {e}",
                path=path,
            )
            raise  # Re-raise the exception if it's not a 'not found' error

    def get_size(self, path: str) -> int:
        """
        Returns the size of the file in bytes, either from Dropbox or the cache if available.
        """
        if self.use_cache:
            with self.lock:
                if path in self.cache:
                    cached_data = self.cache[path]
                    return len(
                        cached_data.encode("utf-8")
                        if isinstance(cached_data, str)
                        else cached_data
                    )
        try:
            metadata: Optional[FileMetadata] = self.__dbx_client.files_get_metadata(
                path
            )
            if isinstance(metadata, FileMetadata):
                return metadata.size
            else:
                self.log_helper.debug(
                    self.logger,
                    f"Could not retrieve file size for {path} from Dropbox.",
                    path=path,
                )
                raise TypeError(f"Expected FileMetadata, got {type(metadata)}")
        except ApiError as e:
            self.log_helper.debug(
                self.logger,
                f"Could not retrieve file size for {path} from Dropbox: {e}",
                path=path,
            )
            return 0

    def makedirs(self, path: str):
        """
        Creates the directory structure specified in 'path' on Dropbox. If the directory already exists,
        Dropbox will return a 'folder_already_exists' error, which we'll ignore since our goal is to ensure
        the directory exists. Any other exceptions encountered during the creation of the directory are
        re-raised.
        """
        try:
            self.__dbx_client.files_create_folder(path)
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_conflict():
                self.log_helper.info(
                    self.logger,
                    f"Directory {path} already exists on Dropbox.",
                    path=path,
                )
            else:
                raise

    def clear_cache_and_write_to_dropbox(self):
        """
        Write all cached changes to Dropbox and clear the cache. This method is called when the program exits.
        It is registered as an atexit handler.
        It can also be called at critical moments in the bot's lifecycle when files must be synced before it is allowed to continue.
        :return: None.
        """
        if not self.use_cache:
            return
        # log calls are log_debug because they are not normal calls that should be done to the API when everything works as it should

        # Deactivate use_cache while we write the cached items to the API and clear the cache
        self.use_cache = False

        self.log_helper.debug(
            self.logger,
            f"Attempting to write all cached changes to Dropbox. Cache size: {len(self.cache)} items.",
        )
        total_size = sum(
            len(data.encode("utf-8") if isinstance(data, str) else data)
            for data in self.cache.values()
        )
        total_size_to_display, unit = self.convert_size_to_display(total_size)

        # Log the formatted size
        self.log_helper.debug(
            self.logger,
            f"Total data size to write: {total_size_to_display:.2f} {unit}.",
        )
        cache_items = list(self.cache.items())
        with self.lock:
            for path, data in cache_items:
                if isinstance(data, bytes):
                    mode = "b"
                else:
                    mode = "w"
                self.write(path, data, mode=mode)
            print("Cleared cache.")
            self.cache.clear()
            print("All cached changes written to Dropbox.")
            # Reactivate use_cache after we've written the cached items to the API and cleared the cache
            self.use_cache = True

    def log_num_calls(self):
        org_use_cache = self.use_cache
        if org_use_cache:
            # Deactivate use_cache while we write the updated log with the number of calls to the API
            self.use_cache = False
        if self.logger is not None:
            self.logger.info(f"Number of Dropbox calls made: {self.num_calls}")
        else:
            print(f"Number of Dropbox calls made: {self.num_calls}")

        if org_use_cache:
            # Reactivate use_cache after we've written the updated log with the number of calls to the API
            self.use_cache = True

    def convert_size_to_display(self, size_in_bytes: int) -> tuple[float, str]:
        # Convert and print the size depending on its magnitude
        if size_in_bytes < 1000 * 1024:  # Less than 1000 KB
            size_to_display = size_in_bytes / 1024
            unit = "KB"
        elif size_in_bytes < 1000 * 1024**2:  # Between 1000 KB and 999 MB
            size_to_display = size_in_bytes / 1024**2
            unit = "MB"
        else:  # Greater than or equal to 1000 MB
            size_to_display = size_in_bytes / 1024**3
            unit = "GB"

        return size_to_display, unit

    def cleanup(self):
        self.clear_cache_and_write_to_dropbox()

    def get_or_refresh_token(self):
        self.token = get_or_refresh_dropbox_token()
