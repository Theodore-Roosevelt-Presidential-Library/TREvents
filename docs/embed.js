/* TR Events embed loader.
 *
 *   <div data-trevents="upcoming" data-limit="5" data-source="trpl,nps"></div>
 *   <script src="https://trevents.labs.trlibrary.com/embed.js" async></script>
 *
 * data-trevents: upcoming | month | week. Any other data-* attribute is passed to the widget
 * (source, attendance, cost, kind, q, limit, recurring, filters, title, theme, bg, compact, date).
 */
(function () {
  "use strict";
  var me = document.currentScript || document.querySelector('script[src*="embed.js"]');
  var base = me ? me.src.replace(/embed\.js(\?.*)?$/, "") : "https://trevents.labs.trlibrary.com/";
  var n = 0, frames = {};

  function mount(el) {
    if (el.getAttribute("data-trevents-mounted")) return;
    el.setAttribute("data-trevents-mounted", "1");
    var view = el.getAttribute("data-trevents") || "upcoming";
    var q = new URLSearchParams();
    Array.prototype.forEach.call(el.attributes, function (a) {
      if (a.name.indexOf("data-") === 0 && a.name !== "data-trevents" && a.name !== "data-trevents-mounted") q.set(a.name.slice(5), a.value);
    });
    var id = "trevents-" + (++n);
    q.set("frame", id);
    var f = document.createElement("iframe");
    f.src = base + "widgets/" + encodeURIComponent(view) + ".html?" + q.toString();
    f.title = view === "upcoming" ? "Upcoming Theodore Roosevelt events" : "Theodore Roosevelt events calendar";
    f.loading = "lazy";
    f.style.cssText = "width:100%;border:0;display:block;overflow:hidden;height:" + (view === "upcoming" ? 520 : 760) + "px";
    f.setAttribute("scrolling", "no");
    el.appendChild(f);
    frames[id] = f;
  }

  window.addEventListener("message", function (ev) {
    var d = ev.data;
    if (!d || d.type !== "trevents:height" || !frames[d.frame]) return;
    if (base.indexOf(ev.origin) !== 0) return;
    frames[d.frame].style.height = Math.max(120, d.height) + "px";
  });

  function scan() { Array.prototype.forEach.call(document.querySelectorAll("[data-trevents]"), mount); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scan); else scan();
})();
