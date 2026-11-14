"""Busca híbrida adaptada do projeto PerguntaEvidencia."""

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import re
from threading import Lock

import numpy as np

MODEL = "sentence-transformers/multi-qa-MiniLM-L6-cos-v1"


@dataclass(frozen=True)
class Link:
    id: int
    url: str
    titulo: str
    descricao: str

    def text(self) -> str:
        return f"{self.titulo}. {self.descricao} {self.url}"


def tokenize(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)


def normalize(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    low, high = min(scores.values()), max(scores.values())
    if low == high:
        return {key: 1.0 for key in scores}
    return {key: (value - low) / (high - low) for key, value in scores.items()}


class SearchEngine:
    def __init__(self, encoder=None):
        self.encoder = encoder
        self.links: tuple[Link, ...] | None = None
        self.lock = Lock()

    def _encode(self, texts):
        if self.encoder is None:
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer(MODEL)
        vectors = self.encoder.encode(texts, convert_to_numpy=True, normalize_embeddings=True,
                                      show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float32)

    def _build(self, links: tuple[Link, ...]):
        frequencies = [Counter(tokenize(link.text())) for link in links]
        lengths = [sum(row.values()) for row in frequencies]
        postings = defaultdict(list)
        for index, row in enumerate(frequencies):
            for term, count in row.items():
                postings[term].append((index, count))
        embeddings = self._encode([link.text() for link in links])
        self.postings = postings
        self.lengths = lengths
        self.average_length = sum(lengths) / len(lengths)
        self.embeddings = embeddings
        self.links = links

    def search(self, links: list[Link], query: str, limit: int) -> list[dict]:
        # Serialize rebuild and inference so concurrent requests never mix snapshots.
        with self.lock:
            snapshot = tuple(sorted(links, key=lambda link: link.id))
            if not snapshot:
                self.links = None
                return []
            if snapshot != self.links:
                self._build(snapshot)
            lexical = defaultdict(float)
            for term, query_frequency in Counter(tokenize(query)).items():
                entries = self.postings.get(term, [])
                if not entries:
                    continue
                idf = math.log(1 + (len(snapshot) - len(entries) + 0.5) / (len(entries) + 0.5))
                for index, frequency in entries:
                    denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * self.lengths[index] / max(self.average_length, 1e-9))
                    lexical[index] += query_frequency * idf * frequency * 2.5 / denominator
            query_vector = self._encode([query])[0]
            similarities = self.embeddings @ query_vector
            dense = {index: float(score) for index, score in enumerate(similarities)}
            lexical, dense = normalize(lexical), normalize(dense)
            scores = {i: 0.5 * lexical.get(i, 0.0) + 0.5 * dense[i] for i in dense}
            ranking = sorted(scores, key=lambda i: (-scores[i], snapshot[i].id))[:limit]
            return [{"id": snapshot[i].id, "url": snapshot[i].url,
                     "titulo": snapshot[i].titulo, "descricao": snapshot[i].descricao,
                     "pontuacao": scores[i]} for i in ranking]
