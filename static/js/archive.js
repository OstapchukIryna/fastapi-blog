/**
 * "Load more" for the lists the API can serve in batches.
 *
 * The server renders the first batch; this module renders the rest, from
 * the same /api that answers Postman. There is no second source of
 * truth: the page and the JSON both go through one service.
 *
 * State lives in the block's data attributes rather than in a module
 * variable. Two reasons: a page may carry more than one list, and a
 * reload has to restore an honest "how many are shown" without the
 * script being involved.
 *
 * ! The card markup below mirrors the macros in templates/_cards.html.
 * ! This is the one deliberate duplication in the project — without a
 * ! build step a Jinja macro cannot run in a browser. Change it there
 * ! and change it here; the seam shows up between the first batch and
 * ! the second.
 */

import { escapeHtml, formatDate, sendRequest } from "./utils.js";

const LOAD_FAILED = "Could not load more. Check your connection and try again.";

// --- Cards ------------------------------------------------------------

function tagLinks(tags) {
  if (!tags?.length) return "";

  const links = tags
    .map((tag) => {
      const safe = escapeHtml(tag);
      return `<a href="/tags/${encodeURIComponent(tag)}">#${safe}</a>`;
    })
    .join("");

  return `<div class="card-tags mono-label">${links}</div>`;
}

function cardBody(post) {
  return `<p class="post-excerpt">${escapeHtml(post.summary)}</p>`;
}

function archiveItem(post) {
  return `
    <article class="archive-item">
        <p class="post-meta mono-label">
            <span>${formatDate(post.date_posted)}</span>
            <span class="sep">/</span>
            <span>${post.reading_minutes} min</span>
        </p>
        <h2>
            <a class="post-title stretched" href="/posts/${post.id}">${escapeHtml(post.title)}</a>
        </h2>
        ${cardBody(post)}
        ${tagLinks(post.tags)}
    </article>`;
}

function topicRow(topic) {
  const posts = `${topic.count} post${topic.count === 1 ? "" : "s"}`;
  return `
    <a class="topic-row" href="/tags/${encodeURIComponent(topic.name)}">
        <span class="name">${escapeHtml(topic.name)}</span>
        <span class="count mono-label">${posts}</span>
    </a>`;
}

const RENDERERS = { post: archiveItem, topic: topicRow };

// --- Feed -------------------------------------------------------------

/**
 * Wire one feed block to its list.
 *
 * @param {HTMLElement} feed the data-feed block, state in its attributes.
 */
function wireFeed(feed) {
  const button = feed.querySelector("[data-feed-button]");
  const status = feed.querySelector("[data-feed-status]");
  const fill = feed.querySelector("[data-feed-fill]");
  const list = document.querySelector("[data-feed-list]");
  const render = RENDERERS[feed.dataset.item];

  if (!button || !list || !render) return;

  const noun = feed.dataset.noun;
  const limit = Number(feed.dataset.limit);
  let busy = false;

  const plural = (count) => `${noun}${count === 1 ? "" : "s"}`;

  function paint(shown, total) {
    feed.dataset.skip = String(shown);
    fill?.style.setProperty("--shown", String(shown));

    if (shown < total) {
      status.textContent = `${shown} of ${total}`;
    } else {
      // * The end: the button has nothing left to do, so it goes. A
      // * disabled button still promises that something more exists.
      status.textContent = `All ${total} ${plural(total)}`;
      button.remove();
    }
  }

  button.addEventListener("click", async () => {
    if (busy) return;
    busy = true;

    const idle = button.innerHTML;
    button.disabled = true;
    button.textContent = "Loading…";
    feed.setAttribute("aria-busy", "true");

    try {
      const skip = Number(feed.dataset.skip);
      const url = `${feed.dataset.url}?skip=${skip}&limit=${limit}`;
      const { ok, data } = await sendRequest(url);

      if (!ok || !data) {
        status.textContent = LOAD_FAILED;
        button.innerHTML = "Try again";
        return;
      }

      // * Focus the first arrival: without this a keyboard reader is
      // * left on a button that has just moved down the page.
      const first = list.children.length;
      list.insertAdjacentHTML("beforeend", data.items.map(render).join(""));
      list.children[first]?.querySelector("a")?.focus({ preventScroll: true });

      button.innerHTML = idle;
      paint(skip + data.items.length, data.total);
    } catch {
      status.textContent = LOAD_FAILED;
      button.innerHTML = "Try again";
    } finally {
      busy = false;
      button.disabled = false;
      feed.removeAttribute("aria-busy");
    }
  });
}

/** Wire every feed on the page. */
export function wireFeeds() {
  for (const feed of document.querySelectorAll("[data-feed]")) {
    wireFeed(feed);
  }
}
