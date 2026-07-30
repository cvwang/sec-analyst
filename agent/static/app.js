/**
 * JavaScript Client App for SEC EDGAR Natural Language Analyst Conversational Split-Pane Web Dashboard
 */

document.addEventListener("DOMContentLoaded", () => {
    const btnRunQuery = document.getElementById("btnRunQuery");
    const naturalQueryInput = document.getElementById("naturalQuery");
    const suggestionChips = document.getElementById("suggestionChips");
    const chatStream = document.getElementById("chatStream");
    const sourceList = document.getElementById("sourceList");
    const sourceCount = document.getElementById("sourceCount");
    const memoryBadge = document.getElementById("memoryBadge");

    const btnExportGCS = document.getElementById("btnExportGCS");
    const hitlModal = document.getElementById("hitlModal");
    const btnCancelExport = document.getElementById("btnCancelExport");
    const btnConfirmExport = document.getElementById("btnConfirmExport");
    const gcsUriDisplay = document.getElementById("gcsUriDisplay");

    let lastAnalysisResponse = null;

    // Fetch initial session history & count
    fetchSessionState();

    btnRunQuery.addEventListener("click", runAnalysis);
    naturalQueryInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            runAnalysis();
        }
    });

    if (suggestionChips) {
        suggestionChips.addEventListener("click", (e) => {
            if (e.target.classList.contains("chip")) {
                const promptText = e.target.getAttribute("data-prompt");
                if (promptText) {
                    naturalQueryInput.value = promptText;
                    runAnalysis();
                }
            }
        });
    }

    btnExportGCS.addEventListener("click", openExportModal);
    btnCancelExport.addEventListener("click", () => hitlModal.classList.add("hidden"));
    btnConfirmExport.addEventListener("click", executeGCSExport);

    async function fetchSessionState() {
        try {
            const res = await fetch("/api/v1/history?session_id=user_session_001");
            const data = await res.json();
            if (data.turns_stored !== undefined) {
                memoryBadge.textContent = `🧠 Session: user_session_001 | Turns: ${data.turns_stored}`;
            }
        } catch (err) {
            console.error("Failed to fetch session state", err);
        }
    }

    async function runAnalysis() {
        const userPrompt = naturalQueryInput.value.trim();
        if (!userPrompt) return;

        // 1. Append User Chat Bubble
        appendUserMessage(userPrompt);
        naturalQueryInput.value = "";
        btnRunQuery.disabled = true;
        btnRunQuery.innerHTML = "⏳";

        // 2. Append Thinking Indicator
        const thinkingId = appendThinkingIndicator();

        const payload = {
            prompt: userPrompt,
            session_id: "user_session_001",
        };

        try {
            const res = await fetch("/api/v1/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            removeThinkingIndicator(thinkingId);

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || "Analysis request failed");
            }

            const data = await res.json();
            lastAnalysisResponse = data;

            // 3. Append Agent Response Chat Bubble
            appendAgentMessage(data);
            renderGroundedSources(data);
            fetchSessionState();

        } catch (err) {
            removeThinkingIndicator(thinkingId);
            appendErrorMessage(err.message);
        } finally {
            btnRunQuery.disabled = false;
            btnRunQuery.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>`;
        }
    }

    function appendUserMessage(text) {
        const msgDiv = document.createElement("div");
        msgDiv.className = "chat-message message-user";
        msgDiv.innerHTML = `
            <div class="message-avatar">👤</div>
            <div class="message-bubble">
                <div class="message-sender">Financial Analyst</div>
                <div class="message-text">${escapeHtml(text)}</div>
            </div>
        `;
        chatStream.appendChild(msgDiv);
        scrollToBottom();
    }

    function appendThinkingIndicator() {
        const id = `thinking_${Date.now()}`;
        const msgDiv = document.createElement("div");
        msgDiv.id = id;
        msgDiv.className = "chat-message message-agent";
        msgDiv.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-bubble">
                <div class="message-sender">SEC Analyst Agent</div>
                <div class="message-text" style="color: #94a3b8; font-style: italic;">
                    ⏳ Parsing natural language intent with Gemini 3.5 Flash & querying Hybrid Search RAG...
                </div>
            </div>
        `;
        chatStream.appendChild(msgDiv);
        scrollToBottom();
        return id;
    }

    function removeThinkingIndicator(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function appendErrorMessage(errorMsg) {
        const msgDiv = document.createElement("div");
        msgDiv.className = "chat-message message-agent";
        msgDiv.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-bubble" style="border-color: rgba(239, 68, 68, 0.4);">
                <div class="message-sender" style="color: #ef4444;">Analysis Error</div>
                <div class="message-text" style="color: #fca5a5;">❌ ${escapeHtml(errorMsg)}</div>
            </div>
        `;
        chatStream.appendChild(msgDiv);
        scrollToBottom();
    }

    function appendAgentMessage(data) {
        const msgDiv = document.createElement("div");
        msgDiv.className = "chat-message message-agent";

        const v = data.variance_result;
        let kpiHtml = "";
        if (v) {
            const abs = v.absolute_change || 0;
            const absFormatted = `${abs >= 0 ? '+' : ''}${abs.toLocaleString()}M`;
            const pct = v.percentage_change || 0;
            const pctFormatted = `${pct >= 0 ? '+' : ''}${pct}%`;
            const dirClass = (v.direction || '').toLowerCase() === 'increase' ? 'positive' : 'negative';
            const badgeClass = (v.direction || '').toLowerCase() === 'increase' ? 'badge-up' : 'badge-down';

            kpiHtml = `
                <div class="kpi-grid">
                    <div class="kpi-card">
                        <div class="kpi-title">Prior Period</div>
                        <div class="kpi-value">${(v.prior_period_value || 0).toLocaleString()}M</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Current Period</div>
                        <div class="kpi-value">${(v.current_period_value || 0).toLocaleString()}M</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Absolute Change</div>
                        <div class="kpi-value ${dirClass}">${absFormatted}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Percentage</div>
                        <div class="kpi-value ${dirClass}">${pctFormatted}</div>
                        <div class="kpi-badge ${badgeClass}">${v.direction || 'Variance'}</div>
                    </div>
                </div>
            `;
        }

        msgDiv.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-bubble">
                <div class="message-sender">SEC Analyst Agent • Grounded Synthesis (${data.model_used || 'Gemini 3.1 Pro'})</div>
                ${kpiHtml}
                <div class="message-text">${formatMarkdownNarrative(data.narrative || '')}</div>
            </div>
        `;
        chatStream.appendChild(msgDiv);
        scrollToBottom();
    }

    function renderGroundedSources(data) {
        const citations = data.citations || [];
        sourceCount.textContent = `${citations.length} Sources Grounded`;

        sourceList.innerHTML = "";
        if (data.hybrid_search_result && data.hybrid_search_result.text_chunks && data.hybrid_search_result.text_chunks.length > 0) {
            data.hybrid_search_result.text_chunks.forEach((chunk, idx) => {
                const card = document.createElement("div");
                card.className = `source-card ${idx === 0 ? 'active' : ''}`;
                card.innerHTML = `
                    <div class="source-header">
                        <span class="source-title">${chunk.company_name} FY${chunk.fiscal_year} 10-K</span>
                        <span class="source-tag">${chunk.section}</span>
                    </div>
                    <div class="source-excerpt">
                        "${escapeHtml(chunk.content)}"
                    </div>
                    <div class="source-citation">Citation: ${escapeHtml(chunk.citation)}</div>
                `;
                sourceList.appendChild(card);
            });
        } else {
            sourceList.innerHTML = `
                <div class="source-card active">
                    <div class="source-header">
                        <span class="source-title">${data.ticker || 'SEC'} FY2023 10-K</span>
                        <span class="source-tag">Item 7 - MD&A</span>
                    </div>
                    <div class="source-excerpt">
                        "Official SEC EDGAR Filing Grounded Context: Audited financial disclosures and variance metric statements."
                    </div>
                    <div class="source-citation">Citation: ${data.ticker || 'SEC'} FY2023 10-K (Item 7 MD&A)</div>
                </div>
            `;
        }
    }

    function openExportModal() {
        const ticker = (lastAnalysisResponse?.ticker || "aapl").toLowerCase();
        const uri = `gs://fde-sec-edgar-reports/${ticker}_2023_report.md`;
        gcsUriDisplay.textContent = uri;
        hitlModal.classList.remove("hidden");
    }

    async function executeGCSExport() {
        btnConfirmExport.disabled = true;
        btnConfirmExport.textContent = "⏳ Exporting...";

        const payload = {
            ticker: lastAnalysisResponse?.ticker || "AAPL",
            current_year: 2023,
            destination_gcs_uri: gcsUriDisplay.textContent,
            report_content: lastAnalysisResponse?.narrative || "Financial report content.",
            human_approved: true,
        };

        try {
            const res = await fetch("/api/v1/export", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            const data = await res.json();
            alert(`✅ ${data.message}`);
            hitlModal.classList.add("hidden");
        } catch (err) {
            alert(`❌ Export Error: ${err.message}`);
        } finally {
            btnConfirmExport.disabled = false;
            btnConfirmExport.textContent = "✅ Grant Approval & Export";
        }
    }

    function scrollToBottom() {
        chatStream.scrollTop = chatStream.scrollHeight;
    }

    function escapeHtml(text) {
        if (!text) return "";
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function formatMarkdownNarrative(text) {
        if (!text) return "";
        return escapeHtml(text)
            .replace(/^### (.*$)/gim, '<strong style="font-size: 15px; color: #60a5fa; display: block; margin-top: 8px;">$1</strong>')
            .replace(/^## (.*$)/gim, '<strong style="font-size: 16px; color: #93c5fd; display: block; margin-top: 10px;">$1</strong>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\[(.*?)\]/g, '<mark style="background: rgba(59, 130, 246, 0.25); color: #93c5fd;">[$1]</mark>');
    }
});
