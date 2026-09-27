/*
 the landing page ticker: a fresh bee scores live solana pools while you read.
 same brain and senses as /trade (web/trade/bee.js). read only, nothing saved.
 all api text goes in through textContent.
*/
(function () {
  "use strict";
  const B = window.Bee, root = document.getElementById("ticker");
  if (!B || !root) return;
  const list = root.querySelector(".tick-list"), stat = root.querySelector(".tick-stat");
  const S = new B.FieldSession("solana"), feed = new B.Feed("solana");
  const usd = (v) => (v <= 0 ? "curve" : v >= 1e6 ? "$" + (v / 1e6).toFixed(1) + "m" : v >= 1e3 ? "$" + (v / 1e3).toFixed(0) + "k" : "$" + v.toFixed(0));
  let busy = false, lastPoll = 0;

  function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }

  function add(r) {
    const li = el("li", "tick v-" + r.verdict.toLowerCase());
    li.append(el("span", "tick-sym", "$" + r.symbol), el("span", "tick-liq", usd(r.liq)),
      el("span", "chip v-" + r.verdict.toLowerCase(), r.verdict.toLowerCase()),
      el("span", "tick-why", r.reasons.length ? r.reasons[0] : "score " + r.comb.toFixed(2)));
    list.prepend(li);
    while (list.children.length > 6) list.lastChild.remove();
    const c = S.counts;
    stat.textContent = S.scored + " pools scored since you opened this page · " + c.PASS + " pass · " + c.WATCH + " watch · " + c.SKIP + " skip";
  }

  async function loop() {
    const now = Date.now();
    if (!busy && now - lastPoll > 30000) {
      busy = true; lastPoll = now;
      try { const { found } = await feed.poll(now / 1000, []); S.ingest(found, Date.now()); }
      finally { busy = false; }
      if (feed.status !== "live") stat.textContent = "the feed is resting, retrying in a moment";
    }
    const r = S.scoreNext(Date.now());
    if (r) add(r);
  }
  // only start when the ticker scrolls into view, so a visitor who never looks costs nothing
  const io = new IntersectionObserver((es) => {
    if (es.some((e) => e.isIntersecting)) { io.disconnect(); loop(); setInterval(loop, 1800); }
  });
  io.observe(root);
})();
