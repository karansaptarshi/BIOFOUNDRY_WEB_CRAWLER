import psycopg2
from typing import Optional


def get_connection():
    return psycopg2.connect(
        dbname="crawler",
        user="karan",      # ← change this!
        password="",       # empty unless you set one
        host="localhost",
        port=5432
    )


def create_pdf_links_table_if_not_exists():
    """
    Create the pdf_links table if it doesn't exist.
    
    Table structure:
    - id: SERIAL PRIMARY KEY
    - title: TEXT (paper title, can be NULL)
    - url: TEXT NOT NULL (the research paper link URL)
    - s3_key: TEXT (S3 key for stored PDF, NULL if not uploaded yet)
    - s3_url: TEXT (S3 URL for stored PDF, NULL if not uploaded yet)
    - created_at: TIMESTAMP DEFAULT NOW()
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        create_table_query = """
        CREATE TABLE IF NOT EXISTS pdf_links (
            id SERIAL PRIMARY KEY,
            title TEXT,
            url TEXT NOT NULL UNIQUE,
            s3_key TEXT,
            s3_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
        
        cur.execute(create_table_query)
        conn.commit()
        cur.close()
        print("✓ Table 'pdf_links' is ready (created or already exists)")
        
    except psycopg2.Error as e:
        print(f"Error creating table: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def save_pdf_link(url: str, title: Optional[str] = None) -> Optional[int]:
    """
    Save a PDF link to the database.
    
    Args:
        url: The research paper link URL to save
        title: Optional paper title (None if not available yet)
    
    Returns:
        The ID of the inserted record, or None if insertion failed
    """
    # First, ensure the table exists
    create_pdf_links_table_if_not_exists()
    
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Try to insert the link
        # Use ON CONFLICT to handle duplicate links gracefully
        # s3_key and s3_url are set to None (NULL) since S3 hasn't been created yet
        insert_query = """
        INSERT INTO pdf_links (title, url, s3_key, s3_url)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING
        RETURNING id;
        """
        
        cur.execute(insert_query, (title, url, None, None))
        
        # Check if a row was inserted (not a duplicate)
        result = cur.fetchone()
        if result:
            inserted_id = result[0]
            conn.commit()
            print(f"✓ Saved PDF link to database (ID: {inserted_id}): {url}")
            return inserted_id
        else:
            conn.commit()
            print(f"⚠ PDF link already exists in database: {url}")
            # Get the existing ID
            cur.execute("SELECT id FROM pdf_links WHERE url = %s;", (url,))
            existing_result = cur.fetchone()
            if existing_result:
                return existing_result[0]
            return None
        
    except psycopg2.Error as e:
        print(f"Error saving PDF link to database: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            cur.close()
            conn.close()


def save_first_pdf_link(links: list[str], title: Optional[str] = None) -> Optional[int]:
    """
    Save the first PDF link from a list of links to the database.
    
    Args:
        links: List of PDF link URLs
        title: Optional paper title (None if not available yet)
    
    Returns:
        The ID of the inserted record, or None if no links or insertion failed
    """
    if not links:
        print("No links provided to save")
        return None
    
    first_link = links[0]
    
    # Save the link with title (None if not provided)
    # s3_key and s3_url will be set to None automatically
    return save_pdf_link(first_link, title)
