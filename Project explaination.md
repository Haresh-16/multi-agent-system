

## 🔧 1. Agents in the System**

* I designed a system where **multiple agents collaborate**, each with a specific responsibility:

  * `DecomposerAgent`: breaks down complex questions
  * `RetrieverAgent`: answers using conversational + document context
  * `SynthesizerAgent`: consolidates sub-answers into a coherent summary
  * `ValidatorAgent`: checks whether the response fully answers the original question
  * `ExplainerAgent`: elaborates further if needed
* Agents are **composable**, **reason independently**, and operate on **shared state** — a key principle of agentic AI.

---

## 🔁 2. How LangGraph Was Used for Orchestration

> *“LangGraph let me define the multi-agent flow as a directed acyclic graph (DAG), with memory and state transitions preserved between nodes.”*

* Each agent is mapped to a **LangGraph node**, and I used:

  * `StateGraph` for sequential execution
  * `ParallelFor` for answering multiple sub-questions in parallel
* State is updated incrementally (e.g. adding `"subquestions"`, then `"responses"`, etc.)
* This enables agents to build on each other’s outputs **without tight coupling**

---

## 🌍 3. Context-Aware Reasoning via **MCP (Model Context Protocol)**

> *“When my validator detects missing context, the system enriches itself by calling a real MCP-compliant public API (PubMed).”*

* This mimics how human agents would pull external documents to support a claim
* Retrieved external context is cached in Redis and injected back into the state
* This improves answer quality in data-sparse scenarios, making the system **autonomous and adaptive**

---

## 🧱 4. Infrastructure & Deployment Readiness

> *“I designed the system to be fully stateless, horizontally scalable, and cloud-friendly.”*

* ✅ **FastAPI** serves the web API and manages background tasks
* ✅ **Redis** handles session state, memory, and intermediate agent results
* ✅ The agent pipeline is run asynchronously for responsiveness
* ✅ Full state (`state_transitions`) is logged per session, enabling:

  * Auditing
  * Resuming
  * Monitoring

### Deployment-ready design:

* Deployable on ECS, GKE, or serverless with no session stickiness
* Redis can be swapped with ElastiCache for production
* LangChain agents are stateless; workflows are restartable

---

## 🧠 5. Framework Knowledge

* **LangChain**: used for memory, prompt templating, LLM abstraction
* **LangGraph**: enables visual and programmable agent orchestration
* **FastAPI**: gives me full control over background processing and REST/WS endpoints
* **Redis**: fast, persistent state store for context and session memory

---




