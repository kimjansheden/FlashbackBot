import atexit
from configparser import ConfigParser
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Union
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from mypy_boto3_s3 import S3Client
from regex import E
from modules.Helpers.FileHandler import FileHandler
from modules.Helpers.Helpers import Helpers
from modules.Logger import Logger


class S3FileHandler(FileHandler):
    PUT_REQUESTS = "PUTRequests"
    GET_REQUESTS = "GETRequests"

    def __init__(self, bucket_name, use_cache=True):
        """
        Initialize the S3 client and set the bucket name.
        :param bucket_name: The name of the S3 bucket to use.
        :param use_cache: Whether to use a cache to store the file contents. Default is True.
        """
        self.s3: S3Client = boto3.client("s3")
        self.bucket_name = bucket_name

        self.helper: None | Helpers = None
        self.config: None | ConfigParser = None
        self.log_level = None
        self.logger: None | Logger = None
        self.logger_assert_msg = "Logger is not initialized"

        self.use_cache = use_cache
        self.cache = {}
        self.lock = Lock()
        self.num_calls = 0
        atexit.register(self._log_num_calls)
        # Register a function to flush the cache at program exit
        atexit.register(self.flush_cache)

    def init(self, helper: Helpers):
        """
        Initialize the S3FileHandler.
        """
        self.helper = helper
        self.config = self.helper.config
        self.log_level = self.config["Logging"]["s3_fh_log_level"]
        self.logger = Logger(
            "S3FileHandler Logger", "s3_fh_log.log", self.log_level, file_handler=self
        )
        self.logger.debug("S3FileHandler initialized.")

    def read(self, path: str, mode: str = "r") -> str | bytes:
        """
        Read the content of a file from S3.
        :param path: The key of the file in the S3 bucket.
        :return: The file content as a string, or None if the file cannot be read.
        """
        if self.use_cache:
            # First, check if the file is in the cache before reading from S3
            with self.lock:
                if path in self.cache:
                    return self.cache[path]
            # If not in cache, read from S3
        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=path)
            self.num_calls += 1
            return response["Body"].read().decode("utf-8")
        except ClientError as e:
            if self.logger is not None:
                self.logger.debug(f"Could not read file {path} from S3: {e}")
            raise FileNotFoundError(f"Could not read file {path} from S3: {e}")

    def write(self, path: str, data: Union[str, bytes], mode: str = "w"):
        """
        Write or cache data to be written to a file in S3. Supports writing/caching both text and binary data.
        :param path: The key for the file in the S3 bucket.
        :param data: The data to write to the file. Can be str or bytes.
        :param mode: The mode in which to write the file. 'w' for text, 'wb' for binary.
        """
        if "b" in mode and isinstance(data, str):
            raise ValueError("Binary mode requires data to be bytes, not str.")
        if "b" not in mode and isinstance(data, bytes):
            raise ValueError("Text mode requires data to be str, not bytes.")
        if mode == "a":
            self.append_to_s3_file(path, data)
            return
        if self.use_cache:
            try:
                # Cache data instead of writing directly to S3
                with self.lock:
                    self.cache[path] = data
                if self.logger is not None and ".log" not in path:
                    self.logger.info(f"File {path} cached for future writing to S3.")
            except ClientError as e:
                if self.logger is not None and ".log" not in path:
                    self.logger.info(f"Could not write file {path} to S3: {e}")
        else:
            try:
                self.s3.put_object(Bucket=self.bucket_name, Key=path, Body=data)
                self.num_calls += 1
                if self.logger is not None and ".log" not in path:
                    self.logger.info(f"File {path} written to S3.")
            except ClientError as e:
                if self.logger is not None and ".log" not in path:
                    self.logger.debug(f"Could not write file {path} to S3: {e}")

    def delete(self, path):
        """
        Delete a file from S3.
        :param path: The key of the file to delete in the S3 bucket.
        """
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=path)
            self.num_calls += 1
            if self.logger is not None:
                self.logger.info(f"File {path} deleted from S3.")
        except ClientError as e:
            if self.logger is not None:
                self.logger.debug(f"Could not delete file {path} from S3: {e}")

    def append_to_s3_file(self, object_key, new_content):
        """
        Append new content to an existing S3 object. If the object does not exist,
        it will be created with the new content.
        :param object_key: Key of the object within the bucket.
        :param new_content: Content to be appended.
        """
        if self.use_cache:
            try:
                # Attempt to retrieve the existing content from cache first
                if object_key in self.cache:
                    existing_content = self.cache[object_key]
                else:
                    # If not in cache, attempt to read from S3
                    existing_content = self.read(object_key)

                updated_content = self._check_types_valid(new_content, existing_content)
                # Update the cache with the combined content
                self.cache[object_key] = updated_content
            except FileNotFoundError:
                # If the file doesn't exist, start with the new content
                self.cache[object_key] = new_content

            # Ensure the updated content is written to cache
            self.write(object_key, self.cache[object_key])
        else:
            # Attempt to retrieve the existing file from S3
            try:
                response = self.s3.get_object(Bucket=self.bucket_name, Key=object_key)
                self.num_calls += 1
                existing_content = response["Body"].read().decode("utf-8")
            except ClientError as error:
                # Check if the error was due to the object not being found
                if error.response["Error"]["Code"] == "NoSuchKey":  # type: ignore
                    existing_content = (
                        ""  # If the object does not exist, start with empty content
                    )
                else:
                    # Re-raise the exception if it was not a NoSuchKey error
                    raise

            # Combine existing content with new content
            updated_content = existing_content + new_content

            # Upload the combined data as a new version of the S3 object
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=updated_content.encode("utf-8"),
            )
            self.num_calls += 1

    def _check_types_valid(self, new_content, existing_content):
        if isinstance(existing_content, bytes) and isinstance(new_content, bytes):
            updated_content = existing_content + new_content
        elif isinstance(existing_content, str) and isinstance(new_content, str):
            updated_content = existing_content + new_content
        else:
            raise ValueError("Mismatched data types for append operation.")
        return updated_content

    def exists(self, path: str) -> bool:
        """
        Check if a file exists in the S3 bucket or in the cache.
        """
        # First check the cache
        if self.use_cache:
            with self.lock:
                if path in self.cache:
                    return True

        # If not in cache, check S3
        try:
            self.s3.head_object(Bucket=self.bucket_name, Key=path)
            self.num_calls += 1
            return True
        except (ClientError, BotoCoreError, NoCredentialsError):
            return False

    def get_size(self, path: str) -> int:
        """
        Returns the size of the file in bytes, either from S3 or the cache if available.
        """
        # First check the cache
        if self.use_cache:
            with self.lock:
                if path in self.cache:
                    cached_data = self.cache[path]
                    return len(
                        cached_data.encode("utf-8")
                        if isinstance(cached_data, str)
                        else cached_data
                    )

        # If not in cache, check S3
        try:
            response = self.s3.head_object(Bucket=self.bucket_name, Key=path)
            self.num_calls += 1
            return response["ContentLength"]
        except (ClientError, BotoCoreError, NoCredentialsError) as e:
            if self.logger is not None:
                self.logger.debug(
                    f"Could not retrieve file size for {path} from S3: {e}"
                )
            return 0

    def makedirs(self, path: str) -> None:
        raise NotImplementedError("make_dirs not implemented for S3FileHandler")

    def flush_cache(self):
        # Write all cached changes to S3
        with self.lock:
            for path, data in self.cache.items():
                try:
                    # Ensure data is in bytes if it's a string
                    if isinstance(data, str):
                        data = data.encode("utf-8")
                    self.s3.put_object(Bucket=self.bucket_name, Key=path, Body=data)
                    self.num_calls += 1
                    if self.logger is not None:
                        self.logger.info(f"Flushed {path} to S3.")
                except ClientError as e:
                    if self.logger is not None:
                        self.logger.info(f"Failed to flush {path} to S3: {e}")
            self.cache.clear()

    def _log_num_calls(self):
        if self.logger is not None:
            self.logger.info(f"Number of S3 calls made: {self.num_calls}")
        else:
            print(f"Number of S3 calls made: {self.num_calls}")

    @classmethod
    def get_s3_requests_used(
        cls, bucket_name, bucket_region, metric_name="PUTRequests"
    ) -> int:
        cloudwatch = boto3.client("cloudwatch", region_name=bucket_region)

        # Set the time period to retrieve data for
        end_time = datetime.now(timezone.utc).astimezone(None)
        # start_time = end_time - timedelta(days=1)  # Retrieve data for the last 24 hours
        start_time = datetime(
            2024, 1, 1, 0, 0, 0
        )  # Set start_time to January 1st, 2024

        # Retrieve statistics for PUT requests
        response = cloudwatch.get_metric_statistics(
            Namespace="AWS/S3",
            MetricName=metric_name,
            Dimensions=[
                {"Name": "BucketName", "Value": bucket_name},
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,  # Aggregation interval in seconds (here: 1 day)
            Statistics=[
                "Sum"
            ],  # Can also use 'Average', 'Minimum', 'Maximum', etc.
        )
        print(response)

        # Check and process the response to extract the number of requests
        if response and "Datapoints" in response and len(response["Datapoints"]) > 0:
            datapoint = response["Datapoints"][0]
            return datapoint["Sum"]
        else:
            return -1  # No datapoints were found for the specified period

    def cleanup(self):
        self.flush_cache()

    def get_or_refresh_token(self):
        return ""
