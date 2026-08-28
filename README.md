# Safe Helpdesk Agent Code

這是一個可在本機操作的 LangChain IT Helpdesk Agent。它會查詢 mock SOP、建立記憶體中的 mock 工單，並把工具軌跡攤開顯示。唯讀 SOP 查詢有退避重試與降級回覆；重複的寫入請求會用 idempotency key 去重。

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

開啟 [http://127.0.0.1:8000](http://127.0.0.1:8000)。頁面有六種操作：

- 輸入問題，執行真正的 LangChain Agent。
- 「查看 SOP 優先流程」不需要 API key，固定顯示先查 SOP、再建 mock 工單的軌跡。
- 「SOP 逾時降級」不需要 API key，固定顯示唯讀查詢耗盡重試預算後，不建立工單的降級回覆。
- 「觸發迴圈停止」不需要 API key，固定走到步數預算後安全停止。
- 「Token／成本上限」與「時間上限」不需要 API key，固定顯示執行預算用完後，停止下一次 Agent 動作。

各示範的目的不同。SOP 示範驗證 Day 3 的工具順序與後端阻擋規則；SOP 逾時示範驗證 Day 4 的重試預算與降級回覆；迴圈示範留給 Day 6；兩個預算示範對應 Day 7。實際 LangChain Agent 同時設定 LangGraph `recursion_limit`、LangChain model/tool call 上限、每次模型呼叫 timeout，以及單次輸出 token 上限。

若要啟用美元成本上限，還要依實際部署模型填入 `MODEL_INPUT_PER_MILLION_USD`、`MODEL_OUTPUT_PER_MILLION_USD` 與 `RUN_COST_BUDGET_USD`。價格留空時，Agent 仍有時間與 Token 上限，但不會猜測模型價格。

## CLI（可選）

如果只想從終端機試跑 Agent：

```bash
python -m app.main
```

## Test

```bash
python -m unittest discover -s tests -v
```
