import os
from modules.Helpers.DropboxFileHandler.DropboxFileHandler import DropboxFileHandler
from modules.Helpers.DropboxFileHandler.get_or_refresh_token import (
    get_or_refresh_dropbox_token,
)
from modules.Helpers.LocalFileHandler import LocalFileHandler
from modules.Helpers.S3FileHandler import S3FileHandler


def create_and_get_file_handler():
    # Determine which File Handler to use
    storage_type = os.getenv("FILE_STORAGE", "LOCAL")
    print(f"Storage type: {storage_type}")
    print("Base path:", os.getenv("BASE_PATH"))

    bucket_name = os.getenv("BUCKET_NAME")
    bucket_region = os.getenv("BUCKET_REGION")

    refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN", "")
    app_key = os.getenv("DROPBOX_APP_KEY", "")
    app_secret = os.getenv("DROPBOX_APP_SECRET", "")
    dropbox_token = get_or_refresh_dropbox_token(refresh_token, app_key, app_secret)

    use_cache = "True" in os.getenv("USE_CACHE", "True")
    should_limit_s3_requests = "True" in os.getenv("SHOULD_LIMIT_S3", "True")
    num_limit_s3_requests = int(os.getenv("NUM_LIMIT_S3_REQUESTS", "2000"))

    if storage_type == "LOCAL":
        file_handler = LocalFileHandler()
    elif storage_type == "AWS":
        if should_limit_s3_requests:
            num_actual_s3_requests = S3FileHandler.get_s3_requests_used(
                bucket_name, bucket_region, S3FileHandler.PUT_REQUESTS
            )
            print(f"Number of S3 requests: {num_actual_s3_requests}")
            if num_actual_s3_requests >= num_limit_s3_requests or num_actual_s3_requests == -1:
                # Fallback to Dropbox File Handler
                print(
                    "Number of requests to S3 could either not be fetched or are above num_limit_s3_requests (for example 2000 for Free Tier). Falling back to Dropbox"
                )
                file_handler = DropboxFileHandler(dropbox_token, use_cache=use_cache)
            else:
                print("Using S3FileHandler")
                file_handler = S3FileHandler(
                    bucket_name=bucket_name, use_cache=use_cache
                )
        else:
            print("Using S3FileHandler")
            file_handler = S3FileHandler(bucket_name=bucket_name, use_cache=use_cache)
    elif storage_type == "DROPBOX":
        file_handler = DropboxFileHandler(dropbox_token, use_cache=use_cache)
        ## TODO  Implement a fallback to Local File Handler if some condition requires it (like number of requests being too high)
    else:
        print(
            f"Unknown storage type: {storage_type}. Falling back to LocalFileHandler."
        )
        file_handler = LocalFileHandler()

    return file_handler
