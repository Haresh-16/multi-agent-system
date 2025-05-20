# 🧠 Agentic AI with Conversational Memory (LangGraph + FastAPI + Redis)

This project implements a production-grade, multi-agent GenAI backend using LangGraph, LangChain, Redis, and FastAPI.

## ✅ What It Does

* Accepts a complex technical query
* Decomposes the query into sub-questions
* Uses LLM-powered agents to retrieve, summarize, validate, and explain answers
* Maintains session-based memory for multi-turn reasoning
* Supports polling, real-time streaming, and full traceability of the agent workflow

---

## ⚙️ Tech Stack

* **FastAPI** – REST + WebSocket API
* **LangGraph** – Agent orchestration with DAG + parallelism
* **LangChain** – Agent abstraction and LLM prompting
* **Redis** – Persistent state and memory store
* **ChatOpenAI** – LLM backend (configurable via LangChain)

---

## 🧩 Modular Agent Pipeline

### 1. **DecomposerAgent**

* Input: user query
* Output: 2–3 sub-questions
* Purpose: breaks complex problems into manageable units

### 2. **RetrieverAgent** (parallel)

* Input: each sub-question
* Output: short, accurate response
* Uses: ConversationBufferMemory for context

### 3. **SynthesizerAgent**

* Input: list of responses
* Output: final 3-sentence summary

### 4. **ValidatorAgent**

* Input: original query + final summary
* Output: validation verdict (Yes/No + reason)

### 5. **ExplainerAgent**

* Input: final summary
* Output: expanded explanation in technical terms

---

## 🧠 Memory

* Each session has a dedicated `ConversationBufferMemory`
* Captures sub-question and response history
* Serialized and saved in Redis under `result:{session_id}`
* Returned in `memory_trace` from the `/status` endpoint

---

## 🔌 API Endpoints

### `POST /query`

Start query processing.
Returns: `{ session_id, status_url }`

### `GET /session/{session_id}/status`

Poll for completion.
Returns:

```json
{
  "status": "complete",
  "result": {
    "final": "...",
    "verdict": "...",
    "explanation": "..."
  },
  "memory_trace": { "history": [...] }
}
```

### `GET /session/{session_id}/stream`

(Experimental) HTTP streaming of final summary sentence-by-sentence.

### `WebSocket /ws/{session_id}`

Real-time summary stream using persistent WebSocket.

---

## 🚀 How to Run

1. Install requirements
2. Start Redis (`redis-server`)
3. Run FastAPI (`uvicorn agentic_ai_with_memory:app --reload`)
4. Test endpoints with Postman, curl, or your frontend

---

## 🗂️ Use Cases

* Multi-turn technical Q\&A assistant
* GenAI-powered customer support backend
* Research copilots with memory and explanation

---

## 🎯 STAR Interview Summary

* **S**: Complex technical queries need intelligent breakdown and coherent reasoning.
* **T**: Build a GenAI backend that decomposes, answers, summarizes, validates, and explains.
* **A**: Used LangGraph, LangChain, FastAPI, Redis, and OpenAI to orchestrate agents with memory.
* **R**: Delivered a scalable system with full traceability, modular agents, session memory, and streaming.
