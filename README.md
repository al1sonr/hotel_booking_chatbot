Slumber Inn: Task-Oriented Hotel Booking Assistant

A production-grade conversational AI backend built with **FastAPI**, **Groq LLM integration**, **dynamic tool calling**, and **local retrieval-augmented generation (RAG)**.\
This application manages hotel room availability checks, nightly cost calculations, and policy lookups using a local file-based knowledge base\
\
Core Features\
\
* **Asynchronous FastAPI Backend:** Built with asynchronous route handlers and real-time streaming responses to minimize user latency.\
* **Dynamic Tool Calling:** Automatically executes Python functions to fetch live room availability and verify hotel policies.\
* **Local RAG Integration:** Queries a structured markdown knowledge base (`kb.md`) to deliver accurate, hallucination-free answers.\
* **Conversation Memory:** Maintains short-term conversational context across multi-turn interactions using server-side session stores.\
* **Automated Evaluation Suite:** Includes a 20-prompt test suite (`prompts.json`) and an evaluation script (`run_evaluation.py`) that logs performance metrics and token usage.\
\
hotel-booking-chatbot/
\
├── app.py                  # FastAPI backend containing endpoints, memory, and tools\
├── kb.md                   # Local knowledge base for hotel policies and FAQs\
├── prompts.json            # 20-prompt evaluation suite categorized by test type\
├── run_evaluation.py       # Evaluation script for automated metric collection\
├── requirements.txt        # Python dependencies\
├── README.md               # Project documentation and setup instructions\
├── results/                \
│   ├── metrics.json        # Raw execution telemetry and token usage\
│   └── evaluation_summary.json # Aggregated test results and success rates\
└── tests/\
    └── test_app.py         # Pytest suite covering tool execution and endpoints\
\

