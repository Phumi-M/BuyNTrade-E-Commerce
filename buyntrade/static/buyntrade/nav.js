(function () {
  const toggle = document.getElementById("mobile-menu-toggle");
  const links = document.getElementById("navbar-links");
  if (!toggle || !links) {
    return;
  }

  function setOpen(open) {
    links.classList.toggle("open", open);
    toggle.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("nav-open", open);
  }

  toggle.addEventListener("click", () => {
    setOpen(!links.classList.contains("open"));
  });

  links.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => setOpen(false));
  });

  document.addEventListener("click", (event) => {
    if (!links.classList.contains("open")) {
      return;
    }
    if (links.contains(event.target) || toggle.contains(event.target)) {
      return;
    }
    setOpen(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setOpen(false);
    }
  });
})();
