(function () {
  const storageKey = "buyntrade-theme";
  const root = document.documentElement;

  function getPreferredTheme() {
    const saved = localStorage.getItem(storageKey);
    if (saved === "light" || saved === "dark") {
      return saved;
    }
    return "light";
  }

  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    localStorage.setItem(storageKey, theme);

    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const isDark = theme === "dark";
      button.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
      button.setAttribute("title", isDark ? "Light mode" : "Dark mode");
    });
  }

  applyTheme(getPreferredTheme());

  document.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-theme-toggle]");
    if (!toggle) {
      return;
    }

    const nextTheme = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
  });
})();
