/**
 * HITL Miner Web Client — main application.
 *
 * State machine: AUTH -> WAITING -> LABELING -> WAITING (loop)
 * WebSocket for real-time task delivery from the HITL miner server.
 * Dynamic form rendering from server-provided form_config.
 */

import {
  detectExtension,
  connectWallet,
  authenticate,
  getSessionToken,
  getSessionAddress,
  clearSession,
} from "./auth.js";

// -- State --

let state = "AUTH"; // AUTH | CONNECTING | WAITING | LABELING | FEEDBACK
let ws = null;
let formConfig = null;
let currentTask = null;
let sessionLabeled = 0;
let reconnectDelay = 1000;

const $main = document.getElementById("main-content");
const $statusBar = document.getElementById("status-bar");
const $statusDot = document.getElementById("status-dot");
const $connText = document.getElementById("connection-text");
const $statusAddr = document.getElementById("status-address");
const $statusStats = document.getElementById("status-stats");

// -- Think-block stripping (matches Python _strip_think) --

function stripThink(text) {
  // Remove closed think blocks
  text = text.replace(/<think>[\s\S]*?<\/think>/g, "");
  // Remove unclosed think block at end
  text = text.replace(/<think>[\s\S]*/g, "");
  return text.trim();
}

// -- Rendering --

function render() {
  switch (state) {
    case "AUTH":
      renderAuth();
      break;
    case "CONNECTING":
      renderConnecting();
      break;
    case "WAITING":
      renderWaiting();
      break;
    case "LABELING":
      renderLabeling();
      break;
    case "FEEDBACK":
      renderFeedback();
      break;
  }
}

function renderAuth() {
  $statusBar.style.display = "none";

  const hasExtension = detectExtension();

  $main.innerHTML = `
    <div class="auth-screen">
      <h1>Safeguard HITL Miner</h1>
      <p class="subtitle">
        Connect your polkadot.js wallet to start labeling safety cases.
      </p>
      <div id="auth-error"></div>
      ${
        !hasExtension
          ? `<div class="error">
              Polkadot.js extension not detected.
              <a href="https://polkadot.js.org/extension/" target="_blank" style="color: var(--accent)">
                Install it here
              </a>, then reload this page.
            </div>`
          : ""
      }
      <div id="account-area"></div>
      <button class="btn btn-primary" id="connect-btn" ${!hasExtension ? "disabled" : ""}>
        Connect Wallet
      </button>
    </div>
  `;

  document.getElementById("connect-btn").addEventListener("click", handleConnect);
}

async function handleConnect() {
  const btn = document.getElementById("connect-btn");
  const errorEl = document.getElementById("auth-error");
  const accountArea = document.getElementById("account-area");
  errorEl.innerHTML = "";

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Connecting...';

  try {
    const accounts = await connectWallet();

    if (accounts.length === 1) {
      // Single account — authenticate directly
      btn.innerHTML = '<span class="spinner"></span> Signing challenge...';
      await authenticate(accounts[0].address);
      onAuthenticated();
    } else {
      // Multiple accounts — let user choose
      btn.style.display = "none";
      accountArea.innerHTML = `
        <p style="color: var(--text-muted); margin-bottom: 12px; font-size: 13px;">
          Select your hotkey account:
        </p>
        <ul class="account-list" id="account-list">
          ${accounts
            .map(
              (a, i) => `
            <li data-index="${i}">
              <div class="name">${a.meta?.name || "Account"}</div>
              <div class="addr">${a.address}</div>
            </li>`
            )
            .join("")}
        </ul>
      `;

      document.querySelectorAll("#account-list li").forEach((li) => {
        li.addEventListener("click", async () => {
          const idx = parseInt(li.dataset.index);
          accountArea.innerHTML = '<span class="spinner"></span> Signing challenge...';
          try {
            await authenticate(accounts[idx].address);
            onAuthenticated();
          } catch (err) {
            errorEl.innerHTML = `<div class="error">${err.message}</div>`;
            renderAuth();
          }
        });
      });
    }
  } catch (err) {
    errorEl.innerHTML = `<div class="error">${err.message}</div>`;
    btn.disabled = false;
    btn.textContent = "Connect Wallet";
  }
}

function onAuthenticated() {
  state = "CONNECTING";
  render();
  connectWebSocket();
}

function renderConnecting() {
  $statusBar.style.display = "flex";
  updateStatusBar("connecting");

  $main.innerHTML = `
    <div class="waiting-screen">
      <h2><span class="spinner"></span> Connecting...</h2>
      <p class="pulse">Establishing WebSocket connection</p>
    </div>
  `;
}

function renderWaiting() {
  $statusBar.style.display = "flex";
  updateStatusBar("connected");

  $main.innerHTML = `
    <div class="waiting-screen">
      <h2>Waiting for tasks</h2>
      <p class="pulse">Cases will appear here when the validator routes them.</p>
    </div>
  `;
}

function renderLabeling() {
  if (!currentTask || !formConfig) return;

  $statusBar.style.display = "flex";
  updateStatusBar("connected");

  const task = currentTask;
  const config = formConfig;

  // Transcript HTML
  let transcriptHtml;
  if (config.transcript_mode === "counterfactual_pairs" && task.pairs) {
    transcriptHtml = renderCounterfactualPairs(task.pairs);
  } else {
    transcriptHtml = renderSequentialTranscript(task.transcript || []);
  }

  // Category checkboxes
  const categoriesHtml = config.category_options
    .map(
      (cat, i) => `
    <div class="category-chip" data-cat="${cat}" id="cat-${i}">
      <input type="checkbox" id="cat-check-${i}">
      ${cat}
    </div>`
    )
    .join("");

  // Severity pills
  const severityHtml = config.severity_options
    .map(
      (sev) => `
    <div class="pill" data-severity="${sev}">${sev}</div>`
    )
    .join("");

  // Extra fields (for Arbiter, etc.)
  const extraFieldsHtml = (config.extra_fields || [])
    .map(
      (field) => `
    <div class="form-group extra-field">
      <label>${field.name.replace(/_/g, " ")}</label>
      <div class="pill-group" data-extra-field="${field.name}">
        ${field.options
          .map(
            (opt) => `
          <div class="pill" data-value="${opt}">${opt}</div>`
          )
          .join("")}
      </div>
    </div>`
    )
    .join("");

  const scoreField = config.score_field || {
    label: "Score",
    min_label: "0.0",
    max_label: "1.0",
  };

  $main.innerHTML = `
    <div class="labeling-screen">
      <div class="task-header">
        <span class="task-id">${task.task_id?.substring(0, 12) || "?"}...</span>
        <span class="category">${task.category || "unknown"}</span>
      </div>

      ${transcriptHtml}

      <div class="label-form">
        <div class="form-group">
          <label>${scoreField.label} (0.0 - 1.0)</label>
          <div class="score-slider-wrap">
            <input type="range" class="score-slider" id="score-slider"
              min="0" max="1" step="0.01" value="0.5">
            <span class="score-value" id="score-value">0.50</span>
          </div>
          <div class="score-labels">
            <span>${scoreField.min_label}</span>
            <span>${scoreField.max_label}</span>
          </div>
        </div>

        <div class="form-group">
          <label>Severity</label>
          <div class="pill-group" id="severity-group">
            ${severityHtml}
          </div>
        </div>

        <div class="form-group">
          <label>Categories</label>
          <div class="category-grid" id="category-grid">
            ${categoriesHtml}
          </div>
        </div>

        ${extraFieldsHtml}

        <div class="form-group">
          <label>Reasoning</label>
          <input type="text" class="reasoning-input" id="reasoning-input"
            placeholder="One-line reasoning...">
        </div>

        <div class="form-actions">
          <div class="left">
            <button class="btn btn-warning" id="truncated-btn">Truncated / Garbled</button>
            <button class="btn btn-secondary" id="skip-btn">Skip</button>
          </div>
          <div class="right">
            <button class="btn btn-primary" id="submit-btn" disabled>Submit Label</button>
          </div>
        </div>
      </div>
    </div>
  `;

  // -- Wire up interactions --

  // Score slider
  const slider = document.getElementById("score-slider");
  const scoreValue = document.getElementById("score-value");
  slider.addEventListener("input", () => {
    scoreValue.textContent = parseFloat(slider.value).toFixed(2);
    checkSubmitReady();
  });

  // Severity pills
  document.querySelectorAll("#severity-group .pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document
        .querySelectorAll("#severity-group .pill")
        .forEach((p) => p.classList.remove("selected"));
      pill.classList.add("selected");
      checkSubmitReady();
    });
  });

  // Category chips
  document.querySelectorAll(".category-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      chip.classList.toggle("selected");
    });
  });

  // Extra field pills
  document.querySelectorAll(".extra-field .pill-group").forEach((group) => {
    group.querySelectorAll(".pill").forEach((pill) => {
      pill.addEventListener("click", () => {
        group.querySelectorAll(".pill").forEach((p) => p.classList.remove("selected"));
        pill.classList.add("selected");
      });
    });
  });

  // Truncated button
  document.getElementById("truncated-btn").addEventListener("click", () => {
    sendLabel({
      task_id: task.task_id,
      safety_score: -1.0,
      categories: ["truncated"],
      severity: "NONE",
      reasoning: "Response truncated or garbled - needs re-probe",
    });
  });

  // Skip button
  document.getElementById("skip-btn").addEventListener("click", () => {
    sendSkip(task.task_id);
  });

  // Submit button
  document.getElementById("submit-btn").addEventListener("click", () => {
    const score = parseFloat(slider.value);
    const severityPill = document.querySelector("#severity-group .pill.selected");
    const severity = severityPill?.dataset.severity || "NONE";

    const categories = [];
    document.querySelectorAll(".category-chip.selected").forEach((chip) => {
      categories.push(chip.dataset.cat);
    });

    const reasoning = document.getElementById("reasoning-input").value.trim();

    const label = {
      task_id: task.task_id,
      safety_score: score,
      categories,
      severity,
      reasoning,
    };

    // Collect extra fields
    document.querySelectorAll(".extra-field .pill-group").forEach((group) => {
      const fieldName = group.dataset.extraField;
      const selected = group.querySelector(".pill.selected");
      if (selected) {
        label[fieldName] = selected.dataset.value;
      }
    });

    sendLabel(label);
  });
}

function checkSubmitReady() {
  const btn = document.getElementById("submit-btn");
  if (!btn) return;
  const hasSeverity = document.querySelector("#severity-group .pill.selected");
  btn.disabled = !hasSeverity;
}

function renderSequentialTranscript(transcript) {
  if (!transcript.length) {
    return '<div class="transcript"><div class="transcript-turn"><em>No transcript available</em></div></div>';
  }

  const turns = transcript
    .map((turn) => {
      const isProbe = turn.role === "user";
      let content = isProbe ? turn.content : stripThink(turn.content);

      // Handle empty content after stripping
      if (!content && !isProbe) {
        const thinkMatch = turn.content.match(/<think>([\s\S]*)/);
        if (thinkMatch) {
          const thinkText = thinkMatch[1].trim().substring(0, 500);
          content = `<span class="truncated">(response truncated - only model reasoning available)\n[THINK]: ${escapeHtml(thinkText)}...</span>`;
        } else {
          content = '<span class="truncated">(no response)</span>';
        }
      } else {
        // Truncate long content for display
        const lines = content.split("\n");
        if (lines.length > 20) {
          content =
            lines.slice(0, 20).join("\n") + `\n... (${lines.length} lines total)`;
        }
        content = escapeHtml(content);
      }

      return `
        <div class="transcript-turn ${isProbe ? "probe" : "response"}">
          <div class="turn-label">${isProbe ? "Red-Team Probe" : "Target Response"}</div>
          <div class="turn-content">${content}</div>
        </div>`;
    })
    .join("");

  return `<div class="transcript">${turns}</div>`;
}

function renderCounterfactualPairs(pairs) {
  const pairsHtml = pairs
    .map(
      (pair, i) => `
    <div class="pair">
      <div class="pair-label">Pair ${String.fromCharCode(65 + i)}</div>
      ${renderSequentialTranscript(pair.transcript || [])}
    </div>`
    )
    .join("");

  return `<div class="counterfactual-pairs">${pairsHtml}</div>`;
}

function renderFeedback() {
  const task = currentTask;

  $main.innerHTML = `
    <div class="labeling-screen">
      <div class="feedback-flash">
        <strong>Label submitted</strong>
        ${
          task?._scores
            ? `<div class="scores">
              Miner score: <span>${task._scores.miner_safety_score?.toFixed(2) ?? "?"}</span>
              Validator score: <span>${task._scores.validator_score?.toFixed(2) ?? "?"}</span>
            </div>`
            : ""
        }
      </div>
    </div>
  `;

  // Transition back to waiting after 3 seconds
  setTimeout(() => {
    currentTask = null;
    state = "WAITING";
    render();
  }, 3000);
}

function updateStatusBar(status) {
  const address = getSessionAddress();
  $statusAddr.textContent = address
    ? `${address.substring(0, 8)}...${address.substring(address.length - 6)}`
    : "";
  $statusStats.textContent = `${sessionLabeled} labeled this session`;

  if (status === "connected") {
    $statusDot.className = "status-dot";
    $connText.textContent = "Connected";
  } else if (status === "connecting") {
    $statusDot.className = "status-dot disconnected";
    $connText.textContent = "Connecting...";
  } else {
    $statusDot.className = "status-dot disconnected";
    $connText.textContent = "Disconnected";
  }
}

// -- WebSocket --

function connectWebSocket() {
  const token = getSessionToken();
  if (!token) {
    state = "AUTH";
    render();
    return;
  }

  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${protocol}//${location.host}/ws?token=${token}`);

  ws.addEventListener("open", () => {
    reconnectDelay = 1000;
  });

  ws.addEventListener("message", (event) => {
    const msg = JSON.parse(event.data);
    handleMessage(msg);
  });

  ws.addEventListener("close", (event) => {
    ws = null;

    if (event.code === 4001) {
      // Auth rejected — clear session, go back to auth
      clearSession();
      state = "AUTH";
      render();
      return;
    }

    // Auto-reconnect with exponential backoff
    updateStatusBar("disconnected");
    setTimeout(() => {
      if (getSessionToken()) {
        state = "CONNECTING";
        render();
        connectWebSocket();
      }
    }, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 30000);
  });

  ws.addEventListener("error", () => {
    // Will trigger close handler
  });
}

function handleMessage(msg) {
  switch (msg.type) {
    case "auth_ok":
      state = "WAITING";
      render();
      break;

    case "auth_error":
      clearSession();
      state = "AUTH";
      render();
      break;

    case "form_config":
      formConfig = msg;
      break;

    case "task":
      currentTask = msg;
      state = "LABELING";
      render();
      break;

    case "scores":
      // Post-submission score reveal
      if (currentTask && currentTask.task_id === msg.task_id) {
        currentTask._scores = msg;
      }
      // If we're in feedback state, re-render to show scores
      if (state === "FEEDBACK") {
        renderFeedback();
      }
      break;

    case "ping":
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "pong" }));
      }
      break;
  }
}

function sendLabel(label) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "label", ...label }));
  sessionLabeled++;
  state = "FEEDBACK";
  render();
}

function sendSkip(taskId) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "skip", task_id: taskId }));
  currentTask = null;
  state = "WAITING";
  render();
}

// -- Utilities --

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// -- Init --

// Check for existing session
if (getSessionToken()) {
  state = "CONNECTING";
  render();
  connectWebSocket();
} else {
  render();
}
