document.addEventListener("DOMContentLoaded", function () {
    const input = document.getElementById("guessInput");
    const popup = document.getElementById("rulesPopup");

    // --- Theme toggle switch ---
    const themeToggle = document.getElementById("themeToggle");
    if (themeToggle) {
        const saved = localStorage.getItem("theme");
        const isDark = saved ? saved === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
        themeToggle.checked = isDark;
        if (isDark) document.documentElement.classList.add("dark");
        themeToggle.addEventListener("change", function () {
            const nowDark = themeToggle.checked;
            document.documentElement.classList.toggle("dark", nowDark);
            localStorage.setItem("theme", nowDark ? "dark" : "light");
        });
    }

    if (input) {
        input.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
                document.getElementById("guessForm").submit();
            }
        });

        // Clickable keyboard letters
        document.querySelectorAll(".key[data-letter]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                if (input.value.length < 5) {
                    input.value += btn.dataset.letter;
                    input.focus();
                }
            });
        });

        // Backspace key
        const backspace = document.querySelector(".key-backspace");
        if (backspace) {
            backspace.addEventListener("click", function () {
                input.value = input.value.slice(0, -1);
                input.focus();
            });
        }

        // Auto-focus input on page load
        input.focus();
    }

    // Share button — copy results grid to clipboard
    const shareBtn = document.getElementById("shareBtn");
    if (shareBtn) {
        shareBtn.addEventListener("click", function () {
            const rows = document.querySelectorAll(".guess-table tr");
            let text = "Clay's Legally Distinct Wordle! " + rows.length + "/6\n\n";
            rows.forEach(function (row) {
                const tiles = row.querySelectorAll("td");
                let line = "";
                tiles.forEach(function (td) {
                    const bg = getComputedStyle(td).backgroundColor;
                    if (bg.includes("0, 128, 0") || bg === "rgb(0, 128, 0)") line += "\u{1F7E9}";       // green
                    else if (bg.includes("201, 180, 88") || bg === "rgb(201, 180, 88)") line += "\u{1F7E8}"; // yellow
                    else line += "\u2B1B"; // gray
                });
                text += line + "\n";
            });
            function showCopied() {
                shareBtn.textContent = "Copied! ✅";
                setTimeout(function () { shareBtn.textContent = "Copy Results 📋"; }, 2000);
            }
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(text).then(showCopied);
            } else {
                // Fallback for non-secure contexts (HTTP over LAN IP)
                var ta = document.createElement("textarea");
                ta.value = text;
                ta.style.position = "fixed";
                ta.style.opacity = "0";
                document.body.appendChild(ta);
                ta.select();
                document.execCommand("copy");
                document.body.removeChild(ta);
                showCopied();
            }
        });
    }

    const rulesBtn = document.getElementById("rulesBtn");
    if (rulesBtn && popup) {
        rulesBtn.addEventListener("click", function () {
            popup.classList.remove("hidden");
        });
    }

    const closeButton = document.getElementById("closePopup");
    if (closeButton && popup) {
        closeButton.addEventListener("click", function () {
            popup.classList.add("hidden");
        });
    }

    // --- Sonic idle animation state machine ---
    const sonic = document.querySelector(".sonic-topleft");
    if (sonic) {
        const TAP_GIF = "/static/sonictap.gif";
        const RUN_GIF = "/static/sonicrun.gif";
        const HOME_LEFT = 14;       // px, original position
        function getOffscreenLeft() {
            return window.innerWidth + 50; // past the right edge + small buffer
        }
        const IDLE_MS = 60000;      // 1 minute
        const RUN_DURATION_MS = 3000; // match CSS transition (3s)

        let state = "tapping"; // tapping | running_right | running_back
        let idleTimer = null;
        let runTimer = null;

        function resetIdleTimer() {
            clearTimeout(idleTimer);
            idleTimer = null;
        }

        function startIdleTimer() {
            resetIdleTimer();
            idleTimer = setTimeout(onIdle, IDLE_MS);
        }

        function onIdle() {
            if (state === "tapping") {
                // Run offscreen to the right
                state = "running_right";
                sonic.src = RUN_GIF;
                sonic.classList.add("running");
                sonic.classList.remove("flipped");
                sonic.style.left = getOffscreenLeft() + "px";
                // After the run animation + another minute idle, run back
                runTimer = setTimeout(function () {
                    if (state === "running_right") {
                        state = "running_back";
                        sonic.classList.add("flipped");
                        sonic.style.left = HOME_LEFT + "px";
                        // After arriving, resume tapping
                        runTimer = setTimeout(function () {
                            if (state === "running_back") {
                                state = "tapping";
                                sonic.src = TAP_GIF;
                                sonic.classList.remove("running");
                                sonic.classList.remove("flipped");
                                startIdleTimer();
                            }
                        }, RUN_DURATION_MS);
                    }
                }, IDLE_MS);
            }
            // If we're already running, the runTimer above handles it
        }

        function onActivity() {
            if (state === "running_right" || state === "running_back") {
                // User is active — cancel the run-back and snap back home
                clearTimeout(runTimer);
                state = "tapping";
                sonic.src = TAP_GIF;
                sonic.classList.remove("running");
                sonic.classList.remove("flipped");
                sonic.style.transition = "none";
                sonic.style.left = HOME_LEFT + "px";
                // Force reflow then restore transition
                void sonic.offsetWidth;
                sonic.style.transition = "";
            }
            startIdleTimer();
        }

        // Listen for any user activity
        document.addEventListener("click", onActivity);
        document.addEventListener("keydown", onActivity);
        document.addEventListener("mousemove", onActivity);
        document.addEventListener("touchstart", onActivity);

        startIdleTimer();
    }
});
