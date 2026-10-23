(() => {
    // The changelist's list_editable formset: Django's prefix is "form".
    var FORM = "#changelist-form";
    var PREFIX = "form-";
    // Set by a script that leaves on purpose, having asked already (the
    // row actions).
    var LEAVING = "djangoAdminTablesLeaving";

    // The fields that save themselves (ListEditableAutosaveMixin) are never
    // unsaved: left out.
    function autosaved() {
        var node = document.getElementById("django-admin-tables-autosave");
        try {
            return node ? JSON.parse(node.textContent).fields : [];
        } catch {
            return [];
        }
    }

    function edits(form) {
        var fields = autosaved();
        var own = (name) =>
            fields.some((field) =>
                new RegExp(`^form-\\d+-${field}(_\\d+)?$`).test(name),
            );
        return new URLSearchParams(
            [...new FormData(form)].filter(
                ([name]) => name.startsWith(PREFIX) && !own(name),
            ),
        ).toString();
    }

    function watch() {
        var form = document.querySelector(FORM);
        if (!form) {
            return;
        }
        // After a save with errors, the page shows what was sent: unsaved.
        var saved = document.querySelector(".errornote") ? null : edits(form);
        var submitting = false;
        // Saving the changelist, or running an action, sends the edits.
        form.addEventListener("submit", () => {
            submitting = true;
        });
        window.addEventListener("beforeunload", (event) => {
            if (
                submitting ||
                document.documentElement.dataset[LEAVING] ||
                edits(form) === saved
            ) {
                return;
            }
            event.preventDefault();
            // Older browsers show the prompt only with a returnValue.
            event.returnValue = "";
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", watch);
    } else {
        watch();
    }
})();
