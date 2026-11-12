import os, re, sys, json
S = sys.argv[1]; NG = os.path.join(S, "notion-guides"); C = os.path.join(S, "content")
DESIGN_ORDER = ["Discovery & Deep Dives", "Sitemap", "Moodboard", "Creative Exploration (Websites)", "Wireframes Mid-Fi", "Wireframes Hi-Fi", "Brand to Pitch Deck"]
INDEX = {"Handbook/Start here": 1, "Handbook/How this system works": 2, "Handbook/Changelog": 9,
         "Agents/Directory": 1, "Agents/Install and update the agent plugins": 2, "Agents/Contribute": 3,
         "Resources/Templates": 1, "Resources/Tools": 2, "Resources/Automations": 3}
def parse(p):
    t = open(p).read(); meta = {}
    end = t.find("\n---", 4)
    for line in t[4:end].splitlines():
        k, _, v = line.partition(":"); meta[k.strip()] = v.strip()
    return meta, t[end + 4:].lstrip("\n")
def dump(meta, body):
    out = ["---"] + [f"{k}: {v}" for k, v in meta.items()] + ["---", ""]
    return "\n".join(out) + body.rstrip() + "\n"
docs = []  # (dest_rel, meta, body)
for root, _, files in os.walk(NG):
    for f in files:
        if not f.endswith(".md"): continue
        rel = os.path.relpath(os.path.join(root, f), NG)[:-3]
        meta, body = parse(os.path.join(root, f))
        title = meta.get("title", "").strip('"') or os.path.basename(rel)
        meta["title"] = json.dumps(title)
        dest = rel
        if rel.startswith("Design/_process/"):
            name = os.path.basename(rel)
            dest = "Design/Website design process/" + name
            step = name.replace("Design Process Guide - ", "")
            if step in DESIGN_ORDER: meta["index"] = str(DESIGN_ORDER.index(step) + 1)
        meta["key"] = "scaffold:templates" if rel == "Resources/Templates" else "notion:" + rel.replace(" ", "-").lower()
        if rel in INDEX: meta["index"] = str(INDEX[rel])
        if rel == "Resources/Templates":
            body = body.rstrip() + "\n\n## Client template\n\nStart a new client from **Client template**. It shows the client overview, engagement, Scope, Decisions and Meetings layout every client follows.\n"
        docs.append((dest, meta, body))
# title -> key, from Notion docs plus the scaffold docs already in content/
titles = {}
for dest, meta, _ in docs: titles[json.loads(meta["title"])] = meta["key"]
for root, _, files in os.walk(C):
    if "/Clients" in root or "/Archive" in root: continue
    for f in files:
        if f.endswith(".md"):
            m, _ = parse(os.path.join(root, f))
            if "key" in m: titles.setdefault(m["title"].strip('"'), m["key"])
linked = {}
def relink(body, self_key):
    out = []
    for line in body.splitlines():
        if re.fullmatch(r"\s*\*\*[^*]+\*\*\s*", line):  # bold-only line acts as a heading
            out.append(line); continue
        def rep(m):
            t = m.group(1)
            k = titles.get(t) or titles.get(t.replace(": ", " - "))
            if not k or k == self_key: return m.group(0)
            linked[t] = linked.get(t, 0) + 1
            return f"[{t}](outline-key:{k})"
        out.append(re.sub(r"(?<!\[)\*\*([^*:\n]{2,60})\*\*", rep, line))
    return "\n".join(out) + "\n"
for dest, meta, body in docs:
    body = relink(body, meta["key"])
    p = os.path.join(C, dest + ".md"); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(dump(meta, body))
print(json.dumps({"written": len(docs), "links": linked}, indent=1))
