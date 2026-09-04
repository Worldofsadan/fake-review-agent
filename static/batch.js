const form = document.getElementById("batch-form");
const fileInput = document.getElementById("csv-file");
const submitBtn = document.getElementById("batch-submit-btn");
const progressEl = document.getElementById("batch-progress");
const errorEl = document.getElementById("batch-error");
const successEl = document.getElementById("batch-success");
const summaryEl = document.getElementById("batch-summary");

function decodeSummaryHeader(header) {
  try {
    return JSON.parse(atob(header));
  } catch (e) {
    return null;
  }
}

function renderSummary(summary) {
  if (!summary) return;
  summaryEl.innerHTML = `
    <strong>Batch Analysis Complete</strong><br/>
    Total Rows: ${summary.total_rows}<br/>
    Processed: ${summary.processed}<br/>
    Cache Hits: ${summary.cache_hits}<br/>
    LLM Calls: ${summary.llm_calls}<br/>
    Needs Human Review: ${summary.needs_human_review}<br/>
    Skipped (too short): ${summary.skipped}<br/>
    Errors: ${summary.errors}
  `;
  summaryEl.classList.remove("hidden");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.classList.add("hidden");
  successEl.classList.add("hidden");
  summaryEl.classList.add("hidden");

  const file = fileInput.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  submitBtn.disabled = true;
  progressEl.classList.remove("hidden");

  const token = localStorage.getItem("access_token");
  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  try {
    const res = await fetch("/predict/batch", {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Batch processing failed.");
    }

    const summaryHeader = res.headers.get("X-Batch-Summary");
    const summary = summaryHeader ? decodeSummaryHeader(summaryHeader) : null;

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "batch_results.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();

    successEl.textContent = "Done! Your results file has been downloaded.";
    successEl.classList.remove("hidden");
    renderSummary(summary);
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  } finally {
    submitBtn.disabled = false;
    progressEl.classList.add("hidden");
  }
});
