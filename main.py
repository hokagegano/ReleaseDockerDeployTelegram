import logging
from telegram.ext import Application, ApplicationBuilder, Defaults, ContextTypes # Import ContextTypes
from telegram.constants import ParseMode
import asyncio

import config
import storage
import docker_checker
import telegram_bot as tg_bot

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set higher logging level for httpx and other noisy libraries if needed
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.INFO)


async def check_for_updates_job(context: ContextTypes.DEFAULT_TYPE): # Corrected type hint
    """Scheduled job to check for new Docker tags and notify users."""
    bot = context.bot # Get bot instance from context
    logger.info("Running hourly check for Docker tag updates...")
    
    all_tracked_data = storage.get_all_tracked_repositories()
    if not all_tracked_data:
        logger.info("No repositories are being tracked by any user.")
        return

    for chat_id_str, user_repos in all_tracked_data.items():
        chat_id = int(chat_id_str)
        for repo_name, repo_data in user_repos.items():
            logger.info(f"Checking {repo_name} for user {chat_id}...")
            last_seen_tag_names = repo_data.get("last_seen_tags", [])
            
            current_tags_data = docker_checker.fetch_docker_tags_data(repo_name)

            if current_tags_data is None:
                logger.error(f"Failed to fetch tags for {repo_name}, skipping for this cycle.")
                # Optionally, notify user about persistent fetch failures
                continue

            current_tag_names = [tag['name'] for tag in current_tags_data]
            
            newly_found_tag_names = [name for name in current_tag_names if name not in last_seen_tag_names]

            if newly_found_tag_names:
                logger.info(f"New tags found for {repo_name} for user {chat_id}: {newly_found_tag_names}")
                
                new_tags_details = [tag for tag in current_tags_data if tag['name'] in newly_found_tag_names]
                
                await tg_bot.send_new_tags_notification(bot, chat_id, repo_name, new_tags_details)
                
                # Update stored tags to current list (all current tags, not just new ones)
                storage.update_last_seen_tags(chat_id, repo_name, current_tag_names)
            else:
                logger.info(f"No new tags for {repo_name} for user {chat_id}.")


def main() -> None:
    """Start the bot."""
    # Set default parse mode for messages
    defaults = Defaults(parse_mode=ParseMode.MARKDOWN_V2)
    
    # Create the Application and pass it your bot's token.
    application = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).defaults(defaults).build()

    # Register handlers
    for handler in tg_bot.get_handlers():
        application.add_handler(handler)

    # Schedule the job
    job_queue = application.job_queue
    # For PTB v20+, context for jobs is the Application instance itself, or you can pass a custom context.
    # The callback function `check_for_updates_job` will receive an instance of `telegram.ext.CallbackContext`.
    # From this context, `context.bot` can be used to access the bot.
    # The first argument to run_repeating is the callback.
    # The `context` argument of `run_repeating` is passed to the job callback as its argument.
    # If we want `context.bot` inside `check_for_updates_job`, we need `application` (or its `bot` attr)
    # to be available. `CallbackContext` passed to jobs has a `bot` attribute.
    
    # The job callback will receive `telegram.ext.CallbackContext`
    # which has `application` and `bot` attributes.
    # So `check_for_updates_job(context)` will have `context.bot`.
    job_queue.run_repeating(check_for_updates_job, interval=3600, first=10) # Check every hour, start after 10s
    logger.info("Hourly Docker tag check job scheduled.")

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting bot polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
