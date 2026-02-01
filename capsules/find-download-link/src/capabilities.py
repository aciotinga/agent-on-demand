"""Pure Python implementations of tools for the Link Scout capsule."""

import requests
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from ddgs import DDGS
from ddgs.exceptions import (
    DDGSException,
    RatelimitException,
    TimeoutException
)
from bs4 import BeautifulSoup


def search_web(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Search the web for download pages or direct links using DDGS metasearch.
    
    Args:
        query: Search term optimized for finding files (e.g., include "download", "release").
        max_results: Maximum number of results to return (default: 10).
        
    Returns:
        List of dictionaries with 'title', 'href', and 'body' keys.
    """
    try:
        # Use DDGS metasearch - backend='auto' automatically handles backend unavailability
        # and tries different backends (google, bing, brave, duckduckgo, etc.) if one fails
        search_results = DDGS().text(
            query=query, 
            max_results=max_results, 
            region='us-en', 
            safesearch='moderate',
            backend='auto'
        )
        
        # Convert results to standardized format
        results = [
            {
                'title': result.get('title', ''),
                'href': result.get('href', ''),
                'body': result.get('body', '')
            }
            for result in search_results
        ]
        
        # Debug: Log search results summary
        print(f"[DEBUG] Search query: '{query}' returned {len(results)} results", flush=True)
        if results:
            print(f"[DEBUG] First result: {results[0].get('title', 'N/A')[:100]}", flush=True)
            print(f"[DEBUG] First result URL: {results[0].get('href', 'N/A')[:100]}", flush=True)
        else:
            print(f"[DEBUG] No results returned for query: '{query}'", flush=True)
        
        return results
    except RatelimitException as e:
        print(f"[WARNING] DDGS rate limit exceeded: {e}", flush=True)
        return []
    except TimeoutException as e:
        print(f"[WARNING] DDGS search timeout: {e}", flush=True)
        return []
    except DDGSException as e:
        print(f"[WARNING] DDGS search error: {e}", flush=True)
        return []
    except Exception as e:
        # Return empty list on error rather than crashing
        print(f"[WARNING] Web search failed with unexpected error: {e}", flush=True)
        import traceback
        traceback.print_exc()
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


def extract_page_links(url: str, filter_pattern: Optional[str] = None) -> List[Dict[str, str]]:
    """Extract all links from a web page.
    
    Args:
        url: The URL of the page to extract links from.
        filter_pattern: Optional pattern to filter links (e.g., ".jar", ".zip"). 
                        If provided, only links containing this pattern will be returned.
        
    Returns:
        List of dictionaries with 'url', 'text', and 'context' keys.
        Each dictionary represents a link found on the page:
        - 'url': The absolute URL of the link
        - 'text': The visible text of the link (anchor text)
        - 'context': Surrounding text context (from parent elements)
    """
    # Use a standard browser User-Agent to avoid being blocked
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Fetch the page content
        response = requests.get(
            url,
            allow_redirects=True,
            timeout=10,
            headers=headers
        )
        response.raise_for_status()
        
        # Get final URL after redirects
        final_url = response.url
        
        # Parse HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract all anchor tags
        links = []
        for anchor in soup.find_all('a', href=True):
            href = anchor.get('href', '').strip()
            if not href:
                continue
            
            # Skip javascript: and mailto: links
            if href.startswith('javascript:') or href.startswith('mailto:'):
                continue
            
            # Resolve relative URLs to absolute URLs
            absolute_url = urljoin(final_url, href)
            
            # Get link text
            link_text = anchor.get_text(strip=True)
            
            # Get context (text from parent elements, up to 200 chars)
            context_parts = []
            parent = anchor.parent
            for _ in range(3):  # Check up to 3 levels up
                if parent and parent.name:
                    parent_text = parent.get_text(strip=True)
                    if parent_text and len(parent_text) < 200:
                        context_parts.append(parent_text)
                    parent = parent.parent
                else:
                    break
            context = ' | '.join(context_parts[:2])  # Limit to 2 context levels
            
            # Apply filter if provided
            if filter_pattern:
                filter_lower = filter_pattern.lower()
                if filter_lower not in absolute_url.lower() and filter_lower not in link_text.lower():
                    continue
            
            links.append({
                'url': absolute_url,
                'text': link_text[:200],  # Limit text length
                'context': context[:300]  # Limit context length
            })
        
        # Debug: Log extraction results
        print(f"[DEBUG] Extracted {len(links)} links from {final_url}", flush=True)
        if filter_pattern:
            print(f"[DEBUG] Filtered by pattern '{filter_pattern}'", flush=True)
        if links:
            print(f"[DEBUG] First link: {links[0].get('url', 'N/A')[:100]}", flush=True)
        
        return links
        
    except requests.exceptions.RequestException as e:
        # Return empty list on connection error
        print(f"[WARNING] Failed to extract links from {url}: {e}", flush=True)
        return []
    except Exception as e:
        # Catch any other unexpected errors (parsing, etc.)
        print(f"[WARNING] Unexpected error extracting links from {url}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return []
