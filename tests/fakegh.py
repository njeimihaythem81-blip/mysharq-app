"""In-memory stand-in for core.ghstore.Repo with the same conflict semantics (for tests)."""
import hashlib
import json

from core.ghstore import Conflict, GhError, NotFound


def _sha(b):
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


class FakeRepo:
    def __init__(self):
        self.files, self.log, self.n = {}, [], 0
        self.fail_paths = {}  # path -> exception to raise on get_file

    def get_file(self, path):
        if path in self.fail_paths:
            raise self.fail_paths[path]
        if path not in self.files:
            raise NotFound("nf")
        return self.files[path], _sha(self.files[path])

    def get_json(self, path):
        d, s = self.get_file(path)
        return json.loads(d.decode()), s

    def put_file(self, path, data, message, sha=None):
        if path in self.files and (sha is None or _sha(self.files[path]) != sha):
            raise Conflict("c")
        if path not in self.files and sha:
            raise Conflict("c")
        self.files[path] = data
        self.log.append(message)
        return _sha(data)

    def delete_file(self, path, sha, message):
        self.files.pop(path, None)

    def list_dir(self, path):
        pre = path.rstrip("/") + "/"
        return [{"name": p[len(pre):], "path": p, "sha": _sha(d), "type": "file"}
                for p, d in self.files.items() if p.startswith(pre) and "/" not in p[len(pre):]]

    def head(self):
        return "head%d" % self.n

    def tree_paths(self, prefix=""):
        return self.head(), [(p, _sha(d)) for p, d in self.files.items() if p.startswith(prefix)]

    def commit_files(self, changes, message):
        for p, d in changes.items():
            if d is None:
                self.files.pop(p, None)
            else:
                self.files[p] = d
        self.n += 1
        self.log.append(message)
        return self.head()

    def commits(self, n=30):
        return [{"message": m, "date": "2026-10-12T00:00:00Z"} for m in reversed(self.log)][:n]
