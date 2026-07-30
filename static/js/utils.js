//Shared helpers for the pages that talk to /api directly.
//The two result windows — #successModal and #errorModal are in layout.html.

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

// Say a validation failure the way the person hears it.
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

// Field name to message, taken from FastAPI's 422 body.
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

// One line for the error window when the refusal is about fields.
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

// Dialogs that are open, or on their way to being open.
const opening = new WeakSet();

function trackModal(element) {
  if (!element || element.dataset.resultTracked) return;
  element.dataset.resultTracked = "1";
  element.addEventListener("show.bs.modal", () => opening.add(element));
  element.addEventListener("hidden.bs.modal", () => opening.delete(element));
}

//  Close one window, then open the next and never both at once.
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

// Fill one of the shared windows and show it.
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
    modal.addEventListener(
      "shown.bs.modal",
      () => document.getElementById("successAction").focus(),
      { once: true },
    );
  } else {
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
 * Send a body to the API and hand back both outcomes the same way.
 *
 * `encoding` is "json" everywhere except the token endpoint:
 * OAuth2PasswordRequestForm reads the credentials from a form body, not
 * from JSON, so signing in has to be sent the other way. It is the one
 * exception, which is why it is a parameter rather than a second helper.
 */
export async function sendJSON(url, method, payload, encoding = "json") {
  const form = encoding === "form";
  const response = await fetch(url, {
    method,
    headers: {
      "Content-Type": form
        ? "application/x-www-form-urlencoded"
        : "application/json",
    },
    body:
      payload === undefined
        ? null
        : form
          ? new URLSearchParams(payload).toString()
          : JSON.stringify(payload),
  });

  const data =
    response.status === 204 ? null : await response.json().catch(() => null);
  return { ok: response.ok, data };
}

//  Mark the fields the API refused and clear the previous marks
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

// One request per form at a time
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
 * @param {(fields: FormData) => {url: string, method: string, payload?: object, encoding?: "json"|"form"}} options.request
 *   what to send.
 * @param {(data: object|null) => {title: string, message: string, action: string}|null} options.result
 *   the whole success window: its heading, its line, and what its button
 *   will do when pressed. Return null to open no window at all, for a
 *   success the destination already announces — signing in is the case:
 *   a dialog between the password and the page is pure friction.
 * @param {(data: object|null) => void} [options.after]
 *   what to do once that window is closed, or straight away when there
 *   is no window — usually a redirect.
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
    event.preventDefault();

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
    // control they pressed.
    const recoverFocus = () => {
      const invalid = form.querySelector(".is-invalid");
      const reachable = submitter?.offsetParent ? submitter : null;
      const opener = closes
        ? document.querySelector(`[data-bs-target="#${closes}"]`)
        : null;
      (invalid ?? reachable ?? opener)?.focus();
    };

    try {
      const { url, method, payload, encoding } = request(new FormData(form));
      const { ok, data } = await sendJSON(url, method, payload, encoding);

      if (ok) {
        markFields(form);
        const outcome = result(data);
        if (outcome) {
          replaceModal(closes, () =>
            showSuccess(outcome.message, {
              title: outcome.title,
              action: outcome.action,
              then: after ? () => after(data) : undefined,
            }),
          );
        } else {
          // No window asked for: whatever `after` does is the report.
          after?.(data);
        }
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
