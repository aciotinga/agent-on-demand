"""Pure Python implementations of tools for the Link Scout capsule."""

import requests
from typing import List, Dict, Optional
from duckduckgo_search import DDGS


def search_web(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Search the web for download pages or direct links.
    
    Args:
        query: Search term optimized for finding files (e.g., include "download", "release").
        max_results: Maximum number of results to return (default: 10).
        
    Returns:
        List of dictionaries with 'title', 'href', and 'body' keys.
    """
    try:
        with DDGS() as ddgs:
            results = []
            for result in ddgs.text(query, max_results=max_results):
                results.append({
                    'title': result.get('title', ''),
                    'href': result.get('href', ''),
                    'body': result.get('body', '')
                })
            return results
    except Exception as e:
        # Return empty list on error rather than crashing
        print(f"[WARNING] Web search failed: {e}", flush=True)
        return []


def verify_url_headers(url: str) -> Dict:
    """Ping a URL to check if it is valid and get file size/type. Does NOT download the file.
    
    Args:
        url: The candidate URL to check.
        
    Returns:
        Dictionary with:
            - 'valid': Boolean (True if status is 200-299)
            - 'final_url': String (URL after redirects)
            - 'content_type': String (from headers)
            - 'content_length': Integer (from headers, default 0)
            - 'status_code': Integer (HTTP status code)
    """
    # Use a standard browser User-Agent to avoid being blocked
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Use HEAD request with redirects enabled
        response = requests.head(
            url,
            allow_redirects=True,
            timeout=10,
            headers=headers
        )
        
        # Get final URL after redirects
        final_url = response.url
        
        # Extract headers
        content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
        content_length_str = response.headers.get('Content-Length', '0')
        try:
            content_length = int(content_length_str) if content_length_str else 0
        except (ValueError, TypeError):
            content_length = 0
        status_code = response.status_code
        
        # Valid if status is 2xx
        valid = 200 <= status_code < 300
        
        return {
            'valid': valid,
            'final_url': final_url,
            'content_type': content_type,
            'content_length': content_length,
            'status_code': status_code
        }
    except requests.exceptions.RequestException as e:
        # Return invalid on any connection error
        print(f"[WARNING] URL verification failed for {url}: {e}", flush=True)
        return {
            'valid': False,
            'final_url': url,
            'content_type': '',
            'content_length': 0,
            'status_code': 0
        }
    except Exception as e:
        # Catch any other unexpected errors
        print(f"[WARNING] Unexpected error verifying URL {url}: {e}", flush=True)
        return {
            'valid': False,
            'final_url': url,
            'content_type': '',
            'content_length': 0,
            'status_code': 0
        }
