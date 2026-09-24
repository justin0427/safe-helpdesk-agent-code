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

開啟 [http://127.0.0.1:8000](http://127.0.0.1:8000)。頁面有十二種操作：

- 輸入問題，執行真正的 LangChain Agent。
- 「查看 SOP 優先流程」不需要 API key，固定顯示先查 SOP、再建 mock 工單的軌跡。
- 「先開單會被擋」不需要 API key，固定顯示後端在尚未查 SOP 時拒絕 mock 寫入。
- 「SOP 逾時降級」不需要 API key，固定顯示唯讀查詢耗盡重試預算後，不建立工單的降級回覆。
- 「服務熔斷」不需要 API key，固定讓 SOP 服務先失敗，再確認下一次查詢被 circuit breaker 直接擋下。
- 「信任邊界」不需要 API key，固定取回建議升級處理的 mock SOP，確認它不會取得寫入授權。
- 「惡意 SOP 被隔離」不需要 API key，固定取回一份含指令式內容的 mock 文件，並在送入模型 context 前隔離。
- 「Context 精簡」不需要 API key，固定示範歷史壓縮、相關性選擇與敏感資料最小化。
- 「外寄資料被擋」不需要 API key，固定驗證外部收件者會在 dispatch 前被 recipient allowlist 拒絕。
- 「觸發迴圈停止」不需要 API key，固定走到步數預算後安全停止。
- 「Token／成本上限」與「時間上限」不需要 API key，固定顯示執行預算用完後，停止下一次 Agent 動作。

各示範的目的不同。SOP 優先流程對應 Day 2；「先開單會被擋」對應 Day 3 的後端阻擋規則；SOP 逾時示範驗證 Day 4 的重試預算與降級回覆；服務熔斷對應 Day 8，讓相依服務已知失敗時後續請求直接降級；信任邊界對應 Day 10，讓文件內容不能自行授權寫入；惡意 SOP 示範對應 Day 11，讓指令式 retrieval 內容在進入模型 context 前被隔離；Context 精簡對應 Day 12，讓歷史資料先經過敏感資料移除、相關性選擇與壓縮。外寄資料示範保留給後續 Tool Design 章節。迴圈示範留給 Day 6；兩個預算示範對應 Day 7。實際 LangChain Agent 同時設定 LangGraph `recursion_limit`、LangChain model/tool call 上限、每次模型呼叫 timeout，以及單次輸出 token 上限。

若要重現 Day 3 的文章截圖，可開啟 `http://127.0.0.1:8000/?scenario=ticket-before-sop`。這個固定畫面和按鈕使用同一個後端情境，會顯示 `create_ticket` 請求、`sop_first` 阻擋與沒有建立 mock 工單的結果。

若要重現 Day 11 的文章截圖，可開啟 `http://127.0.0.1:8000/?scenario=rag-injection`。固定情境會顯示惡意 mock SOP 被 `indirect_prompt_injection` 隔離，以及後端因缺少原始使用者授權而拒絕 `create_ticket`。

若要重現 Day 12 的文章截圖，可開啟 `http://127.0.0.1:8000/?scenario=context-compaction`。固定情境會顯示較舊但相關的 VPN 訊息被保留、無關歷史被省略、穩定資料被壓成摘要，以及 mock secret 在模型 context 前被移除。

若要啟用美元成本上限，還要依實際部署模型填入 `MODEL_INPUT_PER_MILLION_USD`、`MODEL_OUTPUT_PER_MILLION_USD` 與 `RUN_COST_BUDGET_USD`。價格留空時，Agent 仍有時間與 Token 上限，但不會猜測模型價格。

時間、Token 與成本預算會在模型呼叫前與工具執行前檢查。Token 與成本依 provider 回傳的 usage metadata 累積；provider 沒有回傳 usage 時，程式不會假裝知道實際花費。

## CLI（可選）

如果只想從終端機試跑 Agent：

```bash
python -m app.main
```

## Test

```bash
python -m unittest discover -s tests -v
```

## Promptfoo security suite

Day 5 的 deterministic security cases 不需要 OpenAI API key：

```bash
npx --yes promptfoo@latest eval -c evals/promptfooconfig.yaml --no-cache
```

它會驗證正常開單、越權帳號重設請求、SOP 工具不可用、工具失敗時不得假裝成功、Token 預算用完後不得執行工具、服務熔斷後不得繼續重試、惡意 retrieval 內容不得取得工具授權，以及敏感歷史不得進入 model-visible context。Day 9 加入 Promptfoo OpenTelemetry tracing，讓 suite 也驗證工具順序、工具次數與停止事件；它直接呼叫本機 mock workflow，不需要 OpenAI API key。
