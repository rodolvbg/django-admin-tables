(() => {
    var BUTTON = "button[data-django-admin-tables-row-action]";
    var WRAPPER = ".django-admin-tables-row-actions";
    var STATUS_ID = "django-admin-tables-row-action-status";

    // The forms as they were when the page loaded: an action reloads the
    // page, which loses what has been typed since.
    var snapshots = new WeakMap();

    function snapshot(form) {
        return new URLSearchParams(new FormData(form)).toString();
    }

    function remember() {
        document.querySelectorAll("form").forEach((form) => {
            snapshots.set(form, snapshot(form));
        });
    }

    function changed(form) {
        return Boolean(
            form &&
                snapshots.has(form) &&
                snapshots.get(form) !== snapshot(form),
        );
    }

    function csrfToken() {
        var input = document.querySelector("[name=csrfmiddlewaretoken]");
        if (input) {
            return input.value;
        }
        var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    /** Post to `url` in a form of its own: the page follows the response. */
    function submit(url) {
        var form = document.createElement("form");
        form.method = "post";
        form.action = url;
        form.hidden = true;
        for (const [name, value] of [
            ["csrfmiddlewaretoken", csrfToken()],
            ["next", window.location.href],
        ]) {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = name;
            input.value = value;
            form.append(input);
        }
        document.body.append(form);
        form.submit();
    }

    /** The action's messages, announced to screen readers too. */
    function showStatus(status, message) {
        if (!message) {
            return;
        }
        var element = document.getElementById(STATUS_ID);
        if (!element) {
            element = document.createElement("div");
            element.id = STATUS_ID;
            element.setAttribute("role", "status");
            document.body.append(element);
        }
        element.className = `django-admin-tables-row-action-status django-admin-tables-row-action-${status}`;
        element.textContent = message;
    }

    function download(blob, disposition) {
        var link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download =
            disposition.match(/filename="?([^";]+)"?/)?.[1] ?? "download";
        document.body.append(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(link.href);
    }

    /** django-admin-inline-controls' inline: run the action, then refresh
     * only the inline, with its filters and page. */
    async function runInPlace(url, root, controls, failed) {
        var state = controls.stateOf?.(root);
        if (state?.dirty && !window.confirm(state.config.messages.unsaved)) {
            return;
        }
        var data = new FormData();
        data.append("csrfmiddlewaretoken", csrfToken());
        var response;
        try {
            response = await fetch(url, {
                method: "POST",
                body: data,
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
        } catch {
            showStatus("error", failed);
            return;
        }
        var type = response.headers.get("Content-Type") ?? "";
        var disposition = response.headers.get("Content-Disposition") ?? "";
        if (disposition.includes("attachment")) {
            download(await response.blob(), disposition);
            return;
        }
        if (!type.includes("application/json")) {
            // Another page (a redirect, an intermediate step): go there.
            window.location.assign(response.url);
            return;
        }
        var result = await response.json();
        if (state) {
            state.dirty = false; // Already confirmed above.
        }
        await controls.navigate(root, window.location.href);
        showStatus(result.status, result.message);
    }

    document.addEventListener("click", (event) => {
        var button = event.target.closest?.(BUTTON);
        if (!button) {
            return;
        }
        event.preventDefault();
        var { confirmation } = button.dataset;
        if (confirmation && !window.confirm(confirmation)) {
            return;
        }
        var url = button.dataset.djangoAdminTablesRowAction;
        var controls = globalThis.DjangoAdminInlineControls;
        var root = button.closest("[data-inline-controls]");
        var wrapper = button.closest(WRAPPER);
        if (controls && root) {
            runInPlace(url, root, controls, wrapper?.dataset.failed ?? "");
            return;
        }
        var unsaved = wrapper?.dataset.unsaved;
        if (changed(button.closest("form")) && !window.confirm(unsaved)) {
            return;
        }
        submit(url);
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", remember);
    } else {
        remember();
    }
})();
