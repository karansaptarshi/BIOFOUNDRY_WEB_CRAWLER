from src.downloader.database.db import get_connection


def main():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT NOW();")
    print("Connected! Time:", cur.fetchone())

    conn.close()

if __name__ == "__main__":
    main()
