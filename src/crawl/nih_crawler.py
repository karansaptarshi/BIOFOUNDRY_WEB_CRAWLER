"""
NIH crawler that searches for papers using queries and returns paper links.
Uses NIH Entrez E-utilities API to search PubMed.
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
        here = Path(__file__).resolve()  # .../src/crawl/nih_crawler.py
        cfg_path = here.parent.parent / "config" / "sources.yaml"  # .../src/config/sources.yaml
    else:
        cfg_path = Path(path)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return cfg


def search_nih(query: str, max_results: int = 10) -> List[str]:
    """
    Search NIH PubMed for papers matching the query and return list of paper links.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 10)
    
    Returns:
        List of paper URLs (PubMed abstract pages or PMC links)
    """
    sources = load_sources()
    
    # Explicitly ensure we only use NIH API URL
    if "nih" not in sources:
        raise ValueError("NIH configuration not found in sources.yaml")
    
    api_url = sources["nih"]["api_url"]
    base_url = sources["nih"]["base_url"]
    api_key = sources["nih"].get("api_key", None)  # Optional API key
    
    # Safety check: ensure the URL is actually an NIH URL
    if "ncbi" not in api_url.lower() and "nih" not in api_url.lower():
        raise ValueError(f"Invalid NIH API URL detected: {api_url}. This should be an NIH/NCBI URL only.")
    
    # Step 1: Search PubMed using esearch to get PMIDs
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "xml",
        "sort": "relevance"
    }
    
    if api_key:
        search_params["api_key"] = api_key
    
    search_query_string = urllib.parse.urlencode(search_params)
    search_url = f"{api_url}/esearch.fcgi?{search_query_string}"
    
    try:
        # Make request to PubMed search API
        with urllib.request.urlopen(search_url) as response:
            xml_data = response.read().decode('utf-8')
        
        # Parse XML response to get PMIDs
        root = ET.fromstring(xml_data)
        
        # Extract PMIDs
        pmids = []
        id_list = root.find('.//IdList')
        if id_list is not None:
            for id_elem in id_list.findall('Id'):
                if id_elem.text:
                    pmids.append(id_elem.text)
        
        if not pmids:
            return []
        
        # Step 2: Fetch paper details using efetch to get PMC IDs and other info
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml"
        }
        
        if api_key:
            fetch_params["api_key"] = api_key
        
        fetch_query_string = urllib.parse.urlencode(fetch_params)
        fetch_url = f"{api_url}/efetch.fcgi?{fetch_query_string}"
        
        # Make request to fetch paper details
        with urllib.request.urlopen(fetch_url) as response:
            fetch_xml_data = response.read().decode('utf-8')
        
        # Parse XML to extract paper links
        fetch_root = ET.fromstring(fetch_xml_data)
        
        # Extract paper links
        links = []
        articles = fetch_root.findall('.//PubmedArticle')
        
        for article in articles:
            pmid_elem = article.find('.//PMID')
            if pmid_elem is not None and pmid_elem.text:
                pmid = pmid_elem.text
                
                # Check for PMC ID (PubMed Central - open access)
                pmc_elem = article.find('.//ArticleId[@IdType="pmc"]')
                if pmc_elem is not None and pmc_elem.text:
                    # Prefer PMC link if available (usually has full text)
                    pmc_id = pmc_elem.text.lstrip('PMC')
                    link = f"{base_url}/pmc/articles/PMC{pmc_id}/"
                else:
                    # Fallback to PubMed abstract page
                    link = f"{base_url}/pubmed/{pmid}"
                
                links.append(link)
        
        return links
    
    except Exception as e:
        print(f"Error searching NIH PubMed for query '{query}': {e}")
        return []


def crawl_nih(queries: List[str], max_results_per_query: int = 10) -> List[str]:
    """
    Search NIH PubMed with multiple queries and return all paper links.
    
    Args:
        queries: List of search query strings
        max_results_per_query: Maximum results per query (default: 10)
    
    Returns:
        List of unique paper URLs
    """
    all_links = []
    seen_links = set()
    
    for query in queries:
        print(f"Searching NIH PubMed for: {query}")
        links = search_nih(query, max_results=max_results_per_query)
        
        # Add unique links only
        for link in links:
            if link not in seen_links:
                seen_links.add(link)
                all_links.append(link)
        
        # Be polite to NIH API - small delay between requests
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
        print(f"Searching NIH PubMed with {len(qs)} queries...\n")
        
        # Search NIH and get links
        paper_links = crawl_nih(qs, max_results_per_query=10)
        
        print(f"\nFound {len(paper_links)} unique paper links:\n")
        for i, link in enumerate(paper_links, 1):
            print(f"{i}. {link}")
    
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

