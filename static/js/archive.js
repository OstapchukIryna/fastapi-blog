/**
 * «Ещё» для списков, которые API умеет отдавать порциями.
 *
 * Первую порцию рисует сервер, следующие — этот модуль, из того же
 * /api, который отвечает Postman'у. Второго источника правды нет: и
 * страница, и JSON идут через один сервис.
 *
 * Состояние живёт в data-атрибутах блока, а не в переменной модуля.
 * Причин две: на странице может оказаться два списка, и перезагрузка
 * обязана возвращать честное «сколько показано» без участия скрипта.
 *
 * Разметка карточек здесь повторяет макросы из templates/_cards.html.
 * Это единственное сознательное дублирование в проекте: без шага
 * сборки шаблон Jinja в браузере не выполнить. Меняешь там — меняй
 * здесь; шов проверяется глазами на границе первой и второй порции.
 */

import { escapeHtml, formatDate, sendRequest } from "./utils.js";

const LOAD_FAILED = "Could not load more. Check your connection and try again.";

// --- Карточки ---------------------------------------------------------

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

// Оглавление, если оно есть, иначе аннотация — ровно как в макросе.
function cardBody(post) {
  if (post.outline?.length) {
    const items = post.outline
      .map((heading) => `<li>${escapeHtml(heading)}</li>`)
      .join("");
    return `<ol class="post-outline mono-label">${items}</ol>`;
  }
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

// --- Лента ------------------------------------------------------------

/**
 * Wire one feed block to its list.
 *
 * @param {HTMLElement} feed блок с data-feed и состоянием в атрибутах.
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
      // Дошли до конца: кнопке больше нечего делать, и она уходит —
      // отключённая кнопка обещает, что что-то ещё будет.
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

      // Первая из приехавших получает фокус: без этого читатель с
      // клавиатуры остаётся на кнопке, которая уехала вниз на экран.
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
