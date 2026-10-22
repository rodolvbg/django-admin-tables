/**
 * SearchSuggestionsMixin: the changelist's search box suggests the objects
 * it finds as one types (an ARIA combobox); choosing one, with the mouse or
 * the keyboard, opens its change page. Enter without choosing one searches
 * as always. Its configuration: the JSON of #django-admin-tables-search.
 */
(() => {
    const DELAY = 200;

    function config() {
        const node = document.getElementById("django-admin-tables-search");
        try {
            return node ? JSON.parse(node.textContent) : null;
        } catch {
            return null;
        }
    }

    function setup() {
        const options = config();
        const input = document.getElementById("searchbar");
        if (!options || !input || input.dataset.djangoAdminTablesSearch) return;
        input.dataset.djangoAdminTablesSearch = "on";

        const list = document.createElement("ul");
        list.id = "django-admin-tables-search-suggestions";
        list.className = "django-admin-tables-search-suggestions";
        list.setAttribute("role", "listbox");
        list.setAttribute("aria-label", options.texts.label);
        list.hidden = true;
        const box = input.parentElement;
        box.classList.add("django-admin-tables-search");
        box.append(list);

        input.setAttribute("role", "combobox");
        input.setAttribute("aria-autocomplete", "list");
        input.setAttribute("aria-controls", list.id);
        input.setAttribute("aria-expanded", "false");
        input.setAttribute("autocomplete", "off");

        let timer = null;
        let request = null;
        let links = [];
        let active = -1;

        function close() {
            list.hidden = true;
            input.setAttribute("aria-expanded", "false");
            input.removeAttribute("aria-activedescendant");
            active = -1;
        }

        function highlight(index) {
            active = index;
            links.forEach((link, i) => {
                link.parentElement.setAttribute(
                    "aria-selected",
                    String(i === index),
                );
            });
            input.setAttribute(
                "aria-activedescendant",
                links[index].parentElement.id,
            );
            links[index].parentElement.scrollIntoView?.({ block: "nearest" });
        }

        function show(results) {
            links = [];
            active = -1;
            list.replaceChildren();
            if (!results.length) {
                const empty = document.createElement("li");
                empty.className = "django-admin-tables-search-empty";
                empty.textContent = options.texts.empty;
                list.append(empty);
            }
            results.forEach((result, index) => {
                const item = document.createElement("li");
                item.id = `${list.id}-${index}`;
                item.setAttribute("role", "option");
                item.setAttribute("aria-selected", "false");
                const link = document.createElement("a");
                link.href = result.url;
                link.textContent = result.text;
                link.tabIndex = -1;
                // Kept focus: the input's blur doesn't close it first.
                item.addEventListener("mousedown", (event) =>
                    event.preventDefault(),
                );
                item.addEventListener("mousemove", () => highlight(index));
                item.append(link);
                list.append(item);
                links.push(link);
            });
            list.hidden = false;
            input.setAttribute("aria-expanded", "true");
        }

        async function suggest() {
            const term = input.value.trim();
            request?.abort();
            if (term.length < options.minLength) {
                close();
                return;
            }
            request = new AbortController();
            try {
                const response = await fetch(
                    `${options.url}?q=${encodeURIComponent(term)}`,
                    {
                        headers: { Accept: "application/json" },
                        credentials: "same-origin",
                        signal: request.signal,
                    },
                );
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();
                // Typed on meanwhile: this answer is old.
                if (input.value.trim() !== term) return;
                show(data.results);
            } catch {
                close(); // Aborted, or failed: the search still works.
            }
        }

        input.addEventListener("input", () => {
            clearTimeout(timer);
            timer = setTimeout(suggest, DELAY);
        });

        input.addEventListener("keydown", (event) => {
            const open = !list.hidden;
            if (event.key === "ArrowDown" && open && links.length) {
                event.preventDefault();
                highlight((active + 1) % links.length);
            } else if (event.key === "ArrowUp" && open && links.length) {
                event.preventDefault();
                highlight(active <= 0 ? links.length - 1 : active - 1);
            } else if (event.key === "Enter" && open && active >= 0) {
                event.preventDefault();
                links[active].click();
            } else if (event.key === "Escape" && open) {
                event.preventDefault();
                close();
            }
        });

        input.addEventListener("blur", close);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setup);
    } else {
        setup();
    }
})();
