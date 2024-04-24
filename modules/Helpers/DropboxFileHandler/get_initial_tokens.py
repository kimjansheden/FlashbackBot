import os
from dotenv import load_dotenv
from dropbox import DropboxOAuth2FlowNoRedirect
from requests import request

load_dotenv()
app_key = os.getenv("DROPBOX_APP_KEY")
app_secret = os.getenv("DROPBOX_APP_SECRET")

# Since the app is supposed to run on a server without any user interaction, we can't use the default token_access_type "online", because that will give us only short-lived access tokens.
# Instead, we use the "legacy" token_access_type, which gives us long-lived access tokens.
flow = DropboxOAuth2FlowNoRedirect(app_key, app_secret, token_access_type="offline")

# Print the URL to the user to authorize the app
auth_url = flow.start()
print("1. Go to: " + auth_url)
print('2. Click "Allow" (you might have to log in first).')
print("3. Copy the authorization code.")
input("Press any key when you are ready.")
auth_code = input("Enter the authorization code here: ").strip()
if auth_code:
    result = flow.finish(auth_code)
    print("Success! You can now use the Dropbox API.")
    print(f"Access token: {result.access_token}")
    print(f"Refresh token: {result.refresh_token}")
    print("Whole result object:", result)
