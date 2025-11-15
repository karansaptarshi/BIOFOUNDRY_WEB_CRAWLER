"""
arXiv crawler that searches for papers using queries and returns paper links.
"""
from __future__ import annotations
from pathlib import Path
from typing import List
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import yaml
import time


def load_sources(path: str | None = None) -> dict:
    """Load sources configuration from sources.yaml"""
    if path is None:
        here = Path(__file__).resolve()  # .../src/crawl/arxiv_crawler.py
        cfg_path = here.parent.parent / "config" / "sources.yaml"  # .../src/config/sources.yaml
    else:
        cfg_path = Path(path)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return cfg


def search_arxiv(query: str, max_results: int = 10) -> List[str]:
    """
    Search arXiv for papers matching the query and return list of paper links.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 10)
    
    Returns:
        List of paper URLs (abs page links)
    """
    sources = load_sources()
    
    # Explicitly ensure we only use arXiv API URL
    if "arxiv" not in sources:
        raise ValueError("arXiv configuration not found in sources.yaml")
    
    api_url = sources["arxiv"]["api_url"]
    
    # Safety check: ensure the URL is actually an arXiv URL
    if "arxiv" not in api_url.lower():
        raise ValueError(f"Invalid arXiv API URL detected: {api_url}. This should be an arXiv URL only.")
    
    # Build the API query URL
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }
    
    query_string = urllib.parse.urlencode(params)
    url = f"{api_url}?{query_string}"
    
    try:
        # Make request to arXiv API
        with urllib.request.urlopen(url) as response:
            xml_data = response.read().decode('utf-8')
        
        # Parse XML response
        root = ET.fromstring(xml_data)
        
        # Namespace for arXiv Atom feed
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        # Extract paper links
        links = []
        entries = root.findall('atom:entry', ns)
        
        for entry in entries:
            # Get the abstract page link (the main paper page)
            for link in entry.findall('atom:link', ns):
                if link.get('rel') == 'alternate' or link.get('type') == 'text/html':
                    href = link.get('href')
                    if href:
                        links.append(href)
                        break
            else:
                # Fallback: use the id element which contains the abs URL
                id_elem = entry.find('atom:id', ns)
                if id_elem is not None and id_elem.text:
                    links.append(id_elem.text)
        
        return links
    
    except Exception as e:
        print(f"Error searching arXiv for query '{query}': {e}")
        return []


def crawl_arxiv(queries: List[str], max_results_per_query: int = 10) -> List[str]:
    """
    Search arXiv with multiple queries and return all paper links.
    
    Args:
        queries: List of search query strings
        max_results_per_query: Maximum results per query (default: 10)
    
    Returns:
        List of unique paper URLs
    """
    all_links = []
    seen_links = set()
    
    for query in queries:
        print(f"Searching arXiv for: {query}")
        links = search_arxiv(query, max_results=max_results_per_query)
        
        # Add unique links only
        for link in links:
            if link not in seen_links:
                seen_links.add(link)
                all_links.append(link)
        
        # Be polite to arXiv API - small delay between requests
        time.sleep(1)
    
    return all_links


if __name__ == "__main__":
    # Example usage - can be integrated with broaden.py queries
    import sys
    from pathlib import Path
    
    # Add src directory to path for imports
    src_dir = Path(__file__).resolve().parent.parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    from crew.broaden import broaden
    
    try:
        # Get queries from broaden.py
        qs = broaden()
        print(f"Searching arXiv with {len(qs)} queries...\n")
        
        # Search arXiv and get links
        paper_links = crawl_arxiv(qs, max_results_per_query=10)
        
        print(f"\nFound {len(paper_links)} unique paper links:\n")
        for i, link in enumerate(paper_links, 1):
            print(f"{i}. {link}")
    
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

