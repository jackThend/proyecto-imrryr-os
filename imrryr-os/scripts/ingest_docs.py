#!/usr/bin/env python3
"""
ingest_docs.py — Ingesta de documentos a la Memoria Vectorial (ChromaDB)
=======================================================================
Fase 2.2: Toma PDFs y documentos de texto de docs/vault/, los convierte
en vectores y los almacena en ChromaDB (100% local).

Uso:
    python scripts/ingest_docs.py                          # ingesta completa
    python scripts/ingest_docs.py --recreate                # recrea la colección
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
from pathlib import Path

import chromadb
from chromadb.config import Settings

ROOT = Path(__file__).resolve().parent.parent
VAULT_DIR = ROOT / "docs" / "vault"
CHROMA_DIR = ROOT / "vault" / "chroma"
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"
COLLECTION_NAME = "imrryr-knowledge"


def log(msg: str) -> None:
    print(f"[ingest] {msg}", flush=True)


def extract_text(filepath: Path) -> str:
    ext = filepath.suffix.lower()
    if ext == ".pdf":
        try:
            import fitz
            doc = fitz.open(str(filepath))
            return "\n".join(page.get_text() for page in doc)
        except ImportError:
            log("  WARN: pymupdf no instalado. Instala con: pip install pymupdf")
            return ""
    elif ext in (".txt", ".md", ".rst", ".csv"):
        return filepath.read_text(encoding="utf-8", errors="replace")
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingesta de documentos a ChromaDB")
    ap.add_argument("--recreate", action="store_true", help="Recrear la colección desde cero")
    args = ap.parse_args()

    if not VAULT_DIR.exists():
        log(f"Crea la carpeta {VAULT_DIR} y coloca allí tus PDFs/documentos.")
        VAULT_DIR.mkdir(parents=True, exist_ok=True)
        return 1

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    if args.recreate:
        try:
            client.delete_collection(COLLECTION_NAME)
            log("Colección recreada.")
        except Exception:
            pass
        if DB_PATH.exists():
            try:
                conn_fts = sqlite3.connect(str(DB_PATH))
                conn_fts.execute("DELETE FROM documentos_fts")
                conn_fts.commit()
                conn_fts.close()
            except Exception:
                pass

    collection = client.get_or_create_collection(COLLECTION_NAME)

    files = [f for f in VAULT_DIR.rglob("*") if f.suffix.lower() in (".pdf", ".txt", ".md", ".rst", ".csv")]
    if not files:
        log(f"No se encontraron documentos en {VAULT_DIR}")
        return 0

    ingested = 0
    for fpath in sorted(files):
        doc_id = hashlib.md5(str(fpath.relative_to(ROOT)).encode()).hexdigest()

        existing = collection.get(ids=[f"{doc_id}_0"])
        if existing and existing["ids"]:
            log(f"  SKIP {fpath.name} (ya indexado)")
            continue

        text = extract_text(fpath)
        if not text.strip():
            log(f"  SKIP {fpath.name} (vacío o no soportado)")
            continue

        # Chunking simple: dividir en párrafos de ~500 chars
        chunks = []
        current = ""
        for paragraph in text.split("\n\n"):
            if len(current) + len(paragraph) < 500:
                current += "\n\n" + paragraph if current else paragraph
            else:
                if current:
                    chunks.append(current.strip())
                current = paragraph
        if current:
            chunks.append(current.strip())

        if not chunks:
            continue

        chunk_ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": str(fpath.relative_to(ROOT)), "chunk": i, "file": fpath.name}
            for i in range(len(chunks))
        ]

        collection.add(
            documents=chunks,
            ids=chunk_ids,
            metadatas=metadatas,
        )

        # Ingesta en SQLite FTS5 para búsqueda léxica BM25 (RAG Híbrido)
        if DB_PATH.exists():
            try:
                conn_fts = sqlite3.connect(str(DB_PATH))
                for cid, chunk, meta in zip(chunk_ids, chunks, metadatas):
                    conn_fts.execute(
                        "INSERT INTO documentos_fts (chunk_id, archivo, fuente, texto) VALUES (?, ?, ?, ?)",
                        (cid, meta["file"], meta["source"], chunk),
                    )
                conn_fts.commit()
                conn_fts.close()
            except Exception as e:
                log(f"  WARN: error guardando en FTS5: {e}")

        ingested += 1
        log(f"  OK {fpath.name} ({len(chunks)} chunks)")

    total = collection.count()
    log(f"Ingesta completada: {ingested} archivos procesados. Total chunks: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
