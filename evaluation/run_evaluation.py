import json
import os
import time
import requests

PROMPTS_FILE = "evaluation/prompts.json"
API_URL = "http://127.0.0.1:8000/chat"
RESULTS_FILE = "results/evaluation_summary.json"

def run_evaluation():
    if not os.path.exists(PROMPTS_FILE):
        print(f"Error: {PROMPTS_FILE} not found.")
        return

    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    results = []
    total_latency = 0
    total_tokens = 0
    total_cost = 0.0
    success_count = 0

    print(f"Starting evaluation run across {len(prompts)} test prompts...")

    for item in prompts:
        prompt_id = item["id"]
        category = item["category"]
        user_message = item["prompt"]
        conv_id = f"eval_conv_{prompt_id}"

        payload = {
            "conversation_id": conv_id,
            "user_message": user_message
        }

        start_time = time.time()
        try:
            response = requests.post(API_URL, json=payload, timeout=30)
            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                reply_text = response.text
                status = "success"
                success_count += 1
            elif response.status_code == 429:
                reply_text = "Rate limited"
                status = "rate_limited"
            else:
                reply_text = response.text
                status = f"error_{response.status_code}"

            metrics_path = "results/metrics.json"
            turn_tokens = 0
            turn_cost = 0.0
            if os.path.exists(metrics_path):
                with open(metrics_path, "r", encoding="utf-8") as mf:
                    metrics_data = json.load(mf)
                    if metrics_data:
                        latest = metrics_data[-1]
                        turn_tokens = latest.get("prompt_tokens", 0) + latest.get("completion_tokens", 0)
                        turn_cost = latest.get("estimated_cost_usd", 0.0)

            total_latency += latency_ms
            total_tokens += turn_tokens
            total_cost += turn_cost

            results.append({
                "id": prompt_id,
                "category": category,
                "status": status,
                "latency_ms": latency_ms,
                "tokens": turn_tokens,
                "cost_usd": turn_cost,
                "response_snippet": reply_text[:100]
            })
            print(f"[{prompt_id}/20] Category: {category} | Status: {status} | Latency: {latency_ms}ms")

        except Exception as e:
            print(f"[{prompt_id}/20] Failed with exception: {str(e)}")
            results.append({
                "id": prompt_id,
                "category": category,
                "status": "exception",
                "error": str(e)
            })

        time.sleep(0.5)

    summary = {
        "total_prompts": len(prompts),
        "task_success_rate": round((success_count / len(prompts)) * 100, 2),
        "avg_latency_ms": round(total_latency / len(prompts), 2),
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "details": results
    }

    os.makedirs("results", exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as sf:
        json.dump(summary, sf, indent=2)

    print("\nEvaluation complete! Summary saved to results/evaluation_summary.json")
    print(f"Task Success Rate: {summary['task_success_rate']}%")
    print(f"Average Latency: {summary['avg_latency_ms']} ms")

if __name__ == "__main__":
    run_evaluation()