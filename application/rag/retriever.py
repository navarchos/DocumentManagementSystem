"""Vector retrieval over `rag_chunks` with ACL applied via `get_orders_for_user`."""
import logging
from typing import Iterable

from flask import current_app

from app import db
from application.models import RagChunk
from application.rag import client as yandex_client
from application.services import get_orders_for_user

logger = logging.getLogger(__name__)


def _visible_order_ids() -> set[str]:
    """Return order ids the current session is allowed to see."""
    return {o.id for o in get_orders_for_user()}


def search(query: str, *, top_k: int | None = None) -> list[dict]:
    """Embed the query and pull the top-K nearest chunks from rag_chunks.

    The result is a list of dicts ``{chunk_id, order_id, source_type,
    order_file_id, chunk_index, text, score}`` ordered by descending score.
    ACL filtering is mandatory — chunks outside the user's visible orders
    are dropped server-side via SQL.
    """
    if not query or not query.strip():
        return []
    top_k = top_k or current_app.config['RAG_TOP_K']

    visible_ids = _visible_order_ids()
    if not visible_ids:
        return []

    embedding = yandex_client.embed_query(query)

    distance = RagChunk.embedding.cosine_distance(embedding)
    rows: Iterable[tuple[RagChunk, float]] = (
        db.session.query(RagChunk, distance.label('distance'))
        .filter(RagChunk.order_id.in_(visible_ids))
        .filter(RagChunk.embedding.isnot(None))
        .order_by(distance.asc())
        .limit(top_k)
        .all()
    )

    results = []
    for chunk, dist in rows:
        results.append({
            'chunk_id': chunk.id,
            'order_id': chunk.order_id,
            'source_type': chunk.source_type,
            'order_file_id': chunk.order_file_id,
            'chunk_index': chunk.chunk_index,
            'text': chunk.text,
            'score': 1.0 - float(dist),
        })
    return results
