"""GitHub as the database: Contents API + Git Data API. Tokens never appear in errors or logs."""
import base64
import json
import threading
import time

import requests

API = "https://api.github.com"


class GhError(Exception):
    pass


class NotFound(GhError):
    pass


class Conflict(GhError):
    pass


class RateLimited(GhError):
    pass


class Repo:
    def __init__(self, owner, name, token, branch="main"):
        self.owner, self.name, self.branch = owner, name, branch
        self._token = token
        self._s = requests.Session()
        self._blocked_until = 0.0
        self._lock = threading.Lock()

    # ------------- low level -------------
    def _req(self, method, path, raw=False, **kw):
        if time.time() < self._blocked_until:
            raise RateLimited("GitHub rate limit active, retry shortly")
        headers = {"Authorization": "Bearer " + self._token, "X-GitHub-Api-Version": "2022-11-28",
                   "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json"}
        url = "%s/repos/%s/%s%s" % (API, self.owner, self.name, path)
        last = None
        for attempt in range(3):
            try:
                r = self._s.request(method, url, headers=headers, timeout=20, **kw)
            except requests.RequestException:
                last = GhError("GitHub unreachable")
                time.sleep(0.5 * 2 ** attempt)
                continue
            if r.status_code >= 500:
                last = GhError("GitHub error %d" % r.status_code)
                time.sleep(0.5 * 2 ** attempt)
                continue
            if r.status_code == 429 or (r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0"):
                self._blocked_until = time.time() + 60
                raise RateLimited("GitHub rate limit reached")
            if r.status_code == 401:
                raise GhError("GitHub token rejected (401). The token may have expired.")
            if r.status_code == 403:
                raise GhError("GitHub refused the request (403). Check token permissions.")
            if r.status_code == 404:
                raise NotFound("not found")
            if r.status_code in (409, 422):
                raise Conflict("conflict")
            if r.status_code >= 400:
                raise GhError("GitHub error %d" % r.status_code)
            return r
        raise last or GhError("GitHub error")

    @staticmethod
    def _q(path):
        return requests.utils.quote(path, safe="/")

    # ------------- files -------------
    def get_file(self, path):
        """Return (bytes, sha). Raises NotFound only for a real 404."""
        r = self._req("GET", "/contents/" + self._q(path), params={"ref": self.branch})
        j = r.json()
        if isinstance(j, list):
            raise GhError("path is a directory")
        if j.get("content"):
            return base64.b64decode(j["content"]), j["sha"]
        r2 = self._req("GET", "/contents/" + self._q(path), raw=True, params={"ref": self.branch})
        return r2.content, j["sha"]

    def get_json(self, path):
        data, sha = self.get_file(path)
        return json.loads(data.decode("utf-8")), sha

    def put_file(self, path, data, message, sha=None):
        body = {"message": message, "content": base64.b64encode(data).decode(), "branch": self.branch}
        if sha:
            body["sha"] = sha
        r = self._req("PUT", "/contents/" + self._q(path), json=body)
        return r.json()["content"]["sha"]

    def delete_file(self, path, sha, message):
        self._req("DELETE", "/contents/" + self._q(path), json={"message": message, "sha": sha, "branch": self.branch})

    def list_dir(self, path):
        try:
            r = self._req("GET", "/contents/" + self._q(path), params={"ref": self.branch})
        except NotFound:
            return []
        j = r.json()
        return [{"name": x["name"], "path": x["path"], "sha": x["sha"], "type": x["type"]} for x in j] if isinstance(j, list) else []

    # ------------- git data -------------
    def head(self):
        return self._req("GET", "/git/ref/heads/" + self.branch).json()["object"]["sha"]

    def tree_paths(self, prefix=""):
        """[(path, sha)] for every file under prefix, one recursive tree call."""
        head = self.head()
        tree = self._req("GET", "/git/commits/" + head).json()["tree"]["sha"]
        j = self._req("GET", "/git/trees/" + tree, params={"recursive": "1"}).json()
        return head, [(t["path"], t["sha"]) for t in j.get("tree", []) if t["type"] == "blob" and t["path"].startswith(prefix)]

    def commit_files(self, changes, message):
        """Atomic multi-file commit. changes: {path: bytes | None (delete)}."""
        last = None
        for _ in range(3):
            try:
                head = self.head()
                base = self._req("GET", "/git/commits/" + head).json()["tree"]["sha"]
                items = []
                for path, data in changes.items():
                    if data is None:
                        items.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
                    else:
                        b = self._req("POST", "/git/blobs", json={"content": base64.b64encode(data).decode(), "encoding": "base64"}).json()
                        items.append({"path": path, "mode": "100644", "type": "blob", "sha": b["sha"]})
                tree = self._req("POST", "/git/trees", json={"base_tree": base, "tree": items}).json()["sha"]
                c = self._req("POST", "/git/commits", json={"message": message, "tree": tree, "parents": [head]}).json()["sha"]
                self._req("PATCH", "/git/refs/heads/" + self.branch, json={"sha": c, "force": False})
                return c
            except Conflict as e:
                last = e
                time.sleep(0.4)
        raise last or GhError("commit failed")

    def commits(self, n=30):
        r = self._req("GET", "/commits", params={"sha": self.branch, "per_page": n})
        return [{"message": x["commit"]["message"], "date": x["commit"]["committer"]["date"]} for x in r.json()]
