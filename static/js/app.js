const MS_PER_MATCH_MINUTE = 2400;
const AUTO_BREAK_SECONDS = 15;

const elements = {
    action: document.querySelector("#match-action"),
    setupAction: document.querySelector("#setup-action"),
    gameShell: document.querySelector(".game-shell"),
    matchCenter: document.querySelector("#match-center"),
    pauseAtBreaks: document.querySelector("#pause-at-breaks"),
    breakCountdown: document.querySelector("#break-countdown"),
    clock: document.querySelector("#match-clock"),
    errors: document.querySelectorAll("[data-action-error]"),
    providerStatuses: document.querySelectorAll("[data-provider-status]"),
    period: document.querySelector("#match-period"),
    progress: document.querySelector("#timeline-progress"),
    events: document.querySelector("#event-list"),
    decisions: document.querySelector("#decision-list"),
    usage: document.querySelector("#usage-summary"),
    teamSelection: document.querySelector("#team-selection"),
    teamOptions: document.querySelector("#team-options"),
    managerControls: document.querySelectorAll("[data-manager-controls]"),
    assistantRecommendations: document.querySelectorAll("[data-assistant-recommendation]"),
    managementYourTeam: document.querySelector("#management-your-team"),
    managementOpponent: document.querySelector("#management-opponent"),
    tacticOptions: document.querySelectorAll(".tactic-option"),
};

let currentState = null;
let playing = false;
let countdownTimer = null;
const matchVisualizer = window.MatchVisualizer
    ? new window.MatchVisualizer(document.querySelector("#match-visualizer"))
    : null;

function setText(id, value) {
    document.querySelector(`#${id}`).textContent = value;
}

function showError(message) {
    for (const output of elements.errors) {
        output.textContent = message;
        output.hidden = false;
    }
}

function clearErrors() {
    for (const output of elements.errors) output.hidden = true;
}

function renderTeam(prefix, team, energy = team.average_energy) {
    setText(`${prefix}-name`, team.name);
    setText(`${prefix}-tactic`, team.tactic);
    setText(`${prefix}-energy-text`, `${Math.round(energy)}%`);
    document.querySelector(`#${prefix}-energy-bar`).style.width = `${energy}%`;
}

function teamOption(option, selectedSide) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "team-option";
    button.classList.toggle("is-selected", option.side === selectedSide);
    button.setAttribute("aria-pressed", String(option.side === selectedSide));
    const name = document.createElement("strong");
    const details = document.createElement("small");
    name.textContent = option.name;
    details.textContent = `Strength ${option.base_strength} · ${option.squad_size} players`;
    button.append(name, details);
    button.addEventListener("click", () => selectTeam(option.side));
    return button;
}

function renderTeamSelection(state) {
    const selection = state.team_selection;
    const selectedSide = selection.selected_side;
    elements.teamSelection.hidden = state.phase !== "NOT_STARTED";
    elements.teamOptions.replaceChildren(
        ...selection.options.map((option) => teamOption(option, selectedSide)),
    );
    setText("team-a-role", selectedSide === "team_a" ? "Your Team" : selectedSide ? "Opponent" : "Available Team");
    setText("team-b-role", selectedSide === "team_b" ? "Your Team" : selectedSide ? "Opponent" : "Available Team");
    elements.managementYourTeam.textContent = selection.your_team?.name || "Not selected";
    elements.managementOpponent.textContent = selection.opponent?.name || "Not selected";
}

function renderManagerControls(state) {
    const manager = state.human_manager;
    const controlsActive = manager.team_side !== null && !state.is_full_time;
    for (const controls of elements.managerControls) {
        controls.classList.toggle("is-active", controlsActive);
        controls.setAttribute("aria-hidden", String(!controlsActive));
    }
    const recommendation = state.assistant_recommendation;
    for (const output of elements.assistantRecommendations) {
        output.textContent = recommendation
            ? `AI Assistant recommends: ${recommendation.tactic}`
            : "AI Assistant recommendation unavailable.";
    }
    for (const button of elements.tacticOptions) {
        button.classList.toggle("is-selected", button.dataset.tactic === manager.tactic);
        button.setAttribute("aria-pressed", String(button.dataset.tactic === manager.tactic));
        button.disabled = playing || !manager.can_choose_tactic;
    }
}

function renderMatchCenter(state) {
    const open = playing || state.phase !== "NOT_STARTED";
    elements.matchCenter.hidden = !open;
    elements.matchCenter.setAttribute("aria-hidden", String(!open));
    elements.gameShell.inert = open;
    document.body.classList.toggle("match-center-open", open);
}

function eventElement(event) {
    const item = document.createElement("li");
    item.classList.toggle("event-goal", event.type === "GOAL");
    item.classList.toggle("event-presentation", event.kind === "PRESENTATION");
    item.classList.toggle("event-milestone", event.type === "MILESTONE");
    const minute = document.createElement("span");
    minute.className = "event-minute";
    minute.textContent = event.display_minute;
    item.append(minute, document.createTextNode(event.text));
    return item;
}

function renderEvents(events, presentationStarted) {
    if (!events.length) {
        elements.events.innerHTML = presentationStarted
            ? '<li class="empty-state">Match underway. Waiting for the next event.</li>'
            : '<li class="empty-state">The match has not started.</li>';
        return;
    }
    elements.events.replaceChildren(...events.map(eventElement));
    elements.events.scrollTop = elements.events.scrollHeight;
}

function appendEvent(event) {
    elements.events.querySelector(".empty-state")?.remove();
    elements.events.append(eventElement(event));
    elements.events.scrollTop = elements.events.scrollHeight;
}

function decisionRow(title, name, decision) {
    const row = document.createElement("div");
    row.className = "decision";
    const label = document.createElement("div");
    const main = document.createElement("span");
    const hint = document.createElement("small");
    const value = document.createElement("strong");
    main.textContent = name;
    hint.textContent = title;
    value.textContent = decision;
    label.append(main, hint);
    row.append(label, value);
    return row;
}

function renderDecisions(state) {
    if (!state.coach_decisions || !state.footballer_decisions) {
        elements.decisions.innerHTML = '<p class="empty-state">Decisions will appear after the first block.</p>';
        return;
    }
    const coaches = state.coach_decisions;
    const players = state.footballer_decisions;
    elements.decisions.replaceChildren(
        decisionRow(coaches.team_a.role, coaches.team_a.team_name, coaches.team_a.tactic),
        decisionRow(coaches.team_b.role, coaches.team_b.team_name, coaches.team_b.tactic),
        decisionRow("Player", players.team_a.footballer_name, players.team_a.behavior),
        decisionRow("Player", players.team_b.footballer_name, players.team_b.behavior),
    );
}

function formatCost(cost) {
    return cost === null ? "Cost unavailable" : `$${Number(cost).toFixed(6)}`;
}

function renderAction(state) {
    if (state.can_start) {
        elements.action.textContent = "START MATCH";
        elements.action.dataset.endpoint = "/api/match/start";
    } else if (state.can_continue) {
        elements.action.textContent = "CONTINUE MATCH";
        elements.action.dataset.endpoint = "/api/match/continue";
    } else if (state.is_full_time) {
        elements.action.textContent = "NEW MATCH · EXIT MATCH CENTER";
        elements.action.dataset.endpoint = "/api/match/reset";
    } else {
        elements.action.textContent = state.team_selection.required
            ? "CHOOSE A TEAM"
            : "CHOOSE A TACTIC";
        delete elements.action.dataset.endpoint;
    }
    elements.action.disabled = !(state.can_start || state.can_continue || state.is_full_time);
}

function renderSetupAction(state) {
    if (state.can_start) {
        elements.setupAction.textContent = "START MATCH";
        elements.setupAction.dataset.endpoint = "/api/match/start";
    } else {
        elements.setupAction.textContent = state.team_selection.required
            ? "CHOOSE A TEAM"
            : "CHOOSE A TACTIC";
        delete elements.setupAction.dataset.endpoint;
    }
    elements.setupAction.disabled = !state.can_start;
}

function cancelBreakCountdown() {
    if (countdownTimer !== null) {
        window.clearInterval(countdownTimer);
        countdownTimer = null;
    }
    elements.breakCountdown.classList.remove("is-active");
    elements.breakCountdown.setAttribute("aria-hidden", "true");
}

function renderBreakControls(state) {
    const isBreak = !playing && state.can_continue && !state.is_full_time;
    if (!isBreak) cancelBreakCountdown();
}

function startBreakCountdown() {
    if (
        countdownTimer !== null
        || playing
        || !currentState?.can_continue
        || currentState.is_full_time
        || elements.pauseAtBreaks.checked
    ) return;

    let remaining = AUTO_BREAK_SECONDS;
    elements.breakCountdown.classList.add("is-active");
    elements.breakCountdown.setAttribute("aria-hidden", "false");
    elements.breakCountdown.textContent = `Match resumes in ${remaining}…`;
    elements.action.textContent = "AUTO-RESUME ACTIVE";
    elements.action.disabled = true;
    countdownTimer = window.setInterval(() => {
        remaining -= 1;
        elements.breakCountdown.textContent = `Match resumes in ${remaining}…`;
        if (remaining === 0) {
            cancelBreakCountdown();
            runMatchAction("/api/match/continue");
        }
    }, 1000);
}

function renderStatus(status = { provider: "FALLBACK", state: "DETERMINISTIC" }) {
    const provider = status.provider || "FALLBACK";
    const state = status.state || "DETERMINISTIC";
    const style = state === "ACTIVE"
        ? "status-active"
        : state === "ERROR"
            ? "status-error"
            : state === "DETERMINISTIC"
                ? "status-fallback"
                : "status-ready";
    for (const badge of elements.providerStatuses) {
        badge.textContent = `${provider}: ${state}`;
        badge.className = `provider-status ${style}`;
    }
}

function renderState(state, display = {}) {
    currentState = state;
    document.body.classList.toggle("match-setup", state.phase === "NOT_STARTED");
    document.body.classList.toggle("match-live", state.phase !== "NOT_STARTED");
    renderMatchCenter(state);
    const score = display.score || state.score;
    const energy = display.energy || {
        team_a: state.team_a.average_energy,
        team_b: state.team_b.average_energy,
    };
    matchVisualizer?.configure(state.visualizer);
    renderTeamSelection(state);
    renderManagerControls(state);
    renderTeam("team-a", state.team_a, energy.team_a);
    renderTeam("team-b", state.team_b, energy.team_b);
    setText("team-a-score", score.team_a);
    setText("team-b-score", score.team_b);
    elements.clock.textContent = display.clock || state.display_clock;
    elements.period.textContent = display.period || state.display_period;
    elements.progress.style.width = `${display.progress ?? state.progress_percent}%`;
    renderEvents(
        display.feed ?? state.presentation_feed,
        playing || state.presentation_started,
    );
    renderDecisions(state);
    elements.usage.textContent = `${state.usage.calls} calls · ${state.usage.total_tokens.toLocaleString()} tokens · ${formatCost(state.usage.estimated_cost)}`;
    renderStatus(state.provider_status);
    if (!playing) {
        renderAction(state);
        renderSetupAction(state);
    }
    renderBreakControls(state);
    if (!playing && state.can_continue && !elements.pauseAtBreaks.checked) {
        startBreakCountdown();
    }
}

async function selectTeam(side) {
    if (!currentState || playing || currentState.phase !== "NOT_STARTED") return;
    for (const button of elements.teamOptions.querySelectorAll("button")) {
        button.disabled = true;
    }
    try {
        const state = await fetchJson("/api/match/select-team", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ side }),
        });
        renderState(state);
    } catch (error) {
        showError(error.message);
        renderState(currentState);
    }
}

async function selectHumanTactic(tactic) {
    if (!currentState || playing || !currentState.human_manager.can_choose_tactic) return;
    for (const button of elements.tacticOptions) button.disabled = true;
    try {
        const state = await fetchJson("/api/match/human-tactic", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tactic }),
        });
        renderState(state);
    } catch (error) {
        showError(error.message);
        renderState(currentState);
    }
}

async function fetchJson(url, options = {}) {
    clearErrors();
    const response = await fetch(url, options);
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "The match action could not be completed.");
    }
    return response.json();
}

function playBlock(nextState) {
    const playback = nextState.playback;
    const visibleFeed = nextState.presentation_feed.filter(
        (event) => event.block_number < playback.block_number,
    );
    const visibleScore = { ...playback.start_score };
    playing = true;
    cancelBreakCountdown();
    elements.action.textContent = "MATCH IN PROGRESS…";
    elements.action.disabled = true;
    renderState(nextState, {
        score: visibleScore,
        energy: playback.start_energy,
        clock: playback.clocks[0],
        period: playback.status_label,
        progress: playback.start_progress,
        feed: visibleFeed,
    });
    matchVisualizer?.showFrame(nextState.visualizer.frame, 0);
    for (const event of playback.timeline.filter((item) => item.tick === 0)) {
        appendEvent(event);
        matchVisualizer?.showFrame(event.visual, 0);
    }

    return new Promise((resolve) => {
        let tick = 0;
        const timer = window.setInterval(() => {
            tick += 1;
            matchVisualizer?.advanceNeutral(tick);
            elements.clock.textContent = playback.clocks[tick - 1];
            elements.progress.style.width = `${playback.start_progress + tick}%`;
            for (const event of playback.timeline.filter((item) => item.tick === tick)) {
                appendEvent(event);
                matchVisualizer?.showFrame(event.visual, tick);
                if (event.score_after) {
                    visibleScore.team_a = event.score_after.team_a;
                    visibleScore.team_b = event.score_after.team_b;
                    setText("team-a-score", visibleScore.team_a);
                    setText("team-b-score", visibleScore.team_b);
                }
            }
            if (tick === playback.clocks.length) {
                window.clearInterval(timer);
                playing = false;
                renderState(nextState);
                resolve();
            }
        }, MS_PER_MATCH_MINUTE);
    });
}

async function runMatchAction(endpoint) {
    if (!currentState || playing || !endpoint) return;
    cancelBreakCountdown();
    elements.action.disabled = true;
    elements.setupAction.disabled = true;
    elements.action.textContent = endpoint.endsWith("reset") ? "RESETTING…" : "PREPARING MATCH…";
    elements.setupAction.textContent = endpoint.endsWith("reset") ? "RESETTING…" : "PREPARING MATCH…";
    try {
        const nextState = await fetchJson(endpoint, { method: "POST" });
        if (nextState.playback) {
            await playBlock(nextState);
        } else {
            renderState(nextState);
        }
    } catch (error) {
        showError(error.message);
        renderAction(currentState);
        renderSetupAction(currentState);
        renderBreakControls(currentState);
    }
}

elements.action.addEventListener("click", () => {
    runMatchAction(elements.action.dataset.endpoint);
});

elements.setupAction.addEventListener("click", () => {
    runMatchAction(elements.setupAction.dataset.endpoint);
});

for (const button of elements.tacticOptions) {
    button.addEventListener("click", () => selectHumanTactic(button.dataset.tactic));
}

elements.pauseAtBreaks.addEventListener("change", () => {
    if (playing || !currentState?.can_continue || currentState.is_full_time) return;
    if (elements.pauseAtBreaks.checked) {
        cancelBreakCountdown();
        renderAction(currentState);
    } else {
        startBreakCountdown();
    }
});

fetchJson("/api/match/state")
    .then(renderState)
    .catch((error) => {
        showError(error.message);
        elements.action.textContent = "RETRY";
        elements.action.disabled = false;
        elements.action.onclick = () => window.location.reload();
        elements.setupAction.textContent = "RETRY";
        elements.setupAction.disabled = false;
        elements.setupAction.onclick = () => window.location.reload();
    });
