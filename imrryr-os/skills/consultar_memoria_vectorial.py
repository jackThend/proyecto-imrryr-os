#!/usr/bin/env python3
"""
consultar_memoria_vectorial.py — Skill: Consulta RAG Híbrida (ChromaDB + SQLite FTS5 BM25)
=======================================================================================
Combina búsqueda semántica densa (ChromaDB) con búsqueda léxica exacta (SQLite FTS5 BM25)
mediante Reciprocal Rank Fusion (RRF):
    RRF_score(d) = sum(1.0 / (60 + rank))

Garantiza máxima precisión para nombres exactos, códigos y conceptos abstractos.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT / "vault" / "chroma"
DB_PATH = ROOT / "vault" / "sqlite" / "imrryr.db"
COLLECTION_NAME = "imrryr-knowledge"


def log(msg: str) -> None:
    print(f"[consultar_memoria_vectorial] {msg}", flush=True)


def _buscar_chroma(query: str, n_max: int) -> list[dict]:
    import chromadb
    from chromadb.config import Settings

    if not CHROMA_DIR.exists():
        return []

    try:
        client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        try:
            collection = client.get_collection(COLLECTION_NAME)
        except Exception:
            return []

        if collection.count() == 0:
            return []

        resultados = collection.query(query_texts=[query], n_results=min(n_max, collection.count()))
        docs = resultados.get("documents", [[]])[0]
        metas = resultados.get("metadatas", [[]])[0]
        dists = resultados.get("distances", [[]])[0]

        fragmentos = []
        for doc, meta, dist in zip(docs, metas, dists):
            fragmentos.append({
                "texto": doc,
                "fuente": meta.get("source", ""),
                "archivo": meta.get("file", ""),
                "relevancia_vectorial": round(1 - dist, 4) if dist is not None else None,
            })
        return fragmentos
    except Exception as e:
        log(f"Aviso ChromaDB: {e}")
        return []


def _buscar_fts(query: str, n_max: int) -> list[dict]:
    if not DB_PATH.exists():
        return []

    # Extraer términos alfanuméricos válidos
    terminos = re.findall(r"\w+", query)
    terminos = [t for t in terminos if len(t) > 1]
    if not terminos:
        return []

    fts_query = " OR ".join(f'"{t}"*' for t in terminos)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            """
            SELECT chunk_id, archivo, fuente, texto, rank
            FROM documentos_fts
            WHERE documentos_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, n_max),
        )
        filas = cur.fetchall()
        return [
            {
                "texto": f["texto"],
                "fuente": f["fuente"],
                "archivo": f["archivo"],
                "rank_bm25": f["rank"],
            }
            for f in filas
        ]
    except Exception as e:
        log(f"Aviso SQLite FTS5: {e}")
        return []
    finally:
        conn.close()


def consultar(query: str, n_resultados: int = 5) -> list[dict]:
    """Recuperación híbrida RRF combinando ChromaDB (vector) y SQLite FTS5 (BM25)."""
    k_rrf = 60
    candidatos_vector = _buscar_chroma(query, n_resultados * 2)
    candidatos_fts = _buscar_fts(query, n_resultados * 2)

    # Si ninguno tiene resultados, retornar lista vacía
    if not candidatos_vector and not candidatos_fts:
        return []

    rrf_scores: dict[str, float] = {}
    docs_map: dict[str, dict] = {}
    origen_map: dict[str, set[str]] = {}

    for rank, item in enumerate(candidatos_vector):
        key = f"{item['archivo']}:{item['texto'][:100]}"
        score = 1.0 / (k_rrf + rank)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + score
        docs_map[key] = item
        origen_map.setdefault(key, set()).add("vectorial")

    for rank, item in enumerate(candidatos_fts):
        key = f"{item['archivo']}:{item['texto'][:100]}"
        score = 1.0 / (k_rrf + rank)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + score
        if key not in docs_map:
            docs_map[key] = item
        origen_map.setdefault(key, set()).add("bm25")

    ordenados = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)

    resultado = []
    for key in ordenados[:n_resultados]:
        doc = docs_map[key]
        metodos = origen_map[key]
        if "vectorial" in metodos and "bm25" in metodos:
            tipo = "hibrido (vector+bm25)"
        elif "bm25" in metodos:
            tipo = "lexico (bm25)"
        else:
            tipo = "vectorial"

        resultado.append({
            "texto": doc["texto"],
            "fuente": doc["fuente"],
            "archivo": doc["archivo"],
            "relevancia": round(rrf_scores[key], 5),
            "tipo_recuperacion": tipo,
        })

    return resultado


def consultar_memoria_vectorial(query: str, n: int = 5) -> list[dict]:
    """Punto de entrada MCP (mantiene el nombre esperado por los agentes)."""
    return consultar(query, n)


def main() -> int:
    ap = argparse.ArgumentParser(description="Consulta híbrida (ChromaDB + SQLite FTS5)")
    ap.add_argument("--query", type=str, required=True)
    ap.add_argument("--n", type=int, default=5, help="Cantidad de fragmentos a devolver")
    args = ap.parse_args()

    fragmentos = consultar(args.query, args.n)
    log(f"Fragmentos encontrados: {len(fragmentos)}")
    print(json.dumps(fragmentos, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())