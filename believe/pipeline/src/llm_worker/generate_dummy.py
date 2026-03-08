import json

long_text = "The quick brown fox jumps over the lazy dog. " * 1000 # ~45KB

with open("dummy_med.jsonl", "w") as f:
    for i in range(500):
        req = {
            "pmid": str(i),
            "request_params": {
                "model": "openai/gpt-oss-120b",
                "messages": [{"role": "user", "content": long_text}],
                "max_tokens": 10
            }
        }
        f.write(json.dumps(req) + "\n")
