import { afterEach, describe, expect, it, vi } from "vitest";

// A plain script listening on `window`: each test loads a fresh copy on a
// fresh page. Copies from earlier tests watch forms that are gone, unchanged.
const SCRIPT =
    "../../src/django_admin_tables/static/django_admin_tables/unsaved-changes.js";

async function load(html) {
    document.body.innerHTML = html;
    vi.resetModules();
    await import(SCRIPT);
}

const CHANGELIST = `
    <form id="changelist-form">
        <input name="csrfmiddlewaretoken" value="x">
        <select name="action"><option value="">--</option><option value="go">Go</option></select>
        <input name="form-0-title" value="Alps">
    </form>`;

function leave() {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
}

describe("unsaved-changes.js", () => {
    afterEach(() => {
        delete document.documentElement.dataset.djangoAdminTablesLeaving;
        // This test's copy of the script: done with its form, as if saved.
        document
            .getElementById("changelist-form")
            ?.dispatchEvent(new Event("submit"));
    });

    it("lets the page go without changes", async () => {
        await load(CHANGELIST);
        expect(leave()).toBe(false);
    });

    it("ignores what isn't an edit (the action menu)", async () => {
        await load(CHANGELIST);
        document.querySelector("[name=action]").value = "go";
        expect(leave()).toBe(false);
    });

    it("asks before losing an edit", async () => {
        await load(CHANGELIST);
        document.querySelector("[name=form-0-title]").value = "Coast";
        expect(leave()).toBe(true);
    });

    it("lets the changelist be saved", async () => {
        await load(CHANGELIST);
        const form = document.getElementById("changelist-form");
        form.querySelector("[name=form-0-title]").value = "Coast";
        form.dispatchEvent(new Event("submit"));
        expect(leave()).toBe(false);
    });

    it("lets a script that asked already leave", async () => {
        await load(CHANGELIST);
        document.querySelector("[name=form-0-title]").value = "Coast";
        document.documentElement.dataset.djangoAdminTablesLeaving = "true";
        expect(leave()).toBe(false);
    });

    it("does nothing without a changelist", async () => {
        await load(
            `<form id="album_form"><input name="form-0-title" value="Alps"></form>`,
        );
        document.querySelector("input").value = "Coast";
        expect(leave()).toBe(false);
    });

    it("waits for the page when it's still loading", async () => {
        vi.spyOn(document, "readyState", "get").mockReturnValue("loading");
        await load(CHANGELIST);
        vi.restoreAllMocks();
        document.dispatchEvent(new Event("DOMContentLoaded"));

        document.querySelector("[name=form-0-title]").value = "Coast";
        expect(leave()).toBe(true);
    });

    // Last: its listener asks for any page from here on.
    it("asks after a save with errors, whose values weren't saved", async () => {
        await load(
            `<p class="errornote">Please correct the errors below.</p>${CHANGELIST}`,
        );
        expect(leave()).toBe(true);
    });
});
