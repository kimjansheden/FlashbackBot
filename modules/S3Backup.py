from datetime import datetime
import boto3
import os
from dateutil.tz import tzutc

from dotenv import load_dotenv

from .Helpers.Helpers import Helpers
from .Helpers.LocalFileHandler import LocalFileHandler

s3 = boto3.client("s3")


def download_files(bucket_name, local_backup_directory, from_function_dir=False):
    print(f"Attempting to download files to: {local_backup_directory}")
    # Define the prefix based on the 'from_function_dir' flag
    # This allows selective download from the 'function' directory in S3
    prefix = 'function/' if from_function_dir else ''
    
    # List all objects in the bucket
    objects = s3.list_objects_v2(Bucket=bucket_name).get("Contents", [])

    num_local_files = 0
    num_local_files_up_to_date = 0
    num_calls = 0

    for obj in objects:
        s3_key = obj["Key"]  # type: ignore
        print(f"S3 Key: {s3_key}")  # Debugging line to check the S3 key

        # Sanitize the S3 key to avoid paths leading to unintended directories
        # Remove leading slashes and replace problematic characters as needed
        # sanitized_s3_key = s3_key.lstrip("/").replace("/function", "function")
        # Adjust the local file path based on 'from_function_dir' flag
        # This determines whether files are placed directly in 'backup' or within a 'function' subdirectory
        if from_function_dir:
            # Remove the 'function/' prefix from the S3 key when constructing the local path
            # This is done to place files directly in the 'backup' directory as they are within 'function' in S3
            sanitized_s3_key = s3_key[len(prefix):].lstrip("/")
        else:
            # Original sanitization for direct local path usage
            sanitized_s3_key = s3_key.lstrip('/')

        local_file_path = os.path.join(local_backup_directory, sanitized_s3_key)
        print(
            f"Creating directories under: {os.path.dirname(local_file_path)}"
        )  # Confirm the corrected path

        # Create necessary directories based on the sanitized S3 key
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

        # Check if the local file exists and compare modification times
        if os.path.exists(local_file_path):
            num_local_files += 1
            local_file_mod_time = datetime.fromtimestamp(
                os.path.getmtime(local_file_path), tz=tzutc()
            )
            s3_object_last_modified = obj["LastModified"]  # type: ignore

            # Download the file if the S3 object is newer
            if s3_object_last_modified > local_file_mod_time:
                s3.download_file(bucket_name, s3_key, local_file_path)
                num_calls += 1
                print(f"Downloaded {s3_key} to {local_file_path} (S3 object was newer)")
            else:
                print(f"Skipped {s3_key} (local version is up to date)")
                num_local_files_up_to_date += 1
        else:
            # Download the file if the local file does not exist
            s3.download_file(bucket_name, s3_key, local_file_path)
            num_calls += 1
            print(
                f"Downloaded {s3_key} to {local_file_path} (local file did not exist)"
            )
    print(f"{num_local_files_up_to_date}/{num_local_files} local files were already up to date")
    print(f"Number of S3 calls made: {num_calls}")


if __name__ == "__main__":
    file_handler = LocalFileHandler()
    helper = Helpers(file_handler)
    load_dotenv()
    bucket_name = os.getenv("BUCKET_NAME")
    # local_backup_directory = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    local_backup_directory = os.path.join(
        helper.file_helper.get_base_path(os.path.abspath(__file__), 2), "backup"
    )
    helper.file_helper.create_directory_if_not_exist(local_backup_directory)
    download_files(bucket_name, local_backup_directory, from_function_dir=True)
