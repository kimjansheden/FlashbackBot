from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.Helpers.DropboxFileHandler.DropboxFileHandler import DropboxFileHandler
from dropbox.exceptions import ApiError


class DropboxFileReader:
    """
    Handles the reading of files from Dropbox or a local cache depending on the caching policy.

    Attributes:
        handler (DropboxFileHandler): The handler responsible for managing Dropbox operations and associated utilities.
        dbx_client: The Dropbox client obtained from the handler.
        log_helper: A logging helper obtained from the handler for logging activities.
        lock: A threading lock from the handler to manage concurrent access.
        cache (dict): A local cache for file contents managed by the handler.
    """

    def __init__(self, handler: "DropboxFileHandler"):
        self.handler = handler
        self.dbx_client = handler.get_client()
        self.log_helper = handler.log_helper
        self.lock = handler.lock
        self.cache = handler.cache

    def read(self, path: str, mode: str = "r") -> str | bytes:
        """
        Reads content from the specified path, using the local cache if enabled, or directly from Dropbox otherwise.

        Args:
            path (str): The path of the file to read.
            mode (str): The file access mode, defaults to 'r' which indicates read mode.

        Returns:
            str | bytes: The content of the file, either as a string or bytes depending on the mode.

        Raises:
            ValueError: If the provided path is None.
        """
        if path is None:
            raise ValueError("Path cannot be None.")
        return (
            self.read_from_cache(path, mode)
            if self.handler.use_cache
            else self.read_from_dropbox(path, mode)
        )

    def read_from_cache(self, path: str, mode: str = "r") -> str | bytes:
        """
        Attempts to read a file from the local cache.

        Args:
            path (str): The path of the file in the local cache.
            mode (str): The file access mode.

        Returns:
            str | bytes: The cached content of the file, either as a string or bytes depending on the mode.

        Raises:
            ValueError: If caching is not enabled but this method is called.
        """
        logger = self.handler.get_logger()
        self.log_helper.debug(
            logger, f"Attempting to read {path} from cache", path=path
        )
        if self.handler.use_cache:
            if self.lock.locked():
                return self._get_file(path, mode)
            else:
                with self.lock:
                    return self._get_file(path, mode)
        else:
            raise ValueError(
                "Cache is not enabled; this function should not have been called"
            )

    def _get_file(self, path: str, mode: str = "r"):
        """
        Retrieves a file from the cache if present; otherwise, reads it from Dropbox.

        This method first checks the local cache for the file. If the file is not found in the cache,
        it will attempt to read it from Dropbox.

        Args:
            path (str): The path of the file to retrieve or read.
            mode (str): The file access mode, defaults to 'r' which indicates read mode.

        Returns:
            str | bytes: The content of the file, either as a string or bytes depending on the mode.

        Raises:
            FileNotFoundError: If the file cannot be found in Dropbox when attempting to read from it.
        """
        logger = self.handler.get_logger()
        # Check if the file is in the cache
        if path in self.cache:
            self.log_helper.debug(logger, f"File {path} found in cache.", path=path)
            return self.cache[path]
        # If the file is not in the cache, read it from Dropbox
        else:
            self.log_helper.debug(
                logger,
                f"File {path} not found in cache. Proceeding to read from Dropbox",
                path=path,
            )
            return self.read_from_dropbox(path, mode)

    def read_from_dropbox(self, path: str, mode: str = "r") -> str | bytes:
        """
          Reads a file from Dropbox using the specified path and mode, and caches it if caching is enabled.

          Parameters:
          - path (str): The Dropbox path of the file to be read.
          - mode (str): The mode in which to open the file. Defaults to 'r'. If 'b' is
          included in the mode, the file's content is returned as bytes; otherwise,
          it's returned as a decoded string.

          Returns:
          - str | bytes: The content of the file, either as a string or bytes depending
          on the mode.

          Raises:
          - FileNotFoundError: If the file cannot be found or an ApiError occurs during the file access.
          - Exception: For any other issues that occur during file handling.

          Notes:
          - Increments a call counter each time the Dropbox client is accessed.
          - If caching is enabled, the method stores the file content in the cache. If the caching mechanism's thread
        is not already locked, it locks the thread during the caching process to ensure thread safety.
        """
        logger = self.handler.get_logger()
        error_log_msg = f"Could not read file {path} from Dropbox: "
        try:
            self.log_helper.debug(
                logger, f"Attempting to read file {path} from Dropbox.", path=path
            )
            metadata, response = self.dbx_client.files_download(path)
            self.handler.num_calls += 1
            self.log_helper.debug(
                logger, f"File {path} read successfully from Dropbox.", path=path
            )
            self.log_helper.paranoid(
                logger, f"Metadata: {metadata}, Response: {response}"
            )
            # If use_cache is True, we'll store the file in the cache
            if self.handler.use_cache:
                # If thread is not already locked, lock it and store the file in the cache
                # Otherwise, just store the file in the cache
                if self.lock.locked():
                    self.cache[path] = response.content
                else:
                    with self.lock:
                        self.cache[path] = response.content
                self.log_helper.debug(
                    logger, f"File {path} stored in cache.", path=path
                )
            if "b" in mode:
                return response.content
            else:
                return response.content.decode("utf-8")
        except ApiError as e:
            print(error_log_msg, e)
            self.log_helper.debug(logger, error_log_msg, e, path=path)
            raise FileNotFoundError(error_log_msg)
        except Exception as e:
            print(error_log_msg, e)
            self.log_helper.debug(logger, error_log_msg, e, path=path)
            raise e
