/* CareCheck BC — client-side search over search-index.json */
(function () {
  var input = document.getElementById("search-input");
  var panel = document.getElementById("search-results");
  if (!input || !panel) return;

  var index = null;
  var activeIdx = -1;

  function loadIndex() {
    if (index) return Promise.resolve(index);
    return fetch("/search-index.json")
      .then(function (r) { return r.json(); })
      .then(function (data) { index = data; return index; });
  }

  function score(item, terms) {
    var hay = item.h; // pre-lowercased haystack: name + city + type
    var s = 0;
    for (var i = 0; i < terms.length; i++) {
      var t = terms[i];
      if (!t) continue;
      var pos = hay.indexOf(t);
      if (pos === -1) return -1; // every term must match
      s += pos === 0 ? 3 : 1;
      if (item.n.toLowerCase().indexOf(t) === 0) s += 2; // name starts with term
    }
    return s;
  }

  function render(results) {
    panel.innerHTML = "";
    activeIdx = -1;
    if (!results.length) {
      var d = document.createElement("div");
      d.className = "sr-empty";
      d.textContent = "No facilities match. Try a facility name or city.";
      panel.appendChild(d);
    } else {
      results.forEach(function (item) {
        var a = document.createElement("a");
        a.href = "/facility/" + item.s + "/";
        a.textContent = item.n;
        var meta = document.createElement("span");
        meta.className = "sr-meta";
        meta.textContent = item.c + " · " + item.t;
        a.appendChild(meta);
        panel.appendChild(a);
      });
    }
    panel.classList.add("open");
  }

  function search(q) {
    var terms = q.toLowerCase().trim().split(/\s+/);
    var scored = [];
    for (var i = 0; i < index.length; i++) {
      var s = score(index[i], terms);
      if (s >= 0) scored.push([s, index[i]]);
    }
    scored.sort(function (a, b) { return b[0] - a[0]; });
    return scored.slice(0, 8).map(function (x) { return x[1]; });
  }

  var debounce;
  input.addEventListener("input", function () {
    clearTimeout(debounce);
    var q = input.value;
    if (q.trim().length < 2) { panel.classList.remove("open"); return; }
    debounce = setTimeout(function () {
      loadIndex().then(function () { render(search(q)); });
    }, 120);
  });

  input.addEventListener("keydown", function (e) {
    var links = panel.querySelectorAll("a");
    if (!panel.classList.contains("open") || !links.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIdx = Math.min(activeIdx + 1, links.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIdx = Math.max(activeIdx - 1, 0);
    } else if (e.key === "Enter" && activeIdx >= 0) {
      e.preventDefault();
      window.location.href = links[activeIdx].href;
      return;
    } else if (e.key === "Escape") {
      panel.classList.remove("open");
      return;
    } else {
      return;
    }
    links.forEach(function (l, i) { l.classList.toggle("active", i === activeIdx); });
  });

  document.addEventListener("click", function (e) {
    if (!panel.contains(e.target) && e.target !== input) {
      panel.classList.remove("open");
    }
  });
})();
