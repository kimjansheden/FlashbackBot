# FlashbackBot

FlashbackBot is a customizable bot designed for interacting with the Flashback forum. It automates tasks such as posting, scraping new posts, generating answers using your preferred AI model, and decision-making based on forum interactions. This project includes Docker support for deployment and can also be run in a serverless environment using AWS Lambda.

## Installation

To install and set up your project, follow the steps below:

### Environment Setup

Before installing and running the bot, you must configure the necessary environment variables. These variables should be defined in your `.env` file located in the root of the project directory. Here is a list of the required environment variables along with their descriptions:

#### Required Environment Variables

- `MODEL_PATH`: Path to the machine learning model used by the bot for generating answers.
- `USERNAME`: The username the bot uses to log into the forum.
- `PASSWORD`: The password for the forum account used by the bot.
- `FORUM_URL`: The specific URL of the forum thread that the bot will interact with. Should be a full URL, e.g. "https://www.flashback.org/foo123".
- `CHROMIUM_PATH`: Path to the Chromium browser executable, used for web scraping activities.
- `CHROMEDRIVER_PATH`: Path to the ChromeDriver executable, necessary for controlling the browser in web scraping.
- `FILE_STORAGE`: Specifies the type of storage solution used for file handling by the bot. The variable can be set to `LOCAL`, `AWS`, or `DROPBOX`, determining which file handler will be used:
  - `LOCAL`: Utilizes the local file system to store and manage files. Suitable for running the bot on your local machine or in environments where local storage is preferred.
  - `AWS`: Uses Amazon S3 for cloud storage. Includes mechanisms to manage API request limits based on the `SHOULD_LIMIT_S3` and `NUM_LIMIT_S3_REQUESTS` settings to prevent exceeding free tier limits or to manage costs effectively.
  - `DROPBOX`: Employs Dropbox for cloud storage via the Dropbox API.
  
    **Note:** Ensure `BUCKET_NAME`, `BUCKET_REGION`, `DROPBOX_REFRESH_TOKEN`, `DROPBOX_APP_KEY`, and `DROPBOX_APP_SECRET` are set accordingly when using AWS or Dropbox storage options.
- `BASE_PATH`: Specifies the base directory for script execution and data storage. Set this variable to `LOCAL` to use the local filesystem relative to the project's current directory. This is suitable for running the bot directly on your own machine without specific path constraints. For cloud deployments or when a specific directory structure is required (e.g., on AWS Lambda), provide the exact base path (e.g., `your_base_path`) where the bot's scripts and data should reside. This setup allows the bot to adapt its file path handling to the deployment environment, accommodating both local and cloud-based operations.

    **Note:** When set to `LOCAL`, the bot interprets file paths relative to the project's execution directory, allowing flexibility in local development and testing. For cloud environments, ensure the `BASE_PATH` reflects the intended directory in your cloud storage, providing a consistent and accessible location for your bot's resources.


#### Optional Variables

- `FLASHBACK_URL`: The URL of the Flashback forum's home page. Defaults to "https://www.flashback.org/". No need to set this variable unless for some reason you want to.
- `REWARD_TOKENS`: Tokens used as incentives or rewards within the bot's answer-generating processes.
- `UNWANTED_PHRASES`: A comma-separated list of phrases the bot should avoid or filter out during its operations.
    - **Example usage**: `Foo Goo,Ursprungligen postat av \w+\s,( Ej registrerad )`
- `UNWANTED_PHRASES_LITERAL`: A list of literal phrases that should be explicitly blocked or removed. This means the exact phrases will be filtered out during generation, i.e. all letters will be escaped when doing pattern replacements.
    - **Example usage**: `[ Visa mer ]`
- `PB_CREDS`: Credentials for using PushBullet as a notifier; required if PushBullet is used. Go to [PushBullet's website](https://www.pushbullet.com/) to setup an account and get your API key.
- `BUCKET_NAME`: The name of the AWS S3 bucket used for backup and storage.
- `BUCKET_REGION`: The AWS region where the S3 bucket is located.
- `DROPBOX_REFRESH_TOKEN`: Refresh token for accessing Dropbox API, used for backup storage.
- `DROPBOX_APP_KEY`: The application key for the Dropbox API, necessary for Dropbox integration.
- `DROPBOX_APP_SECRET`: The application secret for the Dropbox API.
- `USE_CACHE`: Determines whether the bot should use caching mechanisms to optimize performance. Default is True.
- `NOTIFIER`: Specifies the notifier system to use; defaults to PushBullet unless another is specified.
- `SHOULD_LIMIT_S3`: Set to `True` to enable limiting the number of S3 requests based on a specified maximum. Useful to avoid exceeding free tier limits or to manage costs. Default is `True`.
- `NUM_LIMIT_S3_REQUESTS`: Specifies the maximum number of S3 requests allowed before switching to an alternative storage method like Dropbox. Default is `2000`. This is effective only if `SHOULD_LIMIT_S3` is set to `True`.

Ensure that these variables are set up correctly to avoid runtime errors and ensure that the bot functions as intended.


### Docker

1. **Build the Docker image:**

   Run the following script to build your Docker image:

   ```bash
   ./docker_build.sh <path/to/your/model>
    ```
2. **Run the Docker container:**

    Ensure you are in the project's main folder and execute:
    ```sh
    CURRENT_DIR=$(pwd)
    ```
    ```sh
    docker run --platform linux/arm64 -d \
        -v ~/.aws-lambda-rie:/aws-lambda \
        -v ${CURRENT_DIR}:/function \
        -p 9090:8080 \
        --env-file .env \
        --env BASE_PATH=<YOUR_BASE_PATH or LOCAL> \
        --entrypoint /aws-lambda/aws-lambda-rie \
        fbbot:latest \
        /usr/local/bin/python -m awslambdaric lambda_function.bot_handler
    ```
    This command sets up the container to mimic an AWS Lambda environment for local testing and development.

    **Note**: Choose either a specific directory name for `YOUR_BASE_PATH` if you intend to use a cloud file structure, or `LOCAL` if you plan to use the local filesystem. It is crucial that `YOUR_BASE_PATH` specifies exactly the base path where you want your scripts and data to be accessible.

### Local Machine
1. **Install Python and Dependencies**:
   Ensure you have Python installed on your computer. FlashbackBot also requires some external libraries specified in `requirements.txt`. Install these dependencies using the following command:

   ```bash
   pip install -r requirements.txt
    ```

## Usage

### With AWS Lambda
To run the bot using AWS Lambda, ensure the test_mode key in the event object is appropriately set to trigger different operational modes:

#### Via an API Gateway test request:
```
{
    "test_mode": false
}
```
#### For local testing using curl:
```
curl -X POST "http://localhost:9090/2015-03-31/functions/function/invocations" \
     -H "Content-Type: application/json" \
     -d '{"test_mode": false}'
```

### On Local Machine
FlashbackBot is configured to run with different flags to customize its behavior.

1. **Arguments for Running the Script**:
   - `-c, --continuous`: Specifies whether the bot should run continuously (`true`) or execute once (`false`).
   - `-t, --test`: Run the bot in test mode. This is optional.
   - `-m, --model_path`: Path to the model file. This is optional and used to specify or update the model path in your configuration.

2. **Start the Bot**:
   Use the following command to start the bot. Adjust the arguments based on your needs:

   ```bash
   python -m main --continuous true
   ```

   To run the bot in single execution mode and in test mode, use:

   ```bash
   python -m main --continuous false --test
   ```

   If you want to specify a specific model path when starting the bot, include the `-m` flag:

   ```bash
   python -m main --continuous true --model_path /path/to/your/model
   ```

3. **Handle Model Path**:
   If a model path is already configured, the script will prompt you whether you want to replace it. Answer with `Y` to update or `n` to keep the existing path.

### Frontend Integration
To facilitate the handling of approvals and rejections of the bot's generated responses, a a frontend interface is needed that can communicate with the bot's notification system. This interface will allow users to review and either approve or reject responses generated by the bot before they are posted on the forum.

Feel free to use any suitable technology to achieve this. For instance, PushBullet offers simple solutions for sending notifications which can be integrated into your frontend. More information and their API can be found on [PushBullet's website](https://www.pushbullet.com/).

I have developed an application specifically for this purpose, which will be available soon. Please check back for updates and the link to access the application.

## Backup
To backup from S3 or Dropbox Storage to local hard drive, run the following command from main project folder:
```sh
python -m modules.DropboxBackup
```

or

```sh
python -m modules.S3Backup
```

## Configuration

The configuration of FlashbackBot is managed through a `config.ini` file that centralizes settings for various aspects of the bot's operation. Below are the sections and key settings explained:

### [LaunchAgent]

- `exists`: Indicates whether a macOS LaunchAgent is used to schedule or manage the bot. Set to `False` by default.

### [Time]

- `time_of_last_response`: Records the timestamp of the bot's last received response.
- `time_of_last_post`: Records the timestamp of the bot's last post.
- `scrape_timeout_time`: The maximum time in seconds to wait during scraping operations before timing out.
- `random_sleep_time_min`: The minimum amount of time, in minutes, the bot should randomly sleep to mimic human interaction.
- `random_sleep_time_max`: The maximum amount of time, in minutes, for the bot's random sleep.
- `random_sleep_time_off`: Set to `False` to enable random sleep intervals, ensuring more human-like interactions.

### [Misc]

- `post_lock`: A boolean (`True` or `False`) that indicates whether the bot is currently in the process of posting to prevent concurrent post operations. Set to `False` by default.

### [Logging]

- Various components of the bot have their logging levels set here, including `act_log_level`, `actions_taken_log_level`, and `scraper_log_level`, among others. These settings help control the verbosity of logs to ensure efficient debugging and monitoring.

### [Model]

- Settings related to the AI model's operation like `minimum_new_tokens`, `temperature`, `do_sample`, `top_k`, `top_p`, `repetition_penalty`, `no_repeat_ngram_size`, and others that fine-tune the response generation.
- `model_path`: Specifies the path to the trained machine learning model the bot uses.
- `max_tokens`: The maximum number of tokens to generate per response.
- `special_tokens`: A list of special tokens used in text generation.

### [Scraper]

- `user_agents`: A list of user-agent strings that the bot can use to mimic different browsers during scraping, enhancing stealth and compatibility with forum defenses.