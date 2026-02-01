"""Pure Python implementations of tools for the web-context capsule."""

import requests
from typing import List, Dict
from urllib.parse import urljoin, urlparse
from ddgs import DDGS
from ddgs.exceptions import (
    DDGSException,
    RatelimitException,
    TimeoutException
)
from bs4 import BeautifulSoup
from markdownify import markdownify as md


def search_web(query: str, max_results: int = 10) -> str:
    """Search the web using DDGS metasearch.
    
    Args:
        query: Search term.
        max_results: Maximum number of results to return (default: 10).
        
    Returns:
        Formatted string with numbered list of results as [Title](URL) links.
    """
    try:
        # Use DDGS metasearch - backend='auto' automatically handles backend unavailability
        search_results = DDGS().text(
            query=query,
            max_results=max_results,
            region='us-en',
            safesearch='moderate',
            backend='auto'
        )
        
        # Format results as numbered list with markdown links
        formatted_results = []
        for i, result in enumerate(search_results, 1):
            title = result.get('title', 'Untitled')
            href = result.get('href', '')
            if href:
                formatted_results.append(f"{i}. [{title}]({href})")
        
        if not formatted_results:
            return "No search results found. Try a different query."
        
        result_text = "\n".join(formatted_results)
        print(f"[DEBUG] Search query: '{query}' returned {len(formatted_results)} results", flush=True)
        return result_text
        
    except RatelimitException as e:
        print(f"[WARNING] DDGS rate limit exceeded: {e}", flush=True)
        return "Error: Search rate limit exceeded. Please try again later."
    except TimeoutException as e:
        print(f"[WARNING] DDGS search timeout: {e}", flush=True)
        return "Error: Search request timed out. Please try again."
    except DDGSException as e:
        print(f"[WARNING] DDGS search error: {e}", flush=True)
        return f"Error: Search failed: {e}. Please try a different query."
    except Exception as e:
        print(f"[WARNING] Web search failed with unexpected error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return f"Error: Unexpected search error: {e}. Please try again."


def visit_page(url: str) -> str:
    """Visit a web page and convert it to Markdown format, preserving links.
    
    Args:
        url: The URL of the page to visit. Must be a valid HTTP or HTTPS URL.
        
    Returns:
        Markdown representation of the page content with preserved links, or an error message.
    """
    # Validate URL schema
    if not url.startswith(('http://', 'https://')):
        return f"Error: Invalid URL schema. URL must start with http:// or https://. Got: {url}"
    
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
        
        # Remove scripts, styles, and common ad elements
        for element in soup.find_all(['script', 'style']):
            element.decompose()
        
        # Remove common ad containers (by class/id patterns)
        ad_patterns = [
            'ad', 'ads', 'advertisement', 'advert', 'sponsor', 'sponsored',
            'promo', 'promotion', 'banner', 'popup', 'modal'
        ]
        for element in soup.find_all(class_=lambda x: x and any(pattern in x.lower() for pattern in ad_patterns)):
            element.decompose()
        for element in soup.find_all(id=lambda x: x and any(pattern in x.lower() for pattern in ad_patterns)):
            element.decompose()
        
        # Convert to Markdown using markdownify
        # Use convert=['a'] to ensure links are preserved as [Text](URL)
        markdown_content = md(
            str(soup),
            heading_style="ATX",
            bullets="-",
            convert=['a', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'strong', 'em', 'code', 'blockquote']
        )
        
        # Clean up extra whitespace
        markdown_content = '\n'.join(line.strip() for line in markdown_content.split('\n') if line.strip())
        
        print(f"[DEBUG] Successfully visited page: {final_url} ({len(markdown_content)} chars)", flush=True)
        return markdown_content
        
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else 'unknown'
        if status_code == 404:
            return f"Error accessing page: Page not found (404). Please try a different source."
        elif status_code == 403:
            return f"Error accessing page: Access forbidden (403). Please try a different source."
        else:
            return f"Error accessing page: HTTP {status_code}. Please try a different source."
    except requests.exceptions.Timeout:
        return "Error accessing page: Request timed out. Please try a different source."
    except requests.exceptions.ConnectionError:
        return "Error accessing page: Connection failed. Please try a different source."
    except requests.exceptions.RequestException as e:
        return f"Error accessing page: {str(e)}. Please try a different source."
    except Exception as e:
        print(f"[WARNING] Unexpected error visiting page {url}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return f"Error accessing page: Unexpected error occurred. Please try a different source."
