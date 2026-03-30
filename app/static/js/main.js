/*
// Intercept AI form for async submission (no full page reload)
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("ai-form");
    const btn = document.getElementById("ai-btn");
    const container = document.getElementById("ai-result-container");

    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        btn.disabled = true;
        btn.textContent = "Running...";
        container.innerHTML = "<p>⏳ Analyzing...</p>";

        try {
            const response = await fetch("/ai/run", { method: "POST" });
            const html = await response.text();
            container.innerHTML = html;
        } catch (err) {
            container.innerHTML = `<div class="alert alert-error">Request failed: ${err.message}</div>`;
        } finally {
            btn.disabled = false;
            btn.textContent = "Run AI Analysis";
        }
    });
});
*/