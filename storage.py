import json
import os
import logging
from config import STORAGE_FILE_PATH

logger = logging.getLogger(__name__)

def load_data():
    """Loads data from the JSON storage file."""
    if not os.path.exists(STORAGE_FILE_PATH):
        return {}
    try:
        with open(STORAGE_FILE_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading data from {STORAGE_FILE_PATH}: {e}")
        return {}

def save_data(data):
    """Saves data to the JSON storage file."""
    try:
        # Ensure the directory for the storage file exists
        storage_dir = os.path.dirname(STORAGE_FILE_PATH)
        if storage_dir and not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
            logger.info(f"Created storage directory: {storage_dir}")

        with open(STORAGE_FILE_PATH, 'w') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        logger.error(f"Error saving data to {STORAGE_FILE_PATH}: {e}")

def add_repository(chat_id, docker_hub_repo_name, initial_tags, local_repo_path, service_base_url, api_token):
    """Adds a repository for a given chat_id with its Docker Hub name, initial tags, local repo path, service base URL, and API token."""
    chat_id_str = str(chat_id)
    data = load_data()
    if chat_id_str not in data:
        data[chat_id_str] = {}
    
    # Normalize docker_hub_repo_name (e.g. library/ubuntu -> library/ubuntu)
    # This normalized name is the key in our storage.
    normalized_docker_hub_repo_name = docker_hub_repo_name
    if '/' not in normalized_docker_hub_repo_name:
        normalized_docker_hub_repo_name = f"library/{normalized_docker_hub_repo_name}"

    data[chat_id_str][normalized_docker_hub_repo_name] = {
        "last_seen_tags": initial_tags,
        "local_repo_path": local_repo_path, # Path for the Gitea/service API
        "service_base_url": service_base_url,
        "api_token": api_token
    }
    save_data(data)
    logger.info(f"Repository {normalized_docker_hub_repo_name} (for Docker Hub) linked to local path {local_repo_path} added for chat_id {chat_id_str} with service base URL {service_base_url}, API token, and {len(initial_tags)} initial tags.")

def remove_repository(chat_id, docker_hub_repo_name):
    """Removes a repository for a given chat_id, using the Docker Hub repo name as key."""
    chat_id_str = str(chat_id)
    data = load_data()
    # Normalize docker_hub_repo_name
    normalized_docker_hub_repo_name = docker_hub_repo_name
    if '/' not in normalized_docker_hub_repo_name:
        normalized_docker_hub_repo_name = f"library/{normalized_docker_hub_repo_name}"
        
    if chat_id_str in data and normalized_docker_hub_repo_name in data[chat_id_str]:
        del data[chat_id_str][normalized_docker_hub_repo_name]
        if not data[chat_id_str]: # if user has no more repos
            del data[chat_id_str]
        save_data(data)
        logger.info(f"Repository {normalized_docker_hub_repo_name} removed for chat_id {chat_id_str}.")
        return True
    logger.warning(f"Repository {normalized_docker_hub_repo_name} not found for chat_id {chat_id_str} during removal.")
    return False

def get_repositories_for_user(chat_id):
    """Gets all repositories for a given chat_id."""
    chat_id_str = str(chat_id)
    data = load_data()
    return data.get(chat_id_str, {})

def get_all_tracked_repositories():
    """Gets all repositories tracked by all users."""
    return load_data()

def get_last_seen_tags(chat_id, docker_hub_repo_name):
    """Gets the last seen tags for a repository for a given chat_id."""
    chat_id_str = str(chat_id)
    data = load_data()
    normalized_docker_hub_repo_name = docker_hub_repo_name
    if '/' not in normalized_docker_hub_repo_name:
        normalized_docker_hub_repo_name = f"library/{normalized_docker_hub_repo_name}"
    return data.get(chat_id_str, {}).get(normalized_docker_hub_repo_name, {}).get("last_seen_tags", [])

def get_service_base_url(chat_id, docker_hub_repo_name):
    """Gets the service base URL for a repository for a given chat_id."""
    chat_id_str = str(chat_id)
    data = load_data()
    normalized_docker_hub_repo_name = docker_hub_repo_name
    if '/' not in normalized_docker_hub_repo_name:
        normalized_docker_hub_repo_name = f"library/{normalized_docker_hub_repo_name}"
    return data.get(chat_id_str, {}).get(normalized_docker_hub_repo_name, {}).get("service_base_url")

def get_api_token(chat_id, docker_hub_repo_name):
    """Gets the API token for a repository for a given chat_id."""
    chat_id_str = str(chat_id)
    data = load_data()
    normalized_docker_hub_repo_name = docker_hub_repo_name
    if '/' not in normalized_docker_hub_repo_name:
        normalized_docker_hub_repo_name = f"library/{normalized_docker_hub_repo_name}"
    return data.get(chat_id_str, {}).get(normalized_docker_hub_repo_name, {}).get("api_token")

def get_local_repo_path(chat_id, docker_hub_repo_name):
    """Gets the local repository path for a repository for a given chat_id."""
    chat_id_str = str(chat_id)
    data = load_data()
    normalized_docker_hub_repo_name = docker_hub_repo_name
    if '/' not in normalized_docker_hub_repo_name:
        normalized_docker_hub_repo_name = f"library/{normalized_docker_hub_repo_name}"
    return data.get(chat_id_str, {}).get(normalized_docker_hub_repo_name, {}).get("local_repo_path")

def update_last_seen_tags(chat_id, docker_hub_repo_name, new_tags_list):
    """Updates the last seen tags for a repository for a given chat_id."""
    chat_id_str = str(chat_id)
    data = load_data()
    normalized_docker_hub_repo_name = docker_hub_repo_name
    if '/' not in normalized_docker_hub_repo_name:
        normalized_docker_hub_repo_name = f"library/{normalized_docker_hub_repo_name}"
    if chat_id_str in data and normalized_docker_hub_repo_name in data[chat_id_str]:
        data[chat_id_str][normalized_docker_hub_repo_name]["last_seen_tags"] = new_tags_list
        save_data(data)
        logger.info(f"Updated last seen tags for {normalized_docker_hub_repo_name} for chat_id {chat_id_str}.")
    else:
        logger.warning(f"Could not update tags for {normalized_docker_hub_repo_name} (chat_id {chat_id_str}): repo not found in storage.")
