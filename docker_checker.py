import requests
import logging
from config import DOCKER_HUB_API_URL

logger = logging.getLogger(__name__)

def fetch_docker_tags_data(repo_name):
    """
    Fetches tag data for a given Docker Hub repository.
    Returns a list of tag objects (dicts) with 'name' and 'last_updated', or None on error.
    Example repo_name: "library/python" or "nginx" (will be prefixed with "library/")
    """
    if '/' not in repo_name:
        repo_name = f"library/{repo_name}" # Default to library namespace if not specified

    url = DOCKER_HUB_API_URL.format(repo_name=repo_name)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
        data = response.json()
        
        tags_data = []
        if 'results' in data:
            for tag_info in data['results']:
                tags_data.append({
                    "name": tag_info['name'],
                    "last_updated": tag_info.get('last_updated', 'N/A') 
                })
            # Docker Hub API paginates. For simplicity, we only get the first page (default 10, configured to 100).
            # A more robust solution would handle pagination if more than 100 tags are expected.
            return tags_data
        else:
            logger.warning(f"No 'results' key in Docker Hub API response for {repo_name}. Response: {data}")
            return []
            
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(f"Repository {repo_name} not found on Docker Hub (404). URL: {url}")
        else:
            logger.error(f"HTTP error fetching tags for {repo_name}: {e}. URL: {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching tags for {repo_name}: {e}. URL: {url}")
        return None
    except ValueError as e: # Includes JSONDecodeError
        logger.error(f"Error decoding JSON response for {repo_name}: {e}. URL: {url}")
        return None

def get_current_tag_names(repo_name):
    """Fetches current tag names for a repository. Used for initial add."""
    tags_data = fetch_docker_tags_data(repo_name)
    if tags_data is None: # Error occurred, repo might not exist
        return None
    return [tag['name'] for tag in tags_data]

