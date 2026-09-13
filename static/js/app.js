const MS_PER_MATCH_MINUTE = 2400;
const AUTO_BREAK_SECONDS = 15;

const elements = {
    action: document.querySelector("#match-action"),
    pauseAtBreaks: document.querySelector("#pause-at-breaks"),
    breakCountdown: document.querySelector("#break-countdown"),
    manageTeamArea: document.querySelector("#manage-team-area"),
    clock: document.querySelector("#match-clock"),
    error: document.querySelector("#action-error"),
    groqStatus: document.querySelector("#groq-status"),
    period: document.querySelector("#match-period"),
    progress: document.querySelector("#timeline-progress"),
    events: document.querySelector("#event-list"),
    decisions: document.querySelector("#decision-list"),
    usage: document.querySelector("#usage-summary"),
};

let currentState = null;
let playing = false;
let countdownTimer = null;

function setText(id, value) {
    document.querySelector(`#${id}`).textContent = value;
}

function renderTeam(prefix, team, energy = team.average_energy) {
    setText(`${prefix}-name`, team.name);
    setText(`${prefix}-tactic`, team.tactic);
    setText(`${prefix}-energy-text`, `${Math.round(energy)}%`);
    document.querySelector(`#${prefix}-energy-bar`).style.width = `${energy}%`;
}

function eventElement(event) {
    const item = document.createElement("li");
    item.classList.toggle("event-goal", event.type === "GOAL");
    item.classList.toggle("event-presentation", event.kind === "PRESENTATION");
    const minute = document.createElement("span");
    minute.className = "event-minute";
    minute.textContent = event.display_minute;
    item.append(minute, document.createTextNode(event.text));
    return item;
}

function renderEvents(events) {
    if (!events.length) {
        elements.events.innerHTML = '<li class="empty-state">The match has not started.</li>';
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
        decisionRow("Coach", coaches.team_a.team_name, coaches.team_a.tactic),
        decisionRow("Coach", coaches.team_b.team_name, coaches.team_b.tactic),
        decisionRow("Footballer", players.team_a.footballer_name, players.team_a.behavior),
        decisionRow("Footballer", players.team_b.footballer_name, players.team_b.behavior),
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
        elements.action.textContent = "NEW MATCH";
        elements.action.dataset.endpoint = "/api/match/reset";
    }
    elements.action.disabled = !(state.can_start || state.can_continue || state.is_full_time);
}

function cancelBreakCountdown() {
    if (countdownTimer !== null) {
        window.clearInterval(countdownTimer);
        countdownTimer = null;
    }
    elements.breakCountdown.hidden = true;
}

function renderBreakControls(state) {
    const isBreak = !playing && state.can_continue && !state.is_full_time;
    elements.manageTeamArea.hidden = !isBreak;
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
    elements.breakCountdown.hidden = false;
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

function renderStatus(status) {
    const labels = {
        CONNECTED: "Groq: Connected",
        NOT_CONFIGURED: "Groq: Not configured",
        ERROR: "Groq: Error",
    };
    elements.groqStatus.textContent = labels[status] || "Groq: Not configured";
    const style = status === "CONNECTED" ? "status-connected" : status === "ERROR" ? "status-error" : "status-neutral";
    elements.groqStatus.className = `provider-status ${style}`;
}

function renderState(state, display = {}) {
    currentState = state;
    const score = display.score || state.score;
    const energy = display.energy || {
        team_a: state.team_a.average_energy,
        team_b: state.team_b.average_energy,
    };
    renderTeam("team-a", state.team_a, energy.team_a);
    renderTeam("team-b", state.team_b, energy.team_b);
    setText("team-a-score", score.team_a);
    setText("team-b-score", score.team_b);
    elements.clock.textContent = display.clock || state.display_clock;
    elements.period.textContent = display.period || state.display_period;
    elements.progress.style.width = `${display.progress ?? state.progress_percent}%`;
    renderEvents(display.feed || state.presentation_feed);
    renderDecisions(state);
    elements.usage.textContent = `${state.usage.calls} calls · ${state.usage.total_tokens.toLocaleString()} tokens · ${formatCost(state.usage.estimated_cost)}`;
    renderStatus(state.groq_status);
    if (!playing) renderAction(state);
    renderBreakControls(state);
    if (!playing && state.can_continue && !elements.pauseAtBreaks.checked) {
        startBreakCountdown();
    }
}

async function fetchJson(url, options = {}) {
    elements.error.hidden = true;
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

    return new Promise((resolve) => {
        let tick = 0;
        const timer = window.setInterval(() => {
            tick += 1;
            elements.clock.textContent = playback.clocks[tick - 1];
            elements.progress.style.width = `${playback.start_progress + tick}%`;
            for (const event of playback.timeline.filter((item) => item.tick === tick)) {
                appendEvent(event);
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
    elements.manageTeamArea.hidden = true;
    elements.action.disabled = true;
    elements.action.textContent = endpoint.endsWith("reset") ? "RESETTING…" : "PREPARING MATCH…";
    try {
        const nextState = await fetchJson(endpoint, { method: "POST" });
        if (nextState.playback) {
            await playBlock(nextState);
        } else {
            renderState(nextState);
        }
    } catch (error) {
        elements.error.textContent = error.message;
        elements.error.hidden = false;
        renderAction(currentState);
        renderBreakControls(currentState);
    }
}

elements.action.addEventListener("click", () => {
    runMatchAction(elements.action.dataset.endpoint);
});

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
        elements.error.textContent = error.message;
        elements.error.hidden = false;
        elements.action.textContent = "RETRY";
        elements.action.disabled = false;
        elements.action.onclick = () => window.location.reload();
    });
