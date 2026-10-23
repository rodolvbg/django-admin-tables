import { afterEach, describe, expect, it, vi } from "vitest";

const SCRIPT =
    "../../src/django_admin_tables/static/django_admin_tables/autosave.js";

const CONFIG = {
    url: "/admin/gallery/albumstacked/autosave/",
    fields: ["title", "is_featured", "when", "tags"],
    pk: "id",
    all: true,
    texts: { saving: "Saving…", saved: "Saved", failed: "Not saved" },
};

function page(config = CONFIG) {
    const json =
        config === null
            ? ""
            : `<script id="django-admin-tables-autosave" type="application/json">${
                  typeof config === "string" ? config : JSON.stringify(config)
              }</script>`;
    document.body.innerHTML = `${json}
        <form id="changelist-form">
            <input type="hidden" name="csrfmiddlewaretoken" value="tok">
            <select name="action"><option value="">--</option></select>
            <table><tr>
                <td><input type="hidden" name="form-0-id" value="7">
                    <input name="form-0-title" value="Winter"></td>
                <td><input type="checkbox" name="form-0-is_featured"></td>
                <td><input name="form-0-when_0" value="2026-10-23"><input name="form-0-when_1" value="10:00"></td>
                <td><select name="form-0-tags" multiple><option value="a" selected>a</option><option value="b">b</option></select></td>
                <td><textarea name="form-0-notes"></textarea></td>
                <td><input type="radio" name="form-0-size" value="s"></td>
            </tr></table>
        </form>`;
}

async function load(readyState = "complete") {
    vi.spyOn(document, "readyState", "get").mockReturnValue(readyState);
    vi.resetModules();
    await import(SCRIPT);
}

const field = (name) => document.querySelector(`[name="form-0-${name}"]`);
const status = (name) =>
    field(name)
        .closest("td")
        .querySelector(".django-admin-tables-autosave-status");

function change(input) {
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

function answer(status = 200, data = { saved: true }) {
    return vi.fn(async () => ({
        ok: status < 400,
        status,
        json: async () => {
            if (data instanceof Error) throw data;
            return data;
        },
    }));
}

const flush = async () => {
    for (let i = 0; i < 5; i += 1) await new Promise((r) => setTimeout(r, 0));
};

const sent = (fetch, call = 0) => [...fetch.mock.calls[call][1].body];

describe("autosave.js", () => {
    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it("saves a switch at once, with what it was", async () => {
        const fetch = answer();
        vi.stubGlobal("fetch", fetch);
        page();
        await load();
        field("is_featured").checked = true;
        change(field("is_featured"));
        expect(status("is_featured").textContent).toBe("Saving…");
        expect(status("is_featured").getAttribute("role")).toBe("status");
        await flush();
        const [url, init] = fetch.mock.calls[0];
        expect(url).toBe(CONFIG.url);
        expect(init.method).toBe("POST");
        expect(init.headers["X-CSRFToken"]).toBe("tok");
        expect(sent(fetch)).toEqual([
            ["prefix", "form-0"],
            ["field", "is_featured"],
            ["pk", "7"],
            ["check", "1"],
            ["form-0-is_featured", "on"],
        ]);
        expect(status("is_featured").textContent).toBe("Saved");
        expect(status("is_featured").dataset.state).toBe("saved");

        // Back: what it was is sent along.
        field("is_featured").checked = false;
        change(field("is_featured"));
        await flush();
        expect(sent(fetch, 1)).toEqual([
            ["prefix", "form-0"],
            ["field", "is_featured"],
            ["pk", "7"],
            ["check", "1"],
            ["previous-form-0-is_featured", "on"],
        ]);
    });

    it("says it's saved for a moment", async () => {
        vi.useFakeTimers();
        vi.stubGlobal("fetch", answer());
        page();
        await load();
        field("title").value = "Summer";
        change(field("title"));
        await vi.advanceTimersByTimeAsync(0);
        expect(status("title").textContent).toBe("Saved");
        await vi.advanceTimersByTimeAsync(2000);
        expect(status("title").textContent).toBe("");
        expect(status("title").dataset.state).toBeUndefined();
    });

    it("saves the inputs of one field together (a multi-widget, a multiple select)", async () => {
        const fetch = answer();
        vi.stubGlobal("fetch", fetch);
        page();
        await load();
        field("when_1").value = "11:00";
        change(field("when_1"));
        await flush();
        expect(sent(fetch)).toContainEqual(["form-0-when_0", "2026-10-23"]);
        expect(sent(fetch)).toContainEqual(["form-0-when_1", "11:00"]);
        expect(sent(fetch)).toContainEqual(["previous-form-0-when_1", "10:00"]);

        field("tags").options[1].selected = true;
        change(field("tags"));
        await flush();
        expect(sent(fetch, 1)).toContainEqual(["form-0-tags", "a"]);
        expect(sent(fetch, 1)).toContainEqual(["form-0-tags", "b"]);
        expect(sent(fetch, 1)).toContainEqual(["previous-form-0-tags", "a"]);
    });

    it("puts a field back when it isn't saved, saying why", async () => {
        vi.stubGlobal(
            "fetch",
            answer(409, { error: "Someone else changed it meanwhile." }),
        );
        page();
        await load();
        field("title").value = "Mine";
        change(field("title"));
        await flush();
        expect(field("title").value).toBe("Winter");
        expect(status("title").dataset.state).toBe("failed");
        expect(status("title").textContent).toBe(
            "Someone else changed it meanwhile.",
        );
        expect(status("title").title).toBe(status("title").textContent);

        // Without a reason (not JSON): "Not saved". All kinds, put back.
        vi.stubGlobal("fetch", answer(500, new Error("not JSON")));
        field("is_featured").checked = true;
        change(field("is_featured"));
        field("tags").options[1].selected = true;
        change(field("tags"));
        field("when_0").value = "";
        change(field("when_0"));
        await flush();
        expect(field("is_featured").checked).toBe(false);
        expect([...field("tags").selectedOptions].map((o) => o.value)).toEqual([
            "a",
        ]);
        expect(field("when_0").value).toBe("2026-10-23");
        expect(status("is_featured").textContent).toBe("Not saved");
        // Offline.
        vi.stubGlobal(
            "fetch",
            vi.fn(async () => Promise.reject(new TypeError())),
        );
        field("title").value = "Again";
        change(field("title"));
        await flush();
        expect(status("title").textContent).toBe("Not saved");
    });

    it("sends what changed meanwhile after the request under way, once", async () => {
        let finish;
        const fetch = vi.fn(
            () =>
                new Promise((resolve) => {
                    finish = () =>
                        resolve({
                            ok: true,
                            json: async () => ({ saved: true }),
                        });
                }),
        );
        vi.stubGlobal("fetch", fetch);
        page();
        await load();
        field("title").value = "A";
        change(field("title"));
        field("title").value = "AB";
        change(field("title"));
        field("title").value = "ABC";
        change(field("title"));
        expect(fetch).toHaveBeenCalledTimes(1);
        finish();
        await flush();
        expect(fetch).toHaveBeenCalledTimes(2);
        expect(sent(fetch, 1)).toContainEqual(["form-0-title", "ABC"]);
        expect(sent(fetch, 1)).toContainEqual(["previous-form-0-title", "A"]);
        finish();
        await flush();
        // Nothing new: nothing sent.
        change(field("title"));
        expect(fetch).toHaveBeenCalledTimes(2);
    });

    it("saves a text on Enter, instead of the changelist", async () => {
        const fetch = answer();
        vi.stubGlobal("fetch", fetch);
        page();
        await load();
        field("title").value = "Summer";
        const enter = new KeyboardEvent("keydown", {
            key: "Enter",
            bubbles: true,
            cancelable: true,
        });
        field("title").dispatchEvent(enter);
        expect(enter.defaultPrevented).toBe(true);
        await flush();
        expect(fetch).toHaveBeenCalledOnce();

        const other = new KeyboardEvent("keydown", {
            key: "a",
            bubbles: true,
            cancelable: true,
        });
        field("title").dispatchEvent(other);
        expect(other.defaultPrevented).toBe(false);
    });

    it("leaves alone what doesn't save itself", async () => {
        const fetch = answer();
        vi.stubGlobal("fetch", fetch);
        page({ ...CONFIG, fields: [...CONFIG.fields, "notes", "size"] });
        await load();
        // A textarea's Enter is a new line.
        const enter = new KeyboardEvent("keydown", {
            key: "Enter",
            bubbles: true,
            cancelable: true,
        });
        document.querySelector("[name=form-0-notes]").dispatchEvent(enter);
        expect(enter.defaultPrevented).toBe(false);
        document.querySelector("[name=action]").value = "";
        change(document.querySelector("[name=action]"));
        document
            .querySelector("[name=csrfmiddlewaretoken]")
            .dispatchEvent(
                new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
            );
        // A radio: its own value.
        field("size").checked = true;
        change(field("size"));
        await flush();
        expect(sent(fetch)).toContainEqual(["form-0-size", "s"]);
        expect(fetch).toHaveBeenCalledOnce();
    });

    it("works without a token or a primary key, and the status by the input", async () => {
        const fetch = answer();
        vi.stubGlobal("fetch", fetch);
        page();
        document.querySelector("[name=csrfmiddlewaretoken]").remove();
        document.querySelector("[name=form-0-id]").remove();
        const loose = document.createElement("div");
        loose.innerHTML = '<input name="form-1-title" value="x">';
        document.getElementById("changelist-form").append(loose);
        await load();
        const input = document.querySelector("[name=form-1-title]");
        input.value = "y";
        change(input);
        await flush();
        expect(fetch.mock.calls[0][1].headers["X-CSRFToken"]).toBe("");
        expect(sent(fetch)).toContainEqual(["pk", ""]);
        expect(
            loose.querySelector(".django-admin-tables-autosave-status"),
        ).not.toBe(null);
    });

    it("does nothing without its configuration or a changelist form", async () => {
        const fetch = answer();
        vi.stubGlobal("fetch", fetch);
        page(null);
        await load();
        change(field("title"));
        page("{nope");
        await load();
        change(field("title"));
        document.body.innerHTML = `<script id="django-admin-tables-autosave" type="application/json">${JSON.stringify(CONFIG)}</script>`;
        await load();
        expect(fetch).not.toHaveBeenCalled();
    });

    it("waits for the page, and sets up once", async () => {
        const fetch = answer();
        vi.stubGlobal("fetch", fetch);
        page();
        await load("loading");
        document.dispatchEvent(new Event("DOMContentLoaded"));
        await load();
        field("is_featured").checked = true;
        change(field("is_featured"));
        await flush();
        expect(fetch).toHaveBeenCalledOnce();
    });
});
