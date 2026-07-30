// create_agent.js — Create Agent page logic with domain presets

(function () {
    "use strict";

    // --- State ---
    var presets = [];
    var currentPreset = null;

    // --- Type selector ---
    var typeCards = document.querySelectorAll(".type-card");
    var typeInput = document.getElementById("agent_type");
    var sectionIds = ["scraper", "analyzer", "monitor", "generator", "general"];

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
            // Auto-load presets when scraper is selected
            if (type === "scraper" && !presets.length) {
                loadPresets();
            }
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
        container._setValues = function (newValues) {
            // Clear existing tags
            var existingTags = container.querySelectorAll(".tag");
            existingTags.forEach(function (t) { t.remove(); });
            values = [];
            // Add new values
            newValues.forEach(function (v) { addTag(v); });
        };
    });

    // --- Load presets from API ---
    function loadPresets() {
        fetch("/api/presets")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                presets = data.presets || [];
                renderPresetCards();
            })
            .catch(function (err) {
                console.error("Failed to load presets:", err);
            });
    }

    function renderPresetCards() {
        var container = document.getElementById("preset-selector");
        if (!container) return;
        container.innerHTML = "";

        presets.forEach(function (preset) {
            var card = document.createElement("div");
            card.className = "preset-card border-2 border-gray-200 rounded-lg p-3 cursor-pointer hover:border-indigo-400 transition-all text-center";
            card.dataset.domain = preset.domain;
            card.innerHTML =
                '<div class="text-xl mb-1">' + preset.icon + '</div>' +
                '<div class="text-xs font-medium text-gray-700">' + preset.label + '</div>';

            card.addEventListener("click", function () {
                // Deselect all
                container.querySelectorAll(".preset-card").forEach(function (c) {
                    c.classList.remove("border-indigo-500", "bg-indigo-50");
                    c.classList.add("border-gray-200");
                });
                // Select this one
                card.classList.remove("border-gray-200");
                card.classList.add("border-indigo-500", "bg-indigo-50");
                document.getElementById("scraper_preset").value = preset.domain;
                applyPreset(preset);
            });

            container.appendChild(card);
        });
    }

    function applyPreset(preset) {
        currentPreset = preset;

        // Show preset info
        var infoEl = document.getElementById("preset-info");
        infoEl.classList.remove("hidden");
        document.getElementById("preset-icon").textContent = preset.icon;
        document.getElementById("preset-label").textContent = preset.label;
        document.getElementById("preset-desc").textContent = preset.description;

        // Source selector
        var sourceSection = document.getElementById("source-section");
        var sourceSelect = document.getElementById("scraper_source");
        var urlPreview = document.getElementById("source-url-preview");

        if (preset.sources && preset.sources.length > 0) {
            sourceSection.classList.remove("hidden");
            sourceSelect.innerHTML = "";
            preset.sources.forEach(function (src, idx) {
                var opt = document.createElement("option");
                opt.value = idx;
                opt.textContent = src.name + (src.description ? " — " + src.description : "");
                sourceSelect.appendChild(opt);
            });

            function updateSourcePreview() {
                var idx = parseInt(sourceSelect.value) || 0;
                var src = preset.sources[idx];
                if (src && src.url) {
                    urlPreview.textContent = "URL: " + src.url;
                    // Auto-fill URL if not custom
                    if (preset.domain !== "custom" && src.url) {
                        var urlsInput = document.getElementById("urls-input");
                        if (urlsInput._setValues) {
                            urlsInput._setValues([src.url]);
                        }
                    }
                } else {
                    urlPreview.textContent = "";
                }
            }

            sourceSelect.onchange = updateSourcePreview;
            updateSourcePreview();
        } else {
            sourceSection.classList.add("hidden");
        }

        // Show custom URL section for custom preset always, otherwise hide (auto-filled)
        var customUrlSection = document.getElementById("custom-url-section");
        if (preset.domain === "custom") {
            customUrlSection.classList.remove("hidden");
        } else {
            customUrlSection.classList.remove("hidden"); // Keep visible but pre-filled
        }

        // Fields preview
        var fieldsSection = document.getElementById("fields-section");
        var fieldsPreview = document.getElementById("fields-preview");
        if (preset.fields && preset.fields.length > 0) {
            fieldsSection.classList.remove("hidden");
            fieldsPreview.innerHTML = "";
            preset.fields.forEach(function (f) {
                var badge = document.createElement("span");
                badge.className = "inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800";
                badge.textContent = f.name;
                badge.title = "selector: " + f.selector + " (type: " + f.type + ")";
                fieldsPreview.appendChild(badge);
            });
        } else {
            fieldsSection.classList.add("hidden");
        }

        // Schedule
        var scheduleInput = document.getElementById("scraper_schedule");
        if (preset.default_schedule) {
            scheduleInput.value = preset.default_schedule;
        }

        // Auto-fill domain field
        var domainInput = document.getElementById("domain");
        if (domainInput && preset.domain !== "custom") {
            domainInput.value = preset.domain;
        }
    }

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
            // Preset info
            if (currentPreset && currentPreset.domain !== "custom") {
                extras.push("domain preset: " + currentPreset.domain + " (" + currentPreset.label + ")");
                extras.push("source type: " + currentPreset.source_type);
                if (currentPreset.fields && currentPreset.fields.length) {
                    var fieldNames = currentPreset.fields.map(function (f) {
                        return f.name + " (selector: " + f.selector + ")";
                    });
                    extras.push("extract fields: " + fieldNames.join(", "));
                }
            }

            // URLs
            var urlsEl = document.getElementById("urls-input");
            var urls = urlsEl._getValues ? urlsEl._getValues() : [];
            if (urls.length) { extras.push("target URLs: " + urls.join(", ")); }

            // Schedule
            if (fd.get("scraper_schedule")) {
                extras.push("cron schedule: " + fd.get("scraper_schedule"));
            }
            if (fd.get("scraper_interval")) {
                extras.push("fixed interval: " + fd.get("scraper_interval") + " " + (fd.get("interval_unit") || "minutes"));
            }

            // Advanced
            if (fd.get("rate_limit")) { extras.push("rate limit: " + fd.get("rate_limit") + "s between requests"); }
            if (fd.get("scraper_timeout")) { extras.push("timeout: " + fd.get("scraper_timeout") + "s"); }
            if (fd.get("output_format")) { extras.push("output format: " + fd.get("output_format")); }
            if (fd.get("auth_token")) { extras.push("auth token: provided"); }
            if (fd.get("data_fields")) { extras.push("custom fields override: " + fd.get("data_fields")); }

            // Use forge_agent.scraper module
            extras.push("IMPORTANT: Use forge_agent.scraper module (ScraperConfig, ScraperEngine, SQLiteDataStore)");

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
