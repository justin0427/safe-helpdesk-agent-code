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

開啟 [http://127.0.0.1:8000](http://127.0.0.1:8000)。頁面可執行真實 Agent，也有不需要 API key 的固定安全情境：

- 輸入問題，執行真正的 LangChain Agent。
- 「查看 SOP 優先流程」不需要 API key，固定顯示先查 SOP、再建 mock 工單的軌跡。
- 「先開單會被擋」不需要 API key，固定顯示後端在尚未查 SOP 時拒絕 mock 寫入。
- 「SOP 逾時降級」不需要 API key，固定顯示唯讀查詢耗盡重試預算後，不建立工單的降級回覆。
- 「服務熔斷」不需要 API key，固定讓 SOP 服務先失敗，再確認下一次查詢被 circuit breaker 直接擋下。
- 「信任邊界」不需要 API key，固定取回建議升級處理的 mock SOP，確認它不會取得寫入授權。
- 「惡意 SOP 被隔離」不需要 API key，固定取回一份含指令式內容的 mock 文件，並在送入模型 context 前隔離。
- 「Context 精簡」不需要 API key，固定示範歷史壓縮、相關性選擇與敏感資料最小化。
- 「文件授權邊界」不需要 API key，固定示範 tenant、文件 ACL、檢索後複檢與 NeMo regex Retrieval Rail 預覽。
- 「工具目錄縮減」不需要 API key，固定比較 20 個候選工具與實際只給 Helpdesk Agent 的 2 個必要工具。
- 「外寄政策逐層檢查」不需要 API key，固定顯示工具註冊、read/write/execute 邊界、schema、收件者格式與 allowlist 的逐層決定；外部收件者會在 dispatch 前被拒絕。
- 「工具輸出清理」不需要 API key，固定讓 mock 工具回傳含指令與除錯秘密的錯誤，再確認模型只會看到公開錯誤代碼。
- 「觸發迴圈停止」不需要 API key，固定走到步數預算後安全停止。
- 「Token／成本上限」與「時間上限」不需要 API key，固定顯示執行預算用完後，停止下一次 Agent 動作。

各示範的目的不同。SOP 優先流程對應 Day 2；「先開單會被擋」對應 Day 3 的後端阻擋規則；SOP 逾時示範驗證 Day 4 的重試預算與降級回覆；服務熔斷對應 Day 8，讓相依服務已知失敗時後續請求直接降級；信任邊界對應 Day 10，讓文件內容不能自行授權寫入；惡意 SOP 示範對應 Day 11，讓指令式 retrieval 內容在進入模型 context 前被隔離；Context 精簡對應 Day 12，讓歷史資料先經過敏感資料移除、相關性選擇與壓縮。外寄資料示範保留給後續 Tool Design 章節。迴圈示範留給 Day 6；兩個預算示範對應 Day 7。實際 LangChain Agent 同時設定 LangGraph `recursion_limit`、LangChain model/tool call 上限、每次模型呼叫 timeout，以及單次輸出 token 上限。

若要重現 Day 3 的文章截圖，可開啟 `http://127.0.0.1:8000/?scenario=ticket-before-sop`。這個固定畫面和按鈕使用同一個後端情境，會顯示 `create_ticket` 請求、`sop_first` 阻擋與沒有建立 mock 工單的結果。

若要重現 Day 11 的文章截圖，可開啟 `http://127.0.0.1:8000/?scenario=rag-injection`。固定情境會顯示惡意 mock SOP 被 `indirect_prompt_injection` 隔離，以及後端因缺少原始使用者授權而拒絕 `create_ticket`。

若要重現 Day 12 的文章截圖，可開啟 `http://127.0.0.1:8000/?scenario=context-compaction`。固定情境會顯示較舊但相關的 VPN 訊息被保留、無關歷史被省略、穩定資料被壓成摘要，以及 mock secret 在模型 context 前被移除。

若要重現 Day 14 的文章截圖，可開啟 `http://127.0.0.1:8000/?scenario=document-authorization`。固定情境會先過濾不同 tenant 與角色不符的文件，模擬取回後混入跨 tenant 結果，再由檢索後授權擋下；最後使用 Day 14 NeMo 設定的 regex 進行本機預覽。

若要重現 Day 15 的文章截圖，可開啟 `http://127.0.0.1:8000/?scenario=tool-catalog`。固定情境會顯示應用程式層有 20 個候選工具，但本次 Helpdesk triage 只把 `search_it_sop` 與 `create_ticket` 的 schema 提供給模型。

若要重現 Day 16 的文章截圖，可開啟 `http://127.0.0.1:8000/?scenario=external-share`。固定情境會讓 schema 正確的外寄請求依序通過工具註冊、操作類型、schema 與 email 格式檢查，再由收件者 allowlist 擋下，最後留下 `outbound_dispatch skipped`。

若要重現 Day 17 的文章截圖，可開啟 `http://127.0.0.1:8000/?scenario=tool-output`。固定情境會讓 mock SOP 工具回傳含有未定義欄位、指令式文字與除錯秘密的錯誤物件；頁面只顯示清理規則與固定公開錯誤，不會顯示原始內容。

Day 14 的頁面是 deterministic preview，不會假裝 NeMo runtime 已執行。若要實際用 NeMo Guardrails 0.23.0 載入同一份設定：

```bash
uv pip install -e '.[guardrails]'
python -m app.validate_nemo_config
```

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
