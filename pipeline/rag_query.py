"""Query helpers for the EDGAR RAG pipeline.

Provides search and question-answering against the Milvus collection
populated by edgar_rag_pipeline.py. Supports filtered retrieval by
ticker, filing type, and category.

Usage (in a notebook or script):
    from rag_query import EdgarRAG

    rag = EdgarRAG()
    results = rag.search("What are Apple's material contracts?", ticker="AAPL")
    answer = rag.ask("What are Apple's material contracts?", ticker="AAPL")
"""

import logging
import os
from typing import List, Optional

logger = logging.getLogger("edgar-rag-query")

MILVUS_HOST = os.environ.get("MILVUS_HOST", "milvus-milvus.milvus.svc.cluster.local")
MILVUS_PORT = int(os.environ.get("MILVUS_PORT", "19530"))
MILVUS_DB = os.environ.get("MILVUS_DB", "default")
COLLECTION_NAME = os.environ.get("MILVUS_COLLECTION", "edgar_filings")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


class EdgarRAG:
    """Search and query the EDGAR filings vector store."""

    def __init__(
        self,
        milvus_host: str = MILVUS_HOST,
        milvus_port: int = MILVUS_PORT,
        collection_name: str = COLLECTION_NAME,
        embedding_model: str = EMBEDDING_MODEL,
    ):
        from pymilvus import MilvusClient
        from sentence_transformers import SentenceTransformer

        self.milvus = MilvusClient(
            uri=f"http://{milvus_host}:{milvus_port}", db_name=MILVUS_DB
        )
        self.collection = collection_name
        self.embed_model = SentenceTransformer(embedding_model)
        self.milvus.load_collection(collection_name)
        logger.info("EdgarRAG ready (collection=%s)", collection_name)

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        score_threshold: float = 0.3,
        ticker: Optional[str] = None,
        filing_type: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[dict]:
        """Embed query and search Milvus with optional metadata filters."""
        query_embedding = self.embed_model.encode(
            [query], normalize_embeddings=True
        ).tolist()

        # Build filter expression
        filters = []
        if ticker:
            filters.append(f'ticker == "{ticker.upper()}"')
        if filing_type:
            filters.append(f'filing_type == "{filing_type}"')
        if category:
            filters.append(f'category == "{category}"')
        filter_expr = " and ".join(filters) if filters else ""

        results = self.milvus.search(
            collection_name=self.collection,
            data=query_embedding,
            limit=top_k,
            output_fields=["source_file", "chunk_index", "text", "ticker",
                           "cik", "filing_type", "filing_date", "category"],
            search_params={"metric_type": "COSINE", "params": {"nprobe": 16}},
            filter=filter_expr if filter_expr else None,
        )

        chunks = []
        for hits in results:
            for hit in hits:
                if hit["distance"] >= score_threshold:
                    chunks.append({
                        "text": hit["entity"]["text"],
                        "source_file": hit["entity"]["source_file"],
                        "chunk_index": hit["entity"]["chunk_index"],
                        "ticker": hit["entity"]["ticker"],
                        "filing_type": hit["entity"]["filing_type"],
                        "filing_date": hit["entity"]["filing_date"],
                        "category": hit["entity"]["category"],
                        "score": hit["distance"],
                    })

        logger.info("Search returned %d results (filter: %s)", len(chunks), filter_expr or "none")
        return chunks

    def build_context(self, chunks: List[dict]) -> str:
        """Format retrieved chunks with numbered references for citation."""
        parts = []
        for i, c in enumerate(chunks, 1):
            header = (
                f"[{i}] {c['ticker']} — {c['filing_type']} "
                f"({c['filing_date']}) — {c['source_file']}, "
                f"chunk {c['chunk_index']}, score: {c['score']:.3f}"
            )
            parts.append(f"{header}\n{c['text']}")
        return "\n\n---\n\n".join(parts)

    def ask(
        self,
        question: str,
        *,
        llm_endpoint: Optional[str] = None,
        llm_model: Optional[str] = None,
        top_k: int = 10,
        ticker: Optional[str] = None,
        filing_type: Optional[str] = None,
        category: Optional[str] = None,
    ) -> dict:
        """Search for context and generate an answer using an LLM.

        Requires an OpenAI-compatible endpoint (e.g., OGX or vLLM on KServe).
        If llm_endpoint is not provided, returns just the retrieved context.
        """
        chunks = self.search(
            question, top_k=top_k, ticker=ticker,
            filing_type=filing_type, category=category,
        )
        context = self.build_context(chunks)

        result = {
            "question": question,
            "chunks": chunks,
            "context": context,
            "answer": None,
            "filters": {
                "ticker": ticker,
                "filing_type": filing_type,
                "category": category,
            },
        }

        if not llm_endpoint:
            return result

        from openai import OpenAI

        client = OpenAI(base_url=f"{llm_endpoint}/v1", api_key="unused")

        prompt = (
            "You are a counterparty due diligence analyst. Answer the question "
            "based ONLY on the SEC filing excerpts below.\n\n"
            "Rules:\n"
            "- Cite sources using [1], [2], etc. matching the document numbers.\n"
            "- Include the ticker and filing type in your citations.\n"
            "- If the answer is not in the provided context, say so.\n\n"
            f"## Filing Excerpts\n\n{context}\n\n"
            f"## Question\n\n{question}\n\n"
            "## Analysis\n\n"
        )

        response = client.chat.completions.create(
            model=llm_model or "default",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.1,
        )

        result["answer"] = response.choices[0].message.content
        return result

    def print_results(self, result: dict):
        """Pretty-print a query result."""
        sep = "=" * 60
        print(f"\nQuestion: {result['question']}")
        filters = result.get("filters", {})
        active = {k: v for k, v in filters.items() if v}
        if active:
            print(f"Filters: {active}")
        print(f"Chunks retrieved: {len(result['chunks'])}")

        if result["answer"]:
            print(f"\n{sep}\n  ANSWER\n{sep}\n")
            print(result["answer"])

        print(f"\n{sep}\n  SOURCES\n{sep}\n")
        for i, c in enumerate(result["chunks"], 1):
            print(f"  [{i}] {c['ticker']} {c['filing_type']} ({c['filing_date']}) "
                  f"— {c['source_file']} (score: {c['score']:.3f})")
