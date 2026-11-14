import os
import sys
import types
import unittest

import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import patch

from linkhub.database import DatabaseError, load_links
from linkhub.main import app
from linkhub.search import Link, SearchEngine


class FakeEncoder:
    def __init__(self):
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append(list(texts))
        vectors = []
        for text in texts:
            text = text.lower()
            vector = np.array([float(any(word in text for word in ("gato", "felino"))),
                               float("cachorro" in text)], dtype=np.float32)
            norm = np.linalg.norm(vector)
            vectors.append(vector / norm if norm else vector)
        return np.array(vectors)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.encoder = FakeEncoder()
        self.engine = SearchEngine(self.encoder)
        self.links = [Link(1, "https://example.com/1", "Gato", "Animal doméstico"),
                      Link(2, "https://example.com/2", "Cachorro", "Outro animal")]

    def test_lexical_and_semantic_ranking(self):
        self.assertEqual(self.engine.search(self.links, "gato", 10)[0]["id"], 1)
        # No lexical overlap, but the fake model maps the synonym to the same vector.
        self.assertEqual(self.engine.search(self.links, "felino", 10)[0]["id"], 1)

    def test_changes_rebuild_index_and_empty_data(self):
        self.engine.search(self.links, "gato", 10)
        self.engine.search(self.links, "felino", 10)
        self.assertEqual(len(self.encoder.calls), 3)  # one corpus, two queries
        updated = [Link(1, "https://example.com/1", "Cachorro", "Alterado")]
        self.assertEqual(self.engine.search(updated, "cachorro", 10)[0]["titulo"], "Cachorro")
        self.assertEqual(len(self.encoder.calls), 5)
        self.assertEqual(self.engine.search([], "gato", 10), [])
        self.engine.search(updated, "cachorro", 10)
        self.assertEqual(len(self.encoder.calls), 7)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("linkhub.main.load_links", return_value=[])
    def test_empty_database_and_validation(self, load):
        response = self.client.get("/busca", params={"q": "gato"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"resultados": []})
        self.assertEqual(self.client.get("/busca", params={"q": "  "}).status_code, 422)
        self.assertEqual(self.client.get("/busca", params={"q": "gato", "limite": 101}).status_code, 422)

    @patch("linkhub.main.load_links", side_effect=DatabaseError("erro"))
    def test_database_failure(self, load):
        response = self.client.get("/busca", params={"q": "gato"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("erro", response.text)

    @patch("linkhub.main.engine", new_callable=lambda: SearchEngine(FakeEncoder()))
    @patch("linkhub.main.load_links", return_value=[Link(1, "https://example.com", "Gato", "")])
    def test_search_response(self, load, engine):
        response = self.client.get("/busca", params={"q": "felino", "limite": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["resultados"][0]["id"], 1)


class DatabaseTests(unittest.TestCase):
    def test_connection_and_query(self):
        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def execute(self, query): self.query = query
            def fetchall(self): return [(1, "https://example.com", "Título", "Descrição")]

        cursor = Cursor()

        class Connection:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def cursor(self): return cursor

        fake_driver = types.SimpleNamespace(connect=lambda url, connect_timeout: Connection())
        with patch("linkhub.database.load_dotenv"), \
             patch.dict(os.environ, {"DATABASE_URL": "postgresql://example"}), \
             patch.dict(sys.modules, {"psycopg": fake_driver}):
            self.assertEqual(load_links()[0].titulo, "Título")
        self.assertIn("FROM links", cursor.query)

    @patch("linkhub.database.load_dotenv")
    def test_missing_configuration(self, dotenv):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(DatabaseError):
            load_links()

    @patch("linkhub.database.load_dotenv")
    def test_project_env_overrides_inherited_values(self, dotenv):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(DatabaseError):
            load_links()
        self.assertTrue(dotenv.call_args.kwargs["override"])
        self.assertEqual(dotenv.call_args.args[0].name, ".env")


if __name__ == "__main__":
    unittest.main()
