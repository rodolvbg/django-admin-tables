import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The production file is a plain script that runs once per page load:
// each test sets the page up, then imports a fresh copy of it.
const SCRIPT =
    "../../src/django_admin_tables/static/django_admin_tables/columns.js";
let storageKey;
let counter = 0;

function menuItem(name, maxWidth) {
    if (!maxWidth) {
        return `<label><input type="checkbox" data-django-admin-tables-column="${name}" checked> ${name}</label>`;
    }
    return `<label><input type="checkbox" data-django-admin-tables-column="${name}" data-django-admin-tables-max-width="${maxWidth}" checked> ${name}<span class="django-admin-tables-columns__note" hidden>(narrow screen)</span></label>`;
}

function setUpPage({
    hidden = [],
    columns = ["album_link", "is_primary"],
    config,
    maxWidths = {},
} = {}) {
    storageKey = `test:${++counter}`;
    const script = document.createElement("script");
    script.id = "django-admin-tables-columns";
    script.type = "application/json";
    script.textContent =
        config ?? JSON.stringify({ storageKey, hidden, columns });
    document.head.appendChild(script);

    document.body.innerHTML = `
        <details class="django-admin-tables-columns">
            <summary>Columns</summary>
            <fieldset class="django-admin-tables-columns__menu">
                ${columns.map((name) => menuItem(name, maxWidths[name])).join("")}
            </fieldset>
        </details>
        <p id="outside">outside</p>`;
}

async function runScript() {
    vi.resetModules();
    await import(SCRIPT);
}

function style() {
    return document.getElementById("django-admin-tables-hidden-columns")
        ?.textContent;
}

function checkbox(name) {
    return document.querySelector(
        `[data-django-admin-tables-column="${name}"]`,
    );
}

function toggle(name) {
    const input = checkbox(name);
    input.checked = !input.checked;
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

describe("columns.js", () => {
    beforeEach(() => {
        document.head.innerHTML = "";
        window.localStorage.clear();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("does nothing without its config", async () => {
        document.body.innerHTML = "";
        await runScript();
        expect(style()).toBeUndefined();
    });

    it("does nothing with a broken config", async () => {
        setUpPage({ config: "{not json" });
        await runScript();
        expect(style()).toBeUndefined();
    });

    it("hides the admin's default hidden columns", async () => {
        setUpPage({ hidden: ["is_primary"] });
        await runScript();

        expect(style()).toBe(
            "#result_list .column-is_primary, #result_list .field-is_primary { display: none; }",
        );
        expect(checkbox("is_primary").checked).toBe(false);
        expect(checkbox("album_link").checked).toBe(true);
    });

    it("shows every column when none is hidden", async () => {
        setUpPage();
        await runScript();
        expect(style()).toBe("");
    });

    it("prefers the user's stored choice, ignoring unknown columns", async () => {
        setUpPage({ hidden: ["is_primary"] });
        window.localStorage.setItem(
            storageKey,
            JSON.stringify(["album_link", "gone"]),
        );
        await runScript();

        expect(style()).toContain(".column-album_link");
        expect(style()).not.toContain("is_primary");
        expect(style()).not.toContain("gone");
        expect(checkbox("is_primary").checked).toBe(true);
    });

    it("falls back to the default on a stored value that isn't a list", async () => {
        setUpPage({ hidden: ["is_primary"] });
        window.localStorage.setItem(storageKey, '"album_link"');
        await runScript();
        expect(style()).toContain(".column-is_primary");
    });

    it("hides and shows a column on toggle, and remembers it", async () => {
        setUpPage();
        await runScript();

        toggle("album_link");
        expect(style()).toContain(".field-album_link");
        expect(JSON.parse(window.localStorage.getItem(storageKey))).toEqual([
            "album_link",
        ]);

        toggle("album_link");
        expect(style()).toBe("");
        expect(JSON.parse(window.localStorage.getItem(storageKey))).toEqual([]);
    });

    it("ignores changes of other inputs", async () => {
        setUpPage();
        await runScript();
        const other = document.createElement("input");
        other.type = "checkbox";
        document.body.appendChild(other);

        other.dispatchEvent(new Event("change", { bubbles: true }));

        expect(window.localStorage.getItem(storageKey)).toBeNull();
    });

    it("still works when storage is unavailable", async () => {
        setUpPage({ hidden: ["is_primary"] });
        vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
            throw new Error("blocked");
        });
        vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
            throw new Error("blocked");
        });
        await runScript();

        expect(style()).toContain(".column-is_primary");
        toggle("album_link");
        expect(style()).toContain(".column-album_link");
    });

    it("escapes class names for the selector", async () => {
        setUpPage({ hidden: ["a.b"], columns: ["a.b"] });
        await runScript();
        expect(style()).toContain(".column-a\\.b");
    });

    it("uses CSS.escape when the browser has it", async () => {
        setUpPage({ hidden: ["a.b"], columns: ["a.b"] });
        window.CSS = { escape: () => "escaped" };
        try {
            await runScript();
        } finally {
            delete window.CSS;
        }
        expect(style()).toContain(".column-escaped");
    });

    it("waits for the page when it's still loading", async () => {
        setUpPage({ hidden: ["is_primary"] });
        vi.spyOn(document, "readyState", "get").mockReturnValue("loading");
        await runScript();

        expect(style()).toContain(".column-is_primary");
        expect(checkbox("is_primary").checked).toBe(true);

        document.dispatchEvent(new Event("DOMContentLoaded"));
        expect(checkbox("is_primary").checked).toBe(false);
    });

    describe("columns the viewport hides", () => {
        let listeners;
        let matches;

        function mockMatchMedia() {
            listeners = [];
            window.matchMedia = vi.fn((query) => ({
                get matches() {
                    return matches;
                },
                media: query,
                addEventListener: (_type, listener) => listeners.push(listener),
            }));
        }

        afterEach(() => {
            delete window.matchMedia;
        });

        function note(name) {
            return checkbox(name).parentElement.querySelector(
                ".django-admin-tables-columns__note",
            );
        }

        it("are unchecked, disabled and noted while narrow", async () => {
            setUpPage({ maxWidths: { album_link: "767.98" } });
            matches = true;
            mockMatchMedia();
            await runScript();

            expect(window.matchMedia).toHaveBeenCalledWith(
                "(max-width: 767.98px)",
            );
            expect(checkbox("album_link").checked).toBe(false);
            expect(checkbox("album_link").disabled).toBe(true);
            expect(note("album_link").hidden).toBe(false);
            expect(checkbox("is_primary").disabled).toBe(false);
        });

        it("get the user's choice back when wide again", async () => {
            setUpPage({
                hidden: ["album_link"],
                maxWidths: { album_link: "767.98", is_primary: "1023.98" },
            });
            matches = true;
            mockMatchMedia();
            await runScript();

            matches = false;
            for (const listener of listeners) {
                listener();
            }

            expect(checkbox("album_link").disabled).toBe(false);
            expect(checkbox("album_link").checked).toBe(false);
            expect(checkbox("is_primary").checked).toBe(true);
            expect(note("is_primary").hidden).toBe(true);
        });

        it("work without a note", async () => {
            setUpPage({ maxWidths: { album_link: "767.98" } });
            note("album_link").remove();
            matches = true;
            mockMatchMedia();
            await runScript();
            expect(checkbox("album_link").disabled).toBe(true);
        });

        it("are left alone without matchMedia", async () => {
            setUpPage({ maxWidths: { album_link: "767.98" } });
            await runScript();
            expect(checkbox("album_link").disabled).toBe(false);
            expect(checkbox("album_link").checked).toBe(true);
        });
    });

    describe("responsive_columns", () => {
        function addResponsiveConfig(scope, rules, text) {
            const script = document.createElement("script");
            script.id = `django-admin-tables-responsive-${scope.slice(1)}`;
            script.type = "application/json";
            script.textContent = text ?? JSON.stringify({ scope, rules });
            document.head.appendChild(script);
            return script;
        }

        function responsiveStyle(scope) {
            return document.getElementById(
                `django-admin-tables-responsive-${scope.slice(1)}-style`,
            )?.textContent;
        }

        it("applies each table's media queries", async () => {
            document.body.innerHTML = "";
            addResponsiveConfig("#result_list", [
                { max_width: 1023.98, classes: ["title"] },
                { max_width: 767.98, classes: ["album_link", "pk"] },
            ]);
            addResponsiveConfig("#images-group", [
                { max_width: 767.98, classes: ["is_featured"] },
            ]);
            await runScript();

            expect(responsiveStyle("#result_list")).toBe(
                "@media (max-width: 1023.98px) { #result_list .column-title, #result_list .field-title { display: none; } }\n" +
                    "@media (max-width: 767.98px) { #result_list .column-album_link, #result_list .field-album_link,\n#result_list .column-pk, #result_list .field-pk { display: none; } }",
            );
            expect(responsiveStyle("#images-group")).toContain(
                "#images-group .column-is_featured",
            );
        });

        it("applies a config once, however many times the script runs", async () => {
            document.body.innerHTML = "";
            addResponsiveConfig("#images-group", [
                { max_width: 767.98, classes: ["is_featured"] },
            ]);
            await runScript();
            document.getElementById(
                "django-admin-tables-responsive-images-group-style",
            ).textContent = "changed";

            // The script tag after the next inline.
            addResponsiveConfig("#chapters-group", [
                { max_width: 767.98, classes: ["notes"] },
            ]);
            await runScript();

            expect(responsiveStyle("#images-group")).toBe("changed");
            expect(responsiveStyle("#chapters-group")).toContain(
                ".field-notes",
            );
        });

        it("skips a broken config", async () => {
            document.body.innerHTML = "";
            addResponsiveConfig("#result_list", [], "{not json");
            await runScript();
            expect(responsiveStyle("#result_list")).toBeUndefined();
        });

        it("works along the columns menu", async () => {
            setUpPage({ hidden: ["is_primary"] });
            addResponsiveConfig("#result_list", [
                { max_width: 767.98, classes: ["album_link"] },
            ]);
            await runScript();

            expect(style()).toContain(".column-is_primary");
            expect(responsiveStyle("#result_list")).toContain(
                ".column-album_link",
            );
        });
    });

    describe("constructed stylesheets", () => {
        class FakeSheet {
            replaceSync(text) {
                this.cssText = text;
            }
        }

        beforeEach(() => {
            window.CSSStyleSheet = FakeSheet;
            document.adoptedStyleSheets = [];
        });

        afterEach(() => {
            delete window.CSSStyleSheet;
            delete document.adoptedStyleSheets;
        });

        it("are used instead of <style> elements, for a CSP", async () => {
            setUpPage({ hidden: ["is_primary"] });
            await runScript();

            expect(style()).toBeUndefined();
            expect(document.adoptedStyleSheets).toHaveLength(1);
            expect(document.adoptedStyleSheets[0].cssText).toContain(
                ".column-is_primary",
            );

            // Its own sheet is updated (earlier tests' copies of the script
            // still listen on this document, and add theirs).
            toggle("album_link");
            expect(document.adoptedStyleSheets[0].cssText).toContain(
                ".column-album_link",
            );
        });

        it("fall back to a <style> element when they fail", async () => {
            FakeSheet.prototype.replaceSync = () => {
                throw new Error("unsupported");
            };
            try {
                setUpPage({ hidden: ["is_primary"] });
                await runScript();
            } finally {
                FakeSheet.prototype.replaceSync = function (text) {
                    this.cssText = text;
                };
            }
            expect(style()).toContain(".column-is_primary");
        });
    });

    it("runs the menu once, however many times the script runs", async () => {
        setUpPage();
        await runScript();
        await runScript();
        toggle("album_link");
        expect(JSON.parse(window.localStorage.getItem(storageKey))).toEqual([
            "album_link",
        ]);
    });

    it("closes the menu on a click outside it, or on Escape", async () => {
        setUpPage();
        await runScript();
        const menu = document.querySelector("details");

        menu.open = true;
        checkbox("album_link").click();
        expect(menu.open).toBe(true);
        document.getElementById("outside").click();
        expect(menu.open).toBe(false);

        menu.open = true;
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
        expect(menu.open).toBe(true);
        document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
        expect(menu.open).toBe(false);
        expect(document.activeElement).toBe(menu.querySelector("summary"));
    });
});
