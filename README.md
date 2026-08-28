# Safe Helpdesk Agent Code

這是一個可在本機操作的 LangChain IT Helpdesk Agent。它會查詢 mock SOP、建立記憶體中的 mock 工單，並把工具軌跡攤開顯示。每次 LangGraph 執行都有步數上限。

工單不會連到 Jira、ServiceNow、公司帳號、通知服務或任何真實 IT 系統。

## Requirements

- Python 3.11+
- An OpenAI API key

## 啟動本機頁面

```bash
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e .
cp .env.example .env
```

在 `.env` 設定 `OPENAI_API_KEY` 與 `MODEL_NAME` 後，啟動：

```bash
uvicorn app.web:app --reload
```

開啟 [http://127.0.0.1:8000](http://127.0.0.1:8000)。頁面有五種操作：

- 輸入問題，執行真正的 LangChain Agent。
- 「查看 SOP 優先流程」不需要 API key，固定顯示先查 SOP、再建 mock 工單的軌跡。
- 「觸發迴圈停止」不需要 API key，固定走到步數預算後安全停止。
- 「重試後成功」與「重試停止」不需要 API key，分別顯示唯讀 SOP 查詢在重試後成功，以及用完重試預算後停止。

各示範的目的不同。SOP 示範驗證 Day 3 的工具順序與後端阻擋規則；迴圈示範提供 Day 4 可重現的安全停止軌跡；重試示範驗證 Day 5 的唯讀查詢重試預算。實際 LangChain Agent 仍透過 LangGraph 的 `recursion_limit` 控制執行上限。

## CLI（可選）

如果只想從終端機試跑 Agent：

```bash
python -m app.main
```

## Test

```bash
python -m unittest discover -s tests -v
```
