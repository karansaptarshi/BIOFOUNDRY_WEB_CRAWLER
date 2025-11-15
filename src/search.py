"""
Search orchestration: reads queries, calls broaden(), and searches arXiv, NIH, and bioRxiv.
"""
from __future__ import annotations
from pathlib import Path
from typing import List
import yaml
import tempfile
import os

from crew.broaden import broaden
from crawl.arxiv_crawler import crawl_arxiv
from crawl.nih_crawler import crawl_nih
from crawl.biorxiv_crawler import crawl_biorxiv
from downloader.database.link2pdf import download_link_to_pdf
from downloader.database.db import save_first_pdf_link


def load_queries(path: str | None = None) -> List[tuple[str, int]]:
    """
    Load all seed topics and target counts from queries.yaml.
    
    Supports multiple formats:
    1. List format (recommended):
       seed_topics:
         - seed_topic: "Topic 1"
           target_count: 5
         - seed_topic: "Topic 2"
           target_count: 10
    
    2. Single topic format:
       seed_topic: "Topic 1"
       target_count: 5
    
    3. Duplicate keys format (legacy, parsed manually):
       seed_topic: "Topic 1"
       target_count: 5
       seed_topic: "Topic 2"
       target_count: 10
    
    Returns list of (seed_topic, target_count) tuples.
    """
    if path is None:
        here = Path(__file__).resolve()  # .../src/search.py
        cfg_path = here.parent / "config" / "queries.yaml"  # .../src/config/queries.yaml
    else:
        cfg_path = Path(path)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    
    seed_topics = []
    target_counts = []
    
    # Format 1: List format (recommended)
    if "seed_topics" in cfg and isinstance(cfg["seed_topics"], list):
        for item in cfg["seed_topics"]:
            if isinstance(item, dict) and "seed_topic" in item:
                seed_topics.append(item["seed_topic"])
                target_counts.append(int(item.get("target_count", cfg.get("target_count", 5))))
            elif isinstance(item, str):
                # Handle list of strings
                seed_topics.append(item)
                target_counts.append(int(cfg.get("target_count", 5)))
    
    # Format 2: Single topic
    elif "seed_topic" in cfg:
        # Check if it's a list of strings
        if isinstance(cfg["seed_topic"], list):
            for topic in cfg["seed_topic"]:
                seed_topics.append(topic)
                target_counts.append(int(cfg.get("target_count", 5)))
        else:
            # Single topic
            seed_topics.append(cfg["seed_topic"])
            target_counts.append(int(cfg.get("target_count", 5)))
    
    # Format 3: Legacy duplicate keys format (parse manually)
    if not seed_topics:
        raw_text = cfg_path.read_text(encoding="utf-8")
        lines = raw_text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('seed_topic:'):
                # Extract the topic value
                topic = line.split(':', 1)[1].strip().strip('"').strip("'")
                if topic:
                    seed_topics.append(topic)
                    # Check if next line has target_count for this topic
                    if i + 1 < len(lines) and lines[i + 1].strip().startswith('target_count:'):
                        count_str = lines[i + 1].strip().split(':', 1)[1].strip()
                        target_counts.append(int(count_str))
                        i += 1  # Skip the target_count line
                    else:
                        # Use default or last seen target_count
                        target_counts.append(int(cfg.get("target_count", 5)))
            i += 1
    
    # Return list of (seed_topic, target_count) tuples
    return [(topic, count) for topic, count in zip(seed_topics, target_counts) if topic]


def search(queries_path: str | None = None, max_results_per_query: int = 10) -> List[str]:
    """
    Main search function that:
    1. Reads all seed topics and target counts from queries.yaml
    2. For each seed topic, calls broaden() to expand queries
    3. Calls crawl_arxiv() to search arXiv
    4. Calls crawl_nih() to search NIH PubMed
    5. Calls crawl_biorxiv() to search bioRxiv
    6. Returns combined list of unique paper links (arXiv abstract pages + NIH PubMed/PMC links + bioRxiv links)
    
    Args:
        queries_path: Optional path to queries.yaml (default: src/config/queries.yaml)
        max_results_per_query: Maximum results per query (default: 10)
    
    Returns:
        List of unique paper URLs (arXiv abstract pages, NIH PubMed/PMC links, and bioRxiv links) across all seed topics
    """
    # Read all seed topics and target counts from queries.yaml
    seed_topics = load_queries(queries_path)
    
    if not seed_topics:
        print("No seed topics found in queries.yaml")
        return []
    
    print("=" * 60)
    print("Search Orchestrator")
    print("=" * 60)
    print(f"Found {len(seed_topics)} seed topic(s):")
    for i, (topic, count) in enumerate(seed_topics, 1):
        print(f"  {i}. {topic} (target: {count} queries)")
    print("=" * 60)
    
    # Combine and deduplicate all links across all seed topics
    all_links = []
    seen_links = set()
    total_arxiv_links = 0
    total_nih_links = 0
    total_biorxiv_links = 0
    
    # Track links by seed topic
    links_by_topic = {}
    
    # Process each seed topic
    for topic_idx, (seed_topic, target_count) in enumerate(seed_topics, 1):
        print(f"\n{'=' * 60}")
        print(f"Processing seed topic {topic_idx}/{len(seed_topics)}: {seed_topic}")
        print("=" * 60)
        
        # Create a temporary queries config for this seed topic
        temp_cfg = {
            "seed_topic": seed_topic,
            "target_count": target_count
        }
        
        # Write to temp file or pass directly to broaden
        # Since broaden() reads from file, we'll create a temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_file:
            yaml.dump(temp_cfg, tmp_file)
            temp_path = tmp_file.name
        
        try:
            # Convert Path to string if provided, otherwise use temp file
            broaden_path = temp_path
            
            print(f"\nGenerating expanded queries for '{seed_topic}'...\n")
            
            # Call broaden() to expand the seed topic into queries
            expanded_queries = broaden(broaden_path)
            
            print(f"Generated {len(expanded_queries)} queries:")
            for i, q in enumerate(expanded_queries, 1):
                print(f"  {i}. {q}")
            
            # Search arXiv
            print(f"\nSearching arXiv for topic '{seed_topic}'...")
            arxiv_links = crawl_arxiv(expanded_queries, max_results_per_query=max_results_per_query)
            
            # Search NIH PubMed
            print(f"\nSearching NIH PubMed for topic '{seed_topic}'...")
            nih_links = crawl_nih(expanded_queries, max_results_per_query=max_results_per_query)
            
            # Search bioRxiv
            print(f"\nSearching bioRxiv for topic '{seed_topic}'...")
            biorxiv_links = crawl_biorxiv(expanded_queries, max_results_per_query=max_results_per_query)
            
            # Track links for this topic
            topic_links = []
            
            # Add unique links to the combined list and track by topic
            for link in arxiv_links + nih_links + biorxiv_links:
                if link not in seen_links:
                    seen_links.add(link)
                    all_links.append(link)
                    topic_links.append(link)
            
            # Store links for this topic
            links_by_topic[seed_topic] = topic_links
            
            total_arxiv_links += len(arxiv_links)
            total_nih_links += len(nih_links)
            total_biorxiv_links += len(biorxiv_links)
            
            print(f"\nTopic '{seed_topic}' results:")
            print(f"  arXiv: {len(arxiv_links)} links")
            print(f"  NIH: {len(nih_links)} links")
            print(f"  bioRxiv: {len(biorxiv_links)} links")
            print(f"  New unique links added: {len(topic_links)}")
        
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
    
    print("\n" + "=" * 60)
    print(f"Final Summary (across all {len(seed_topics)} seed topics):")
    print(f"  Total arXiv links: {total_arxiv_links}")
    print(f"  Total NIH links: {total_nih_links}")
    print(f"  Total bioRxiv links: {total_biorxiv_links}")
    print(f"  Total unique paper links: {len(all_links)}")
    print("=" * 60)
    
    # Output links grouped by seed topic (print all links)
    print("\n" + "=" * 60)
    print("Paper Links by Seed Topic:")
    print("=" * 60)
    
    for topic_idx, (seed_topic, _) in enumerate(seed_topics, 1):
        topic_links = links_by_topic.get(seed_topic, [])
        print(f"\n[{topic_idx}] {seed_topic}")
        print("-" * 60)
        if topic_links:
            for i, link in enumerate(topic_links, 1):
                print(f"  {i}. {link}")
            print(f"\n  Total: {len(topic_links)} unique links")
        else:
            print("  No links found for this topic.")
    
    print("\n" + "=" * 60)
    
    # Per-topic summary at the end
    for topic_idx, (seed_topic, _) in enumerate(seed_topics, 1):
        topic_links = links_by_topic.get(seed_topic, [])
        print(f"{seed_topic}: {len(topic_links)} links")
    
    return all_links


if __name__ == "__main__":
    try:
        # Run the search pipeline
        paper_links = search(max_results_per_query=10)
        
        # Download only the first PDF (for testing)
        print("\n" + "=" * 60)
        print("Downloading PDFs (Testing - Downloading 1 only):")
        print("=" * 60)
        
        if paper_links:
            # Save the first PDF link to the database
            print("\n" + "=" * 60)
            print("Saving first PDF link to database:")
            print("=" * 60)
            db_id = save_first_pdf_link(paper_links)
            if db_id:
                print(f"✓ First PDF link saved to database with ID: {db_id}")
            else:
                print("⚠ Failed to save PDF link to database")
            
            # For now, download only the first link
            first_link = paper_links[0]
            print(f"\nDownloading first link: {first_link}")
            
            downloaded_path = download_link_to_pdf(first_link)
            
            if downloaded_path:
                print(f"\n✓ Successfully downloaded PDF to: {downloaded_path}")
                print(f"  Total links found: {len(paper_links)}")
                print(f"  (Downloaded 1 of {len(paper_links)} links)")
            else:
                print(f"\n✗ Failed to download PDF from: {first_link}")
        else:
            print("No links found to download.")
        
        print("=" * 60)
    
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

