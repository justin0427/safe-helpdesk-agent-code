# Safe Helpdesk Agent Code

Minimal runnable LangChain IT Helpdesk Agent. It can search mock IT SOPs and create a mock ticket through model-selected tool calls.

The ticket system is in memory. It does not connect to Jira, ServiceNow, company accounts, notifications, or any other external IT system.

## Requirements

- Python 3.11+
- An OpenAI API key

## Run

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Set `OPENAI_API_KEY` and `MODEL_NAME` in `.env`, then run:

```bash
python -m app.main
```

Example input:

```text
VPN 連不上，從今天早上九點開始發生，請幫我開一張高優先級工單。
```

## Test

```bash
python -m unittest discover -s tests -v
```
