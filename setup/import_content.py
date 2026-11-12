#!/usr/bin/env python3
"""Import prepared markdown into Outline. Safe to re-run: nothing is duplicated.

Layout: <content>/<Collection>/<Doc>.md, children in <content>/<Collection>/<Doc>/.
Frontmatter: title, key, source, source_url, moved, index (optional).

Matching: a local state file maps each doc's `key` to its Outline id. If the state is lost, docs are matched
on title + parent, as the build brief asks. Pass 1 creates or updates every doc; pass 2 rewrites
`outline-key:<key>` links to real Outline links and appends the source line.

Usage: import_content.py <content dir> <state.json> [--dry-run]
Needs OUTLINE_SETUP_KEY in ../.env. Talks to https://papertiger.agency via curl.
"""
import os, re, sys, json, time, subprocess

CONTENT, STATE = sys.argv[1], sys.argv[2]
DRY = "--dry-run" in sys.argv
HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, "..", ".env")
BASE = "https://papertiger.agency"
RESOLVE = os.environ.get("OUTLINE_RESOLVE", "papertiger.agency:443:64.225.7.247")


def key_from_env():
    for line in open(ENV):
        if line.startswith("OUTLINE_SETUP_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    sys.exit("OUTLINE_SETUP_KEY missing from .env")


KEY = key_from_env()


def api(method, body, tries=6):
    for attempt in range(tries):
        cmd = ["curl", "-s", "-X", "POST", f"{BASE}/api/{method}", "-H", "content-type: application/json",
               "-H", f"Authorization: Bearer {KEY}", "--data-binary", "@-", "-w", "\n%{http_code}"]
        if RESOLVE:
            cmd[1:1] = ["--resolve", RESOLVE]
        out = subprocess.run(cmd, input=json.dumps(body).encode(), capture_output=True).stdout.decode()
        payload, _, code = out.rpartition("\n")
        if code == "429" or code.startswith("5"):
            time.sleep(min(60, 5 * (attempt + 1)))
            continue
        data = json.loads(payload) if payload else {}
        if not data.get("ok", False):
            raise RuntimeError(f"{method} failed ({code}): {data.get('error')} {data.get('message')}")
        return data
    raise RuntimeError(f"{method}: gave up after {tries} tries")


def parse(path):
    text = open(path).read()
    meta = {}
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        for line in text[4:end].splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                v = v.strip()
                meta[k.strip()] = json.loads(v) if v.startswith('"') else v
        text = text[end + 4:].lstrip("\n")
    meta.setdefault("title", os.path.basename(path)[:-3])
    return meta, text


def walk(dirpath):
    """Yield (meta, body, children) in import order."""
    names = sorted(f for f in os.listdir(dirpath) if f.endswith(".md"))
    items = []
    for f in names:
        meta, body = parse(os.path.join(dirpath, f))
        sub = os.path.join(dirpath, f[:-3])
        items.append((meta, body, walk(sub) if os.path.isdir(sub) else []))
    is_meetings = os.path.basename(dirpath) == "Meetings"
    def order(it):
        m = it[0]
        if "index" in m:
            return (0, int(m["index"]), "")
        return (1, 0, m["title"])
    items.sort(key=order)
    if is_meetings:  # newest first
        items.sort(key=lambda it: it[0]["title"], reverse=True)
    return items


def source_line(meta):
    src = meta.get("source", "")
    url = meta.get("source_url")
    where = f"[{src}]({url})" if url else src
    if src.startswith("Written during"):
        return f"\n\n---\n\n_Written for Outline on {meta.get('moved')}._\n"
    return f"\n\n---\n\n_Source: {where}. Moved to Outline on {meta.get('moved')}._\n"


def main():
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    colls = {c["name"]: c["id"] for c in api("collections.list", {"limit": 100})["data"]}
    stats = {"created": 0, "updated": 0, "unchanged": 0}
    docs = []  # (meta, body, id)
    order = {}  # (collection, parent) -> child ids in the wanted order

    def existing_children(coll_id, parent_id):
        out, offset = {}, 0
        while True:
            body = {"collectionId": coll_id, "limit": 100, "offset": offset}
            if parent_id:
                body["parentDocumentId"] = parent_id
            res = api("documents.list", body)["data"]
            for d in res:
                if (d.get("parentDocumentId") or None) == parent_id:
                    out[d["title"]] = d["id"]
            if len(res) < 100:
                return out
            offset += 100

    def put(items, coll_id, parent_id):
        siblings = None
        for meta, body, children in items:
            k = meta.get("key") or f"path:{coll_id}:{parent_id}:{meta['title']}"
            doc_id = state.get(k)
            if doc_id:
                try:
                    api("documents.info", {"id": doc_id})
                except RuntimeError:
                    doc_id = None
            if not doc_id:
                if siblings is None:
                    siblings = existing_children(coll_id, parent_id) if not DRY else {}
                doc_id = siblings.get(meta["title"])
            text = re.sub(r"\]\(outline-key:[^)]+\)", "]()", body)  # links filled in pass 2
            if DRY:
                print(("update " if doc_id else "create ") + meta["title"])
                doc_id = doc_id or f"dry-{len(state)}"
            elif doc_id:
                api("documents.update", {"id": doc_id, "title": meta["title"], "publish": True})
                stats["updated"] += 1
            else:
                req = {"collectionId": coll_id, "title": meta["title"], "text": text, "publish": True}
                if parent_id:
                    req["parentDocumentId"] = parent_id
                doc_id = api("documents.create", req)["data"]["id"]
                stats["created"] += 1
            state[k] = doc_id
            docs.append((meta, body, doc_id, k))
            order.setdefault((coll_id, parent_id), []).append(doc_id)
            if not DRY:
                json.dump(state, open(STATE, "w"), indent=1)
            put(children, coll_id, doc_id)

    for coll in sorted(os.listdir(CONTENT)):
        p = os.path.join(CONTENT, coll)
        if not os.path.isdir(p) or coll.startswith("_"):
            continue
        if coll not in colls:
            print(f"!! no collection named {coll}, skipping"); continue
        put(walk(p), colls[coll], None)

    if DRY:
        print(f"dry run: {len(docs)} docs"); return

    # pass 2: real links + source line, and record each doc's URL
    urls = {}
    for meta, body, doc_id, k in docs:
        urls[k] = api("documents.info", {"id": doc_id})["data"]["url"]
    missing = set()
    for meta, body, doc_id, k in docs:
        def rep(m):
            target = m.group(1)
            if target in urls:
                return f"]({BASE}{urls[target]})"
            missing.add(target)
            return "]()"
        text = re.sub(r"\]\(outline-key:([^)]+)\)", rep, body).rstrip() + source_line(meta)
        api("documents.update", {"id": doc_id, "text": text, "publish": True})
    json.dump({"ids": state, "urls": {k: BASE + u for k, u in urls.items()}}, open(STATE.replace(".json", ".urls.json"), "w"), indent=1)

    # pass 3: sidebar order. Outline puts each new doc first, so set the order explicitly.
    # Docs added by hand in Outline keep their place after the imported ones.
    moves = 0
    for coll_id in {c for c, _ in order}:
        actual = {}
        def walk_tree(nodes, parent):
            actual[parent] = [n["id"] for n in nodes]
            for n in nodes:
                walk_tree(n.get("children", []), n["id"])
        walk_tree(api("collections.documents", {"id": coll_id})["data"], None)
        for (c, parent), wanted in order.items():
            if c != coll_id:
                continue
            now = [i for i in actual.get(parent, []) if i in wanted]
            if now == wanted:
                continue
            for i, doc_id in enumerate(wanted):
                body = {"id": doc_id, "collectionId": coll_id, "index": i}
                if parent:
                    body["parentDocumentId"] = parent
                api("documents.move", body)
                moves += 1
    print(json.dumps({**stats, "total": len(docs), "reordered": moves, "unresolved_links": sorted(missing)}, indent=1))


main()
