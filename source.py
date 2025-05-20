# Final version of agentic AI system with:
# - Shared conversational memory
# - LangGraph multi-agent workflow
# - External context via MCP (public API)
# - Automatic reprocessing if validator flags insufficient context
# - Citation source tracing

from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langgraph.graph import StateGraph, ParallelFor, END
import redis
import uuid
import json
import logging
import requests
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI()
rdb = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

class QueryRequest(BaseModel):
    query: str
    paper_url: str = None
    session_id: str = None

@app.get("/mcp_context/{session_id}")
def get_mcp_context(session_id: str):
    # Deprecated placeholder endpoint
    return JSONResponse({"message": "This endpoint is no longer used. MCP context is fetched directly in node_validate."})

class RetrieverAgent:
    def __init__(self, llm, memory):
        self.prompt = PromptTemplate(
            input_variables=["subquestion", "chat_history"],
            template="Here is the prior conversation context:\n{chat_history}\n\nNow answer the following sub-question in 2 sentences:\n{subquestion}"
        )
        self.llm = llm
        self.memory = memory

    def run(self, subquestion):
        chat_history = "\n".join([f"User: {m.content}" if m.type == 'human' else f"AI: {m.content}" for m in self.memory.chat_memory.messages])
        result = self.llm.invoke(self.prompt.format(subquestion=subquestion, chat_history=chat_history)).content.strip()
        self.memory.chat_memory.add_user_message(subquestion)
        self.memory.chat_memory.add_ai_message(result)
        logger.info(f"RetrieverAgent response for '{subquestion}': {result}")
        return result

class SynthesizerAgent:
    def __init__(self, llm, memory):
        self.prompt = PromptTemplate(
            input_variables=["responses", "chat_history"],
            template="Here is the prior conversation:\n{chat_history}\n\nGiven these pieces of information:\n{responses}\n\nSummarize the key insight in 3 sentences."
        )
        self.llm = llm
        self.memory = memory

    def run(self, responses):
        chat_history = "\n".join([f"User: {m.content}" if m.type == 'human' else f"AI: {m.content}" for m in self.memory.chat_memory.messages])
        return self.llm.invoke(self.prompt.format(responses=responses, chat_history=chat_history)).content.strip()

class ValidatorAgent:
    def __init__(self, llm):
        self.prompt = PromptTemplate(
            input_variables=["summary", "query"],
            template="Does this summary properly answer the question?\n\nQuestion: {query}\n\nSummary: {summary}\n\nAnswer yes or no and explain briefly."
        )
        self.llm = llm

    def run(self, query, summary):
        return self.llm.invoke(self.prompt.format(query=query, summary=summary)).content.strip()

class ExplainerAgent:
    def __init__(self, llm, memory):
        self.prompt = PromptTemplate(
            input_variables=["summary", "chat_history"],
            template="Here is the chat history:\n{chat_history}\n\nExplain this summary in more detail for a technical audience:\n{summary}"
        )
        self.llm = llm
        self.memory = memory

    def run(self, summary):
        chat_history = "\n".join([f"User: {m.content}" if m.type == 'human' else f"AI: {m.content}" for m in self.memory.chat_memory.messages])
        return self.llm.invoke(self.prompt.format(summary=summary, chat_history=chat_history)).content.strip()

@app.post("/query")
def handle_query(req: QueryRequest, background_tasks: BackgroundTasks):
    session_id = req.session_id or str(uuid.uuid4())
    rdb.set(f"status:{session_id}", "processing")

    memory = ConversationBufferMemory(return_messages=True)
    decomposer = lambda state: {"subquestions": [f"Sub-question 1 from: {state['query']}"]}  # Simplified example
    retriever = RetrieverAgent(ChatOpenAI(temperature=0.0), memory)
    synthesizer = SynthesizerAgent(ChatOpenAI(temperature=0.7), memory)
    validator = ValidatorAgent(ChatOpenAI(temperature=0.2))
    explainer = ExplainerAgent(ChatOpenAI(temperature=0.6), memory)

    def node_decompose(state):
        return decomposer(state)

    def retrieve_one(state):
        subq = state["subquestion"]
        return {"response": f"Q: {subq}\nA: {retriever.run(subq)}"}

    def node_summarize(state):
        summary = synthesizer.run("\n\n".join(state["responses"]))
        cited_chunk = state.get("api_context") or state.get("doc_context") or "[No citation available]"
        cited_chunk = cited_chunk[:300] + "..." if cited_chunk else "[No citation]"
        state["citation"] = cited_chunk
        return {"final": summary, "citation": cited_chunk}

    def node_validate(state):
        verdict = validator.run(state["query"], state["final"])
        if "need more context" in verdict.lower():
            try:
                logger.info("Validator indicates context is insufficient. Fetching from public MCP server...")
                response = requests.get("https://mcpdemo.fly.dev/api/context/pubmed", params={"q": state["query"]})
                if response.status_code == 200:
                    external_context = response.text
                    rdb.set(f"context:api:{state.get('session_id', 'unknown')}", external_context)
                    enhanced_responses = [
                        f"Q: {q}\nA: {RetrieverAgent(ChatOpenAI(temperature=0.0), memory).run(q)}"
                        for q in state["subquestions"]
                    ]
                    summary = SynthesizerAgent(ChatOpenAI(temperature=0.7), memory).run("\n\n".join(enhanced_responses))
                    verdict = validator.run(state["query"], summary)
                    state["final"] = summary
                    state["responses"] = enhanced_responses
            except Exception as e:
                logger.warning(f"Failed to enrich with external API context: {e}")
        return {"verdict": verdict}

    def node_explain(state):
        return {"explanation": explainer.run(state["final"])}

    builder = StateGraph()
    builder.add_node("decompose", node_decompose)
    builder.add_node("synthesize", node_summarize)
    builder.add_node("validate", node_validate)
    builder.add_node("explain", node_explain)

    parallel = ParallelFor("subquestions")
    parallel.add_node("retrieve_one", retrieve_one)
    parallel.set_entry_point("retrieve_one")
    parallel.add_edge("retrieve_one", END)
    builder.add_node("retrieve", parallel)

    builder.set_entry_point("decompose")
    builder.add_edge("decompose", "retrieve")
    builder.add_edge("retrieve", "synthesize")
    builder.add_edge("synthesize", "validate")
    builder.add_edge("validate", "explain")
    builder.add_edge("explain", END)

    graph = builder.compile()

    def process_query():
        initial_state = {"query": req.query, "session_id": session_id, "doc_context": req.paper_url}
        result = graph.invoke(initial_state)
        memory_json = json.dumps(memory.load_memory_variables({}))
        rdb.set(f"result:{session_id}", json.dumps({
            "state_transitions": result,
            "output": result,
            "memory": memory_json
        }))
        rdb.set(f"status:{session_id}", "complete")

    background_tasks.add_task(process_query)
    return {"message": "Processing started.", "session_id": session_id, "status_url": f"/session/{session_id}/status"}

@app.get("/session/{session_id}/status")
def get_result(session_id: str):
    status = rdb.get(f"status:{session_id}")
    if not status:
        return {"error": "Session not found"}
    if status == "processing":
        return {"status": "processing"}
    result = rdb.get(f"result:{session_id}")
    full_data = json.loads(result)
    return {
        "status": "complete",
        "result": full_data.get("output", {}),
        "memory_trace": full_data.get("memory", {}),
        "citation": full_data.get("output", {}).get("citation", "")
    }
