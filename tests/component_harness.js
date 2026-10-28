const fs = require("fs");
const path = require("path"), root = path.join(__dirname, "..", "components", "item_search");
const M = require(path.join(root, "matcher.js"));
global.MATCH = M;
function el(id) { const e = { id, children: [], style: {}, className: "", textContent: "", value: "", scrollTop: 0, listeners: {},
  addEventListener(t, f) { this.listeners[t] = f; }, appendChild(c) { this.children.push(c); }, scrollBy(o) { this.scrollTop += o.top; }, placeholder: "" };
  Object.defineProperty(e, "textContent", { get() { return this._t || ""; }, set(v) { this._t = v; if (v === "") this.children = []; } });
  return e; }
const els = {}; ["q","box","list","cnt","up","dn","wrap"].forEach(i => els[i] = el(i));
let frame = 0;                       // iframe height set by the component via setFrameHeight
const contentHeight = () => 44 + (els.box.style.display === "block" ? 6 + Math.min(276, 46 * Math.max(1, els.list.children.length)) + 5 + 34 : 0);
els.wrap.getBoundingClientRect = () => ({ height: contentHeight() });
const posted = [];
global.window = { parent: { postMessage: (m) => { posted.push(m); if (m.type === "streamlit:setFrameHeight") frame = m.height; } }, addEventListener: (t, f) => { global.window.msg = f; } };
global.document = { getElementById: i => els[i], createElement: () => el("x"), documentElement: { get scrollHeight() { return Math.max(contentHeight(), frame); } } };   // like a real iframe
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
eval(html.match(/<script>([\s\S]*?)<\/script>/)[1]);
const rows = []; for (let i = 0; i < 40; i++) rows.push(["LC1D" + String(i).padStart(2, "0") + "M7", "Contactor " + i, i % 2]);
rows.push(["XB5AA31", "Push button", 1]);
window.msg({ data: { type: "streamlit:render", args: { rows, placeholder: "Type", show_status: true } } });
const typed = (v) => { els.q.value = v; els.q.listeners.input(); };
typed("lc1d");
if (els.list.children.length !== 40) throw new Error("expected 40 rows, got " + els.list.children.length);
if (els.cnt.textContent !== "1-6 of 40") throw new Error("counter: " + els.cnt.textContent);
els.dn.listeners.click(); els.list.scrollTop = 276; els.list.listeners.scroll();
if (els.cnt.textContent !== "7-12 of 40") throw new Error("counter after scroll: " + els.cnt.textContent);
typed("lc1d0");                                   // typing one more character: list shrinks and returns to the top
if (els.list.children.length !== 10 || els.list.scrollTop !== 0) throw new Error("shrink/top failed " + els.list.children.length + " " + els.list.scrollTop);
typed("lc1d");                                    // removing a character widens it again
if (els.list.children.length !== 40) throw new Error("widen failed");
typed("xb5");
if (els.list.children.length !== 1) throw new Error("xb5 failed");
els.q.listeners.keydown({ key: "Enter", preventDefault() {} });
const val = posted.filter(m => m.type === "streamlit:setComponentValue").pop();
if (!val || val.value.item_no !== "XB5AA31") throw new Error("selection failed " + JSON.stringify(val));
if (els.box.style.display !== "none") throw new Error("list should hide after choosing");
typed("xb5a");                                    // editing after a choice clears the selection
const clr = posted.filter(m => m.type === "streamlit:setComponentValue").pop();
if (clr.value.item_no !== null) throw new Error("clear failed");
typed("zzz"); if (els.list.children.length !== 1) throw new Error("no-match row missing");
typed(""); if (els.box.style.display !== "none") throw new Error("empty query must hide the list");
// layout shift regression: many Streamlit reruns must NOT make the frame taller and taller
typed("");
const before = frame;
for (let i = 0; i < 200; i++) window.msg({ data: { type: "streamlit:render", args: { rows, placeholder: "Type", show_status: true } } });
if (frame !== before) throw new Error("frame grew from " + before + " to " + frame + " after 200 reruns");
if (frame !== 44 + 2) throw new Error("idle frame should be 46px, got " + frame);
const nSent = posted.filter(m => m.type === "streamlit:setFrameHeight").length;
for (let i = 0; i < 50; i++) window.msg({ data: { type: "streamlit:render", args: { rows, placeholder: "Type", show_status: true } } });
if (posted.filter(m => m.type === "streamlit:setFrameHeight").length !== nSent) throw new Error("height messages must not repeat when nothing changed");
typed("lc1d"); if (frame !== contentHeight() + 2) throw new Error("open list height wrong: " + frame + " vs " + (contentHeight() + 2));
console.log("component behaviour OK");
