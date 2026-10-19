(() => {
  const ROWS = 6;
  const COLS = 5;
  const COLOR_CYCLE = ["", "b", "y", "g"];

  const boardEl = document.getElementById("board");
  const statusEl = document.getElementById("status");
  const guessInput = document.getElementById("guess-input");
  const recList = document.getElementById("rec-list");
  const candidatesEl = document.getElementById("candidates");
  const candCount = document.getElementById("cand-count");
  const hardMode = document.getElementById("hard-mode");
  const btnSubmit = document.getElementById("btn-submit");
  const btnUndo = document.getElementById("btn-undo");
  const btnNew = document.getElementById("btn-new");
  const btnSim = document.getElementById("btn-sim");
  const simStatus = document.getElementById("sim-status");
  const simMetrics = document.getElementById("sim-metrics");

  let draftColors = ["", "", "", "", ""];
  let remainingHistory = [2309];
  let entropyChart;
  let shrinkChart;
  let distChart;
  let busy = false;

  function api(path, options = {}) {
    return fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    }).then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    });
  }

  function buildBoard() {
    boardEl.innerHTML = "";
    for (let r = 0; r < ROWS; r++) {
      const row = document.createElement("div");
      row.className = "row";
      row.dataset.row = String(r);
      for (let c = 0; c < COLS; c++) {
        const tile = document.createElement("div");
        tile.className = "tile";
        tile.dataset.row = String(r);
        tile.dataset.col = String(c);
        tile.addEventListener("click", () => onTileClick(r, c));
        row.appendChild(tile);
      }
      boardEl.appendChild(row);
    }
  }

  function tileAt(r, c) {
    return boardEl.querySelector(`.tile[data-row="${r}"][data-col="${c}"]`);
  }

  function paintHistory(history) {
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const tile = tileAt(r, c);
        tile.className = "tile";
        tile.textContent = "";
        tile.classList.remove("editable");
      }
    }

    history.forEach((h, r) => {
      for (let c = 0; c < COLS; c++) {
        const tile = tileAt(r, c);
        const ch = h.guess[c] || "";
        const color = h.colors[c] || "b";
        tile.textContent = ch;
        tile.classList.add("filled", color);
      }
    });

    const draftRow = history.length;
    if (draftRow < ROWS) {
      const word = guessInput.value.toUpperCase().padEnd(5).slice(0, 5);
      for (let c = 0; c < COLS; c++) {
        const tile = tileAt(draftRow, c);
        const ch = word[c] && word[c] !== " " ? word[c] : "";
        tile.textContent = ch;
        tile.classList.add("editable");
        if (ch) tile.classList.add("filled", "pop");
        const color = draftColors[c];
        if (color) tile.classList.add(color);
      }
    }
  }

  function onTileClick(r, c) {
    const historyLen = Number(boardEl.dataset.historyLen || 0);
    if (r !== historyLen || busy) return;
    const letter = (guessInput.value[c] || "").toUpperCase();
    if (!letter) return;
    const cur = draftColors[c] || "";
    const next = COLOR_CYCLE[(COLOR_CYCLE.indexOf(cur) + 1) % COLOR_CYCLE.length];
    draftColors[c] = next;
    paintHistory(JSON.parse(boardEl.dataset.historyJson || "[]"));
  }

  function syncDraftFromInput() {
    const v = guessInput.value.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 5);
    guessInput.value = v;
    // reset colors for emptied slots
    for (let i = v.length; i < 5; i++) draftColors[i] = "";
    paintHistory(JSON.parse(boardEl.dataset.historyJson || "[]"));
  }

  function renderRecs(recs) {
    recList.innerHTML = "";
    const maxEnt = Math.max(...recs.map((r) => r.entropy), 0.001);
    recs.forEach((r) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "rec";
      btn.innerHTML = `
        <span class="word">${r.word}</span>
        <span class="bar-track"><span class="bar" style="width:${(r.entropy / maxEnt) * 100}%"></span></span>
        <span class="meta">${r.entropy.toFixed(2)}${r.in_answers ? '<span class="tag">答案</span>' : '<span class="tag">探测</span>'}</span>
      `;
      btn.addEventListener("click", () => {
        guessInput.value = r.word;
        draftColors = ["", "", "", "", ""];
        syncDraftFromInput();
        guessInput.focus();
      });
      recList.appendChild(btn);
    });

    const labels = recs.map((r) => r.word);
    const values = recs.map((r) => r.entropy);
    const ctx = document.getElementById("entropy-chart");
    if (entropyChart) entropyChart.destroy();
    entropyChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "信息熵",
            data: values,
            backgroundColor: "#6aaa64",
            borderRadius: 6,
          },
        ],
      },
      options: {
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, grid: { color: "#e5ebe3" } },
          y: { grid: { display: false } },
        },
      },
    });
  }

  function renderShrink() {
    const ctx = document.getElementById("shrink-chart");
    if (shrinkChart) shrinkChart.destroy();
    shrinkChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: remainingHistory.map((_, i) => (i === 0 ? "开局" : `第${i}步`)),
        datasets: [
          {
            label: "剩余候选",
            data: remainingHistory,
            borderColor: "#2f6f4e",
            backgroundColor: "rgba(47, 111, 78, 0.15)",
            fill: true,
            tension: 0.25,
            pointRadius: 4,
          },
        ],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, grid: { color: "#e5ebe3" } },
          x: { grid: { display: false } },
        },
      },
    });
  }

  function renderCandidates(state) {
    candCount.textContent = `(${state.remaining})`;
    candidatesEl.innerHTML = "";
    state.candidates.forEach((w) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = w.toUpperCase();
      candidatesEl.appendChild(chip);
    });
    if (state.candidates_truncated) {
      const more = document.createElement("span");
      more.className = "chip";
      more.textContent = "…";
      candidatesEl.appendChild(more);
    }
  }

  function applyState(state, { resetShrink = false } = {}) {
    hardMode.checked = !!state.hard;
    boardEl.dataset.historyLen = String(state.history.length);
    boardEl.dataset.historyJson = JSON.stringify(state.history);

    if (resetShrink) {
      remainingHistory = [2309];
    }
    // rebuild shrink from history length vs current remaining
    if (state.history.length + 1 !== remainingHistory.length || resetShrink) {
      // approximate trail: keep previous points if undo/new handled by caller
    }
    if (remainingHistory.length === state.history.length) {
      remainingHistory.push(state.remaining);
    } else if (remainingHistory.length !== state.history.length + 1) {
      remainingHistory = [2309];
      // we don't have intermediate values after reload — just show current end
      if (state.history.length > 0) remainingHistory.push(state.remaining);
    }

    if (state.solved) {
      statusEl.textContent = `完成！答案 ${state.answer} · ${state.history.length} 步`;
      statusEl.className = "status solved";
      guessInput.disabled = true;
      btnSubmit.disabled = true;
    } else if (state.remaining === 0) {
      statusEl.textContent = "没有候选了，请检查反馈或撤销";
      statusEl.className = "status";
      guessInput.disabled = false;
      btnSubmit.disabled = false;
    } else {
      statusEl.textContent = `第 ${state.turn} 步 · 剩余候选 ${state.remaining}`;
      statusEl.className = "status";
      guessInput.disabled = false;
      btnSubmit.disabled = false;
    }

    draftColors = ["", "", "", "", ""];
    if (!state.solved && state.recommendations[0]) {
      guessInput.value = state.recommendations[0].word;
    } else if (state.solved) {
      guessInput.value = "";
    }
    paintHistory(state.history);
    renderRecs(state.recommendations);
    renderCandidates(state);
    renderShrink();
  }

  async function refresh() {
    const state = await api("/api/state");
    remainingHistory = [2309];
    if (state.history.length) remainingHistory.push(state.remaining);
    applyState(state);
  }

  async function newGame() {
    busy = true;
    try {
      const state = await api("/api/new", {
        method: "POST",
        body: JSON.stringify({ hard: hardMode.checked }),
      });
      remainingHistory = [2309];
      applyState(state, { resetShrink: true });
    } catch (e) {
      statusEl.textContent = e.message;
    } finally {
      busy = false;
    }
  }

  async function submitGuess() {
    if (busy) return;
    const guess = guessInput.value.trim();
    if (guess.length !== 5) {
      statusEl.textContent = "请输入 5 个字母";
      return;
    }
    if (draftColors.some((c) => !c)) {
      statusEl.textContent = "请为每个字母设置颜色（点击格子）";
      return;
    }
    busy = true;
    btnSubmit.disabled = true;
    try {
      const state = await api("/api/guess", {
        method: "POST",
        body: JSON.stringify({ guess, colors: draftColors.join("") }),
      });
      applyState(state);
    } catch (e) {
      statusEl.textContent = e.message;
      statusEl.className = "status";
    } finally {
      busy = false;
      btnSubmit.disabled = false;
    }
  }

  async function undo() {
    if (busy) return;
    busy = true;
    try {
      const state = await api("/api/undo", { method: "POST", body: "{}" });
      remainingHistory = remainingHistory.slice(0, Math.max(1, state.history.length));
      if (remainingHistory.length === state.history.length) {
        remainingHistory.push(state.remaining);
      }
      applyState(state);
    } catch (e) {
      statusEl.textContent = e.message;
    } finally {
      busy = false;
    }
  }

  async function runSim() {
    const limitVal = document.getElementById("sim-limit").value;
    const hard = document.getElementById("sim-hard").checked;
    btnSim.disabled = true;
    simStatus.textContent = "模拟中，请稍候…";
    simMetrics.classList.add("hidden");
    try {
      const body = { hard };
      if (limitVal !== "") body.limit = Number(limitVal);
      const stats = await api("/api/simulate", {
        method: "POST",
        body: JSON.stringify(body),
      });
      simStatus.textContent = hard ? "Hard Mode 模拟完成" : "普通模式模拟完成";
      simMetrics.classList.remove("hidden");
      simMetrics.innerHTML = `
        <div class="metric"><span class="label">局数</span><span class="value">${stats.n}</span></div>
        <div class="metric"><span class="label">胜率</span><span class="value">${(stats.win_rate * 100).toFixed(1)}%</span></div>
        <div class="metric"><span class="label">平均步数</span><span class="value">${stats.avg_steps.toFixed(3)}</span></div>
        <div class="metric"><span class="label">最大步数</span><span class="value">${stats.max_steps}</span></div>
        <div class="metric"><span class="label">失败</span><span class="value">${stats.fails}</span></div>
      `;

      const labels = Object.keys(stats.distribution).sort((a, b) => Number(a) - Number(b));
      const values = labels.map((k) => stats.distribution[k]);
      const ctx = document.getElementById("dist-chart");
      if (distChart) distChart.destroy();
      distChart = new Chart(ctx, {
        type: "bar",
        data: {
          labels: labels.map((k) => `${k} 步`),
          datasets: [
            {
              label: "局数",
              data: values,
              backgroundColor: "#c9b458",
              borderRadius: 8,
            },
          ],
        },
        options: {
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#e5ebe3" } },
            x: { grid: { display: false } },
          },
        },
      });
    } catch (e) {
      simStatus.textContent = e.message;
    } finally {
      btnSim.disabled = false;
    }
  }

  // ---- Challenge / 题库对战 ----
  const gameBoardEl = document.getElementById("game-board");
  const gameStatusEl = document.getElementById("game-status");
  const gameInput = document.getElementById("game-input");
  const gameRecList = document.getElementById("game-rec-list");
  const gameHard = document.getElementById("game-hard");
  const btnGameNew = document.getElementById("btn-game-new");
  const btnGameGuess = document.getElementById("btn-game-guess");
  const btnGameAutoStep = document.getElementById("btn-game-auto-step");
  const btnGameAutoAll = document.getElementById("btn-game-auto-all");
  let gameBusy = false;
  let gameActive = false;

  function buildGameBoard() {
    gameBoardEl.innerHTML = "";
    for (let r = 0; r < ROWS; r++) {
      const row = document.createElement("div");
      row.className = "row";
      for (let c = 0; c < COLS; c++) {
        const tile = document.createElement("div");
        tile.className = "tile";
        tile.dataset.grow = String(r);
        tile.dataset.gcol = String(c);
        row.appendChild(tile);
      }
      gameBoardEl.appendChild(row);
    }
  }

  function gameTile(r, c) {
    return gameBoardEl.querySelector(`.tile[data-grow="${r}"][data-gcol="${c}"]`);
  }

  function paintGameBoard(history, draftWord) {
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const tile = gameTile(r, c);
        tile.className = "tile";
        tile.textContent = "";
      }
    }
    history.forEach((h, r) => {
      for (let c = 0; c < COLS; c++) {
        const tile = gameTile(r, c);
        tile.textContent = h.guess[c] || "";
        tile.classList.add("filled", h.colors[c] || "b", "pop");
      }
    });
    const draftRow = history.length;
    if (draftRow < ROWS && draftWord) {
      const word = draftWord.toUpperCase().padEnd(5).slice(0, 5);
      for (let c = 0; c < COLS; c++) {
        const ch = word[c] && word[c] !== " " ? word[c] : "";
        if (!ch) continue;
        const tile = gameTile(draftRow, c);
        tile.textContent = ch;
        tile.classList.add("filled", "pop");
      }
    }
  }

  function setGameControls(enabled) {
    gameInput.disabled = !enabled;
    btnGameGuess.disabled = !enabled;
    btnGameAutoStep.disabled = !enabled;
    btnGameAutoAll.disabled = !enabled;
  }

  function renderGameRecs(recs) {
    gameRecList.innerHTML = "";
    if (!recs || !recs.length) {
      gameRecList.innerHTML = '<p class="side-note">本局结束后不再给出建议。</p>';
      return;
    }
    const maxEnt = Math.max(...recs.map((r) => r.entropy), 0.001);
    recs.forEach((r) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "rec";
      btn.innerHTML = `
        <span class="word">${r.word}</span>
        <span class="bar-track"><span class="bar" style="width:${(r.entropy / maxEnt) * 100}%"></span></span>
        <span class="meta">${r.entropy.toFixed(2)}${r.in_answers ? '<span class="tag">答案</span>' : '<span class="tag">探测</span>'}</span>
      `;
      btn.addEventListener("click", () => {
        if (gameInput.disabled) return;
        gameInput.value = r.word;
        paintGameBoard(JSON.parse(gameBoardEl.dataset.historyJson || "[]"), gameInput.value);
        gameInput.focus();
      });
      gameRecList.appendChild(btn);
    });
  }

  function applyGameState(state) {
    gameActive = !!state.active || !!state.history;
    const history = state.history || [];
    gameBoardEl.dataset.historyJson = JSON.stringify(history);

    document.getElementById("gm-used").textContent = String(state.guesses_used ?? history.length);
    document.getElementById("gm-left").textContent = String(
      state.guesses_left ?? Math.max(0, 6 - history.length)
    );
    document.getElementById("gm-rem").textContent =
      state.remaining != null ? String(state.remaining) : "—";

    if (state.won) {
      gameStatusEl.textContent = `猜中了！答案 ${state.answer} · ${history.length} 步`;
      gameStatusEl.className = "status solved";
      document.getElementById("gm-state").textContent = "胜利";
      setGameControls(false);
    } else if (state.lost) {
      gameStatusEl.textContent = `未猜出。答案是 ${state.answer}`;
      gameStatusEl.className = "status lost";
      document.getElementById("gm-state").textContent = "失败";
      setGameControls(false);
    } else if (!gameActive && !(state.history && state.history.length)) {
      gameStatusEl.textContent = "点击「抽一题」从答案库随机出题。";
      gameStatusEl.className = "status muted";
      document.getElementById("gm-state").textContent = "未开始";
      setGameControls(false);
    } else {
      gameStatusEl.textContent = `第 ${state.turn} 步 · 还剩 ${state.guesses_left} 次机会`;
      gameStatusEl.className = "status";
      document.getElementById("gm-state").textContent = "进行中";
      setGameControls(true);
      if (state.recommendations && state.recommendations[0] && !gameInput.value) {
        gameInput.value = state.recommendations[0].word;
      }
    }

    paintGameBoard(history, gameInput.disabled ? "" : gameInput.value);
    renderGameRecs(state.recommendations || []);
  }

  async function gameNew() {
    if (gameBusy) {
      gameStatusEl.textContent = "正在处理上一操作，请稍候…";
      gameStatusEl.className = "status muted";
      return;
    }
    gameBusy = true;
    if (btnGameNew) btnGameNew.disabled = true;
    gameStatusEl.textContent = "正在抽题…";
    gameStatusEl.className = "status muted";
    try {
      const state = await api("/api/game/new", {
        method: "POST",
        body: JSON.stringify({ hard: gameHard.checked }),
      });
      gameInput.value = "";
      applyGameState({ ...state, active: true });
    } catch (e) {
      gameStatusEl.textContent = e.message || "抽题失败";
      gameStatusEl.className = "status";
    } finally {
      gameBusy = false;
      if (btnGameNew) btnGameNew.disabled = false;
    }
  }

  async function gameGuess() {
    if (gameBusy) return;
    const guess = gameInput.value.trim();
    if (guess.length !== 5) {
      gameStatusEl.textContent = "请输入 5 个字母";
      gameStatusEl.className = "status";
      return;
    }
    gameBusy = true;
    try {
      const state = await api("/api/game/guess", {
        method: "POST",
        body: JSON.stringify({ guess }),
      });
      gameInput.value = "";
      applyGameState({ ...state, active: true });
    } catch (e) {
      gameStatusEl.textContent = e.message;
      gameStatusEl.className = "status";
    } finally {
      gameBusy = false;
    }
  }

  async function gameAutoStep() {
    if (gameBusy) return;
    gameBusy = true;
    try {
      const state = await api("/api/game/auto-step", {
        method: "POST",
        body: "{}",
      });
      gameInput.value = "";
      applyGameState({ ...state, active: true });
    } catch (e) {
      gameStatusEl.textContent = e.message;
      gameStatusEl.className = "status";
    } finally {
      gameBusy = false;
    }
  }

  async function gameAutoAll() {
    if (gameBusy) return;
    gameBusy = true;
    btnGameAutoAll.disabled = true;
    gameStatusEl.textContent = "系统求解中…";
    try {
      const state = await api("/api/game/auto-all", {
        method: "POST",
        body: "{}",
      });
      gameInput.value = "";
      applyGameState({ ...state, active: true });
    } catch (e) {
      gameStatusEl.textContent = e.message;
      gameStatusEl.className = "status";
    } finally {
      gameBusy = false;
    }
  }

  async function loadGameState() {
    try {
      const state = await api("/api/game/state");
      if (state.active) applyGameState(state);
    } catch (_) {
      /* ignore */
    }
  }

  // tabs
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`panel-${tab.dataset.tab}`).classList.add("active");
      if (tab.dataset.tab === "game") loadGameState();
    });
  });

  guessInput.addEventListener("input", syncDraftFromInput);
  guessInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitGuess();
  });
  btnSubmit.addEventListener("click", submitGuess);
  btnUndo.addEventListener("click", undo);
  btnNew.addEventListener("click", newGame);
  hardMode.addEventListener("change", newGame);
  btnSim.addEventListener("click", runSim);

  gameInput.addEventListener("input", () => {
    const v = gameInput.value.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 5);
    gameInput.value = v;
    paintGameBoard(JSON.parse(gameBoardEl.dataset.historyJson || "[]"), v);
  });
  gameInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") gameGuess();
  });
  btnGameNew.addEventListener("click", gameNew);
  btnGameGuess.addEventListener("click", gameGuess);
  btnGameAutoStep.addEventListener("click", gameAutoStep);
  btnGameAutoAll.addEventListener("click", gameAutoAll);
  gameHard.addEventListener("change", () => {
    if (gameActive) gameNew();
  });

  buildBoard();
  buildGameBoard();
  refresh().catch((e) => {
    statusEl.textContent = e.message;
  });
})();
