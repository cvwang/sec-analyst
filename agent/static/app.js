/**
 * JavaScript Client App for SEC EDGAR Natural Language Analyst Split-Pane Web Dashboard
 */

document.addEventListener("DOMContentLoaded", () => {
    const btnRunQuery = document.getElementById("btnRunQuery");
    const naturalQueryInput = document.getElementById("naturalQuery");
    const selectQueryType = document.getElementById("selectQueryType");
    const selectTicker = document.getElementById("selectTicker");
    const selectCurrentYear = document.getElementById("selectCurrentYear");
    const selectPriorYear = document.getElementById("selectPriorYear");
    const selectMetric = document.getElementById("selectMetric");

    const kpiPrior = document.getElementById("kpiPrior");
    const kpiCurrent = document.getElementById("kpiCurrent");
    const kpiAbs = document.getElementById("kpiAbs");
    const kpiPct = document.getElementById("kpiPct");
    const kpiBadge = document.getElementById("kpiBadge");

    const reportContent = document.getElementById("reportContent");
    const sourceList = document.getElementById("sourceList");
    const sourceCount = document.getElementById("sourceCount");
    const memoryBadge = document.getElementById("memoryBadge");

    const btnExportGCS = document.getElementById("btnExportGCS");
    const hitlModal = document.getElementById("hitlModal");
    const btnCancelExport = document.getElementById("btnCancelExport");
    const btnConfirmExport = document.getElementById("btnConfirmExport");
    const gcsUriDisplay = document.getElementById("gcsUriDisplay");

    let lastAnalysisResponse = null;

    // Fetch initial health and session state
    fetchSessionState();

    btnRunQuery.addEventListener("click", runAnalysis);
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
        btnRunQuery.disabled = true;
        btnRunQuery.textContent = "⏳ Analyzing...";
        reportContent.innerHTML = "<p>🚀 Invoking RootOrchestrator and Hybrid Search RAG...</p>";

        let tickerVal = selectTicker.value.trim().toUpperCase() || "AAPL";
        const nQuery = naturalQueryInput.value.toUpperCase();
        
        // Extract custom ticker from prompt if typed (e.g. TSLA, META, AMD, JPM, WMT)
        const commonTickers = ["TSLA", "META", "AMD", "JPM", "BAC", "WMT", "NFLX", "INTC", "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN"];
        for (const t of commonTickers) {
            if (nQuery.includes(t)) {
                tickerVal = t;
                selectTicker.value = t;
                break;
            }
        }

        const payload = {
            query_type: selectQueryType.value,
            ticker: tickerVal,
            current_year: parseInt(selectCurrentYear.value),
            prior_year: parseInt(selectPriorYear.value),
            metric_name: selectMetric.value,
            session_id: "user_session_001",
        };

        try {
            const res = await fetch("/api/v1/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || "Analysis request failed");
            }

            const data = await res.json();
            lastAnalysisResponse = data;
            renderAnalysisResult(data);
            fetchSessionState();

        } catch (err) {
            reportContent.innerHTML = `<p style="color: #ef4444;">❌ Error: ${err.message}</p>`;
        } finally {
            btnRunQuery.disabled = false;
            btnRunQuery.textContent = "🚀 Run Analysis";
        }
    }

    function renderAnalysisResult(data) {
        // Update KPI Cards
        const v = data.variance_result;
        if (v) {
            kpiPrior.textContent = `${v.prior_period_value.toLocaleString()}M`;
            kpiCurrent.textContent = `${v.current_period_value.toLocaleString()}M`;
            
            const absFormatted = `${v.absolute_change >= 0 ? '+' : ''}${v.absolute_change.toLocaleString()}M`;
            kpiAbs.textContent = absFormatted;
            kpiAbs.className = `kpi-value ${v.absolute_change >= 0 ? 'positive' : 'negative'}`;

            const pctFormatted = `${v.percentage_change >= 0 ? '+' : ''}${v.percentage_change}%`;
            kpiPct.textContent = pctFormatted;
            kpiPct.className = `kpi-value ${v.percentage_change >= 0 ? 'positive' : 'negative'}`;

            kpiBadge.textContent = v.direction;
            kpiBadge.className = `kpi-badge ${v.direction.toLowerCase() === 'increase' ? 'badge-up' : 'badge-down'}`;
        }

        // Render Report Narrative
        reportContent.textContent = data.narrative || "No narrative generated.";

        // Render Grounded 10-K Sources
        const citations = data.citations || [];
        sourceCount.textContent = `${citations.length} Sources Grounded`;

        sourceList.innerHTML = "";
        if (data.hybrid_search_result && data.hybrid_search_result.text_chunks) {
            data.hybrid_search_result.text_chunks.forEach((chunk, idx) => {
                const card = document.createElement("div");
                card.className = `source-card ${idx === 0 ? 'active' : ''}`;
                card.innerHTML = `
                    <div class="source-header">
                        <span class="source-title">${chunk.company_name} FY${chunk.fiscal_year} 10-K</span>
                        <span class="source-tag">${chunk.section}</span>
                    </div>
                    <div class="source-excerpt">
                        "${chunk.content}"
                    </div>
                    <div class="source-citation">Citation: ${chunk.citation}</div>
                `;
                sourceList.appendChild(card);
            });
        }
    }

    function openExportModal() {
        const ticker = selectTicker.value.toLowerCase();
        const year = selectCurrentYear.value;
        const uri = `gs://fde-sec-edgar-reports/${ticker}_${year}_report.md`;
        gcsUriDisplay.textContent = uri;
        hitlModal.classList.remove("hidden");
    }

    async function executeGCSExport() {
        btnConfirmExport.disabled = true;
        btnConfirmExport.textContent = "⏳ Exporting...";

        const payload = {
            ticker: selectTicker.value,
            current_year: parseInt(selectCurrentYear.value),
            destination_gcs_uri: gcsUriDisplay.textContent,
            report_content: reportContent.textContent,
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
});
