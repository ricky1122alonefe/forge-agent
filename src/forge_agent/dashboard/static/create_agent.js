// create_agent.js — Create Agent page logic

(function () {
    "use strict";

    // --- Type selector ---
    const typeCards = document.querySelectorAll(".type-card");
    const typeInput = document.getElementById("agent_type");
    const sectionIds = ["scraper", "analyzer", "monitor", "generator", "general"];

    typeCards.forEach(function (card) {
        card.addEventListener("click", function () {
            typeCards.forEach(function (c) { c.classList.remove("selected"); });
            card.classList.add("selected");
            var type = card.dataset.type;
            typeInput.value = type;
            sectionIds.forEach(function (key) {
                var el = document.getElementById("section-" + key);
                if (el) {
                    if (key === type) { el.classList.remove("hidden"); }
                    else { el.classList.add("hidden"); }
                }
            });
        });
    });

    // --- Tag inputs ---
    document.querySelectorAll(".tag-input").forEach(function (container) {
        var input = container.querySelector("input");
        var values = [];

        container.addEventListener("click", function () { input.focus(); });

        input.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && input.value.trim()) {
                e.preventDefault();
                addTag(input.value.trim());
                input.value = "";
            }
            if (e.key === "Backspace" && !input.value && values.length) {
                removeTag(values.length - 1);
            }
        });

        function addTag(text) {
            values.push(text);
            var tag = document.createElement("span");
            tag.className = "tag";
            tag.innerHTML = text + ' <button type="button">&times;</button>';
            tag.querySelector("button").addEventListener("click", function () {
                var idx = values.indexOf(text);
                if (idx > -1) { values.splice(idx, 1); }
                tag.remove();
            });
            container.insertBefore(tag, input);
        }

        function removeTag(idx) {
            values.splice(idx, 1);
            var tags = container.querySelectorAll(".tag");
            if (tags[idx]) { tags[idx].remove(); }
        }

        container._getValues = function () { return values.slice(); };
    });

    // --- Form submit ---
    var form = document.getElementById("create-form");
    form.addEventListener("submit", function (e) {
        e.preventDefault();

        var type = typeInput.value;
        if (!type) {
            alert("Please select an Agent type");
            return;
        }

        var btn = document.getElementById("generate-btn");
        var panel = document.getElementById("result-panel");
        var loading = document.getElementById("result-loading");
        var success = document.getElementById("result-success");
        var error = document.getElementById("result-error");

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Generating...';
        panel.classList.remove("hidden");
        loading.classList.remove("hidden");
        success.classList.add("hidden");
        error.classList.add("hidden");

        // Build payload
        var fd = new FormData(form);
        var requirement = fd.get("description") || "";
        var extras = [];

        if (type === "scraper") {
            var urlsEl = document.getElementById("urls-input");
            var urls = urlsEl._getValues ? urlsEl._getValues() : [];
            if (urls.length) { extras.push("target URLs: " + urls.join(", ")); }
            if (fd.get("max_depth")) { extras.push("max crawl depth: " + fd.get("max_depth")); }
            if (fd.get("rate_limit")) { extras.push("rate limit: " + fd.get("rate_limit") + " req/s"); }
            if (fd.get("data_fields")) { extras.push("extract fields: " + fd.get("data_fields")); }
            if (fd.get("output_format")) { extras.push("output format: " + fd.get("output_format")); }
        } else if (type === "monitor") {
            if (fd.get("check_interval")) {
                extras.push("check every " + fd.get("check_interval") + " " + (fd.get("interval_unit") || "minutes"));
            }
            if (fd.get("alert_threshold")) { extras.push("alert when: " + fd.get("alert_threshold")); }
            if (fd.get("cron_schedule")) { extras.push("cron: " + fd.get("cron_schedule")); }
        } else if (type === "analyzer") {
            if (fd.get("data_source")) { extras.push("data source: " + fd.get("data_source")); }
            if (fd.get("analysis_type")) { extras.push("analysis type: " + fd.get("analysis_type")); }
            if (fd.get("output_metrics")) { extras.push("output metrics: " + fd.get("output_metrics")); }
        } else if (type === "generator") {
            if (fd.get("gen_output_type")) { extras.push("output type: " + fd.get("gen_output_type")); }
            if (fd.get("tone_style")) { extras.push("tone: " + fd.get("tone_style")); }
            if (fd.get("max_length")) { extras.push("max length: " + fd.get("max_length")); }
        }

        if (extras.length) {
            requirement += "\n\nAdditional details:\n- " + extras.join("\n- ");
        }

        // Constraints
        var constraintsEl = document.getElementById("constraints-input");
        var constraints = constraintsEl._getValues ? constraintsEl._getValues() : [];
        if (constraints.length) {
            requirement += "\n\nConstraints:\n- " + constraints.join("\n- ");
        }

        var payload = {
            requirement: requirement,
            agent_id: fd.get("agent_id"),
            name: fd.get("name"),
            domain: fd.get("domain"),
            agent_type: type,
            provider: fd.get("provider") || null,
            deploy_mode: fd.get("deploy_mode") || "manual_review",
        };

        fetch("/api/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                loading.classList.add("hidden");
                if (data.success) {
                    success.classList.remove("hidden");
                    document.getElementById("res-agent-id").textContent = data.agent_id || payload.agent_id;
                    document.getElementById("res-status").textContent = data.deployed ? "Deployed" : "Saved";
                    document.getElementById("res-path").textContent = data.code_path || "N/A";
                    document.getElementById("res-attempts").textContent = data.attempts || "1";
                } else {
                    error.classList.remove("hidden");
                    document.getElementById("res-error-msg").textContent = data.error || "Unknown error";
                }
            })
            .catch(function (err) {
                loading.classList.add("hidden");
                error.classList.remove("hidden");
                document.getElementById("res-error-msg").textContent = err.message || "Network error";
            })
            .finally(function () {
                btn.disabled = false;
                btn.innerHTML = "Generate Agent";
            });
    });
})();
