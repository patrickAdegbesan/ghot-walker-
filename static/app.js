// Accessibility: persistent high-contrast mode toggle.
(function () {
  var root = document.documentElement;
  var toggle = document.getElementById("contrast-toggle");
  if (!toggle) return;

  function apply(on) {
    if (on) {
      root.setAttribute("data-contrast", "high");
    } else {
      root.removeAttribute("data-contrast");
    }
    toggle.setAttribute("aria-pressed", String(on));
  }

  apply(localStorage.getItem("high-contrast") === "1");

  toggle.addEventListener("click", function () {
    var on = root.getAttribute("data-contrast") !== "high";
    localStorage.setItem("high-contrast", on ? "1" : "0");
    apply(on);
  });
})();
