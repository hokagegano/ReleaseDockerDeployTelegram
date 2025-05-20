import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import storage
import docker_checker
import requests # Import requests for making HTTP calls

logger = logging.getLogger(__name__)

def escape_markdown_v2(text: str) -> str:
    """Helper function to escape text for MarkdownV2."""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the /start command is issued."""
    await update.message.reply_text(
        "Welcome to Docker Release Notifier Bot\\!\n"
        "Use /addrepo \\<docker\\_hub\\_repo\\> \\<local\\_repo\\_path\\> \\<service\\_base\\_url\\> \\<api\\_token\\> to add a repository\\.\n"
        "Example: /addrepo grafana/grafana gano/grafana https://my\\.repo\\.org/api/v1/repos/ your\\_token\n"
        "  \\- \\<docker\\_hub\\_repo\\>: e\\.g\\., `grafana/grafana` or `python` \\(for official images\\)\n"
        "  \\- \\<local\\_repo\\_path\\>: e\\.g\\., `gano/grafana` \\(used for the API call path\\)\n"
        "  \\- \\<service\\_base\\_url\\>: e\\.g\\., `https://my\\.repo\\.org/api/v1/repos/`\n"
        "  \\- \\<api\\_token\\>: Your API token for the service\n"
        "Use /listrepos to see your tracked repositories\\.\n"
        "Use /delrepo \\<docker\\_hub\\_repo\\> to remove a repository\\."
    )

async def add_repo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adds a Docker Hub repository, its local repo path, service base URL, and API token."""
    chat_id = update.effective_chat.id
    if len(context.args) < 4:
        await update.message.reply_text(
            "Please provide all four arguments\\. \n"
            "Usage: /addrepo \\<docker\\_hub\\_repo\\> \\<local\\_repo\\_path\\> \\<service\\_base\\_url\\> \\<api\\_token\\>\n"
            "Example: /addrepo grafana/grafana gano/grafana https://my\\.repo\\.org/api/v1/repos/ yourtoken"
        )
        return

    docker_hub_repo_input = context.args[0].lower()
    local_repo_path_input = context.args[1].lower() # Gitea paths are often case-sensitive, but user input is lowercased here. Adjust if needed.
    service_base_url = context.args[2]
    api_token = context.args[3]
    
    if not (service_base_url.startswith("http://") or service_base_url.startswith("https://")):
        await update.message.reply_text("Invalid service base URL\\. It must start with http:// or https://")
        return
    if not service_base_url.endswith("/"):
        service_base_url += "/"
        
    # Normalize the Docker Hub repo name for storage and Docker Hub API calls
    normalized_docker_hub_repo_name = docker_hub_repo_input
    if '/' not in normalized_docker_hub_repo_name:
        normalized_docker_hub_repo_name = f"library/{normalized_docker_hub_repo_name}"

    user_repos = storage.get_repositories_for_user(chat_id)
    escaped_docker_hub_repo_msg = escape_markdown_v2(normalized_docker_hub_repo_name)
    
    if normalized_docker_hub_repo_name in user_repos:
        await update.message.reply_text(f"Docker Hub repository {escaped_docker_hub_repo_msg} is already in your tracking list\\.")
        return

    initial_tag_names = docker_checker.get_current_tag_names(normalized_docker_hub_repo_name)

    if initial_tag_names is None:
        await update.message.reply_text(f"Could not fetch tags for Docker Hub repository {escaped_docker_hub_repo_msg}\\. Please ensure it exists and is public\\.")
        return

    storage.add_repository(chat_id, normalized_docker_hub_repo_name, initial_tag_names, local_repo_path_input, service_base_url, api_token)
    
    escaped_local_repo_path_msg = escape_markdown_v2(local_repo_path_input)
    escaped_service_base_url_display = escape_markdown_v2(service_base_url)
    
    await update.message.reply_text(
        f"Watching Docker Hub repo: {escaped_docker_hub_repo_msg}\\.\n"
        f"Local API path: {escaped_local_repo_path_msg}\\.\n"
        f"Service base URL: {escaped_service_base_url_display}\\.\n"
        f"API token configured\\. Currently tracking {len(initial_tag_names)} tags\\."
    )

async def list_repos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists all repositories tracked by the user."""
    chat_id = update.effective_chat.id
    user_repos_data = storage.get_repositories_for_user(chat_id) 
    if not user_repos_data:
        await update.message.reply_text("You are not tracking any repositories yet\\. Use /addrepo to add one\\.")
        return

    message = "You are tracking the following repositories:\n"
    for docker_hub_repo_name, data in user_repos_data.items():
        escaped_docker_hub_repo = escape_markdown_v2(docker_hub_repo_name)
        local_repo_path = data.get("local_repo_path", "Not set")
        escaped_local_repo_path = escape_markdown_v2(local_repo_path)
        service_base_url_data = data.get("service_base_url", "Not set")
        escaped_service_base_url = escape_markdown_v2(service_base_url_data)
        api_token_set = "Set" if data.get("api_token") else "Not set"
        
        message += (f"\\- Docker Hub: *{escaped_docker_hub_repo}*\n"
                    f"  Local API Path: `{escaped_local_repo_path}`\n"
                    f"  Service Base URL: `{escaped_service_base_url}`\n"
                    f"  API Token: {api_token_set}\n\n")
    await update.message.reply_text(message)

async def del_repo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Removes a Docker Hub repository from the user's tracking list."""
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Please provide the Docker Hub repository name\\. Usage: /delrepo \\<docker\\_hub\\_repo\\>")
        return
    
    docker_hub_repo_input = context.args[0].lower()
    # Normalize repo_name for consistency with storage key
    normalized_docker_hub_repo_name = docker_hub_repo_input
    if '/' not in normalized_docker_hub_repo_name:
        normalized_docker_hub_repo_name = f"library/{normalized_docker_hub_repo_name}"

    escaped_repo_name_msg = escape_markdown_v2(normalized_docker_hub_repo_name)

    if storage.remove_repository(chat_id, normalized_docker_hub_repo_name): # Use normalized name for removal
        await update.message.reply_text(f"Repository {escaped_repo_name_msg} removed from your tracking list\\.")
    else:
        await update.message.reply_text(f"Repository {escaped_repo_name_msg} not found in your tracking list\\.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button presses from notification messages."""
    query = update.callback_query
    await query.answer() 

    action, docker_hub_repo_name, tag_name = query.data.split(":", 2) 

    chat_id = query.message.chat_id # Corrected: Get chat_id from query.message
    escaped_docker_hub_repo_name_msg = escape_markdown_v2(docker_hub_repo_name)
    escaped_tag_name_msg = escape_markdown_v2(tag_name)

    if action == "deploy":
        logger.info(f"User {query.from_user.id} pressed 'Deploy' for Docker Hub repo {docker_hub_repo_name}, tag {tag_name}")
        
        local_repo_path = storage.get_local_repo_path(chat_id, docker_hub_repo_name)
        service_base_url = storage.get_service_base_url(chat_id, docker_hub_repo_name)
        api_token = storage.get_api_token(chat_id, docker_hub_repo_name)

        if not local_repo_path or not service_base_url or not api_token:
            await query.edit_message_text(
                text=f"Deployment configuration incomplete for Docker Hub repository {escaped_docker_hub_repo_name_msg}\\. Please check local path, service URL, and API token settings\\."
            )
            return
        
        full_service_url = f"{service_base_url}{local_repo_path}/tags" # Use local_repo_path here
        
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"token {api_token}"
        }
        payload = {"tag_name": tag_name}

        escaped_full_service_url_msg = escape_markdown_v2(full_service_url)
        await query.edit_message_text(
            text=f"🚀 Attempting to create tag for {escaped_tag_name_msg} on Gitea repo {escape_markdown_v2(local_repo_path)} via {escaped_full_service_url_msg}\\.\\.\\."
        )
        
        try:
            response = requests.post(full_service_url, json=payload, headers=headers, timeout=15) # 15s timeout
            response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ Successfully triggered deployment for {escaped_repo_name_msg}:{escaped_tag_name_msg}\\. Service responded with {response.status_code}\\."
            )
            logger.info(f"Successfully called deployment service for {repo_name}:{tag_name}. Status: {response.status_code}")

        except requests.exceptions.HTTPError as e:
            error_reason = escape_markdown_v2(e.response.reason)
            error_text = f"HTTP error {e.response.status_code}: {error_reason}"
            logger.error(f"HTTP error calling deployment service for {repo_name}:{tag_name} to {service_url}: {error_text}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Failed to trigger deployment for {escaped_repo_name_msg}:{escaped_tag_name_msg}\\. Service responded with: {error_text}"
            )
        except requests.exceptions.RequestException as e:
            error_str = escape_markdown_v2(str(e))
            logger.error(f"Error calling deployment service for {repo_name}:{tag_name} to {service_url}: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Failed to call deployment service for {escaped_repo_name_msg}:{escaped_tag_name_msg}\\. Error: {error_str}\\."
            )
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Unexpected error during deployment call for {repo_name}:{tag_name}: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ An unexpected error occurred while trying to deploy {escaped_repo_name_msg}:{escaped_tag_name_msg}\\."
            )
    else:
        logger.warning(f"Unknown action in callback_query: {query.data}")
        await query.edit_message_text(text=f"Unknown action: {action}")


async def send_new_tags_notification(bot, chat_id, repo_name, new_tags_details):
    """Sends a notification message about new tags for a repository."""
    if not new_tags_details:
        return

    # Filter out tags that are likely not deployable or too long for callback_data
    deployable_tags_details = []
    for tag_detail in new_tags_details:
        tag_name = tag_detail['name']
        # Filter criteria:
        if tag_name.endswith(".sig"): # Skip signature files
            logger.info(f"Skipping .sig tag: {tag_name} for repo {repo_name}")
            continue
        if tag_name.startswith("sha256-"): # Skip tags that look like digests
            logger.info(f"Skipping sha256- prefixed tag: {tag_name} for repo {repo_name}")
            continue
        
        # Check callback_data length
        # Format: "deploy:{repo_name}:{tag_name}"
        # 7 (deploy:) + 1 (:) + len(repo_name) + 1 (:) + len(tag_name)
        callback_data_len = 7 + 1 + len(repo_name) + 1 + len(tag_name)
        if callback_data_len > 64:
            logger.warning(
                f"Tag '{tag_name}' for repo '{repo_name}' results in callback_data too long ({callback_data_len} bytes). Skipping button."
            )
            # Optionally, still list the tag in the message but without a button
            # For now, we just skip it from having a button. If you want to list it,
            # you'd add it to a separate list and modify message_text construction.
            continue
        
        deployable_tags_details.append(tag_detail)

    if not deployable_tags_details:
        logger.info(f"No deployable new tags found for {repo_name} after filtering.")
        # You might want to send a different kind of notification or none at all
        # For now, if all new tags are filtered out, no notification with buttons is sent.
        # Consider sending a simple text message if new non-deployable tags were found.
        # For example, if new_tags_details was not empty but deployable_tags_details is.
        if new_tags_details: # Original list had tags
             plain_text = f"🔔 New non-deployable tags found for {escape_markdown_v2(repo_name)}:\n"
             for tag_detail in new_tags_details: # Iterate original list
                 if tag_detail not in deployable_tags_details: # if it was filtered out
                     plain_text += f"  \\- Tag: {escape_markdown_v2(tag_detail['name'])}\n"
             try:
                 await bot.send_message(chat_id=chat_id, text=plain_text, parse_mode='MarkdownV2')
             except Exception as e_fallback_info:
                 logger.error(f"Failed to send info about non-deployable tags for {repo_name}: {e_fallback_info}")
        return

    escaped_repo_name_title = escape_markdown_v2(repo_name)
    message_text = f"🔔 New deployable tags found for *{escaped_repo_name_title}*:\n\n"
    keyboard = []

    for tag_detail in deployable_tags_details: # Iterate filtered list
        tag_name = tag_detail['name']
        last_updated = tag_detail['last_updated']
        escaped_tag_name = escape_markdown_v2(tag_name)
        escaped_last_updated = escape_markdown_v2(last_updated)
        
        message_text += f"🏷️ *Tag:* `{escaped_tag_name}`\n"
        message_text += f"   *Updated:* {escaped_last_updated}\n\n"
        
        callback_data = f"deploy:{repo_name}:{tag_name}"
        button_text_tag_name = tag_name 
        if len(tag_name) > 20: # Shorten button text if tag name is very long
            button_text_tag_name = tag_name[:17] + "..."
        keyboard.append([InlineKeyboardButton(f"Deploy {button_text_tag_name}", callback_data=callback_data)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Sent new deployable tags notification to {chat_id} for {repo_name}.")
    except Exception as e:
        logger.error(f"Failed to send notification to {chat_id} for {repo_name}: {e}")
        # Fallback to plain text if Markdown fails
        try:
            plain_text = f"New deployable tags for {repo_name}:\n" # Not escaped, as parse_mode=None
            for tag_detail in deployable_tags_details:
                plain_text += f"- Tag: {tag_detail['name']}, Updated: {tag_detail['last_updated']}\n"
            await bot.send_message(chat_id=chat_id, text=plain_text, parse_mode=None) # Explicitly set parse_mode=None
        except Exception as fallback_e:
            logger.error(f"Fallback plain text notification also failed for {chat_id}, {repo_name}: {fallback_e}")


def get_handlers():
    """Returns a list of command and callback query handlers for the bot."""
    return [
        CommandHandler("start", start_command),
        CommandHandler("addrepo", add_repo_command),
        CommandHandler("listrepos", list_repos_command),
        CommandHandler("delrepo", del_repo_command),
        CallbackQueryHandler(button_callback)
    ]

