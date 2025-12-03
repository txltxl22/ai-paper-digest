You are an expert research assistant specializing in Artificial Intelligence (AI). Your task is to generate topic tags for the following paper SUMMARY (not the original paper).

Requirements:
- Produce two levels of tags:
  1) top: choose 1-3 broad categories like items in : ["biology", "medical", "llm", "natural language processing", "computer vision", "reinforcement learning", "agents", "systems", "theory", "robotics", "audio", "multi-modal", "model training", "model evaluation", "machine learning", "video generation", "aigc", "data", "video", "benchmark", "behavior", "general", "financial", "text-to-video", "object completion", "multi-agents"]
  2) tags: generate 1-5 concise, specific topics (1-3 words), lowercase, no duplicates
- Output MUST be pure JSON with keys: {{"top": [...], "tags": [...]}} and nothing else.

Output example:
```json
{{
  "top": [
    "llm",
    "agents"
  ],
  "tags": [
    "benchmark",
    "tool usage",
    "evaluation"
  ]
}}
```

**重要：确保返回的是有效的JSON格式，所有字符串用双引号包围。**

Summary:
{summary_content}
