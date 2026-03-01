/**
 * Murmur — Frontend API Logic
 * Fetches data from the Flask API and renders entry cards, search results,
 * stats, and tags dynamically. Each page initializer checks for the presence
 * of its container element before running.
 */

const API = localStorage.getItem("murmur_pi_url") || window.MURMUR_API || "";

// ─────────────────────────────────────────────────────────────────────────────
// API Key helper
// ─────────────────────────────────────────────────────────────────────────────

function getOpenAIKey() {
    return localStorage.getItem("murmur_openai_key") || "";
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return {
        day: String(d.getDate()).padStart(2, "0"),
        month: d.toLocaleString("en-US", { month: "short" }).toUpperCase(),
        time: d.toLocaleString("en-US", { hour: "numeric", minute: "2-digit", hour12: true }),
    };
}

function formatDuration(seconds) {
    if (!seconds) return null;
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
}

function getPreviewText(entry) {
    return entry.transcription || entry.notes || "";
}

function getTitle(entry) {
    const text = getPreviewText(entry);
    if (!text) return "Untitled memory";
    // Use first sentence or first ~60 chars
    const firstSentence = text.split(/[.!?]/)[0];
    return firstSentence.length > 60 ? firstSentence.substring(0, 60) + "..." : firstSentence;
}

function sourceLabel(entry) {
    const source = entry.source === "voice" ? "Voice" : "Written";
    const dur = formatDuration(entry.duration_seconds);
    return dur ? `${source} \u00B7 ${dur}` : source;
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared card renderers
// ─────────────────────────────────────────────────────────────────────────────

function renderTimelineCard(entry) {
    const { day, month, time } = formatDate(entry.created_at);
    const li = document.createElement("li");
    li.className = "cs-item";
    li.innerHTML = `
        <a href="/entry/?id=${entry.id}" class="cs-card-link">
            <div class="cs-date-block">
                <span class="cs-date-day">${day}</span>
                <span class="cs-date-month">${month}</span>
            </div>
            <div class="cs-text-box">
                <h3 class="cs-h3">${escapeHtml(getTitle(entry))}</h3>
                <div class="cs-details">
                    <span class="cs-date">${time}</span>
                    <span class="cs-source">${sourceLabel(entry)}</span>
                </div>
                <p class="cs-item-text">${escapeHtml(getPreviewText(entry))}</p>
            </div>
        </a>
    `;
    return li;
}

function renderSearchCard(entry) {
    const { day, month, time } = formatDate(entry.created_at);
    const li = document.createElement("li");
    li.className = "cs-result-item";
    li.innerHTML = `
        <a href="/entry/?id=${entry.id}" class="cs-card-link">
            <div class="cs-date-block">
                <span class="cs-date-day">${day}</span>
                <span class="cs-date-month">${month}</span>
            </div>
            <div class="cs-text-box">
                <h3 class="cs-h3">${escapeHtml(getTitle(entry))}</h3>
                <div class="cs-details">
                    <span class="cs-date">${time}</span>
                    <span class="cs-source">${sourceLabel(entry)}</span>
                </div>
                <p class="cs-item-text">${escapeHtml(getPreviewText(entry))}</p>
            </div>
        </a>
    `;
    return li;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ─────────────────────────────────────────────────────────────────────────────
// Timeline page
// ─────────────────────────────────────────────────────────────────────────────

async function initTimeline() {
    const container = document.getElementById("timeline-entries");
    const statsEl = document.getElementById("timeline-stats");
    if (!container) return;

    try {
        // Fetch entries and stats in parallel
        const [entriesRes, statsRes] = await Promise.all([
            fetch(`${API}/api/entries`),
            fetch(`${API}/api/stats`),
        ]);
        const entriesData = await entriesRes.json();
        const stats = await statsRes.json();

        // Render stats line
        if (statsEl) {
            statsEl.textContent = `${stats.total_entries} entries \u00B7 ${stats.total_favorites} favorites \u00B7 ${stats.streak} day streak`;
        }

        // Render entry cards
        container.innerHTML = "";
        for (const entry of entriesData.entries) {
            container.appendChild(renderTimelineCard(entry));
        }
    } catch (err) {
        if (statsEl) {
            statsEl.textContent = `API: ${API || "(empty)"} — Error: ${err.message}`;
            statsEl.style.color = "red";
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Search page
// ─────────────────────────────────────────────────────────────────────────────

let searchTimeout = null;

async function doSearch(query) {
    const container = document.getElementById("search-results");
    if (!container) return;

    if (!query) {
        container.innerHTML = "";
        return;
    }

    const res = await fetch(`${API}/api/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();

    container.innerHTML = "";
    if (data.entries.length === 0) {
        container.innerHTML = `<li class="cs-result-item"><div class="cs-text-box"><p class="cs-item-text">No memories found for "${escapeHtml(query)}"</p></div></li>`;
        return;
    }
    for (const entry of data.entries) {
        container.appendChild(renderSearchCard(entry));
    }
}

async function initSearch() {
    const form = document.getElementById("search-form");
    const input = document.getElementById("cs-search-input");
    const tagsContainer = document.querySelector("#search-tags .cs-tags");
    if (!form || !input) return;

    // Prevent form submission from reloading
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        doSearch(input.value.trim());
    });

    // Live search with debounce
    input.addEventListener("input", () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            doSearch(input.value.trim());
        }, 300);
    });

    // Load tags from API for quick filters
    if (tagsContainer) {
        const res = await fetch(`${API}/api/tags`);
        const data = await res.json();

        tagsContainer.innerHTML = "";
        for (const tag of data.tags) {
            const li = document.createElement("li");
            li.className = "cs-tag-item";
            const btn = document.createElement("button");
            btn.className = "cs-tag";
            btn.type = "button";
            btn.textContent = tag.name;
            btn.addEventListener("click", () => {
                input.value = tag.name;
                doSearch(tag.name);
            });
            li.appendChild(btn);
            tagsContainer.appendChild(li);
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// New Entry page
// ─────────────────────────────────────────────────────────────────────────────

let mediaRecorder = null;
let audioChunks = [];
let recordingStartTime = null;
let timerInterval = null;
let recordedBlob = null;
let recordedDuration = 0;
let selectedTags = [];

function updateTimer() {
    const timerEl = document.getElementById("record-timer");
    if (!timerEl || !recordingStartTime) return;
    const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
    const m = Math.floor(elapsed / 60);
    const s = elapsed % 60;
    timerEl.textContent = `${m}:${String(s).padStart(2, "0")}`;
}

async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    // Pick a format the browser supports — prefer mp4 (Safari) then webm (Chrome/Firefox)
    const mimeType = MediaRecorder.isTypeSupported("audio/mp4") ? "audio/mp4"
        : MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm"
        : "";
    mediaRecorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.addEventListener("dataavailable", (e) => {
        audioChunks.push(e.data);
    });

    mediaRecorder.addEventListener("stop", () => {
        // Stop all tracks so the mic indicator goes away
        stream.getTracks().forEach((t) => t.stop());

        recordedBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
        recordedDuration = Math.round((Date.now() - recordingStartTime) / 1000);

        // Show playback
        const playback = document.getElementById("playback");
        const preview = document.getElementById("audio-preview");
        if (playback && preview) {
            preview.src = URL.createObjectURL(recordedBlob);
            playback.style.display = "";
        }

        const label = document.getElementById("record-label");
        if (label) label.textContent = "Recording saved";
    });

    mediaRecorder.start();
    recordingStartTime = Date.now();
    timerInterval = setInterval(updateTimer, 1000);

    const btn = document.getElementById("record-btn");
    const label = document.getElementById("record-label");
    if (btn) btn.classList.add("cs-recording");
    if (label) label.textContent = "Recording... tap to stop";
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
    }
    clearInterval(timerInterval);

    const btn = document.getElementById("record-btn");
    if (btn) btn.classList.remove("cs-recording");
}

function discardRecording() {
    recordedBlob = null;
    recordedDuration = 0;
    audioChunks = [];

    const playback = document.getElementById("playback");
    const preview = document.getElementById("audio-preview");
    const timer = document.getElementById("record-timer");
    const label = document.getElementById("record-label");

    if (playback) playback.style.display = "none";
    if (preview) preview.src = "";
    if (timer) timer.textContent = "0:00";
    if (label) label.textContent = "Tap to record";
}

function renderSelectedTags() {
    const container = document.getElementById("selected-tags");
    if (!container) return;
    container.innerHTML = "";
    for (const tag of selectedTags) {
        const pill = document.createElement("button");
        pill.type = "button";
        pill.className = "cs-tag-pill";
        pill.innerHTML = `${escapeHtml(tag)}<span class="cs-tag-remove">&times;</span>`;
        pill.addEventListener("click", () => {
            selectedTags = selectedTags.filter((t) => t !== tag);
            renderSelectedTags();
        });
        container.appendChild(pill);
    }
}

async function saveEntry() {
    const statusEl = document.getElementById("save-status");
    const saveBtn = document.getElementById("save-btn");
    const voicePanel = document.getElementById("voice-panel");
    const isVoice = voicePanel && voicePanel.style.display !== "none";

    if (statusEl) statusEl.textContent = "Saving...";
    if (saveBtn) saveBtn.disabled = true;

    try {
        let res;
        if (isVoice) {
            if (!recordedBlob) {
                if (statusEl) statusEl.textContent = "Record something first!";
                if (saveBtn) saveBtn.disabled = false;
                return;
            }
            // Voice entry — upload audio as multipart form
            const formData = new FormData();
            const ext = recordedBlob.type.includes("mp4") ? "m4a" : "webm";
            formData.append("audio", recordedBlob, `recording.${ext}`);
            formData.append("source", "web-audio");
            formData.append("duration", String(recordedDuration));
            const voiceNotes = document.getElementById("voice-notes")?.value.trim();
            if (voiceNotes) formData.append("notes", voiceNotes);
            if (selectedTags.length) formData.append("tags", selectedTags.join(","));

            const voiceHeaders = {};
            const apiKey = getOpenAIKey();
            if (apiKey) voiceHeaders["X-OpenAI-Key"] = apiKey;

            res = await fetch(`${API}/api/entries`, {
                method: "POST",
                headers: voiceHeaders,
                body: formData,
            });
        } else {
            // Text entry — send JSON
            const notes = document.getElementById("entry-notes")?.value.trim();
            if (!notes) {
                if (statusEl) statusEl.textContent = "Write something first!";
                if (saveBtn) saveBtn.disabled = false;
                return;
            }
            const jsonHeaders = { "Content-Type": "application/json" };
            const textApiKey = getOpenAIKey();
            if (textApiKey) jsonHeaders["X-OpenAI-Key"] = textApiKey;

            res = await fetch(`${API}/api/entries`, {
                method: "POST",
                headers: jsonHeaders,
                body: JSON.stringify({
                    notes: notes,
                    source: "web",
                    tags: selectedTags,
                }),
            });
        }

        if (res.ok) {
            if (statusEl) statusEl.textContent = "Memory saved!";
            // Redirect to timeline after short delay
            setTimeout(() => {
                window.location.href = "/";
            }, 1000);
        } else {
            let errBody = "";
            try { errBody = await res.text(); } catch (_) {}
            console.error("Save failed:", res.status, res.statusText, errBody);
            if (statusEl) statusEl.textContent = `Save failed (${res.status}). Check console for details.`;
            if (saveBtn) saveBtn.disabled = false;
        }
    } catch (err) {
        console.error("Save error:", err);
        if (statusEl) statusEl.textContent = `Connection error: ${err.message}`;
        if (saveBtn) saveBtn.disabled = false;
    }
}

async function initNewEntry() {
    const recordBtn = document.getElementById("record-btn");
    if (!recordBtn) return;

    const discardBtn = document.getElementById("discard-btn");
    const saveBtn = document.getElementById("save-btn");
    const modeVoice = document.getElementById("mode-voice");
    const modeType = document.getElementById("mode-type");
    const voicePanel = document.getElementById("voice-panel");
    const typePanel = document.getElementById("type-panel");
    const voiceNotesGroup = document.getElementById("voice-notes-group");
    const tagInput = document.getElementById("tag-input");
    const suggestedContainer = document.getElementById("suggested-tags");

    // Load daily prompt
    try {
        const promptRes = await fetch(`${API}/api/prompt`);
        const prompt = await promptRes.json();
        const promptText = document.querySelector("#daily-prompt .cs-prompt-text");
        if (promptText && prompt.text) {
            promptText.textContent = `"${prompt.text}"`;
        }
    } catch (_) {}

    // Load existing tags as suggestions
    try {
        const tagsRes = await fetch(`${API}/api/tags`);
        const tagsData = await tagsRes.json();
        if (suggestedContainer && tagsData.tags.length) {
            for (const tag of tagsData.tags) {
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "cs-suggestion";
                btn.textContent = tag.name;
                btn.addEventListener("click", () => {
                    if (!selectedTags.includes(tag.name)) {
                        selectedTags.push(tag.name);
                        renderSelectedTags();
                    }
                });
                suggestedContainer.appendChild(btn);
            }
        }
    } catch (_) {}

    // Mode toggle
    modeVoice.addEventListener("click", () => {
        modeVoice.classList.add("cs-active");
        modeType.classList.remove("cs-active");
        voicePanel.style.display = "";
        typePanel.style.display = "none";
        voiceNotesGroup.style.display = "";
    });
    modeType.addEventListener("click", () => {
        modeType.classList.add("cs-active");
        modeVoice.classList.remove("cs-active");
        typePanel.style.display = "";
        voicePanel.style.display = "none";
        voiceNotesGroup.style.display = "none";
    });

    // Record button
    recordBtn.addEventListener("click", () => {
        if (mediaRecorder && mediaRecorder.state === "recording") {
            stopRecording();
        } else {
            discardRecording();
            startRecording();
        }
    });

    // Discard
    discardBtn.addEventListener("click", discardRecording);

    // Tag input
    tagInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            const val = tagInput.value.trim().replace(/,/g, "");
            if (val && !selectedTags.includes(val.toLowerCase())) {
                selectedTags.push(val.toLowerCase());
                renderSelectedTags();
            }
            tagInput.value = "";
        }
    });

    // Save
    saveBtn.addEventListener("click", saveEntry);
}

// ─────────────────────────────────────────────────────────────────────────────
// Entry Detail page
// ─────────────────────────────────────────────────────────────────────────────

async function initEntryDetail() {
    const container = document.getElementById("entry-content");
    const statusEl = document.getElementById("entry-status");
    if (!container || !statusEl) return;

    const id = new URLSearchParams(window.location.search).get("id");
    if (!id) {
        statusEl.textContent = "No entry specified.";
        return;
    }

    try {
        const res = await fetch(`${API}/api/entries/${id}`);
        if (!res.ok) {
            statusEl.textContent = res.status === 404 ? "Entry not found." : `Error loading entry (${res.status}).`;
            return;
        }

        const entry = await res.json();
        const { day, month, time } = formatDate(entry.created_at);

        // Date header
        document.getElementById("entry-day").textContent = day;
        document.getElementById("entry-month").textContent = month;
        document.getElementById("entry-time").textContent = time;
        document.getElementById("entry-source").textContent = sourceLabel(entry);
        document.getElementById("entry-title").textContent = getTitle(entry);

        // Audio player
        if (entry.audio_filename) {
            const audioSection = document.getElementById("entry-audio");
            const player = document.getElementById("entry-player");
            player.src = `${API}/api/audio/${entry.audio_filename}`;
            audioSection.style.display = "";
        }

        // Transcription (with polling for pending status)
        const transcriptionSection = document.getElementById("entry-transcription-section");
        const transcriptionEl = document.getElementById("entry-transcription");

        function showTranscription(e) {
            if (e.transcription) {
                transcriptionEl.textContent = e.transcription;
                transcriptionSection.style.display = "";
            } else if (e.transcription_status === "pending") {
                transcriptionEl.textContent = "Transcribing...";
                transcriptionSection.style.display = "";
            } else if (e.transcription_status === "failed") {
                transcriptionEl.textContent = "Transcription failed.";
                transcriptionSection.style.display = "";
            }
        }
        showTranscription(entry);

        if (entry.transcription_status === "pending") {
            const pollInterval = setInterval(async () => {
                try {
                    const pollRes = await fetch(`${API}/api/entries/${id}`);
                    if (!pollRes.ok) return;
                    const updated = await pollRes.json();
                    showTranscription(updated);
                    if (updated.transcription_status !== "pending") {
                        clearInterval(pollInterval);
                    }
                } catch (_) {}
            }, 3000);
        }

        // Notes
        if (entry.notes) {
            const section = document.getElementById("entry-notes-section");
            document.getElementById("entry-notes").textContent = entry.notes;
            section.style.display = "";
        }

        // Tags
        if (entry.tags && entry.tags.length) {
            const section = document.getElementById("entry-tags-section");
            const tagList = document.getElementById("entry-tags");
            tagList.innerHTML = "";
            for (const tag of entry.tags) {
                const pill = document.createElement("span");
                pill.className = "cs-tag-pill";
                pill.textContent = tag;
                tagList.appendChild(pill);
            }
            section.style.display = "";
        }

        // Favorite toggle
        const favBtn = document.getElementById("entry-favorite-btn");
        const heart = document.getElementById("entry-heart");
        const favLabel = document.getElementById("entry-favorite-label");

        function updateFavoriteUI(isFav) {
            heart.setAttribute("fill", isFav ? "currentColor" : "none");
            favBtn.classList.toggle("cs-active", !!isFav);
            favLabel.textContent = isFav ? "Favorited" : "Favorite";
        }
        updateFavoriteUI(entry.is_favorite);

        favBtn.addEventListener("click", async () => {
            favBtn.disabled = true;
            try {
                const r = await fetch(`${API}/api/entries/${id}/favorite`, { method: "POST" });
                const updated = await r.json();
                updateFavoriteUI(updated.is_favorite);
            } catch (err) {
                console.error("Favorite toggle failed:", err);
            }
            favBtn.disabled = false;
        });

        // Delete
        document.getElementById("entry-delete-btn").addEventListener("click", async () => {
            if (!confirm("Delete this memory? This cannot be undone.")) return;
            try {
                await fetch(`${API}/api/entries/${id}`, { method: "DELETE" });
                window.location.href = "/";
            } catch (err) {
                console.error("Delete failed:", err);
            }
        });

        // Show content, hide loading
        statusEl.style.display = "none";
        container.style.display = "";
    } catch (err) {
        console.error("Entry load error:", err);
        statusEl.textContent = `Connection error: ${err.message}`;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Settings page
// ─────────────────────────────────────────────────────────────────────────────

async function initSettings() {
    const keyInput = document.getElementById("openai-key");
    if (!keyInput) return;

    const saveBtn = document.getElementById("save-key-btn");
    const statusEl = document.getElementById("key-status");
    const toggleBtn = document.getElementById("toggle-key-vis");

    // --- Pi Address ---
    const piInput = document.getElementById("pi-url");
    const piSaveBtn = document.getElementById("save-pi-btn");
    const piStatus = document.getElementById("pi-status");

    if (piInput) {
        const existingPi = localStorage.getItem("murmur_pi_url") || "";
        if (existingPi) piInput.value = existingPi;

        piSaveBtn.addEventListener("click", async () => {
            const url = piInput.value.trim().replace(/\/+$/, ""); // strip trailing slash
            piSaveBtn.disabled = true;

            if (!url) {
                localStorage.removeItem("murmur_pi_url");
                if (piStatus) {
                    piStatus.textContent = "Cleared — using same-host API.";
                    piStatus.style.color = "";
                }
                piSaveBtn.disabled = false;
                return;
            }

            // Test connection
            if (piStatus) {
                piStatus.textContent = "Testing connection...";
                piStatus.style.color = "";
            }
            try {
                const res = await fetch(`${url}/api/stats`, { signal: AbortSignal.timeout(5000) });
                if (res.ok) {
                    localStorage.setItem("murmur_pi_url", url);
                    if (piStatus) {
                        piStatus.textContent = "Connected! Pi address saved.";
                        piStatus.style.color = "var(--secondary)";
                    }
                } else {
                    if (piStatus) {
                        piStatus.textContent = `Error: server returned ${res.status}`;
                        piStatus.style.color = "var(--error, #e74c3c)";
                    }
                }
            } catch (err) {
                if (piStatus) {
                    piStatus.textContent = `Connection failed: ${err.message}`;
                    piStatus.style.color = "var(--error, #e74c3c)";
                }
            }
            piSaveBtn.disabled = false;
        });
    }

    // --- OpenAI Key ---

    // Load existing key from localStorage, or show server-persisted key as placeholder
    const existing = getOpenAIKey();
    if (existing) {
        keyInput.value = existing;
    } else {
        try {
            const res = await fetch(`${API}/api/settings/openai-key`);
            const data = await res.json();
            if (data.masked_key) {
                keyInput.placeholder = `${data.masked_key} (saved on Pi)`;
            }
        } catch (_) {}
    }

    // Show/hide toggle
    toggleBtn.addEventListener("click", () => {
        const isPassword = keyInput.type === "password";
        keyInput.type = isPassword ? "text" : "password";
    });

    // Save — persist to both localStorage and Pi
    saveBtn.addEventListener("click", async () => {
        const key = keyInput.value.trim();
        if (key) {
            localStorage.setItem("murmur_openai_key", key);
            try {
                await fetch(`${API}/api/settings/openai-key`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ key }),
                });
                if (statusEl) statusEl.textContent = "Key saved (browser + Pi).";
            } catch (_) {
                if (statusEl) statusEl.textContent = "Key saved (browser only — couldn't reach Pi).";
            }
        } else {
            localStorage.removeItem("murmur_openai_key");
            if (statusEl) statusEl.textContent = "Key removed.";
        }
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// WiFi management (settings page)
// ─────────────────────────────────────────────────────────────────────────────

async function initWiFi() {
    const section = document.getElementById("wifi-section");
    if (!section) return;

    // Probe the WiFi API — if it fails, we're not on the Pi, so hide the section
    try {
        const probe = await fetch(`${API}/api/wifi/status`, { signal: AbortSignal.timeout(3000) });
        if (!probe.ok) return;
        const status = await probe.json();
        section.style.display = "";
        renderWiFiStatus(status);
    } catch (_) {
        return; // Not on Pi or API unreachable — keep section hidden
    }

    // Scan button
    const scanBtn = document.getElementById("wifi-scan-btn");
    scanBtn.addEventListener("click", async () => {
        scanBtn.disabled = true;
        scanBtn.textContent = "Scanning...";
        try {
            const res = await fetch(`${API}/api/wifi/scan`);
            const data = await res.json();
            renderWiFiNetworks(data.networks);
        } catch (err) {
            console.error("WiFi scan error:", err);
        }
        scanBtn.disabled = false;
        scanBtn.textContent = "Scan for Networks";
    });

    // Load saved networks
    loadSavedNetworks();

    // Password modal handlers
    const modal = document.getElementById("wifi-modal");
    const modalCancel = document.getElementById("wifi-modal-cancel");
    const modalConnect = document.getElementById("wifi-modal-connect");
    const modalPassword = document.getElementById("wifi-password");
    const modalStatus = document.getElementById("wifi-modal-status");

    modalCancel.addEventListener("click", () => {
        modal.style.display = "none";
        modalPassword.value = "";
        modalStatus.textContent = "";
    });

    modalConnect.addEventListener("click", async () => {
        const ssid = document.getElementById("wifi-modal-ssid").textContent;
        const password = modalPassword.value;
        if (!password) {
            modalStatus.textContent = "Password required.";
            return;
        }
        await doWiFiConnect(ssid, password, modalConnect, modalStatus);
    });

    modalPassword.addEventListener("keydown", (e) => {
        if (e.key === "Enter") modalConnect.click();
    });

    // Add network manually form
    const addBtn = document.getElementById("wifi-add-btn");
    const addForm = document.getElementById("wifi-add-form");
    const addSave = document.getElementById("wifi-add-save");
    const addCancel = document.getElementById("wifi-add-cancel");
    const addSSID = document.getElementById("wifi-add-ssid");
    const addPassword = document.getElementById("wifi-add-password");
    const addStatus = document.getElementById("wifi-add-status");

    addBtn.addEventListener("click", () => {
        addForm.style.display = "";
        addBtn.style.display = "none";
        addSSID.focus();
    });

    addCancel.addEventListener("click", () => {
        addForm.style.display = "none";
        addBtn.style.display = "";
        addSSID.value = "";
        addPassword.value = "";
        addStatus.textContent = "";
    });

    addSave.addEventListener("click", async () => {
        const ssid = addSSID.value.trim();
        if (!ssid) {
            addStatus.textContent = "Network name is required.";
            return;
        }
        addSave.disabled = true;
        addSave.textContent = "Saving...";
        addStatus.textContent = "";
        try {
            const body = { ssid };
            const pw = addPassword.value.trim();
            if (pw) body.password = pw;
            const res = await fetch(`${API}/api/wifi/add`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const data = await res.json();
            addStatus.textContent = data.message || (data.success ? "Saved!" : "Failed.");
            if (data.success) {
                addSSID.value = "";
                addPassword.value = "";
                loadSavedNetworks();
            }
        } catch (err) {
            addStatus.textContent = "Error saving network.";
        }
        addSave.disabled = false;
        addSave.textContent = "Save Network";
    });

    addPassword.addEventListener("keydown", (e) => {
        if (e.key === "Enter") addSave.click();
    });
}

function renderWiFiStatus(status) {
    const ssidEl = document.getElementById("wifi-ssid");
    const ipEl = document.getElementById("wifi-ip");
    const signalEl = document.getElementById("wifi-signal");

    if (status.active) {
        ssidEl.textContent = status.ssid || "Unknown";
        ipEl.textContent = status.ip || "--";
        signalEl.textContent = status.signal != null ? `${status.signal}%` : "--";
    } else {
        ssidEl.textContent = "Not connected";
        ipEl.textContent = "--";
        signalEl.textContent = "--";
    }
}

function renderWiFiNetworks(networks) {
    const container = document.getElementById("wifi-networks");
    container.style.display = "";
    container.innerHTML = "";

    if (!networks.length) {
        container.innerHTML = '<div class="wifi-network-item"><span class="wifi-network-name">No networks found</span></div>';
        return;
    }

    for (const net of networks) {
        const item = document.createElement("div");
        item.className = "wifi-network-item";
        item.innerHTML = `
            <div class="wifi-network-info">
                <span class="wifi-network-name">${escapeHtml(net.ssid)}</span>
                <span class="wifi-network-meta">${net.signal}% ${net.secured ? "&#x1f512;" : "Open"}</span>
            </div>
            <button class="wifi-connect-btn" type="button">Connect</button>
        `;
        item.querySelector(".wifi-connect-btn").addEventListener("click", () => {
            if (net.secured) {
                showPasswordModal(net.ssid);
            } else {
                doWiFiConnect(net.ssid, null, item.querySelector(".wifi-connect-btn"));
            }
        });
        container.appendChild(item);
    }
}

function showPasswordModal(ssid) {
    const modal = document.getElementById("wifi-modal");
    document.getElementById("wifi-modal-ssid").textContent = ssid;
    document.getElementById("wifi-password").value = "";
    document.getElementById("wifi-modal-status").textContent = "";
    modal.style.display = "";
}

async function doWiFiConnect(ssid, password, btn, statusEl) {
    const originalText = btn ? btn.textContent : "";
    if (btn) { btn.disabled = true; btn.textContent = "Connecting..."; }
    if (statusEl) statusEl.textContent = "Connecting...";

    // Warn user about potential disconnection
    const currentSSID = document.getElementById("wifi-ssid").textContent;
    if (currentSSID && currentSSID !== "Not connected" && currentSSID !== ssid) {
        if (!confirm(`Connecting to "${ssid}" will disconnect you from "${currentSSID}". You may need to reconnect your browser to the new network. Continue?`)) {
            if (btn) { btn.disabled = false; btn.textContent = originalText; }
            if (statusEl) statusEl.textContent = "";
            return;
        }
    }

    try {
        const body = { ssid };
        if (password) body.password = password;
        const res = await fetch(`${API}/api/wifi/connect`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (data.success) {
            if (statusEl) statusEl.textContent = "Connected!";
            // Close modal if open
            document.getElementById("wifi-modal").style.display = "none";
            // Refresh status and saved networks after a short delay
            setTimeout(async () => {
                try {
                    const statusRes = await fetch(`${API}/api/wifi/status`);
                    const status = await statusRes.json();
                    renderWiFiStatus(status);
                    loadSavedNetworks();
                } catch (_) {
                    // May have lost connection if network switched
                    renderWiFiStatus({ active: false });
                    if (statusEl) statusEl.textContent = "Connected, but browser may have lost access. Reconnect to the new network.";
                }
            }, 2000);
        } else {
            if (statusEl) statusEl.textContent = data.message || "Connection failed.";
        }
    } catch (err) {
        if (statusEl) statusEl.textContent = "Connection lost — you may need to reconnect to the new network.";
    }
    if (btn) { btn.disabled = false; btn.textContent = originalText; }
}

async function loadSavedNetworks() {
    try {
        const res = await fetch(`${API}/api/wifi/saved`);
        const data = await res.json();
        const section = document.getElementById("wifi-saved-section");
        const list = document.getElementById("wifi-saved-list");

        if (data.networks.length === 0) {
            section.style.display = "none";
            return;
        }

        section.style.display = "";
        list.innerHTML = "";
        for (const net of data.networks) {
            const item = document.createElement("div");
            item.className = "wifi-network-item";
            item.innerHTML = `
                <span class="wifi-network-name">${escapeHtml(net.ssid)}</span>
                <button class="wifi-forget-btn" type="button">Forget</button>
            `;
            item.querySelector(".wifi-forget-btn").addEventListener("click", async () => {
                if (!confirm(`Forget "${net.ssid}"? You'll need to re-enter the password to reconnect.`)) return;
                try {
                    await fetch(`${API}/api/wifi/forget`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ ssid: net.ssid }),
                    });
                    loadSavedNetworks();
                } catch (err) {
                    console.error("Forget network error:", err);
                }
            });
            list.appendChild(item);
        }
    } catch (_) {}
}

// ─────────────────────────────────────────────────────────────────────────────
// Init — run the right page initializer based on what's in the DOM
// ─────────────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    // First-run detection: if not on the Pi (no same-host API) and no Pi address configured, show setup
    const isCapacitor = window.location.protocol === "capacitor:" || window.location.protocol === "ionic:";
    const isLocalhost = window.location.hostname === "localhost" && !window.location.port;
    if ((isCapacitor || isLocalhost) && !localStorage.getItem("murmur_pi_url")) {
        const banner = document.getElementById("cap-setup-banner");
        if (banner) banner.style.display = "";
    }

    initTimeline();
    initSearch();
    initNewEntry();
    initEntryDetail();
    initSettings();
    initWiFi();
});
