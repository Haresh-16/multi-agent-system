# agentic_ai_with_memory.py
# This file implements a FastAPI-based agentic AI system with shared conversational memory, session tracking, and multiple collaborating agents.

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langgraph.graph import StateGraph, ParallelFor, END
import redis
import uuid
import json
import logging
import time

# ---------------------------
# WebSocket Support
# ---------------------------
from fastapi import WebSocket, WebSocketDisconnect
# ---------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI()

# ---------------------------
# Redis Setup for Session Persistence
# ---------------------------
rdb = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

# ---------------------------
# Request Body Format
# ---------------------------
class QueryRequest(BaseModel):
    query: str
    session_id: str = None  # Optional session_id for tracking multi-turn sessions

# ---------------------------
# Additional Agents
# ---------------------------

# CritiqueAgent: Offers feedback on the summary's completeness and tone
class CritiqueAgent:
    def __init__(self, llm):
        self.prompt = PromptTemplate(
            input_variables=["summary"],
            template="Critique the following summary for completeness, tone, and potential improvements:

{summary}"
        )
        self.llm = llm

    def run(self, summary):
        try:
            result = self.llm.invoke(self.prompt.format(summary=summary)).content.strip()
            logger.info(f"CritiqueAgent output: {result}")
            return result
        except Exception as e:
            logger.error(f"CritiqueAgent error: {e}")
            return "[Error generating critique]"

# RankerAgent: Ranks sub-responses by relevance and quality
class RankerAgent:
    def __init__(self, llm):
        self.prompt = PromptTemplate(
            input_variables=["responses"],
            template="Rank the following answers in order of relevance and clarity:

{responses}"
        )
        self.llm = llm

    def run(self, responses):
        try:
            formatted = "

".join(responses)
            result = self.llm.invoke(self.prompt.format(responses=formatted)).content.strip()
            logger.info(f"RankerAgent output: {result}")
            return result
        except Exception as e:
            logger.error(f"RankerAgent error: {e}")
            return "[Error ranking responses]"
# ---------------------------

# DecomposerAgent: Splits a complex query into manageable sub-questions
class DecomposerAgent:
    def __init__(self, llm):
        self.prompt = PromptTemplate(
            input_variables=["query"],
            template="Break this question into 2-3 sub-questions:\n\n{query}"
        )
        self.llm = llm

    def run(self, query):
        for attempt in range(3):
            result = self.llm.invoke(self.prompt.format(query=query))
            subquestions = [line.strip() for line in result.content.strip().split("\n") if line.strip()]
            if subquestions:
                logger.info(f"DecomposerAgent output: {subquestions}")
                return subquestions
            time.sleep(1)
        return ["[Failed to decompose question]"]

# RetrieverAgent: Answers each sub-question with access to shared memory context
class RetrieverAgent:
    def __init__(self, llm, memory):
        self.prompt = PromptTemplate(
            input_variables=["subquestion"],
            template="Answer this question in 2 sentences using any previous context:\n\n{subquestion}"
        )
        self.llm = llm
        self.memory = memory

    def run(self, subquestion):
        for attempt in range(3):
            try:
                result = self.llm.invoke(self.prompt.format(subquestion=subquestion)).content.strip()
                if result and not result.lower().startswith("[error"):
                    self.memory.chat_memory.add_user_message(subquestion)
                    self.memory.chat_memory.add_ai_message(result)
                    logger.info(f"RetrieverAgent response for '{subquestion}': {result}")
                    return result
            except Exception as e:
                logger.error(f"RetrieverAgent error: {e}")
            time.sleep(1)
        return "[Error retrieving response]"

# SynthesizerAgent: Summarizes multiple sub-question answers into a cohesive final insight
class SynthesizerAgent:
    def __init__(self, llm):
        self.prompt = PromptTemplate(
            input_variables=["responses"],
            template="Given these pieces of information:\n\n{responses}\n\nSummarize the key insight in 3 sentences."
        )
        self.llm = llm

    def run(self, responses):
        for attempt in range(3):
            try:
                result = self.llm.invoke(self.prompt.format(responses=responses)).content.strip()
                if result and not result.lower().startswith("[error"):
                    logger.info(f"SynthesizerAgent output: {result}")
                    return result
            except Exception as e:
                logger.error(f"SynthesizerAgent error: {e}")
            time.sleep(1)
        return "[Error generating summary]"

# ValidatorAgent: Fact-checks or evaluates if the summary aligns with the original query
class ValidatorAgent:
    def __init__(self, llm):
        self.prompt = PromptTemplate(
            input_variables=["summary", "query"],
            template="Does this summary properly answer the question?\n\nQuestion: {query}\n\nSummary: {summary}\n\nAnswer yes or no and explain briefly."
        )
        self.llm = llm

    def run(self, query, summary):
        try:
            result = self.llm.invoke(self.prompt.format(query=query, summary=summary)).content.strip()
            logger.info(f"ValidatorAgent output: {result}")
            return result
        except Exception as e:
            logger.error(f"ValidatorAgent error: {e}")
            return "[Error validating summary]"

# ExplainerAgent: Adds elaboration to a completed summary when asked to "explain more"
class ExplainerAgent:
    def __init__(self, llm):
        self.prompt = PromptTemplate(
            input_variables=["summary"],
            template="Explain this summary in more detail for a technical audience:\n\n{summary}"
        )
        self.llm = llm

    def run(self, summary):
        try:
            result = self.llm.invoke(self.prompt.format(summary=summary)).content.strip()
            logger.info(f"ExplainerAgent output: {result}")
            return result
        except Exception as e:
            logger.error(f"ExplainerAgent error: {e}")
            return "[Error generating explanation]"

# ---------------------------
# API Endpoint: Handle New Query
# ---------------------------
@app.post("/query")
def handle_query(req: QueryRequest, background_tasks: BackgroundTasks):
    session_id = req.session_id or str(uuid.uuid4())
    rdb.set(f"status:{session_id}", "processing")

    memory = ConversationBufferMemory(return_messages=True)

    decomposer = DecomposerAgent(ChatOpenAI(temperature=0.5))
    retriever = RetrieverAgent(ChatOpenAI(temperature=0.0), memory)
    synthesizer = SynthesizerAgent(ChatOpenAI(temperature=0.7))
    validator = ValidatorAgent(ChatOpenAI(temperature=0.2))
    explainer = ExplainerAgent(ChatOpenAI(temperature=0.6))

    def node_decompose(state):
        subqs = decomposer.run(state["query"])
        return {"subquestions": subqs}

    def retrieve_one(state):
        subq = state["subquestion"]
        return {"response": f"Q: {subq}\nA: {retriever.run(subq)}"}

    def node_summarize(state):
        summary = synthesizer.run("\n\n".join(state["responses"]))
        return {"final": summary}

    def node_validate(state):
        verdict = validator.run(state["query"], state["final"])
        return {"verdict": verdict}

    def node_explain(state):
        expanded = explainer.run(state["final"])
        return {"explanation": expanded}

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
        result = graph.invoke({"query": req.query})
        memory_json = json.dumps(memory.load_memory_variables({}))
        rdb.set(f"result:{session_id}", json.dumps({"output": result, "memory": memory_json}))
        rdb.set(f"status:{session_id}", "complete")

    background_tasks.add_task(process_query)

    return {
        "message": "Processing started.",
        "session_id": session_id,
        "status_url": f"/session/{session_id}/status"
    }

# ---------------------------
# WebSocket Endpoint: Real-time Summary Streaming
# ---------------------------
@app.websocket("/ws/{session_id}")
async def websocket_summary(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            result = rdb.get(f"result:{session_id}")
            if not result:
                await websocket.send_text("[Waiting for result...]")
                await asyncio.sleep(1)
                continue

            full_data = json.loads(result)
            summary = full_data.get("output", {}).get("final", "[No summary available]")
            for sentence in summary.split(". "):
                await websocket.send_text(sentence.strip() + ".")
                await asyncio.sleep(0.3)
            await websocket.close()
            break
    except WebSocketDisconnect:
        logger.info(f"WebSocket {session_id} disconnected")
    except Exception as e:
        await websocket.send_text(f"[ERROR] {str(e)}")
        await websocket.close()

# ---------------------------
# API Endpoint: Polling Summary Result
