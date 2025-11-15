"""
Download PDFs from paper links (arXiv, NIH PMC, etc.) to temporary directory.
"""
from __future__ import annotations
from pathlib import Path
import tempfile
import urllib.request
import urllib.parse
import urllib.error
import re
import os
from typing import Optional


def arxiv_link_to_pdf(link: str) -> Optional[str]:
    """
    Convert arXiv abstract page link to PDF URL.
    
    Args:
        link: arXiv abstract page URL (e.g., https://arxiv.org/abs/1234.5678)
    
    Returns:
        PDF URL or None if conversion fails
    """
    # Pattern: https://arxiv.org/abs/XXXX.XXXXX or http://arxiv.org/abs/XXXX.XXXXX
    # Convert to: https://arxiv.org/pdf/XXXX.XXXXX.pdf
    pattern = r'https?://arxiv\.org/abs/([^\s]+)'
    match = re.search(pattern, link)
    if match:
        paper_id = match.group(1)
        # Remove version suffix if present (e.g., v1, v2)
        paper_id = re.sub(r'v\d+$', '', paper_id)
        pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
        return pdf_url
    return None


def nih_link_to_pdf(link: str) -> Optional[str]:
    """
    Convert NIH PMC link to PDF URL.
    
    Args:
        link: NIH PMC or PubMed link (e.g., https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123456/)
    
    Returns:
        PDF URL or None if conversion fails
    """
    # Pattern: https://www.ncbi.nlm.nih.gov/pmc/articles/PMCXXXXXX/
    # Convert to: https://www.ncbi.nlm.nih.gov/pmc/articles/PMCXXXXXX/pdf/
    pattern = r'https?://www\.ncbi\.nlm\.nih\.gov/pmc/articles/(PMC\d+)/?'
    match = re.search(pattern, link)
    if match:
        pmc_id = match.group(1)
        # Try to get PDF - PMC articles often have PDFs at this endpoint
        # We'll need to check if the PDF exists
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/"
        return pdf_url
    
    # For PubMed links, we can't easily get PDFs without additional API calls
    # Return None for now
    return None


def biorxiv_link_to_pdf(link: str) -> Optional[str]:
    """
    Convert bioRxiv abstract page link to PDF URL.
    
    Args:
        link: bioRxiv abstract page URL (e.g., https://www.biorxiv.org/content/10.1101/2023.01.01.123456v1)
    
    Returns:
        PDF URL or None if conversion fails
    """
    # Pattern: https://www.biorxiv.org/content/{doi}v{version}
    # Convert to: https://www.biorxiv.org/content/{doi}v{version}.full.pdf
    pattern = r'https?://www\.biorxiv\.org/content/([^\s]+)'
    match = re.search(pattern, link)
    if match:
        content_path = match.group(1)
        # Remove .full.pdf if already present, then add it
        content_path = re.sub(r'\.full\.pdf$', '', content_path)
        pdf_url = f"https://www.biorxiv.org/content/{content_path}.full.pdf"
        return pdf_url
    return None


def download_pdf(url: str, output_path: Path) -> bool:
    """
    Download PDF from URL to output path.
    
    Args:
        url: URL of the PDF
        output_path: Path where PDF should be saved
    
    Returns:
        True if download successful, False otherwise
    """
    try:
        # Create a request with headers to mimic a browser
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        
        # Create an opener that handles redirects
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        
        # Download the PDF (follows redirects automatically)
        with opener.open(req, timeout=30) as response:
            # Get the final URL after redirects
            final_url = response.geturl()
            
            # Check if it's actually a PDF
            content_type = response.headers.get('Content-Type', '')
            # Some servers don't set Content-Type correctly, so we'll check the data
            pdf_data = response.read()
            
            # Check if the data starts with PDF magic bytes
            if not pdf_data.startswith(b'%PDF'):
                # Check if we got HTML instead (common for error pages)
                if pdf_data.startswith(b'<') or b'<!DOCTYPE' in pdf_data[:100]:
                    print(f"Received HTML instead of PDF from {final_url}")
                    return False
                # Some PDFs might not start with %PDF, but let's be lenient
                # and check content type or file extension
                if 'pdf' not in content_type.lower() and 'application/octet-stream' not in content_type.lower():
                    # Check if URL ends with .pdf
                    if not final_url.lower().endswith('.pdf'):
                        print(f"Content-Type is {content_type}, and URL doesn't end with .pdf")
                        return False
            
            # Save to output path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(pdf_data)
            
            return True
    
    except urllib.error.HTTPError as e:
        print(f"HTTP error downloading PDF from {url}: {e.code} {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"URL error downloading PDF from {url}: {e.reason}")
        return False
    except Exception as e:
        print(f"Error downloading PDF from {url}: {e}")
        return False


def link_to_pdf_url(link: str) -> Optional[str]:
    """
    Convert a paper link to its PDF URL.
    
    Args:
        link: Paper link (arXiv, NIH PMC, bioRxiv, etc.)
    
    Returns:
        PDF URL or None if conversion not possible
    """
    # Check if it's an arXiv link
    if 'arxiv.org' in link:
        return arxiv_link_to_pdf(link)
    
    # Check if it's an NIH/PMC link
    if 'ncbi.nlm.nih.gov' in link:
        return nih_link_to_pdf(link)
    
    # Check if it's a bioRxiv link
    if 'biorxiv.org' in link:
        return biorxiv_link_to_pdf(link)
    
    # Unknown link type
    return None


def download_link_to_pdf(link: str, output_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Download PDF from a paper link to temporary directory.
    
    Args:
        link: Paper link (arXiv, NIH PMC, etc.)
        output_dir: Optional output directory (default: system temp directory)
    
    Returns:
        Path to downloaded PDF file, or None if download failed
    """
    # Convert link to PDF URL
    pdf_url = link_to_pdf_url(link)
    
    if not pdf_url:
        print(f"Could not convert link to PDF URL: {link}")
        return None
    
    # Determine output directory
    if output_dir is None:
        output_dir = Path(tempfile.gettempdir())
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate output filename
    # Extract a meaningful name from the URL
    if 'arxiv.org' in link:
        # Extract paper ID from arXiv link
        match = re.search(r'arxiv\.org/abs/([^\s/]+)', link)
        if match:
            paper_id = match.group(1).replace('/', '_')
            filename = f"arxiv_{paper_id}.pdf"
        else:
            filename = "arxiv_paper.pdf"
    elif 'ncbi.nlm.nih.gov' in link:
        # Extract PMC ID from NIH link
        match = re.search(r'PMC(\d+)', link)
        if match:
            pmc_id = match.group(1)
            filename = f"pmc_{pmc_id}.pdf"
        else:
            filename = "nih_paper.pdf"
    elif 'biorxiv.org' in link:
        # Extract DOI from bioRxiv link
        match = re.search(r'biorxiv\.org/content/([^\s/]+)', link)
        if match:
            doi_part = match.group(1).replace('/', '_').replace('v', '_v')
            filename = f"biorxiv_{doi_part}.pdf"
        else:
            filename = "biorxiv_paper.pdf"
    else:
        filename = "paper.pdf"
    
    output_path = output_dir / filename
    
    # Download the PDF
    print(f"Downloading PDF from: {pdf_url}")
    if download_pdf(pdf_url, output_path):
        print(f"PDF downloaded to: {output_path}")
        return output_path
    else:
        print(f"Failed to download PDF from: {pdf_url}")
        return None


if __name__ == "__main__":
    # Test with a sample link
    import sys
    
    if len(sys.argv) > 1:
        link = sys.argv[1]
        result = download_link_to_pdf(link)
        if result:
            print(f"Success! PDF saved to: {result}")
        else:
            print("Failed to download PDF")
    else:
        print("Usage: python link2pdf.py <paper_link>")
        print("Example: python link2pdf.py https://arxiv.org/abs/1706.03762")

