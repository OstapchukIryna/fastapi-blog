/**
 * Shared helpers for the pages that talk to /api directly.
 *
 * The two result windows — #successModal and #errorModal — live in
 * layout.html, so every page reports the outcome the same way and there
 * is one place to change how that looks. Their title and their button
 * label are set per call: a delete is not "Saved", and a button that
 * navigates does not say "Close".
 */

const NETWORK_ERROR =
  "Network error. Please check your connection and try again.";

// Error message extraction from API responses
export function getErrorMessage(error) {
  if (typeof error?.detail === "string") {
    return error.detail;
  } else if (Array.isArray(error?.detail)) {
    return error.detail.map((err) => err.msg).join(". ");
  }
  return "An error occurred. Please try again.";
}

/**
 * Say a validation failure the way the person hears it.
 *
 * Mirrors form_errors() in main.py on purpose: the same field can be
 * refused by the API here or by the server-side route without this
 * script, and hearing two different sentences for one mistake is worse
 * than either of them.
 */
function humaniseFieldError(item) {
  const limit = item.ctx ?? {};

  switch (item.type) {
    case "missing":
      return "Required.";
    case "string_too_short":
      return limit.min_length === 1
        ? "Required."
        : `At least ${limit.min_length} characters.`;
    case "string_too_long":
      return `At most ${limit.max_length} characters.`;
    default:
      return item.msg;
  }
}

/**
 * Field name to message, taken from FastAPI's 422 body.
 *
 * loc is ["body", "title"], so the field is its last element. Errors
 * about the body as a whole land under "body" and match no input, which
 * is why markFields looks controls up rather than trusting the key.
 */
export function getFieldErrors(error) {
  if (!Array.isArray(error?.detail)) return {};

  const fields = {};
  for (const item of error.detail) {
    const name = item.loc?.at(-1);
    if (typeof name === "string" && !(name in fields)) {
      fields[name] = humaniseFieldError(item);
    }
  }
  return fields;
}

/**
 * One line for the error window when the refusal is about fields.
 *
 * Names the fields rather than repeating their messages: those are
 * already under the inputs, and three copies of "Required." say less
 * than a list of what to look at.
 *
 * Returns null when nothing matched an input on this form — then the
 * caller falls back to getErrorMessage, which handles a 400 or a 404.
 */
export function describeFieldErrors(form, errors) {
  const named = Object.keys(errors).filter((name) => form.elements[name]);
  if (named.length === 0) return null;

  const labels = named.map(
    (name) =>
      form.querySelector(`label[for="${name}"]`)?.textContent.trim() ?? name,
  );

  return named.length === 1
    ? `Check the highlighted field: ${labels[0]}.`
    : `Check the highlighted fields: ${labels.join(", ")}.`;
}

// Show a Bootstrap modal by ID
export function showModal(modalId) {
  const modal = bootstrap.Modal.getOrCreateInstance(
    document.getElementById(modalId),
  );
  modal.show();
  return modal;
}

// Hide a Bootstrap modal by ID
export function hideModal(modalId) {
  const modal = bootstrap.Modal.getInstance(document.getElementById(modalId));
  if (modal) modal.hide();
}

/**
 * Dialogs that are open, or on their way to being open.
 *
 * Neither `display` nor the `show` class answers that question. Bootstrap
 * shows the backdrop first and displays the dialog itself a moment later,
 * so for the whole opening stretch a dialog that is already committed to
 * appearing still reads as closed — and acting on that reading is what
 * put two dialogs on screen at once. show.bs.modal fires at the very
 * start of that stretch and hidden.bs.modal at the end of the other one,
 * so the pair of events is the only honest record of the state.
 */
const opening = new WeakSet();

function trackModal(element) {
  if (!element || element.dataset.resultTracked) return;
  element.dataset.resultTracked = "1";
  element.addEventListener("show.bs.modal", () => opening.add(element));
  element.addEventListener("hidden.bs.modal", () => opening.delete(element));
}

/**
 * Close one window, then open the next — never both at once.
 *
 * Bootstrap counts one backdrop and one scroll lock per open dialog and
 * does that bookkeeping across the transitions. Overlapping them left
 * the closing dialog on screen with two backdrops behind it and the page
 * scroll-locked for good; the only way out was a reload. Waiting for
 * hidden.bs.modal makes the handover a sequence.
 *
 * The retry is the other half of the same problem: hide() is ignored
 * outright while a dialog is still animating in, and an ignored hide
 * emits no hidden.bs.modal. Someone who confirms a delete before the
 * confirmation has finished appearing would otherwise wait on an event
 * that never arrives and see no result at all. Hiding again on shown
 * covers exactly that window — once the entrance is over, hide() takes.
 */
function replaceModal(closingId, open) {
  const closing = closingId && document.getElementById(closingId);
  const instance = closing && bootstrap.Modal.getInstance(closing);

  if (!instance || !opening.has(closing)) {
    open();
    return;
  }

  let opened = false;
  closing.addEventListener(
    "hidden.bs.modal",
    () => {
      if (opened) return;
      opened = true;
      open();
    },
    { once: true },
  );

  instance.hide();
  closing.addEventListener("shown.bs.modal", () => instance.hide(), {
    once: true,
  });
}

/**
 * Fill one of the shared windows and show it.
 *
 * `then` runs after the window is closed, not when it opens: navigating
 * straight away would leave the message unread.
 */
function showResult(kind, { title, message, action, then }) {
  const name = kind === "success" ? "success" : "error";
  const modal = document.getElementById(`${name}Modal`);

  document.getElementById(`${name}ModalLabel`).textContent = title;
  document.getElementById(`${name}Message`).textContent = message;
  document.getElementById(`${name}Action`).textContent = action;

  if (then) {
    modal.addEventListener("hidden.bs.modal", then, { once: true });
  }

  if (kind === "success") {
    // One action, so put the keyboard on it: Bootstrap focuses the
    // container, which costs two tabs to reach the only thing there is
    // to do — and that thing is opening the post you just wrote.
    modal.addEventListener(
      "shown.bs.modal",
      () => document.getElementById("successAction").focus(),
      { once: true },
    );
  } else {
    // Bootstrap writes role="dialog" itself while opening, which drops
    // the alertdialog set in the markup. Restored afterwards: a window
    // that arrives because something failed should have its message read
    // out, not just its heading. Focus stays on the dialog for the same
    // reason — the message is the point, not the button.
    modal.addEventListener(
      "shown.bs.modal",
      () => modal.setAttribute("role", "alertdialog"),
      { once: true },
    );
  }

  showModal(`${name}Modal`);
}

// Report success. `action` names what closing the window will do.
export function showSuccess(
  message,
  { title = "Saved", action = "Close", then } = {},
) {
  showResult("success", { title, message, action, then });
}

// Report failure.
export function showError(
  message,
  { title = "Not saved", action = "Close", then } = {},
) {
  showResult("error", { title, message, action, then });
}

/**
 * Send JSON to the API.
 *
 * Returns {ok, data} rather than throwing: a 400 is an answer, not a
 * breakdown, and the caller wants the body either way. data is null for
 * 204 and for anything that is not JSON.
 */
export async function sendJSON(url, method, payload) {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: payload === undefined ? null : JSON.stringify(payload),
  });

  const data =
    response.status === 204 ? null : await response.json().catch(() => null);
  return { ok: response.ok, data };
}

/**
 * Mark the fields the API refused and clear the previous marks.
 *
 * Every field renders its error paragraph up front, hidden while empty,
 * so this only fills text in — no markup is built here. aria-invalid
 * goes with the class: the rose border is colour, and colour on its own
 * tells a screen reader nothing.
 */
export function markFields(form, errors = {}) {
  for (const control of form.querySelectorAll("[name]")) {
    const message = errors[control.name];
    control.classList.toggle("is-invalid", Boolean(message));
    if (message) {
      control.setAttribute("aria-invalid", "true");
    } else {
      control.removeAttribute("aria-invalid");
    }

    const note = form.querySelector(`#${control.name}-error`);
    if (note) {
      note.textContent = message ?? "";
      note.hidden = !message;
    }
  }
}

// One request per form at a time. See the guard in wireForm.
const inFlight = new WeakSet();

/**
 * Wire a form to the API: one submit path, one pair of windows.
 *
 * The form keeps its own action and method, so a browser without this
 * script still posts it the ordinary way. Only the parts that differ
 * per form are passed in.
 *
 * @param {HTMLFormElement} form
 * @param {object} options
 * @param {(fields: FormData) => {url: string, method: string, payload?: object}} options.request
 *   what to send.
 * @param {(data: object|null) => {title: string, message: string, action: string}} options.result
 *   the whole success window: its heading, its line, and what its button
 *   will do when pressed.
 * @param {(data: object|null) => void} [options.after]
 *   what to do once that window is closed — usually a redirect.
 * @param {{title?: string, action?: string}} [options.failure]
 *   overrides for the error window. Its message comes from the API.
 * @param {string} [options.busy]
 *   what the submit button says while the request is out. A disabled
 *   button with an unchanged label is the whole of the feedback
 *   otherwise, and a long post can take a noticeable moment to save.
 * @param {string} [options.closes]
 *   id of a modal the form lives in. It is closed first, and the result
 *   window opens only once it is gone.
 */
export function wireForm(
  form,
  { request, result, after, failure = {}, busy, closes },
) {
  // Watch the containing dialog from page load, so its state is already
  // known by the time a submit needs it
  if (closes) trackModal(document.getElementById(closes));

  form.addEventListener("submit", async (event) => {
    // Stop default form submission - we'll handle it with JavaScript
    event.preventDefault();

    // A form submitted with Enter has no event.submitter, so the button
    // is not a reliable latch — the flag is on the form itself.
    if (inFlight.has(form)) return;
    inFlight.add(form);

    const submitter = event.submitter ?? form.querySelector("[type=submit]");
    const idleLabel = submitter?.textContent;
    if (submitter) {
      submitter.disabled = true;
      if (busy) submitter.textContent = busy;
    }
    form.setAttribute("aria-busy", "true");

    // Send the reader back to the thing they have to fix, or to the
    // control they pressed. Bootstrap restores neither, and a modal shown
    // from script has no trigger to return focus to, so without this the
    // keyboard lands on <body> and has to tab in from the top of the page.
    // When the form itself lived in a dialog that has now closed, its
    // submit button is unfocusable, and the control that opened it is the
    // only place left that means anything.
    const recoverFocus = () => {
      const invalid = form.querySelector(".is-invalid");
      const reachable = submitter?.offsetParent ? submitter : null;
      const opener = closes
        ? document.querySelector(`[data-bs-target="#${closes}"]`)
        : null;
      (invalid ?? reachable ?? opener)?.focus();
    };

    try {
      const { url, method, payload } = request(new FormData(form));
      const { ok, data } = await sendJSON(url, method, payload);

      if (ok) {
        markFields(form);
        const outcome = result(data);
        replaceModal(closes, () =>
          showSuccess(outcome.message, {
            title: outcome.title,
            action: outcome.action,
            then: after ? () => after(data) : undefined,
          }),
        );
      } else {
        const fields = getFieldErrors(data);
        markFields(form, fields);
        const message =
          describeFieldErrors(form, fields) ?? getErrorMessage(data ?? {});
        replaceModal(closes, () =>
          showError(message, { ...failure, then: recoverFocus }),
        );
      }
    } catch {
      replaceModal(closes, () =>
        showError(NETWORK_ERROR, { ...failure, then: recoverFocus }),
      );
    } finally {
      inFlight.delete(form);
      form.removeAttribute("aria-busy");
      if (submitter) {
        submitter.disabled = false;
        if (busy) submitter.textContent = idleLabel;
      }
    }
  });
}
