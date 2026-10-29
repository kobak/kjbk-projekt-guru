(function () {
  "use strict";
  var key = "guru-theme";
  var media = window.matchMedia("(prefers-color-scheme: dark)");
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
  window.GuruAppearance = { apply: apply };
  apply(initial, false);
  media.addEventListener("change", function () {
    if (document.documentElement.dataset.themeMode === "system")
      apply("system", false);
  });
  window.addEventListener("storage", function (event) {
    if (event.key === key) apply(event.newValue || "system", false);
  });
})();
