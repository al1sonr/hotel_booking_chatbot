hotel-booking-chatbot/
├── app.py                  # FastAPI backend containing endpoints, memory, and tools
├── kb.md                   # Local knowledge base for hotel policies and FAQs
├── prompts.json            # 20-prompt evaluation suite categorized by test type
├── run_evaluation.py       # Evaluation script for automated metric collection
├── requirements.txt        # Python dependencies
├── README.md               # Project documentation and setup instructions
├── results/                
│   ├── metrics.json        # Raw execution telemetry and token usage
│   └── evaluation_summary.json # Aggregated test results and success rates
└── tests/
    └── test_app.py         # Pytest suite covering tool execution and endpoints