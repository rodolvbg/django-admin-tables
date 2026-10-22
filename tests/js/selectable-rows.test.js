import { afterEach, describe, expect, it, vi } from "vitest";

const SCRIPT =
    "../../src/django_admin_tables/static/django_admin_tables/selectable-rows.js";

async function load(html, readyState = "complete") {
    document.body.innerHTML = html;
    vi.spyOn(document, "readyState", "get").mockReturnValue(readyState);
    vi.resetModules();
    await import(SCRIPT);
}

const COUNTER =
    '<span class="action-counter" data-actions-icnt="3">0 of 3 selected</span>';
const ROWS = `
    <table>
        <tr><td><input type="checkbox" disabled class="django-admin-tables-unselectable"></td></tr>
        <tr><td><input type="checkbox" class="action-select"></td></tr>
        <tr><td><input type="checkbox" class="action-select"></td></tr>
    </table>`;

const total = () =>
    document.querySelector(".action-counter").dataset.actionsIcnt;

describe("selectable-rows.js", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("counts only the rows that can be selected", async () => {
        await load(COUNTER + ROWS);
        expect(total()).toBe("2");
    });

    it("leaves the count alone when every row can be", async () => {
        await load(
            `${COUNTER}<table><tr><td><input class="action-select"></td></tr></table>`,
        );
        expect(total()).toBe("3");
    });

    it("waits for the page when it's still loading", async () => {
        await load(COUNTER + ROWS, "loading");
        expect(total()).toBe("3");
        document.dispatchEvent(new Event("DOMContentLoaded"));
        expect(total()).toBe("2");
    });
});
