const message = document.querySelector("#message");
const runButton = document.querySelector("#run-agent");
const sopButton = document.querySelector("#run-sop-demo");
const loopButton = document.querySelector("#run-loop-demo");
const retrySuccessButton = document.querySelector("#run-retry-success-demo");
const retryBudgetButton = document.querySelector("#run-retry-budget-demo");
const status = document.querySelector("#run-status");
const response = document.querySelector("#response");
const ticketBlock = document.querySelector("#ticket-block");
const ticket = document.querySelector("#ticket");
const trace = document.querySelector("#trace");

function setStatus(text, state = "") {
  status.textContent = text;
  status.className = `status ${state}`;
}

function setBusy(isBusy) {
  [runButton, sopButton, loopButton, retrySuccessButton, retryBudgetButton].forEach((button) => {
    button.disabled = isBusy;
  });
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

function renderResult(result) {
  response.textContent = result.response;
  renderTrace(result.trace || []);
  ticketBlock.hidden = !result.ticket;
  if (result.ticket) {
    ticket.textContent = JSON.stringify(result.ticket, null, 2);
  }
  setStatus(result.stopped ? "已安全停止" : "完成", result.stopped ? "stopped" : "success");
}

async function request(url, body) {
  setBusy(true);
  setStatus("執行中", "running");
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

runButton.addEventListener("click", () => request("/api/run", { message: message.value.trim() }));
sopButton.addEventListener("click", () => request("/api/demos/sop-first"));
loopButton.addEventListener("click", () => request("/api/demos/runaway-loop"));
retrySuccessButton.addEventListener("click", () => request("/api/demos/retry-success"));
retryBudgetButton.addEventListener("click", () => request("/api/demos/retry-budget"));
