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

function initSettings() {
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

    // Load existing key
    const existing = getOpenAIKey();
    if (existing) keyInput.value = existing;

    // Show/hide toggle
    toggleBtn.addEventListener("click", () => {
        const isPassword = keyInput.type === "password";
        keyInput.type = isPassword ? "text" : "password";
    });

    // Save
    saveBtn.addEventListener("click", () => {
        const key = keyInput.value.trim();
        if (key) {
            localStorage.setItem("murmur_openai_key", key);
            if (statusEl) statusEl.textContent = "Key saved.";
        } else {
            localStorage.removeItem("murmur_openai_key");
            if (statusEl) statusEl.textContent = "Key removed.";
        }
    });
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
});
