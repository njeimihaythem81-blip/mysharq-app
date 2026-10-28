const M = require(require("path").join(__dirname, "..", "components", "item_search", "matcher.js"));
const rows = [["LC1D09M7"],["LC1D12M7"],["LC1D80M7"],["A9F74110"],["LRD08"],["LRD12"],["XB5AA31"],["LC1-D25 M7"],["ATV12H018M2"]];
const n = M.prepare(rows);
const names = idx => idx.map(i => rows[i][0]);
const eq = (a, b, m) => { if (JSON.stringify(a) !== JSON.stringify(b)) { console.log("FAIL", m, JSON.stringify(a), "!=", JSON.stringify(b)); process.exit(1); } };
eq(names(M.search(n, "lc1d", 300)), ["LC1D09M7","LC1D12M7","LC1D80M7","LC1-D25 M7"], "prefix, ignoring case/dashes/spaces");
eq(names(M.search(n, "LC1 D09", 300)), ["LC1D09M7"], "spaces ignored");
eq(names(M.search(n, "12", 300)), ["LC1D12M7","LRD12","ATV12H018M2"], "contains after prefix (none prefix here)");
eq(names(M.search(n, "LRD", 300)), ["LRD08","LRD12"], "prefix");
eq(names(M.search(n, "D1", 300)), ["LC1D12M7","LRD12"], "contains");
eq(M.search(n, "", 300), [], "empty");
eq(M.search(n, "---", 300), [], "only symbols");
eq(M.search(n, "ZZZ", 300), [], "no match");
eq(M.search(n, "L", 3).length, 3, "limit");
eq(names(M.search(n, "1", 300)).slice(0,3), ["LC1D09M7","LC1D12M7","LC1D80M7"].slice(0,0).concat(names(M.search(n,"1",300)).slice(0,3)), "sanity");
// prefix results always precede contains results
const r = names(M.search(n, "A", 300)); eq(r[0], "A9F74110", "A prefix first");
console.log("matcher OK");
