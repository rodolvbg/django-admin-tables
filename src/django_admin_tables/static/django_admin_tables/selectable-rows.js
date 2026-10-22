/**
 * SelectableRowsMixin: the admin counts the rows of the page ("2 of 25
 * selected"); those that can't be selected (their checkbox disabled, out of
 * the admin's selection) aren't among them.
 */
(() => {
    function recount() {
        if (!document.querySelector("input.django-admin-tables-unselectable")) {
            return;
        }
        const selectable = document.querySelectorAll(
            "tr input.action-select",
        ).length;
        for (const counter of document.querySelectorAll(
            ".action-counter[data-actions-icnt]",
        )) {
            counter.dataset.actionsIcnt = String(selectable);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", recount);
    } else {
        recount();
    }
})();
