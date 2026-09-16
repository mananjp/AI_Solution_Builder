# Feature Ticket: Semantic Retrieval & pgvector RAG Pipeline

**Ticket ID:** `FEAT-RAG-001`  
**Status:** Planned / Architecture Ready  
**Component:** Backend (`app/models/context.py`, `app/ingestion/`, `app/agents/`)  
**Priority:** Medium (Enhancement)  

---

## 1. Problem Statement & Background

Currently, documents uploaded by users (PDF, DOCX, CSV/Excel, OpenAPI specs, URL scrapes) are parsed into plain text and injected directly into LangGraph state (`raw_input` / `conversation_history`).

While the database schema already includes a dedicated `context_chunks` table with a `pgvector` column (`embedding Vector(384)`, migration `659ce2bb944d_initial_schema.py`), no code currently chunks documents or populates embeddings upon ingestion. Consequently:
- Large reference documents consume excessive context window tokens.
- Agents receive monolithic input text rather than semantically relevant excerpts matching the immediate phase (HLD, LLD, ER diagram, API specification).

---

## 2. Existing Assets & Architecture

### A. Database Model (`app/models/context.py`)
```python
class ContextChunk(Base):
    __tablename__ = "context_chunks"

    id: Mapped[uuid.UUID]
    org_id: Mapped[uuid.UUID]
    solution_id: Mapped[uuid.UUID | None]
    source_type: Mapped[str]  # "document", "url", "conversation"
    source_name: Mapped[str]
    chunk_index: Mapped[int]
    content: Mapped[str]
    detected_lang: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime]
```

### B. Configuration (`app/core/config.py`)
- `EMBEDDING_MODEL = "all-MiniLM-L6-v2"`
- `EMBEDDING_DIM = 384`

---

## 3. Implementation Plan

### Step 1: Chunking & Embedding Service (`app/services/embeddings.py`)
- Implement `RecursiveCharacterTextSplitter` with `chunk_size=500`, `chunk_overlap=50`.
- Use `sentence_transformers.SentenceTransformer(settings.EMBEDDING_MODEL)` to generate 384-dimensional dense vectors asynchronously.

### Step 2: Ingestion Pipeline Integration (`app/api/ingestion.py` / `app/ingestion/parser.py`)
- When a document is uploaded or URL scraped:
  1. Extract structured text using the universal parser (`PyMuPDF`, `python-docx`, `openpyxl`, `bs4`).
  2. Split extracted text into chunks.
  3. Batch-compute embeddings.
  4. Bulk insert `ContextChunk` records associated with `org_id` and `solution_id`.

### Step 3: Vector Similarity Query Function (`app/services/retrieval.py`)
- Use SQLAlchemy 2.0 + pgvector L2 distance or cosine distance:
  ```python
  stmt = (
      select(ContextChunk)
      .where(ContextChunk.solution_id == solution_id)
      .order_by(ContextChunk.embedding.cosine_distance(query_embedding))
      .limit(top_k)
  )
  ```

### Step 4: Multi-Agent RAG Node Integration (`app/agents/nodes/`)
- In `requirements_analyst` and `solutions_architect`:
  - Dynamically query `ContextChunk` for the top 3-5 relevant chunks based on the user's specific prompt or confirmed module names.
  - Prepend retrieved snippets as structured context:
    ```markdown
    ### Retrieved Context References:
    - [Source: PRD.pdf | Chunk 2]: "The booking system requires Stripe Webhook integration..."
    ```

---

## 4. Acceptance Criteria & Verification

1. **Embedding Generation**: Uploading a PDF or Markdown document creates corresponding records in `context_chunks` with non-null 384-dim `embedding` arrays.
2. **Semantic Search Accuracy**: Cosine distance queries return top-ranked chunks relevant to search terms (e.g. searching "database schema" ranks DDL and entity chunks highest).
3. **Tenant & Solution Isolation**: Queries strictly filter on `org_id` and `solution_id`.
4. **Performance**: Ingestion and embedding computation for a 20-page document completes in < 3 seconds using local ONNX or torch CPU inference.
