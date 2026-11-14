import logging

from fastapi import FastAPI, HTTPException, Query

from linkhub.database import DatabaseError, load_links
from linkhub.search import SearchEngine

app = FastAPI(title="Linkhub")
engine = SearchEngine()
logger = logging.getLogger(__name__)


@app.get("/busca")
def busca(q: str = Query(..., min_length=1), limite: int = Query(10, ge=1, le=100)):
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Informe uma consulta não vazia.")
    try:
        links = load_links()
    except DatabaseError as exc:
        cause = exc.__cause__
        logger.error("Falha ao consultar o banco: %s (tipo: %s, SQLSTATE: %s)",
                     exc, type(cause).__name__ if cause else "configuração",
                     getattr(cause, "sqlstate", None))
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.") from exc
    try:
        return {"resultados": engine.search(links, query, limite)}
    except Exception as exc:
        logger.exception("Falha no motor de busca")
        raise HTTPException(status_code=503, detail="Motor de busca indisponível.") from exc
