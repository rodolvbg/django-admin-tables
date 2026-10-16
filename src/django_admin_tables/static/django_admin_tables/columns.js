(() => {
    var CONFIG_ID = "django-admin-tables-columns";
    var STYLE_ID = "django-admin-tables-hidden-columns";
    // One per table with responsive_columns: the changelist, each inline.
    var RESPONSIVE = 'script[id^="django-admin-tables-responsive-"]';
    var MENU = "details.django-admin-tables-columns";
    var INPUT = "input[data-django-admin-tables-column]";

    function escapeClass(value) {
        if (window.CSS && typeof CSS.escape === "function") {
            return CSS.escape(value);
        }
        return String(value).replace(/[^\w-]/g, "\\$&");
    }

    function parse(element) {
        try {
            return JSON.parse(element.textContent);
        } catch {
            return null;
        }
    }

    // CSS set from a script, so a Content Security Policy needs no
    // 'unsafe-inline' in style-src: a constructed stylesheet, or a <style>
    // element in browsers without them (which that policy would block).
    var sheets = {};

    function setStyles(id, cssText) {
        if (
            typeof CSSStyleSheet === "function" &&
            Array.isArray(document.adoptedStyleSheets)
        ) {
            try {
                if (!sheets[id]) {
                    sheets[id] = new CSSStyleSheet();
                    document.adoptedStyleSheets = [
                        ...document.adoptedStyleSheets,
                        sheets[id],
                    ];
                }
                sheets[id].replaceSync(cssText);
                return;
            } catch {
                // Fall back to a <style> element.
            }
        }
        var style = document.getElementById(id);
        if (!style) {
            style = document.createElement("style");
            style.id = id;
            document.head.appendChild(style);
        }
        style.textContent = cssText;
    }

    function hideRule(scope, classes) {
        var selectors = classes.map((name) => {
            var cls = escapeClass(name);
            return `${scope} .column-${cls}, ${scope} .field-${cls}`;
        });
        return `${selectors.join(",\n")} { display: none; }`;
    }

    // responsive_columns: each table's media queries, applied as soon as
    // its config is parsed, so its columns never flash on a narrow screen.
    function applyResponsive() {
        document.querySelectorAll(RESPONSIVE).forEach((element) => {
            if (element.dataset.djangoAdminTablesApplied) {
                return;
            }
            element.dataset.djangoAdminTablesApplied = "true";
            var config = parse(element);
            if (!config) {
                return;
            }
            setStyles(
                `${element.id}-style`,
                config.rules
                    .map(
                        (rule) =>
                            `@media (max-width: ${rule.max_width}px) { ${hideRule(config.scope, rule.classes)} }`,
                    )
                    .join("\n"),
            );
        });
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

    // One rule hides each column, header and cells alike, by the
    // `column-<name>`/`field-<name>` classes the admin gives them: it
    // applies while the table is parsed, so hidden columns never flash.
    function applyHidden(hidden) {
        setStyles(
            STYLE_ID,
            hidden.length ? hideRule("#result_list", hidden) : "",
        );
    }

    function bindMenu(config, hidden) {
        document.querySelectorAll(INPUT).forEach((input) => {
            input.checked = !hidden.includes(
                input.dataset.djangoAdminTablesColumn,
            );
        });

        // A column the viewport hides (responsive_columns) can't be shown
        // from the menu while it's that narrow: unchecked, disabled, noted.
        document
            .querySelectorAll(`${INPUT}[data-django-admin-tables-max-width]`)
            .forEach((input) => {
                if (typeof window.matchMedia !== "function") {
                    return;
                }
                var query = window.matchMedia(
                    `(max-width: ${input.dataset.djangoAdminTablesMaxWidth}px)`,
                );
                var note = input.parentElement.querySelector(
                    ".django-admin-tables-columns__note",
                );
                function update() {
                    input.disabled = query.matches;
                    input.checked =
                        !query.matches &&
                        !hidden.includes(input.dataset.djangoAdminTablesColumn);
                    if (note) {
                        note.hidden = !query.matches;
                    }
                }
                update();
                query.addEventListener("change", update);
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

    applyResponsive();

    var menuConfig = document.getElementById(CONFIG_ID);
    if (!menuConfig || menuConfig.dataset.djangoAdminTablesApplied) {
        return;
    }
    menuConfig.dataset.djangoAdminTablesApplied = "true";
    var config = parse(menuConfig);
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
