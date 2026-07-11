(function () {
  const grid = document.getElementById("product-grid");
  if (!grid) {
    return;
  }

  const cards = Array.from(grid.querySelectorAll("[data-listing-card]"));
  const priceRange = document.getElementById("price-range");
  const priceMaxLabel = document.getElementById("price-max-label");
  const sortSelect = document.getElementById("sort-select");
  const filterSelect = document.getElementById("filter-select");
  const noResults = document.getElementById("no-results");

  function applyFilters() {
    const maxPrice = priceRange ? Number(priceRange.value) : Infinity;
    const quickFilter = filterSelect ? filterSelect.value : "all";

    let visibleCount = 0;

    cards.forEach((card) => {
      const price = Number(card.dataset.price || 0);
      let visible = price <= maxPrice;

      if (quickFilter === "under-100" && price >= 100) {
        visible = false;
      }
      if (quickFilter === "under-500" && price >= 500) {
        visible = false;
      }

      card.hidden = !visible;
      card.classList.toggle("is-hidden", !visible);
      if (visible) {
        visibleCount += 1;
      }
    });

    if (noResults) {
      noResults.hidden = visibleCount > 0;
    }
  }

  function sortCards() {
    const mode = sortSelect ? sortSelect.value : "default";
    if (mode === "default") {
      return;
    }

    const sorted = [...cards].sort((a, b) => {
      const priceA = Number(a.dataset.price || 0);
      const priceB = Number(b.dataset.price || 0);
      const titleA = a.dataset.title || "";
      const titleB = b.dataset.title || "";

      if (mode === "price-asc") {
        return priceA - priceB;
      }
      if (mode === "price-desc") {
        return priceB - priceA;
      }
      if (mode === "name-asc") {
        return titleA.localeCompare(titleB);
      }
      return 0;
    });

    sorted.forEach((card) => grid.appendChild(card));
  }

  priceRange?.addEventListener("input", () => {
    if (priceMaxLabel) {
      priceMaxLabel.textContent = `R${priceRange.value}`;
    }
    applyFilters();
  });

  sortSelect?.addEventListener("change", () => {
    sortCards();
    applyFilters();
  });

  filterSelect?.addEventListener("change", applyFilters);
})();

(function () {
  const sidebar = document.getElementById("shop-sidebar");
  const toggle = document.getElementById("sidebar-toggle");
  const panel = document.getElementById("shop-sidebar-panel");
  if (!sidebar || !toggle || !panel) {
    return;
  }

  const mobileQuery = window.matchMedia("(max-width: 900px)");

  function setExpanded(expanded) {
    toggle.setAttribute("aria-expanded", String(expanded));
    sidebar.classList.toggle("is-open", expanded);
  }

  toggle.addEventListener("click", () => {
    setExpanded(!sidebar.classList.contains("is-open"));
  });

  panel.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      if (mobileQuery.matches) {
        setExpanded(false);
      }
    });
  });

  mobileQuery.addEventListener("change", () => {
    if (!mobileQuery.matches) {
      setExpanded(false);
    }
  });
})();
