(function () {
  "use strict";
  var key = "guru-theme";
  var media = window.matchMedia("(prefers-color-scheme: dark)");
  function applyLayout(font, density, cache) {
    font = font === "large" ? "large" : "normal";
    density = density === "spacious" ? "spacious" : "compact";
    document.documentElement.dataset.fontSize = font;
    document.documentElement.dataset.density = density;
    if (cache !== false) {
      try {
        window.localStorage.setItem(
          "guru-layout",
          JSON.stringify({ font_size: font, density: density }),
        );
      } catch (_) {}
    }
    window.dispatchEvent(new Event("guru-theme-change"));
  }
  function apply(mode, cache) {
    if (mode !== "light" && mode !== "dark" && mode !== "system")
      mode = "system";
    var resolved =
      mode === "system" ? (media.matches ? "dark" : "light") : mode;
    document.documentElement.dataset.themeMode = mode;
    document.documentElement.dataset.theme = resolved;
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = resolved === "dark" ? "#141119" : "#462773";
    if (cache !== false) {
      try {
        window.localStorage.setItem(key, mode);
      } catch (_) {}
    }
    window.dispatchEvent(new Event("guru-theme-change"));
  }
  var initial = "system";
  try {
    initial = window.localStorage.getItem(key) || initial;
  } catch (_) {}
  window.GuruAppearance = { apply: apply, applyLayout: applyLayout };
  apply(initial, false);
  var layout = {};
  try {
    layout = JSON.parse(window.localStorage.getItem("guru-layout") || "{}");
  } catch (_) {}
  applyLayout(layout && layout.font_size, layout && layout.density, false);
  media.addEventListener("change", function () {
    if (document.documentElement.dataset.themeMode === "system")
      apply("system", false);
  });
  window.addEventListener("storage", function (event) {
    if (event.key === key) apply(event.newValue || "system", false);
    if (event.key === "guru-layout") {
      var next = {};
      try {
        next = JSON.parse(event.newValue || "{}");
      } catch (_) {}
      applyLayout(next && next.font_size, next && next.density, false);
    }
  });
})();
