(function () {
  const gallery = document.querySelector("[data-gallery]");
  if (!gallery) {
    return;
  }

  const main = gallery.querySelector("[data-gallery-main]");
  const mainImage = gallery.querySelector("[data-gallery-image]");
  const thumbs = gallery.querySelectorAll(".gallery-thumb");

  if (!main || !mainImage) {
    return;
  }

  thumbs.forEach((thumb) => {
    thumb.addEventListener("click", () => {
      const src = thumb.dataset.gallerySrc;
      if (!src) {
        return;
      }

      mainImage.src = src;
      thumbs.forEach((item) => {
        const isActive = item === thumb;
        item.classList.toggle("is-active", isActive);
        item.setAttribute("aria-selected", String(isActive));
      });
      resetZoom();
    });
  });

  function resetZoom() {
    mainImage.style.transform = "scale(1)";
    mainImage.style.transformOrigin = "center center";
    main.classList.remove("is-zoomed");
  }

  main.addEventListener("mousemove", (event) => {
    if (window.matchMedia("(max-width: 768px)").matches) {
      return;
    }

    const rect = main.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;
    mainImage.style.transformOrigin = `${x}% ${y}%`;
    mainImage.style.transform = "scale(2)";
    main.classList.add("is-zoomed");
  });

  main.addEventListener("mouseleave", resetZoom);

  mainImage.addEventListener("click", () => {
    if (window.matchMedia("(max-width: 768px)").matches) {
      main.classList.toggle("is-zoomed-mobile");
    }
  });
})();
