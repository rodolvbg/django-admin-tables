import { afterEach, describe, expect, it, vi } from "vitest";

// Loaded while the page is still loading: it remembers the forms once
// they're parsed. A file of its own, for a fresh document.
describe("row-actions.js, loaded with the page", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("remembers the forms when the page is parsed", async () => {
        vi.spyOn(document, "readyState", "get").mockReturnValue("loading");
        await import(
            "../../src/django_admin_tables/static/django_admin_tables/row-actions.js"
        );
        document.body.innerHTML = `
            <form>
                <input name="title" value="Peak">
                <button type="button" data-django-admin-tables-row-action="/run/">Run</button>
            </form>`;
        document.dispatchEvent(new Event("DOMContentLoaded"));
        const submit = vi
            .spyOn(HTMLFormElement.prototype, "submit")
            .mockImplementation(() => {});
        const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);

        document.querySelector("[name=title]").value = "Edited";
        document.querySelector("button").click();

        // Outside its usual wrapper: no message of its own to show.
        expect(confirm).toHaveBeenCalledWith(undefined);
        expect(submit).not.toHaveBeenCalled();
    });
});
