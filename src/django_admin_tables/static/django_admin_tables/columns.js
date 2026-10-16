(() => {
    var CONFIG_ID = "django-admin-tables-columns";
    var STYLE_ID = "django-admin-tables-hidden-columns";
    var MENU = "details.django-admin-tables-columns";
    var INPUT = "input[data-django-admin-tables-column]";

    function escapeClass(value) {
        if (window.CSS && typeof CSS.escape === "function") {
            return CSS.escape(value);
        }
        return String(value).replace(/[^\w-]/g, "\\$&");
    }

    function readConfig() {
        var element = document.getElementById(CONFIG_ID);
        if (!element) {
            return null;
        }
        try {
            return JSON.parse(element.textContent);
        } catch {
            return null;
        }
    }

    // The user's choice, or the admin's default (`list_display_hidden`)
    // until there's one. Storage can be unavailable (private windows,
    // blocked site data): the default applies then, for this page only.
    function loadHidden(config) {
        var stored;
        try {
            stored = JSON.parse(window.localStorage.getItem(config.storageKey));
            if (Array.isArray(stored)) {
                return stored.filter((name) => config.columns.includes(name));
            }
        } catch {
            // Fall through to the default.
        }
        return config.hidden.slice();
    }

    function saveHidden(config, hidden) {
        try {
            window.localStorage.setItem(
                config.storageKey,
                JSON.stringify(hidden),
            );
        } catch {
            // Not remembered, still applied.
        }
    }

    // One <style> rule hides each column, header and cells alike, by the
    // `column-<name>`/`field-<name>` classes the admin gives them: it
    // applies while the table is parsed, so hidden columns never flash.
    function applyHidden(hidden) {
        var style = document.getElementById(STYLE_ID);
        if (!style) {
            style = document.createElement("style");
            style.id = STYLE_ID;
            document.head.appendChild(style);
        }
        var selectors = hidden.map((name) => {
            var cls = escapeClass(name);
            return `#result_list .column-${cls}, #result_list .field-${cls}`;
        });
        style.textContent = hidden.length
            ? `${selectors.join(",\n")} { display: none; }`
            : "";
    }

    function bindMenu(config, hidden) {
        document.querySelectorAll(INPUT).forEach((input) => {
            input.checked = !hidden.includes(
                input.dataset.djangoAdminTablesColumn,
            );
        });

        document.addEventListener("change", (event) => {
            var input = event.target;
            if (!input.matches?.(INPUT)) {
                return;
            }
            var name = input.dataset.djangoAdminTablesColumn;
            var index = hidden.indexOf(name);
            if (input.checked && index !== -1) {
                hidden.splice(index, 1);
            } else if (!input.checked && index === -1) {
                hidden.push(name);
            }
            saveHidden(config, hidden);
            applyHidden(hidden);
        });

        // Close the menu on a click outside it, or on Escape.
        document.addEventListener("click", (event) => {
            document.querySelectorAll(`${MENU}[open]`).forEach((menu) => {
                if (!menu.contains(event.target)) {
                    menu.open = false;
                }
            });
        });
        document.addEventListener("keydown", (event) => {
            if (event.key !== "Escape") {
                return;
            }
            document.querySelectorAll(`${MENU}[open]`).forEach((menu) => {
                menu.open = false;
                menu.querySelector("summary")?.focus();
            });
        });
    }

    var config = readConfig();
    if (!config) {
        return;
    }
    var hidden = loadHidden(config);
    applyHidden(hidden);
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () =>
            bindMenu(config, hidden),
        );
    } else {
        bindMenu(config, hidden);
    }
})();
