(function () {
    "use strict";

    const SVG_NS = "http://www.w3.org/2000/svg";
    const VISUAL_MODES = new Set(["NEUTRAL", "PRESSURE", "CHANCE", "GOAL"]);
    const MOVE_DURATION = { NEUTRAL: 1850, PRESSURE: 900, CHANCE: 700, GOAL: 950 };

    function marker(side, index) {
        const node = document.createElementNS(SVG_NS, "circle");
        node.setAttribute("r", index === 0 ? "2.1" : "1.75");
        node.setAttribute("class", `visual-player ${side}`);
        node.setAttribute("aria-hidden", "true");
        return node;
    }

    class MatchVisualizer {
        constructor(root) {
            this.root = root;
            this.pitch = root.querySelector(".visual-pitch");
            this.playerLayer = root.querySelector(".visual-players");
            this.ball = root.querySelector(".visual-ball");
            this.status = root.querySelector(".visual-status");
            this.teamALabel = root.querySelector(".visual-team-a-name");
            this.teamBLabel = root.querySelector(".visual-team-b-name");
            this.reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            this.players = { team_a: [], team_b: [] };
            for (const side of ["team_a", "team_b"]) {
                for (let index = 0; index < 11; index += 1) {
                    const node = marker(side, index);
                    this.playerLayer.append(node);
                    this.players[side].push(node);
                }
            }
            this.move(this.ball, 50, 30, "NEUTRAL");
        }

        configure(contract) {
            if (!contract || contract.schema_version !== 1) return;
            this.contract = contract;
            this.formations = contract.formations;
            this.animationTargets = contract.animation_targets || {};
            this.teamALabel.textContent = contract.teams.team_a.name;
            this.teamBLabel.textContent = contract.teams.team_b.name;
            for (const side of ["team_a", "team_b"]) {
                contract.formations[side].forEach((position, index) => {
                    this.players[side][index].dataset.role = position.role;
                });
            }
            this.root.classList.add("is-ready");
            this.showFrame(contract.frame, 0);
        }

        showFrame(frame = { mode: "NEUTRAL", attacking_side: null }, tick = 0) {
            const mode = VISUAL_MODES.has(frame.mode) ? frame.mode : "NEUTRAL";
            const attackingSide = frame.attacking_side || null;
            this.root.dataset.mode = mode.toLowerCase();
            this.root.dataset.attackingSide = attackingSide || "none";
            this.positionTeam("team_a", mode, attackingSide, tick);
            this.positionTeam("team_b", mode, attackingSide, tick);
            this.positionBall(mode, attackingSide, tick);
            this.describe(mode, attackingSide);
            if (mode === "GOAL") {
                this.pitch.classList.remove("goal-flash");
                void this.pitch.getBoundingClientRect();
                this.pitch.classList.add("goal-flash");
            }
        }

        advanceNeutral(tick) {
            this.showFrame({ mode: "NEUTRAL", attacking_side: null }, tick);
        }

        positionTeam(side, mode, attackingSide, tick) {
            const base = this.formations?.[side];
            if (!base) return;
            const targets = this.animationTargets?.[attackingSide]?.[mode]?.[side];
            base.forEach(({ x, y }, index) => {
                const phase = (tick * 0.83) + (index * 1.17) + (side === "team_b" ? 0.6 : 0);
                const neutralX = x + (Math.sin(phase) * (0.45 + ((index % 3) * 0.28)));
                const neutralY = y + (Math.cos(phase * 0.79) * (0.5 + ((index % 4) * 0.18)));
                const target = targets?.[index];
                const targetX = target ? target.x : neutralX;
                const targetY = target ? target.y : neutralY;
                const accent = target && mode !== "GOAL" ? Math.sin(phase) * 0.3 : 0;
                this.move(
                    this.players[side][index],
                    Math.max(2.5, Math.min(97.5, targetX + accent)),
                    Math.max(3, Math.min(57, targetY)),
                    mode,
                    index,
                );
            });
        }

        positionBall(mode, attackingSide, tick) {
            let x = 50 + Math.sin(tick * 0.9) * 3;
            let y = 30 + Math.cos(tick * 0.65) * 5;
            if (attackingSide) {
                const direction = attackingSide === "team_a" ? 1 : -1;
                const target = { PRESSURE: 67, CHANCE: 86, GOAL: 99.4 }[mode] || 50;
                x = direction === 1 ? target : 100 - target;
                y = mode === "GOAL" ? 30 : 25 + (tick % 3) * 5;
            }
            this.move(this.ball, x, y, mode);
        }

        move(node, x, y, mode, index = 0) {
            const next = `translate(${x}px, ${y}px)`;
            if (!this.reduceMotion && node.style.transform) {
                node.animate(
                    [{ transform: node.style.transform }, { transform: next }],
                    {
                        duration: (MOVE_DURATION[mode] || 800) + ((index % 4) * 65),
                        delay: (index % 3) * 28,
                        easing: mode === "GOAL" ? "cubic-bezier(.2,.8,.2,1)" : "ease-in-out",
                        fill: "forwards",
                    },
                );
            }
            node.style.transform = next;
        }

        describe(mode, attackingSide) {
            const teamName = attackingSide
                ? this.contract?.teams?.[attackingSide]?.name
                : null;
            const labels = {
                NEUTRAL: "Open play",
                PRESSURE: teamName ? `${teamName} applies pressure` : "Attacking pressure",
                CHANCE: teamName ? `Chance for ${teamName}` : "Chance",
                GOAL: teamName ? `Goal for ${teamName}` : "Goal",
            };
            if (this.status.textContent !== labels[mode]) {
                this.status.textContent = labels[mode];
            }
        }
    }

    window.MatchVisualizer = MatchVisualizer;
}());
