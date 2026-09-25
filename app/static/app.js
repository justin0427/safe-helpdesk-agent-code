const message = document.querySelector("#message");
const experimentDay = document.querySelector("#experiment-day");
const experimentBoundary = document.querySelector("#experiment-boundary");
const runButton = document.querySelector("#run-agent");
const sopButton = document.querySelector("#run-sop-demo");
const ticketBeforeSopButton = document.querySelector("#run-ticket-before-sop-demo");
const sopTimeoutButton = document.querySelector("#run-sop-timeout-demo");
const circuitButton = document.querySelector("#run-circuit-demo");
const contextButton = document.querySelector("#run-context-demo");
const ragInjectionButton = document.querySelector("#run-rag-injection-demo");
const contextCompactionButton = document.querySelector("#run-context-compaction-demo");
const documentAuthorizationButton = document.querySelector("#run-document-authorization-demo");
const toolCatalogButton = document.querySelector("#run-tool-catalog-demo");
const externalShareButton = document.querySelector("#run-external-share-demo");
const toolOutputButton = document.querySelector("#run-tool-output-demo");
const nemoInputButton = document.querySelector("#run-nemo-input-demo");
const backendAuthorizationButton = document.querySelector("#run-backend-authorization-demo");
const memoryBoundaryButton = document.querySelector("#run-memory-boundary-demo");
const memoryGovernanceButton = document.querySelector("#run-memory-governance-demo");
const memoryPoisoningButton = document.querySelector("#run-memory-poisoning-demo");
const loopButton = document.querySelector("#run-loop-demo");
const tokenCostButton = document.querySelector("#run-token-cost-demo");
const timeButton = document.querySelector("#run-time-demo");
const status = document.querySelector("#run-status");
const response = document.querySelector("#response");
const ticketBlock = document.querySelector("#ticket-block");
const ticket = document.querySelector("#ticket");
const trace = document.querySelector("#trace");
const liveModeStatus = document.querySelector("#live-mode-status");
const liveModeDetail = document.querySelector("#live-mode-detail");
const runEvidence = document.querySelector("#run-evidence");
let isLiveReady = false;
let isExperimentCatalogReady = false;

const scenarioButtons = [
  sopButton,
  ticketBeforeSopButton,
  sopTimeoutButton,
  circuitButton,
  contextButton,
  ragInjectionButton,
  contextCompactionButton,
  documentAuthorizationButton,
  toolCatalogButton,
  externalShareButton,
  toolOutputButton,
  nemoInputButton,
  backendAuthorizationButton,
  memoryBoundaryButton,
  memoryGovernanceButton,
  memoryPoisoningButton,
  loopButton,
  tokenCostButton,
  timeButton,
];

function setStatus(text, state = "") {
  status.textContent = text;
  status.className = `status ${state}`;
}

function setBusy(isBusy) {
  scenarioButtons.forEach((button) => {
    button.disabled = isBusy;
  });
  experimentDay.disabled = isBusy || !isExperimentCatalogReady;
  runButton.disabled = isBusy || !isLiveReady || !isExperimentCatalogReady;
}

async function loadRuntimeStatus() {
  try {
    const result = await fetch("/api/runtime");
    const runtime = await result.json();
    isLiveReady = Boolean(runtime.live_llm_ready);
    liveModeStatus.textContent = isLiveReady ? "已連接" : "尚未設定";
    liveModeDetail.textContent = isLiveReady
      ? `模型：${runtime.model_name}（${runtime.provider}）`
      : "請先設定 MODEL_NAME 與模型憑證。";
  } catch (_error) {
    liveModeStatus.textContent = "狀態無法讀取";
    liveModeDetail.textContent = "deterministic tests 仍可使用。";
  } finally {
    runButton.disabled = !isLiveReady || !isExperimentCatalogReady;
  }
}

async function loadExperimentCatalog() {
  try {
    const result = await fetch("/api/experiments");
    const experiments = await result.json();
    experimentDay.replaceChildren();
    experiments.forEach((experiment) => {
      const option = document.createElement("option");
      option.value = String(experiment.day);
      option.textContent = `Day ${experiment.day}｜${experiment.title}`;
      option.dataset.prompt = experiment.prompt;
      option.dataset.boundary = experiment.expected_boundary;
      experimentDay.append(option);
    });
    isExperimentCatalogReady = true;
    experimentDay.disabled = false;
    selectExperiment();
  } catch (_error) {
    experimentDay.replaceChildren(new Option("實驗清單無法載入", ""));
    experimentBoundary.textContent = "請重新整理頁面後再試。";
  } finally {
    runButton.disabled = !isLiveReady || !isExperimentCatalogReady;
  }
}

function selectExperiment() {
  const option = experimentDay.selectedOptions[0];
  if (!option) return;
  message.value = option.dataset.prompt || "";
  experimentBoundary.textContent = `本次主要邊界：${option.dataset.boundary || "server-side policy"}`;
  runButton.textContent = `執行 Day ${option.value} Live 測試`;
}

function renderTrace(events) {
  trace.replaceChildren();
  if (!events.length) {
    const item = document.createElement("li");
    item.className = "empty-state";
    item.textContent = "這次沒有可顯示的軌跡。";
    trace.append(item);
    return;
  }

  events.forEach((event) => {
    const item = document.createElement("li");
    const eventBody = document.createElement("div");
    const eventName = document.createElement("span");
    const eventDetail = document.createElement("span");
    const eventStatus = document.createElement("span");

    eventName.className = "trace-name";
    eventName.textContent = `${event.kind}: ${event.name}`;
    eventDetail.className = "trace-detail";
    eventDetail.textContent = event.detail;
    eventStatus.className = `event-status ${event.status}`;
    eventStatus.textContent = event.status;
    eventBody.append(eventName, eventDetail);
    item.append(eventBody, eventStatus);
    trace.append(item);
  });
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderInlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
}

function renderMarkdown(value) {
  const blocks = [];
  let listType = null;

  const closeList = () => {
    if (!listType) return;
    blocks.push(`</${listType}>`);
    listType = null;
  };

  value.split(/\r?\n/).forEach((line) => {
    const text = line.trim();
    const heading = text.match(/^(#{1,3})\s+(.+)$/);
    const orderedItem = text.match(/^(\d+)\.\s+(.+)$/);
    const unorderedItem = text.match(/^[-*]\s+(.+)$/);

    if (!text) {
      closeList();
      return;
    }
    if (heading) {
      closeList();
      const level = heading[1].length + 2;
      blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      return;
    }
    if (orderedItem || unorderedItem) {
      const nextListType = orderedItem ? "ol" : "ul";
      if (listType !== nextListType) {
        closeList();
        listType = nextListType;
        const start = orderedItem ? ` start="${orderedItem[1]}"` : "";
        blocks.push(`<${listType}${start}>`);
      }
      const itemText = orderedItem ? orderedItem[2] : unorderedItem[1];
      blocks.push(`<li>${renderInlineMarkdown(itemText)}</li>`);
      return;
    }

    closeList();
    if (/^---+$/.test(text)) {
      blocks.push("<hr>");
      return;
    }
    if (text.startsWith("> ")) {
      blocks.push(`<blockquote>${renderInlineMarkdown(text.slice(2))}</blockquote>`);
      return;
    }
    blocks.push(`<p>${renderInlineMarkdown(text)}</p>`);
  });
  closeList();
  response.innerHTML = blocks.join("");
}

function renderResult(result) {
  renderMarkdown(result.response);
  renderTrace(result.trace || []);
  ticketBlock.hidden = !result.ticket;
  if (result.ticket) {
    ticket.textContent = JSON.stringify(result.ticket, null, 2);
  }
  setStatus(result.stopped ? "已安全停止" : "完成", result.stopped ? "stopped" : "success");
}

async function request(url, body, evidence = "固定資料回歸測試；本次沒有呼叫 LLM。") {
  setBusy(true);
  setStatus("執行中", "running");
  runEvidence.textContent = evidence;
  try {
    const options = { method: "POST", headers: { "Content-Type": "application/json" } };
    if (body) options.body = JSON.stringify(body);
    const result = await fetch(url, options);
    const payload = await result.json();
    if (!result.ok) throw new Error(payload.detail || "執行失敗");
    renderResult(payload);
  } catch (error) {
    response.textContent = error.message;
    ticketBlock.hidden = true;
    renderTrace([]);
    setStatus("無法執行", "error");
  } finally {
    setBusy(false);
  }
}

experimentDay.addEventListener("change", selectExperiment);
runButton.addEventListener("click", () => {
  const prompt = message.value.trim();
  if (!prompt) {
    response.textContent = "請先輸入 Prompt。";
    setStatus("無法執行", "error");
    return;
  }
  request(
    "/api/experiments/run",
    { day: Number(experimentDay.value), message: prompt },
    "Prompt 由你輸入；trace 中的 live_llm requested／completed 代表真正模型呼叫。",
  );
});
sopButton.addEventListener("click", () => request("/api/demos/sop-first"));
ticketBeforeSopButton.addEventListener("click", () => request("/api/demos/ticket-before-sop"));
sopTimeoutButton.addEventListener("click", () => request("/api/demos/sop-timeout"));
circuitButton.addEventListener("click", () => request("/api/demos/circuit-open"));
contextButton.addEventListener("click", () => request("/api/demos/context-boundary"));
ragInjectionButton.addEventListener("click", () => request("/api/demos/rag-injection"));
contextCompactionButton.addEventListener("click", () => request("/api/demos/context-compaction"));
documentAuthorizationButton.addEventListener("click", () => request("/api/demos/document-authorization"));
toolCatalogButton.addEventListener("click", () => request("/api/demos/tool-catalog"));
externalShareButton.addEventListener("click", () => request("/api/demos/external-share"));
toolOutputButton.addEventListener("click", () => request("/api/demos/tool-output"));
nemoInputButton.addEventListener("click", () => request("/api/demos/nemo-input-rails"));
backendAuthorizationButton.addEventListener("click", () => request("/api/demos/backend-authorization"));
memoryBoundaryButton.addEventListener("click", () => request("/api/demos/memory-boundary"));
memoryGovernanceButton.addEventListener("click", () => request("/api/demos/memory-governance"));
memoryPoisoningButton.addEventListener("click", () => request("/api/demos/memory-poisoning"));
loopButton.addEventListener("click", () => request("/api/demos/runaway-loop"));
tokenCostButton.addEventListener("click", () => request("/api/demos/token-cost-budget"));
timeButton.addEventListener("click", () => request("/api/demos/time-budget"));

loadRuntimeStatus();
loadExperimentCatalog();
