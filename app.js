const state = {
  posts: [],
  filter: "all",
  query: "",
  visibleCount: 4,
};

const gallery = document.querySelector("#gallery");
const resultCount = document.querySelector("#result-count");
const emptyState = document.querySelector("#empty-state");
const loadMore = document.querySelector("#load-more");
const searchInput = document.querySelector("#search-input");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getFilteredPosts() {
  const query = state.query.trim().toLowerCase();

  return state.posts.filter((post) => {
    const hashtags = Array.isArray(post.hashtags) ? post.hashtags : [];
    const label = post.label || "";
    const title = post.title || "";
    const excerpt = post.excerpt || "";

    const matchesFilter =
      state.filter === "all" ||
      label === state.filter ||
      hashtags.includes(state.filter);

    const searchable =
      `${title} ${excerpt} ${label} ${hashtags.join(" ")}`
        .toLowerCase();

    return matchesFilter && (!query || searchable.includes(query));
  });
}

function render() {
  const filtered = getFilteredPosts();
  const visible = filtered.slice(0, state.visibleCount);

  resultCount.textContent =
    `Showing ${visible.length} of ${filtered.length} community posts`;

  gallery.innerHTML = visible
    .map((post) => {
      const instagramUrl =
        post.permalink || "https://www.instagram.com/theartofed/";

      return `
        <article class="post-card">
          <div class="post-image-wrap">
            <img
              class="post-image"
              src="${escapeHtml(post.image)}"
              alt="${escapeHtml(
                post.alt || "Community Instagram post",
              )}"
              loading="lazy"
            />
            <span
              class="post-tag"
              style="color:${escapeHtml(post.accent || "#025A89")}"
            >
              ${escapeHtml(post.label || "Community post")}
            </span>
            ${
              post.featured
                ? '<span class="featured-tag">✦ Featured</span>'
                : ""
            }
          </div>

          <div class="post-body">
            <p class="post-source">
              ${escapeHtml(
                post.source || "Instagram community post",
              )}
            </p>

            <h2 class="post-title">
              ${escapeHtml(post.title || "Community post")}
            </h2>

            <p class="post-excerpt">
              ${escapeHtml(post.excerpt || "")}
            </p>

            <a
              class="post-link"
              href="${escapeHtml(instagramUrl)}"
              target="_blank"
              rel="noreferrer"
            >
              View on Instagram ↗
            </a>
          </div>
        </article>
      `;
    })
    .join("");

  emptyState.hidden = visible.length !== 0;
  loadMore.hidden =
    visible.length >= filtered.length || filtered.length === 0;
}

async function loadPosts() {
  try {
    const response = await fetch("data/posts.json", {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Could not load posts: ${response.status}`);
    }

    const data = await response.json();
    state.posts = Array.isArray(data) ? data : [];
    render();
  } catch (error) {
    state.posts = [];
    resultCount.textContent = "No community posts available";
    gallery.innerHTML = "";
    emptyState.hidden = false;
    console.error(error);
  }
}

document.querySelectorAll(".filter-button").forEach((button) => {
  button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    state.visibleCount = 4;

    document.querySelectorAll(".filter-button").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-selected", String(active));
    });

    render();
  });
});

searchInput.addEventListener("input", (event) => {
  state.query = event.target.value;
  state.visibleCount = 4;
  render();
});

loadMore.addEventListener("click", () => {
  state.visibleCount += 2;
  render();
});

document.querySelector("#clear-filters").addEventListener("click", () => {
  state.filter = "all";
  state.query = "";
  state.visibleCount = 4;
  searchInput.value = "";
  document.querySelector('[data-filter="all"]').click();
});

document.querySelector("#info-toggle").addEventListener("click", (event) => {
  const panel = document.querySelector("#info-panel");
  const expanded =
    event.currentTarget.getAttribute("aria-expanded") === "true";

  event.currentTarget.setAttribute("aria-expanded", String(!expanded));
  panel.hidden = expanded;
});

loadPosts();
