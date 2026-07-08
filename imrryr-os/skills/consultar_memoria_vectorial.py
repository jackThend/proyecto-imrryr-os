#!/usr/bin/env python3
"""
consultar_memoria_vectorial.py — Skill: Consulta la Memoria Vectorial (ChromaDB)
=================================================================================
Usada por el Agente Comercial (CRM) y cualquier otro agente que necesite
recuperar contexto de proyectos/documentos previos ingeridos con
scripts/ingest_docs.py.

Uso:
    python skills/consultar_memoria_vectorial.py --query "cotización museografía" --n 3
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT / "vault" / "chroma"
COLLECTION_NAME = "imrryr-knowledge"


def log(msg: str) -> None:
    print(f"[consultar_memoria_vectorial] {msg}", flush=True)


def consultar(query: str, n_resultados: int = 5) -> list[dict]:
    import chromadb
    from chromadb.config import Settings

    if not CHROMA_DIR.exists():
        log(f"ERROR: No existe {CHROMA_DIR}. Ejecuta primero: python scripts/ingest_docs.py")
        return []

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        log(f"ERROR: La colección '{COLLECTION_NAME}' no existe todavía. Ejecuta: python scripts/ingest_docs.py")
        return []

    if collection.count() == 0:
        log("La colección está vacía. Ejecuta: python scripts/ingest_docs.py")
        return []

    resultados = collection.query(query_texts=[query], n_results=min(n_resultados, collection.count()))

    fragmentos = []
    documentos = resultados.get("documents", [[]])[0]
    metadatas = resultados.get("metadatas", [[]])[0]
    distancias = resultados.get("distances", [[]])[0]
    for doc, meta, dist in zip(documentos, metadatas, distancias):
        fragmentos.append({
            "texto": doc,
            "fuente": meta.get("source", ""),
            "archivo": meta.get("file", ""),
            "relevancia": round(1 - dist, 4) if dist is not None else None,
        })
    return fragmentos


def consultar_memoria_vectorial(query: str, n: int = 5) -> list[dict]:
    """Punto de entrada MCP (nombre = nombre de la skill, ver mcp_server/skills_server.py)."""
    return consultar(query, n)


def main() -> int:
    ap = argparse.ArgumentParser(description="Consulta la memoria vectorial (ChromaDB)")
    ap.add_argument("--query", type=str, required=True)
    ap.add_argument("--n", type=int, default=5, help="Cantidad de fragmentos a devolver")
    args = ap.parse_args()

    fragmentos = consultar(args.query, args.n)
    log(f"Fragmentos encontrados: {len(fragmentos)}")
    print(json.dumps(fragmentos, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
