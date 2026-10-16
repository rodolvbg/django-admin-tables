import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The production file is a plain script with no exports: importing it
// for its side effect is enough to register the same delegated
// `change` listener a real page load would, on the same `document`
// jsdom provides here.
import "../../src/django_admin_rows/static/django_admin_rows/radio-select.js";

function addRadio({ name, group, checked = false }) {
    const input = document.createElement("input");
    input.type = "radio";
    input.className = "radio-select-exclusive";
    input.name = name;
    input.dataset.radioSelectGroup = group;
    input.checked = checked;
    document.body.appendChild(input);
    return input;
}

function change(input) {
    input.checked = true;
    input.dispatchEvent(new Event("change", { bubbles: true }));
}

describe("radio-select.js", () => {
    beforeEach(() => {
        document.body.innerHTML = "";
    });

    it("checking one radio unchecks the others in the same group", () => {
        const a = addRadio({
            name: "images-0-is_primary",
            group: "images::is_primary",
            checked: true,
        });
        const b = addRadio({
            name: "images-1-is_primary",
            group: "images::is_primary",
        });
        const c = addRadio({
            name: "images-2-is_primary",
            group: "images::is_primary",
        });

        change(b);

        expect(b.checked).toBe(true);
        expect(a.checked).toBe(false);
        expect(c.checked).toBe(false);
    });

    it("different configured fields are independent groups", () => {
        const primary = addRadio({
            name: "images-0-is_primary",
            group: "images::is_primary",
            checked: true,
        });
        const featuredA = addRadio({
            name: "images-0-is_featured",
            group: "images::is_featured",
        });
        const featuredB = addRadio({
            name: "images-1-is_featured",
            group: "images::is_featured",
        });

        change(featuredB);

        expect(featuredB.checked).toBe(true);
        expect(featuredA.checked).toBe(false);
        // Untouched: is_primary is a different group entirely.
        expect(primary.checked).toBe(true);
    });

    it("different inline formsets (different group prefixes) are independent", () => {
        const inlineOnePrimary = addRadio({
            name: "images-0-is_primary",
            group: "images::is_primary",
            checked: true,
        });
        const inlineTwoPrimary = addRadio({
            name: "attachments-0-is_primary",
            group: "attachments::is_primary",
        });

        change(inlineTwoPrimary);

        expect(inlineTwoPrimary.checked).toBe(true);
        expect(inlineOnePrimary.checked).toBe(true);
    });

    it("rows added after the initial page load are covered without rebinding", () => {
        // Simulates Django admin's "Add another": a delegated listener
        // already covers nodes that don't exist yet at import time.
        const a = addRadio({
            name: "images-0-is_primary",
            group: "images::is_primary",
            checked: true,
        });
        const b = addRadio({
            name: "images-1-is_primary",
            group: "images::is_primary",
        });
        const dynamicallyAdded = addRadio({
            name: "images-2-is_primary",
            group: "images::is_primary",
        });

        change(dynamicallyAdded);

        expect(dynamicallyAdded.checked).toBe(true);
        expect(a.checked).toBe(false);
        expect(b.checked).toBe(false);
    });

    it("ignores change events from unrelated inputs", () => {
        const text = document.createElement("input");
        text.type = "text";
        text.className = "radio-select-exclusive";
        document.body.appendChild(text);

        expect(() =>
            text.dispatchEvent(new Event("change", { bubbles: true })),
        ).not.toThrow();
    });

    it("a group key containing quotes doesn't break the internal selector", () => {
        const weird = addRadio({
            name: 'images-0-is_"weird"',
            group: 'images::is_"weird"',
            checked: true,
        });
        const other = addRadio({
            name: 'images-1-is_"weird"',
            group: 'images::is_"weird"',
        });

        expect(() => change(other)).not.toThrow();
        expect(other.checked).toBe(true);
        expect(weird.checked).toBe(false);
    });

    describe("when the browser provides CSS.escape", () => {
        afterEach(() => {
            vi.unstubAllGlobals();
        });

        it("uses it instead of the manual fallback", () => {
            // A real (if simplified) escaper, not a dummy: the resulting
            // selector still has to actually match the element in the DOM.
            const cssEscape = vi.fn((value) => value.replace(/["\\]/g, "\\$&"));
            vi.stubGlobal("CSS", { escape: cssEscape });

            const weird = addRadio({
                name: 'images-0-is_"weird"',
                group: 'images::is_"weird"',
                checked: true,
            });
            const other = addRadio({
                name: 'images-1-is_"weird"',
                group: 'images::is_"weird"',
            });

            change(other);

            expect(cssEscape).toHaveBeenCalledWith('images::is_"weird"');
            expect(other.checked).toBe(true);
            expect(weird.checked).toBe(false);
        });
    });
});
