# 🧠 Agentic AI for Medical-Patent Legal Assistance

This project implements a powerful, extensible GenAI system for assisting medical lawyers in analyzing research documents and preparing patent filings. It uses LangGraph to orchestrate agents with shared memory and integrates Model Context Protocol (MCP) to bring in external knowledge when internal context is insufficient.

---

## ✅ Key Features

* 📄 Accepts user queries and optional document links (e.g., medical trials or patent data)
* 🤖 Decomposes complex questions into sub-questions
* 🔍 Retrieves and answers using document and chat context
* 🧠 Summarizes key insights
* 📉 Validates responses; auto-enriches via public MCP server if needed
* 📎 Provides citations from document or external data
* 💬 Maintains full conversational memory per session

---

## 🚀 How It Works

### 🧩 Agent Workflow

1. **Decompose**: Breaks the question into 2–3 manageable sub-questions
2. **Retrieve** (Parallel): Answers each sub-question using document/chat context
3. **Synthesize**: Summarizes all sub-answers into a coherent response
4. **Validate**: Assesses if the summary is sufficient
5. **Enrich** (if needed): Calls MCP API (PubMed) to fetch more context and reruns
6. **Explain**: Expands the final result in technical detail

### 🧠 Context Layers

* **Document Context**: Uploaded as a URL in `paper_url`
* **API Context (MCP)**: Fetched from `https://mcpdemo.fly.dev/api/context/pubmed` using query terms
* **Chat Memory**: Maintained using `ConversationBufferMemory`

### 🧠 Citation

The system captures and returns the relevant text chunk (from the doc or API) that supports the final answer.

---

## 📦 API Usage

### `POST /query`

**Input:**

```json
{
  "query": "Does this document show effectiveness against Disease X?",
  "paper_url": "<document text or link>"
}
```

**Response:**

```json
{
  "message": "Processing started.",
  "session_id": "abc123",
  "status_url": "/session/abc123/status"
}
```

### `GET /session/{session_id}/status`

**Returns final result with trace:**

```json
{
  "status": "complete",
  "result": {
    "final": "...",
    "verdict": "...",
    "explanation": "..."
  },
  "memory_trace": { "history": [...] },
  "citation": "...excerpt from doc/API..."
}
```

---

## 🧱 System Architecture

* **FastAPI** – API Gateway & background tasks
* **LangGraph** – Agent workflow with state management
* **LangChain** – Memory and LLM chains
* **Redis** – Session tracking and memory persistence
* **Public MCP Server** – `https://mcpdemo.fly.dev/api/context/pubmed`

---

## 🎯 Use Case: Medical-Patent Filing

* Upload trial data or journal references
* Ask domain-specific legal/clinical questions
* Get accurate answers, summaries, and source citations
* System fills context gaps by auto-calling PubMed via MCP

---

## 🛠 Setup

1. Install dependencies
2. Start Redis (`redis-server`)
3. Run FastAPI app:

```bash
uvicorn agentic_ai_final:app --reload
```

---

## 🧪 Example Test

```json
POST /query
{
  "query": "Is there evidence in this paper that Drug A is effective against Disease B?",
  "paper_url": "This document discusses results of a double-blind trial..."
}
```

---

## 🧠 STAR Summary (Interview)

* **S**: Legal teams filing patents often need AI to interpret documents
* **T**: Build an agentic assistant that answers questions using private and public knowledge
* **A**: Used LangGraph + LangChain + Redis + MCP public APIs
* **R**: Created a reusable, context-aware system with fallback enrichment and traceable citations
