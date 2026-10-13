import os, json, time, re
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from fastapi.responses import Response

load_dotenv()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("OPENAI_API_KEY")
)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content="", media_type="image/x-icon")

CONV: Dict[str, List[Dict[str, Any]]] = {} 
REQUEST_TIMESTAMPS: Dict[str, List[float]] = {}
RATE_LIMIT_WINDOW = 60
MAX_REQUESTS_IN_WINDOW = 15
MAX_HISTORY_MESSAGES = 10

SYSTEM_PROMPT = (
    "You are a helpful, safe customer service assistant for Slumber Inn. "
    "Your responses must strictly align with the Slumber Inn Knowledge Base.\n\n"

    "CRITICAL POLICIES TO ENFORCE:\n"
    "1. PAYMENT POLICY: Cash and prepaid cards are NEVER accepted for room bookings, "
    "deposits, or incidentals. Guests MUST provide a valid major credit card (Visa, "
    "Mastercard, AMEX, Discover) or digital wallet (Apple Pay, Google Pay) matching "
    "their photo ID at check-in.\n"
    "2. LATE CHECK-OUT & SPECIAL REQUESTS: Direct guests to contact the front desk "
    "directly or email frontdesk@slumberinn.com.\n\n"

    "GENERAL GUIDELINES:\n"
    "- If information is not provided in your knowledge base or if a query is out of "
    "scope/unsafe, state your limitations briefly and politely direct the guest to contact "
    "the front desk."
)
# ---------- HELPER FUNCTIONS ----------

def redact_secrets(text: str) -> str:
    text = re.sub(r'sk-[a-zA-Z0-9-_]{20,}', '[REDACTED_API_KEY]', text)
    text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[REDACTED_CC]', text)
    return text

def check_safety_policy(message: str) -> bool:
    unsafe_keywords = ["hack", "exploit", "malware", "bomb", "suicide"]
    lower_msg = message.lower()
    return not any(word in lower_msg for word in unsafe_keywords)

def enforce_rate_limit(conversation_id: str):
    now = time.time()
    timestamps = REQUEST_TIMESTAMPS.setdefault(conversation_id, [])
    timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    if len(timestamps) >= MAX_REQUESTS_IN_WINDOW:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait before sending more messages.")
    timestamps.append(now)
    REQUEST_TIMESTAMPS[conversation_id] = timestamps

def get_trimmed_convo(conversation_id: str) -> List[Dict[str, Any]]:
    full_convo = CONV[conversation_id]
    if not full_convo:
        return []
    system_prompt = full_convo[0]
    history = full_convo[1:]
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]
    return [system_prompt] + history

def log_metrics(metrics_record: Dict[str, Any]):
    os.makedirs("results", exist_ok=True)
    metrics_file = "results/metrics.json"
    existing_metrics = []
    if os.path.exists(metrics_file):
        try:
            with open(metrics_file, "r", encoding="utf-8") as f:
                existing_metrics = json.load(f)
        except json.JSONDecodeError:
            existing_metrics = []
    
    existing_metrics.append(metrics_record)
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(existing_metrics, f, indent=2)

# ---------- TOOL DEFINITIONS ----------

def check_room_availability(room_type: str, check_in: str, check_out: str) -> Dict[str, Any]:
    inventory = {
        "king suite": {"available": True, "nightly_rate_usd": 189, "max_guests": 2},
        "double queen": {"available": True, "nightly_rate_usd": 149, "max_guests": 4},
        "penthouse": {"available": False, "nightly_rate_usd": 450, "max_guests": 4}
    }
    key = room_type.lower()
    if key in inventory:
        return {"room_type": room_type, "check_in": check_in, "check_out": check_out, **inventory[key]}
    return {"error": "Room type not found"}

def lookup_kb(query: str) -> Dict[str, Any]:
    """Searches the local kb.md file for relevant hotel information."""
    kb_path = Path("kb.md")
    if not kb_path.exists():
        return {"results": {"note": "Knowledge base file not found"}}
    
    content = kb_path.read_text(encoding="utf-8")
    sections = content.split("## ")
    hits = {}
    
    for section in sections:
        if not section.strip():
            continue
        lines = section.strip().split("\n")
        heading = lines[0].lower()
        body = "\n".join(lines[1:])
        
        if query.lower() in heading or query.lower() in body.lower():
            hits[lines[0]] = body.strip()
            
    return {"results": hits or {"note": "no match"}}

TOOLS = {
    "check_room_availability": {
        "fn": check_room_availability, 
        "schema": {
            "type": "object", 
            "properties": {
                "room_type": {"type": "string"}, 
                "check_in": {"type": "string"}, 
                "check_out": {"type": "string"}
            }, 
            "required": ["room_type", "check_in", "check_out"]
        }
    },
    "lookup_kb": {
        "fn": lookup_kb, 
        "schema": {
            "type": "object", 
            "properties": {
                "query": {"type": "string"}
            }, 
            "required": ["query"]
        }
    },
}

# ---------- FASTAPI ROUTES ----------

class ChatIn(BaseModel):
    conversation_id: str
    user_message: str

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>index.html not found in workspace directory.</h3>"

@app.post("/chat")
async def chat(inp: ChatIn):
    conversation_id = inp.conversation_id
    raw_message = inp.user_message

    enforce_rate_limit(conversation_id)
    if not check_safety_policy(raw_message):
        return StreamingResponse(iter(["I am sorry, but I cannot fulfill this request due to safety policies."]), media_type="text/plain")

    clean_message = redact_secrets(raw_message)

    if conversation_id not in CONV:
        CONV[conversation_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    CONV[conversation_id].append({"role": "user", "content": clean_message})

    def _stream():
        start = time.time()
        tool_calls_made = []
        full_reply = ""
        try:
            tool_specs = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Search the local hotel knowledge base (kb.md) for policies, pet rules, parking fees, Wi-Fi, pool hours, and amenities." if name == "lookup_kb" else f"Check live inventory and rates for Slumber Inn rooms.",
            "parameters": spec["schema"]
        }
    } 
    for name, spec in TOOLS.items()
]
            
            current_messages = get_trimmed_convo(conversation_id)

            response = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "openai/gpt-oss-20b"),
                messages=current_messages,
                tools=tool_specs,
                tool_choice="auto",
                temperature=0.4,
                stream=True
            )

            tool_calls_buffer = []
            
            for chunk in response:
                delta = chunk.choices[0].delta
                
                content = getattr(delta, "content", None)
                if not content and hasattr(chunk.choices[0], "text"):
                    content = chunk.choices[0].text

                if content:
                    full_reply += content
                    yield content

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        if len(tool_calls_buffer) <= tc_delta.index:
                            tool_calls_buffer.append({"id": "", "name": "", "arguments": ""})
                        if tc_delta.id:
                            tool_calls_buffer[tc_delta.index]["id"] += tc_delta.id
                        if tc_delta.function.name:
                            tool_calls_buffer[tc_delta.index]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_buffer[tc_delta.index]["arguments"] += tc_delta.function.arguments

            if tool_calls_buffer:
                for tc in tool_calls_buffer:
                    func_name = tc["name"]
                    func_args = json.loads(tc["arguments"])
                    tool_calls_made.append(func_name)

                    if func_name in TOOLS:
                        tool_result = TOOLS[func_name]["fn"](**func_args)
                        
                        CONV[conversation_id].append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": func_name, "arguments": tc["arguments"]}
                            }]
                        })
                        CONV[conversation_id].append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(tool_result)
                        })

                        follow_up = client.chat.completions.create(
                            model=os.environ.get("OPENAI_MODEL", "openai/gpt-oss-20b"),
                            messages=get_trimmed_convo(conversation_id),
                            temperature=0.4,
                            stream=True
                        )

                        for f_chunk in follow_up:
                            f_delta = f_chunk.choices[0].delta
                            f_content = getattr(f_delta, "content", None)
                            if not f_content and hasattr(f_chunk.choices[0], "text"):
                                f_content = f_chunk.choices[0].text

                            if f_content:
                                full_reply += f_content
                                yield f_content

            CONV[conversation_id].append({"role": "assistant", "content": full_reply})
        except Exception as e:
            yield f"\n[Backend Error: {str(e)}]"

        end = time.time()
        latency_ms = int((end - start) * 1000)
        prompt_tokens = sum(len(str(m.get("content", "")).split()) * 1.3 for m in CONV[conversation_id] if m.get("content"))
        completion_tokens = len(full_reply.split()) * 1.3
        estimated_cost = ((prompt_tokens / 1000000) * 0.075) + ((completion_tokens / 1000000) * 0.30)

        metrics_record = {
            "conversation_id": conversation_id,
            "latency_ms": latency_ms,
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "estimated_cost_usd": round(estimated_cost, 6),
            "tool_calls": tool_calls_made
        }

        log_metrics(metrics_record)

    return StreamingResponse(_stream(), media_type="text/plain")