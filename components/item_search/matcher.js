// Pure matching logic (also unit-tested with node). Item numbers are compared without spaces, dashes or letter case.
(function (root) {
  function norm(s) { return String(s).toUpperCase().replace(/[^0-9A-Z]/g, ""); }
  function prepare(rows) { return rows.map(function (r) { return norm(r[0]); }); }
  // Items whose number STARTS with the typed characters come first, then items that CONTAIN them (same typed order).
  // No next-letter suggestion. Result = array of row indexes, at most `limit`.
  function search(normArr, query, limit) {
    var q = norm(query);
    if (!q) return [];
    var pre = [], con = [];
    for (var i = 0; i < normArr.length; i++) {
      var p = normArr[i].indexOf(q);
      if (p === 0) pre.push(i); else if (p > 0) con.push(i);
    }
    return pre.concat(con).slice(0, limit || 300);
  }
  var api = { norm: norm, prepare: prepare, search: search };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.MATCH = api;
})(this);
