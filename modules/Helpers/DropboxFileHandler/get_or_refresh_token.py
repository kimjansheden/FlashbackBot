from datetime import datetime, timezone
import os
from typing import Any
import requests
from requests import Response
import json
import time


def read_token_from_file():
    """
    Reads the token information from a file. Returns the token data if the file exists, otherwise None.
    """
    try:
        with open("db_token.json", "r") as file:
            data: dict[str, Any] = json.load(file)
            return data
    except FileNotFoundError:
        return None


def write_token_to_file(access_token, expires_in):
    """
    Writes the new access token and its expiration time to a file.
    """
    expiration_time = time.time() + expires_in  # Calculate the absolute expiration time
    data = {"access_token": access_token, "expires_at": expiration_time}
    with open("db_token.json", "w") as file:
        json.dump(data, file)


def get_new_access_token(refresh_token: str, app_key: str, app_secret: str):
    """
    Obtains a new access token using the refresh token.
    """
    token_url = "https://api.dropboxapi.com/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": app_key,
        "client_secret": app_secret,
    }
    response: Response = requests.post(token_url, headers=headers, data=data)
    response_data: dict[str, Any] = response.json()
    new_access_token: str = response_data.get("access_token", "")
    expires_in: int = response_data.get("expires_in", 0)

    # Check if the response contains an access token
    if not new_access_token:
        raise ValueError("No access token found in the response.")

    # Check if the response contains an expiration time
    if not expires_in:
        raise ValueError("No expiration time found in the response.")

    # Return both the new access token and its expiration time
    return new_access_token, expires_in


def get_or_refresh_dropbox_token(refresh_token="", app_key="", app_secret=""):
    """
    Retrieves a valid Dropbox access token, either from the stored file or by renewing it.
    """
    if not refresh_token:
        refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN", "")
    if not app_key:
        app_key = os.getenv("DROPBOX_APP_KEY", "")
    if not app_secret:
        app_secret = os.getenv("DROPBOX_APP_SECRET", "")

    if not refresh_token or not app_key or not app_secret:
        raise ValueError("Refresh token, app key, and app secret must be provided.")
    
    token_data = read_token_from_file()

    ## TODO: Replace prints with logger
    # Check if the token exists and has not expired
    if token_data and time.time() < token_data.get("expires_at", 0):
        print("Using existing valid access token.")

        # Convert Unix timestamp to a datetime object in the user's local timezone
        expires_at: int = token_data.get("expires_at", 0)
        expires_at_datetime = datetime.fromtimestamp(expires_at, tz=timezone.utc).astimezone(tz=None)

        # Format the datetime object to exclude microseconds
        formatted_expiration_time = expires_at_datetime.strftime("%Y-%m-%d %H:%M:%S")

        print(f"Token expires at: {formatted_expiration_time}")

        current_token: str = token_data["access_token"]
        return current_token
    else:
        print(
            "Existing access token is invalid, expired, or missing; fetching a new one."
        )
        # print("refresh_token:", refresh_token, "app_key:", app_key, "app_secret:", app_secret)
        try:
            new_access_token, expires_in = get_new_access_token(
                refresh_token, app_key, app_secret
            )
            write_token_to_file(new_access_token, expires_in)
            return new_access_token
        except Exception as e:
            print(f"Error fetching new access token: {e}")
            return ""
