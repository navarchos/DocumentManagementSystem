"""Build and maintain the RAG vector store for orders, history and attachments."""
import hashlib
import logging
import threading

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app import app, db
from application.models import (
    Order,
    OrderFile,
    OrderHistory,
    RagChunk,
    RagDocument,
)
from application.rag import client as yandex_client
from application.rag.chunker import chunk_text
from application.rag.extractors import (
    extract_file_text,
    extract_order_content,
    extract_order_history,
)

logger = logging.getLogger(__name__)


SOURCE_ORDER_CONTENT = 'order_content'
SOURCE_ORDER_HISTORY = 'order_history'
SOURCE_ORDER_FILE = 'order_file'


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _empty_stats() -> dict:
    return {'documents': 0, 'chunks': 0, 'skipped': 0, 'errors': 0}


def _rag_supported() -> bool:
    is_supported = getattr(app, 'is_rag_supported', None)
    return bool(is_supported() if callable(is_supported) else False)


def _index_document(
    *,
    source_type: str,
    order_id: str,
    title: str | None,
    text: str | None,
    order_file_id: int | None = None,
    stats: dict,
) -> None:
    if not text:
        existing = RagDocument.query.filter_by(
            source_type=source_type, order_id=order_id, order_file_id=order_file_id
        ).first()
        if existing:
            RagChunk.query.filter_by(document_id=existing.id).delete()
            db.session.delete(existing)
            db.session.commit()
        stats['skipped'] += 1
        return

    digest = _content_hash(text)
    existing = RagDocument.query.filter_by(
        source_type=source_type, order_id=order_id, order_file_id=order_file_id
    ).first()
    if existing and existing.content_hash == digest:
        stats['skipped'] += 1
        return

    chunks = list(
        chunk_text(
            text,
            max_tokens=current_app.config['RAG_CHUNK_TOKENS'],
            overlap_tokens=current_app.config['RAG_CHUNK_OVERLAP'],
        )
    )
    if not chunks:
        stats['skipped'] += 1
        return

    try:
        embeddings = yandex_client.embed_documents([c['text'] for c in chunks])
    except yandex_client.YandexAPIError:
        logger.exception(
            'Failed to embed chunks for %s/%s (file=%s)', source_type, order_id, order_file_id
        )
        stats['errors'] += 1
        return

    if existing:
        RagChunk.query.filter_by(document_id=existing.id).delete()
        existing.content_hash = digest
        existing.title = title
        document = existing
    else:
        document = RagDocument(
            source_type=source_type,
            order_id=order_id,
            order_file_id=order_file_id,
            title=title,
            content_hash=digest,
        )
        db.session.add(document)
        db.session.flush()

    for chunk, vector in zip(chunks, embeddings):
        db.session.add(
            RagChunk(
                document_id=document.id,
                order_id=order_id,
                source_type=source_type,
                order_file_id=order_file_id,
                chunk_index=chunk['index'],
                text=chunk['text'],
                token_count=chunk['token_count'],
                embedding=vector,
            )
        )
    db.session.commit()
    stats['documents'] += 1
    stats['chunks'] += len(chunks)


def _index_order_content(order, stats: dict) -> None:
    text = extract_order_content(order)
    _index_document(
        source_type=SOURCE_ORDER_CONTENT,
        order_id=order.id,
        title=order.title,
        text=text,
        stats=stats,
    )


def _index_order_history(order, stats: dict) -> None:
    history = (
        OrderHistory.query.filter_by(order_id=order.id)
        .order_by(OrderHistory.created_at.asc())
        .all()
    )
    text = extract_order_history(history, order.result)
    _index_document(
        source_type=SOURCE_ORDER_HISTORY,
        order_id=order.id,
        title=f'История: {order.title}' if order.title else None,
        text=text,
        stats=stats,
    )


def _index_order_files(order, stats: dict, only_file_id: int | None = None) -> None:
    files_query = OrderFile.query.filter_by(order_id=order.id)
    if only_file_id is not None:
        files_query = files_query.filter_by(id=only_file_id)
    for order_file in files_query.all():
        text = extract_file_text(order_file)
        _index_document(
            source_type=SOURCE_ORDER_FILE,
            order_id=order.id,
            title=order_file.original_name,
            text=text,
            order_file_id=order_file.id,
            stats=stats,
        )


def reindex_order(order_id: str) -> dict:
    """Reindex all sources for one order (content, history and attached files)."""
    stats = _empty_stats()
    if not _rag_supported():
        logger.info('RAG not supported; skipping reindex_order(%s)', order_id)
        return stats
    order = db.session.get(Order, order_id)
    if not order:
        logger.warning('Order %s not found, nothing to index', order_id)
        return stats
    try:
        _index_order_content(order, stats)
        _index_order_history(order, stats)
        _index_order_files(order, stats)
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception('Database error while indexing order %s', order_id)
        stats['errors'] += 1
    return stats


def reindex_file(order_file_id: int) -> dict:
    """Reindex a single attached file."""
    stats = _empty_stats()
    if not _rag_supported():
        return stats
    order_file = db.session.get(OrderFile, order_file_id)
    if not order_file:
        logger.warning('OrderFile %s not found', order_file_id)
        return stats
    order = db.session.get(Order, order_file.order_id)
    if not order:
        logger.warning('Order %s for file %s not found', order_file.order_id, order_file_id)
        return stats
    try:
        _index_order_files(order, stats, only_file_id=order_file_id)
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception('Database error while indexing file %s', order_file_id)
        stats['errors'] += 1
    return stats


def reindex_all() -> dict:
    """Reindex every order in the system. Intended for cold start / manual runs."""
    stats = _empty_stats()
    if not _rag_supported():
        logger.info('RAG not supported; skipping reindex_all()')
        return stats
    orders = Order.query.all()
    for order in orders:
        chunk_stats = reindex_order(order.id)
        for key, value in chunk_stats.items():
            stats[key] += value
    return stats


def _run_in_background(fn, *args, **kwargs) -> None:
    """Run a reindex callable in a daemon thread under a fresh app context."""

    def runner():
        with app.app_context():
            try:
                result = fn(*args, **kwargs)
                if isinstance(result, dict) and result.get('errors'):
                    logger.warning('Background %s finished with errors: %s', fn.__name__, result)
            except Exception:  # pragma: no cover - defensive
                logger.exception('Background reindex failed: %s', fn.__name__)

    threading.Thread(target=runner, daemon=True).start()


def schedule_reindex_order(order_id: str) -> None:
    """Fire-and-forget reindex; safe to call from request handlers."""
    if not _rag_supported():
        return
    _run_in_background(reindex_order, order_id)


def schedule_reindex_file(order_file_id: int) -> None:
    if not _rag_supported():
        return
    _run_in_background(reindex_file, order_file_id)
