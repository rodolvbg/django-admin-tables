(() => {
    var SELECTOR = 'input[type="radio"].radio-select-exclusive';

    function escapeAttrValue(value) {
        if (window.CSS && typeof CSS.escape === "function") {
            return CSS.escape(value);
        }
        return String(value).replace(/["\\]/g, "\\$&");
    }

    function uncheckOthersInGroup(radio) {
        var group = radio.dataset.radioSelectGroup;
        var selector =
            SELECTOR +
            '[data-radio-select-group="' +
            escapeAttrValue(group) +
            '"]';
        document.querySelectorAll(selector).forEach((other) => {
            if (other !== radio) {
                other.checked = false;
            }
        });
    }

    // A single delegated listener on `document` covers inline rows added
    // later too (Django admin's "Add another"), since `change` bubbles
    // from any input inserted into the page — no MutationObserver or
    // dependency on Django's internal jQuery formset events needed.
    document.addEventListener("change", (event) => {
        var radio = event.target;
        if (radio.matches?.(SELECTOR) && radio.checked) {
            uncheckOthersInGroup(radio);
        }
    });
})();
