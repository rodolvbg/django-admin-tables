/**
 * ListEditableAutosaveMixin: the changelist's list_editable fields that
 * save themselves (#django-admin-tables-autosave), one row and one field at
 * a time: a switch, a checkbox or a select at once, a text when it's left
 * or on Enter. One request at a time per field; what changes meanwhile goes
 * after it. Its cell says how it went; if it failed, the field goes back.
 */
(() => {
    const ROW = /^(form-\d+)-(.+)$/;
    const SAVED_FOR = 2000;

    function config() {
        const node = document.getElementById("django-admin-tables-autosave");
        try {
            return node ? JSON.parse(node.textContent) : null;
        } catch {
            return null;
        }
    }

    /** The values of `inputs`, as the form would send them. */
    function snapshot(inputs) {
        const pairs = [];
        for (const input of inputs) {
            if (input.type === "checkbox" || input.type === "radio") {
                if (input.checked) pairs.push([input.name, input.value]);
            } else if (input.multiple && input.options) {
                for (const option of input.options) {
                    if (option.selected) pairs.push([input.name, option.value]);
                }
            } else {
                pairs.push([input.name, input.value]);
            }
        }
        return pairs;
    }

    /** Put `pairs` back in `inputs`. */
    function restore(inputs, pairs) {
        const has = (name, value) =>
            pairs.some(([n, v]) => n === name && v === value);
        for (const input of inputs) {
            if (input.type === "checkbox" || input.type === "radio") {
                input.checked = has(input.name, input.value);
            } else if (input.multiple && input.options) {
                for (const option of input.options) {
                    option.selected = has(input.name, option.value);
                }
            } else {
                // A text's value is always there (snapshot() takes it).
                input.value = pairs.find(([n]) => n === input.name)[1];
            }
        }
    }

    const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

    function setup() {
        const options = config();
        const form = document.getElementById("changelist-form");
        if (!options || !form || form.dataset.djangoAdminTablesAutosave) return;
        form.dataset.djangoAdminTablesAutosave = "on";
        const fields = options.fields;
        const cells = new Map();

        /** The autosaved field an input is of: `form-3-active`, or one of
         * a multi-widget's (`form-3-when_0`). */
        function owner(input) {
            const match = ROW.exec(input.name);
            if (!match) return null;
            const [, prefix, rest] = match;
            const field = fields.find(
                (name) => rest === name || rest.startsWith(`${name}_`),
            );
            return field ? cell(prefix, field) : null;
        }

        function cell(prefix, field) {
            const key = `${prefix}-${field}`;
            if (!cells.has(key)) {
                const inputs = () =>
                    form.querySelectorAll(`[name="${key}"], [name^="${key}_"]`);
                cells.set(key, {
                    prefix,
                    field,
                    inputs,
                    saved: snapshot(inputs()),
                    busy: false,
                    again: false,
                    status: null,
                    timer: null,
                });
            }
            return cells.get(key);
        }

        function show(entry, state, message) {
            if (!entry.status) {
                entry.status = document.createElement("span");
                entry.status.className = "django-admin-tables-autosave-status";
                entry.status.setAttribute("role", "status");
                const [first] = entry.inputs();
                (first.closest("td") ?? first.parentElement).append(
                    entry.status,
                );
            }
            clearTimeout(entry.timer);
            entry.status.dataset.state = state;
            entry.status.textContent = message ?? options.texts[state];
            entry.status.title = entry.status.textContent;
            if (state === "saved") {
                entry.timer = setTimeout(() => {
                    entry.status.textContent = "";
                    delete entry.status.dataset.state;
                }, SAVED_FOR);
            }
        }

        async function save(entry) {
            if (entry.busy) {
                entry.again = true;
                return;
            }
            const current = snapshot(entry.inputs());
            if (same(current, entry.saved)) return;
            entry.busy = true;
            show(entry, "saving");
            const body = new FormData();
            body.append("prefix", entry.prefix);
            body.append("field", entry.field);
            body.append(
                "pk",
                form.querySelector(`[name="${entry.prefix}-${options.pk}"]`)
                    ?.value ?? "",
            );
            body.append("check", "1");
            for (const [name, value] of current) body.append(name, value);
            for (const [name, value] of entry.saved) {
                body.append(`previous-${name}`, value);
            }
            try {
                const response = await fetch(options.url, {
                    method: "POST",
                    body,
                    credentials: "same-origin",
                    headers: {
                        Accept: "application/json",
                        "X-CSRFToken":
                            form.querySelector("[name=csrfmiddlewaretoken]")
                                ?.value ?? "",
                    },
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(data.error ?? "");
                entry.saved = current;
                show(entry, "saved");
            } catch (error) {
                entry.again = false;
                restore(entry.inputs(), entry.saved);
                show(entry, "failed", error.message || undefined);
            } finally {
                entry.busy = false;
            }
            if (entry.again) {
                entry.again = false;
                save(entry);
            }
        }

        for (const input of form.elements) owner(input); // What there is now.

        form.addEventListener("change", (event) => {
            const entry = owner(event.target);
            if (entry) save(entry);
        });
        // Enter saves a text that saves itself, instead of the changelist.
        form.addEventListener("keydown", (event) => {
            const entry = owner(event.target);
            if (event.key !== "Enter" || !entry) return;
            if (event.target.tagName === "TEXTAREA") return;
            event.preventDefault();
            save(entry);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", setup);
    } else {
        setup();
    }
})();
