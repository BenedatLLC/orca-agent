"""
Functions for retrieving runbook content from a given URL.
"""

import requests
import logging
from urllib.parse import urlparse, urlunparse

class RunbookRetrievalError(Exception):
    """Exception raised when there is an error retrieving the runbook."""
    pass




def rewrite_github_url(url: str) -> str:
    """
    Checks if the domain of a given URL is github.com and, if so,
    replaces it with raw.githubusercontent.com and inserts '/refs/heads'
    into the path after the repository name and removes the 'blob' path component.
    For example:
        https://github.com/BenedatLLC/otel-demo/blob/main/RCA/CrashLoop.md becomes
        https://raw.githubusercontent.com/BenedatLLC/otel-demo/refs/heads/main/RCA/CrashLoop.md

    Args:
        url (str): The input URL string.

    Returns:
        str: The modified URL string, or the original URL if no change is needed.
    """
    parsed_url = urlparse(url)
    if parsed_url.netloc != 'github.com':
        return url # nothing to do
    
    new_path = parsed_url.path 
    
    # Split the path into components. The first element will be an empty string
    # if the path starts with a slash (e.g., '/a/b' -> ['', 'a', 'b']).
    path_parts = parsed_url.path.split('/')

    # Ensure the path has at least a leading slash, user, and repo component.
    # For a path like '/user/repo/file.js', path_parts would be ['', 'user', 'repo', 'file.js'].
    # So, length must be at least 3 to have '/user/repo'.
    if len(path_parts) >= 3:
        # Insert 'refs' and 'heads' after the repo part (which is at index 2).
        # path_parts[:3] captures the leading empty string, user, and repo.
        # path_parts[3:] captures the rest of the path components.
        new_path_parts = path_parts[:3] + ['refs', 'heads'] + path_parts[4:] # path_parts[3] was 'blob'
        # Rejoin the path components to form the new path string.
        new_path = '/'.join(new_path_parts)
    
    # Reconstruct the URL with the new domain and the (potentially modified) path.
    return urlunparse(parsed_url._replace(netloc='raw.githubusercontent.com', path=new_path))


def get_runbook_text(url: str) -> str:
    """
    Retrieve the content of a runbook from the specified URL. The URL should point to a text or markdown file.
    Raw HTML is currently not handled. We do rewrite GitHub urls to point to the associated raw content
    instead of the full HTML text. Otherwise, you get a bunch of style sheets, etc.

    Parameters
    ----------
    url : str
        The URL of the runbook to retrieve.

    Returns
    -------
    str
        The content of the runbook as a string.

    Raises
    ------
    RunbookRetrievalError
        If there is an error retrieving the runbook content from the URL.
    """
    try:
        url = rewrite_github_url(url)
        response = requests.get(url)
        response.raise_for_status()
        logging.info(f"Retrieved runbook of length {len(response.text)} from {url}")
        return response.text
    except Exception as e:
        raise RunbookRetrievalError(f"Failed to retrieve runbook from {url}") from e
