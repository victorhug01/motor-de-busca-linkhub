import os
from pathlib import Path

from dotenv import load_dotenv

from linkhub.search import Link


class DatabaseError(Exception):
    pass


def load_links() -> list[Link]:
    # The project configuration must not be shadowed by a stale inherited URL.
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)
    url = os.getenv("DATABASE_URL")
    if not url:
        raise DatabaseError("DATABASE_URL não configurada")
    try:
        import psycopg
        with psycopg.connect(url, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                query = (Path(__file__).parent / "links.sql").read_text(encoding="utf-8")
                cursor.execute(query)
                return [Link(*row) for row in cursor.fetchall()]
    except Exception as exc:
        raise DatabaseError("Não foi possível consultar o banco de dados") from exc
