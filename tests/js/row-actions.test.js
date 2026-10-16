import {
    afterEach,
    beforeAll,
    beforeEach,
    describe,
    expect,
    it,
    vi,
} from "vitest";

// A plain script with a delegated click listener on `document`: imported
// once, like a page load.
const SCRIPT =
    "../../src/django_admin_tables/static/django_admin_tables/row-actions.js";

function setUpPage({ confirmation = "", inline = false } = {}) {
    document.body.innerHTML = `
        <form id="page-form">
            <input name="csrfmiddlewaretoken" value="token">
            <input name="title" value="Peak">
            <div ${inline ? 'id="images-inline-controls" data-inline-controls="{}"' : ""}>
                <span class="django-admin-tables-row-actions" data-unsaved="Unsaved!" data-failed="Failed!">
                    <button type="button" data-django-admin-tables-row-action="/admin/run/"${
                        confirmation
                            ? ` data-confirmation="${confirmation}"`
                            : ""
                    }>Run</button>
                </span>
            </div>
        </form>`;
    return document.querySelector("button");
}

function submittedForms() {
    return [...document.querySelectorAll("body > form[hidden]")];
}

describe("row-actions.js", () => {
    let submit;
    // The page's form when the script loaded: the one it remembers.
    let loadedForm;

    beforeAll(async () => {
        setUpPage();
        loadedForm = document.getElementById("page-form");
        await import(SCRIPT);
    });

    beforeEach(() => {
        submit = vi
            .spyOn(HTMLFormElement.prototype, "submit")
            .mockImplementation(() => {});
        vi.spyOn(window, "confirm").mockReturnValue(true);
    });

    afterEach(() => {
        vi.restoreAllMocks();
        delete globalThis.DjangoAdminInlineControls;
        document
            .getElementById("django-admin-tables-row-action-status")
            ?.remove();
    });

    it("posts the action in a form of its own, back to this page", () => {
        setUpPage().click();

        const [form] = submittedForms();
        expect(form.method).toBe("post");
        expect(form.getAttribute("action")).toBe("/admin/run/");
        expect(new FormData(form).get("csrfmiddlewaretoken")).toBe("token");
        expect(new FormData(form).get("next")).toBe(window.location.href);
        expect(submit).toHaveBeenCalledOnce();
    });

    it("asks for the action's confirmation", () => {
        window.confirm.mockReturnValue(false);
        setUpPage({ confirmation: "Sure?" }).click();

        expect(window.confirm).toHaveBeenCalledWith("Sure?");
        expect(submit).not.toHaveBeenCalled();
    });

    it("warns about the page's unsaved changes", () => {
        document.body.replaceChildren(loadedForm);
        const title = loadedForm.querySelector("[name=title]");
        const button = loadedForm.querySelector("button");

        button.click(); // Unchanged: no warning.
        expect(window.confirm).not.toHaveBeenCalled();
        expect(submit).toHaveBeenCalledOnce();

        title.value = "Edited";
        window.confirm.mockReturnValue(false);
        button.click();

        expect(window.confirm).toHaveBeenCalledWith("Unsaved!");
        expect(submit).toHaveBeenCalledOnce();
        title.value = "Peak";
    });

    it("takes the CSRF token from the cookie when the page has no input", () => {
        const button = setUpPage();
        document.querySelector("[name=csrfmiddlewaretoken]").remove();
        // biome-ignore lint/suspicious/noDocumentCookie: Django's CSRF cookie, read by the script.
        document.cookie = "csrftoken=from-cookie";

        button.click();

        expect(
            new FormData(submittedForms()[0]).get("csrfmiddlewaretoken"),
        ).toBe("from-cookie");
        // biome-ignore lint/suspicious/noDocumentCookie: removing it again.
        document.cookie = "csrftoken=; max-age=0";
    });

    it("posts without a CSRF token when the page has none", () => {
        const button = setUpPage();
        document.querySelector("[name=csrfmiddlewaretoken]").remove();

        button.click();

        expect(
            new FormData(submittedForms()[0]).get("csrfmiddlewaretoken"),
        ).toBe("");
    });

    it("ignores other clicks", () => {
        setUpPage();
        document.querySelector("[name=title]").click();
        expect(submit).not.toHaveBeenCalled();
    });

    describe("on a django-admin-inline-controls inline", () => {
        let controls;
        let state;

        function respond(body, headers = {}, url = "/admin/run/") {
            vi.spyOn(window, "fetch").mockResolvedValue({
                url,
                headers: new Headers(headers),
                json: async () => body,
                blob: async () => new Blob(["data"]),
            });
        }

        beforeEach(() => {
            state = {
                dirty: false,
                config: { messages: { unsaved: "Lose?" } },
            };
            controls = {
                stateOf: vi.fn(() => state),
                navigate: vi.fn(async () => {}),
            };
            globalThis.DjangoAdminInlineControls = controls;
        });

        function status() {
            return document.getElementById(
                "django-admin-tables-row-action-status",
            );
        }

        it("runs the action, then refreshes only the inline", async () => {
            respond(
                { status: "done", message: "Featured." },
                { "Content-Type": "application/json" },
            );
            setUpPage({ inline: true }).click();

            await vi.waitFor(() =>
                expect(controls.navigate).toHaveBeenCalled(),
            );
            const [url, options] = window.fetch.mock.calls[0];
            expect(url).toBe("/admin/run/");
            expect(options.headers["X-Requested-With"]).toBe("XMLHttpRequest");
            expect(options.body.get("csrfmiddlewaretoken")).toBe("token");
            expect(controls.navigate.mock.calls[0][1]).toBe(
                window.location.href,
            );
            await vi.waitFor(() =>
                expect(status()?.textContent).toBe("Featured."),
            );
            expect(status().getAttribute("role")).toBe("status");
            expect(submit).not.toHaveBeenCalled();
        });

        it("confirms losing the inline's unsaved rows first", async () => {
            state.dirty = true;
            window.confirm.mockReturnValue(false);
            respond({}, { "Content-Type": "application/json" });

            setUpPage({ inline: true }).click();

            expect(window.confirm).toHaveBeenCalledWith("Lose?");
            expect(window.fetch).not.toHaveBeenCalled();
        });

        it("doesn't ask twice when it was confirmed", async () => {
            state.dirty = true;
            respond(
                { status: "done", message: "" },
                { "Content-Type": "application/json" },
            );

            setUpPage({ inline: true }).click();

            await vi.waitFor(() =>
                expect(controls.navigate).toHaveBeenCalled(),
            );
            expect(state.dirty).toBe(false);
            expect(status()).toBeNull();
        });

        it("works without the inline's state", async () => {
            controls.stateOf = undefined;
            respond(
                { status: "error", message: "No." },
                { "Content-Type": "application/json" },
            );

            setUpPage({ inline: true }).click();

            await vi.waitFor(() => expect(status()?.textContent).toBe("No."));
            expect(status().className).toContain(
                "django-admin-tables-row-action-error",
            );
        });

        it("downloads a file the action returns", async () => {
            respond(null, {
                "Content-Disposition": 'attachment; filename="images.csv"',
            });
            URL.createObjectURL = vi.fn(() => "blob:x");
            URL.revokeObjectURL = vi.fn();
            const click = vi
                .spyOn(HTMLAnchorElement.prototype, "click")
                .mockImplementation(() => {});

            setUpPage({ inline: true }).click();

            await vi.waitFor(() => expect(click).toHaveBeenCalled());
            expect(click.mock.contexts[0].download).toBe("images.csv");
            expect(controls.navigate).not.toHaveBeenCalled();
        });

        it("names a download without a filename", async () => {
            respond(null, { "Content-Disposition": "attachment" });
            URL.createObjectURL = vi.fn(() => "blob:x");
            URL.revokeObjectURL = vi.fn();
            const click = vi
                .spyOn(HTMLAnchorElement.prototype, "click")
                .mockImplementation(() => {});

            setUpPage({ inline: true }).click();

            await vi.waitFor(() => expect(click).toHaveBeenCalled());
            expect(click.mock.contexts[0].download).toBe("download");
        });

        it("goes to another page the action returns", async () => {
            respond(
                null,
                { "Content-Type": "text/html" },
                "http://localhost/step/",
            );
            const assign = vi.fn();
            vi.spyOn(window, "location", "get").mockReturnValue({
                href: "http://localhost/admin/",
                assign,
            });

            setUpPage({ inline: true }).click();

            await vi.waitFor(() =>
                expect(assign).toHaveBeenCalledWith("http://localhost/step/"),
            );
        });

        it("tells when the request fails", async () => {
            vi.spyOn(window, "fetch").mockRejectedValue(new Error("offline"));

            setUpPage({ inline: true }).click();

            await vi.waitFor(() =>
                expect(status()?.textContent).toBe("Failed!"),
            );
            expect(controls.navigate).not.toHaveBeenCalled();
        });

        it("has an empty failure message outside its wrapper", async () => {
            vi.spyOn(window, "fetch").mockRejectedValue(new Error("offline"));
            const button = setUpPage({ inline: true });
            button
                .closest(".django-admin-tables-row-actions")
                .replaceWith(button);

            button.click();

            await vi.waitFor(() => expect(window.fetch).toHaveBeenCalled());
            expect(status()).toBeNull();
        });

        it("reuses its status element", async () => {
            respond(
                { status: "done", message: "One." },
                { "Content-Type": "application/json" },
            );
            setUpPage({ inline: true }).click();
            await vi.waitFor(() => expect(status()?.textContent).toBe("One."));

            respond(
                { status: "done", message: "Two." },
                { "Content-Type": "application/json" },
            );
            document.querySelector("button").click();
            await vi.waitFor(() => expect(status()?.textContent).toBe("Two."));
            expect(document.querySelectorAll("[role=status]")).toHaveLength(1);
        });
    });
});
