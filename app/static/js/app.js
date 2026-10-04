document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("textarea[data-counter]").forEach(function (ta) {
    var out = document.getElementById(ta.dataset.counter);
    var update = function () { if (out) out.textContent = ta.value.length; };
    ta.addEventListener("input", update);
    update();
  });
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });
});
