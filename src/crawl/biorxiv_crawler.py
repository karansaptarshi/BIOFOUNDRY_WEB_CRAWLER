"""
Simple bioRxiv crawler that fetches the latest paper links from RSS feed.
"""
from __future__ import annotations
from typing import List
import feedparser
import requests
import time


def fetch_biorxiv_links(limit: int = 50) -> List[str]:
    """
    Fetch the latest bioRxiv paper links from RSS feed.
    
    Args:
        limit: Maximum number of links to return (default: 50)
    
    Returns:
        List of paper URLs (abstract page links)
    """
    rss_url = "https://connect.biorxiv.org/biorxiv_xml.php?subject=all"
    links = []
    
    try:
        # Use requests with proper headers to bypass Cloudflare
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.biorxiv.org/',
        }
        
        response = requests.get(rss_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse the RSS feed
        feed = feedparser.parse(response.text)
        
        # Even if there are parsing warnings, entries might still be available
        # Check if we have entries regardless of bozo flag
        if hasattr(feed, 'entries') and len(feed.entries) > 0:
            entries = feed.entries[:limit] if len(feed.entries) > limit else feed.entries
            
            for entry in entries:
                # Try multiple ways to get the link
                link = entry.get("link", "") or entry.get("id", "")
                if link:
                    # Remove RSS query parameter if present
                    if "?rss=1" in link:
                        link = link.split("?rss=1")[0]
                    links.append(link)
            
            if links:
                print(f"✓ Fetched {len(links)} bioRxiv links from RSS feed")
            else:
                print(f"⚠️  No links found in RSS feed entries")
        else:
            if feed.bozo:
                print(f"⚠️  RSS feed parsing issues: {feed.bozo_exception}")
            print(f"⚠️  No entries found in RSS feed")
        
    except Exception as e:
        print(f"⚠️  Error fetching bioRxiv RSS feed from {rss_url}: {e}")
        import traceback
        traceback.print_exc()
    
    return links


def crawl_biorxiv_links(limit: int = 50) -> List[str]:
    """
    Crawl bioRxiv and return latest paper links.
    
    Args:
        limit: Maximum number of links to return (default: 50)
    
    Returns:
        List of paper URLs
    """
    return fetch_biorxiv_links(limit)


def search_biorxiv(query: str, max_results: int = 10) -> List[str]:
    """
    Search bioRxiv for papers matching a single query.
    
    Fetches papers from RSS feed and filters them by checking if the query
    appears in title or abstract.
    
    Args:
        query: Search query string
        max_results: Maximum number of links to return (default: 10)
    
    Returns:
        List of paper URLs matching the query
    """
    if not query:
        return []
    
    rss_url = "https://connect.biorxiv.org/biorxiv_xml.php?subject=all"
    matching_links = []
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.biorxiv.org/',
        }
        
        response = requests.get(rss_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        feed = feedparser.parse(response.text)
        
        if hasattr(feed, 'entries') and len(feed.entries) > 0:
            # Normalize query for matching
            query_lower = query.lower()
            query_words = query_lower.split()
            
            # Check each entry against the query
            for entry in feed.entries:
                if len(matching_links) >= max_results:
                    break
                
                title = entry.get("title", "").lower()
                abstract = entry.get("summary", "").lower() if "summary" in entry else ""
                
                # Check if query matches
                matches = False
                if query_lower in title or query_lower in abstract:
                    matches = True
                elif len(query_words) > 1:
                    # For multi-word queries, check if at least 2 words match
                    title_words = set(title.split())
                    abstract_words = set(abstract.split())
                    matching_words = sum(1 for word in query_words if word in title_words or word in abstract_words)
                    if matching_words >= min(2, len(query_words)):
                        matches = True
                
                if matches:
                    link = entry.get("link", "") or entry.get("id", "")
                    if link:
                        # Remove RSS query parameter if present
                        if "?rss=1" in link:
                            link = link.split("?rss=1")[0]
                        matching_links.append(link)
        
    except Exception as e:
        print(f"⚠️  Error searching bioRxiv for query '{query}': {e}")
    
    return matching_links


def crawl_biorxiv(queries: List[str], max_results_per_query: int = 200) -> List[str]:
    """
    Search bioRxiv with multiple queries and return all paper links.
    
    Args:
        queries: List of search query strings
        max_results_per_query: Maximum results per query (default: 200)
    
    Returns:
        List of unique paper URLs
    """
    all_links = []
    seen_links = set()
    
    for query in queries:
        print(f"Searching bioRxiv for: {query}")
        links = search_biorxiv(query, max_results=max_results_per_query)
        
        # Add unique links only
        for link in links:
            if link not in seen_links:
                seen_links.add(link)
                all_links.append(link)
        
        # Be polite - small delay between requests
        time.sleep(0.5)
    
    if all_links:
        print(f"✓ Found {len(all_links)} unique bioRxiv papers across all queries")
    else:
        print(f"⚠️  No bioRxiv papers found matching the queries")
    
    return all_links


if __name__ == "__main__":
    print("Testing bioRxiv RSS feed crawler...\n")
    test_links = fetch_biorxiv_links(limit=10)
    if test_links:
        print(f"✓ RSS feed working! Found {len(test_links)} papers")
        print(f"Sample link: {test_links[0]}")
    else:
        print("⚠ No links found — RSS feed might be unavailable.")
