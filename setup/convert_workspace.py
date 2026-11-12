#!/usr/bin/env python3
"""Convert pt-workspace/clients into Outline-ready markdown laid out like the Outline structure.

Output: <out>/<Clients|Archive>/<Client>.md, <Client>/<Engagement>.md, <Engagement>/Scope.md,
<Engagement>/Decisions.md, <Client>/Meetings.md, <Client>/Meetings/<YYYY-MM-DD Title>.md

Every file gets frontmatter: title, key (stable, used by the importer to match docs), source, source_url, moved.
Links between docs become `outline-key:<key>` so the importer can rewrite them to real Outline URLs.
Usage: convert_workspace.py <pt-workspace path> <out dir>
"""
import os, re, sys, glob, json
import yaml

WS, OUT = sys.argv[1], sys.argv[2]
MOVED = "2026-11-12"
GH = "https://github.com/PaperTiger/pt-workspace/blob/develop/"
report = {"clients": [], "warnings": []}


def fm(title, key, source, source_url=None):
    lines = ["---", f"title: {json.dumps(title)}", f"key: {key}", f"source: {json.dumps(source)}"]
    if source_url:
        lines.append(f"source_url: {source_url}")
    lines += [f"moved: {MOVED}", "---", ""]
    return "\n".join(lines)


def strip_frontmatter(text):
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return yaml.safe_load(text[4:end]) or {}, text[end + 4:].lstrip("\n")
    return {}, text


def inline_reference_links(text):
    """[text][ref] + [ref]: url  ->  [text](url). Outline's importer does not keep reference definitions."""
    defs = dict(re.findall(r"^\[([^\]]+)\]:\s*(\S+)\s*$", text, flags=re.M))
    text = re.sub(r"^\[[^\]]+\]:\s*\S+\s*$\n?", "", text, flags=re.M)
    def rep(m):
        label, ref = m.group(1), (m.group(2) or m.group(1))
        return f"[{label}]({defs[ref]})" if ref in defs else m.group(0)
    text = re.sub(r"\[([^\]]+)\]\[([^\]]*)\]", rep, text)
    return text.rstrip() + "\n"


def drop_h1(text):
    return re.sub(r"\A\s*# .*\n+", "", text, count=1)


def drop_section(text, heading):
    """Remove a '## heading' section up to the next '## '."""
    return re.sub(rf"^## {re.escape(heading)}\s*\n.*?(?=^## |\Z)", "", text, flags=re.M | re.S)


def section(text, heading):
    m = re.search(rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    return m.group(1).strip() if m else ""


def safe(name):
    return name.replace("/", "-").replace(":", " -").strip()


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def main():
    for cdir in sorted(glob.glob(os.path.join(WS, "clients", "*", "client.yaml"))):
        cpath = os.path.dirname(cdir)
        slug = os.path.basename(cpath)
        y = yaml.safe_load(open(cdir))
        name, status = y["name"], y.get("status", "active")
        coll = "Clients" if status == "active" else "Archive"
        base = os.path.join(OUT, coll, safe(name))
        ckey = f"ws:client:{slug}"
        info = {"slug": slug, "name": name, "status": status, "collection": coll, "engagements": [], "meetings": 0}

        # map of relative path (from client dir) -> key, for link rewriting
        keymap = {"README.md": ckey}
        titles = {ckey: name, ckey + ":meetings": "Meetings"}
        engs = []
        for e in y.get("engagements", []):
            edir = os.path.join(cpath, "engagements", e["id"])
            if not os.path.isdir(edir):
                report["warnings"].append(f"{slug}: engagement folder missing for {e['id']}")
                continue
            ek = f"ws:eng:{slug}:{e['id']}"
            keymap[f"engagements/{e['id']}/README.md"] = ek
            keymap[f"engagements/{e['id']}/scope.md"] = ek + ":scope"
            keymap[f"engagements/{e['id']}/decisions.md"] = ek + ":decisions"
            keymap[f"engagements/{e['id']}/meetings"] = ckey + ":meetings"
            titles.update({ek: e["name"], ek + ":scope": "Scope", ek + ":decisions": "Decisions"})
            for mf in glob.glob(os.path.join(edir, "meetings", "*.md")):
                keymap[f"engagements/{e['id']}/meetings/{os.path.basename(mf)}"] = f"ws:meeting:{slug}:{os.path.basename(mf)[:-3]}"
            engs.append((e, edir, ek))

        def relink(text, here):
            """Rewrite relative .md links. `here` is the file's dir relative to the client dir."""
            def rep(m):
                label, target = m.group(1), m.group(2)
                if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                    return m.group(0)
                path = target.split("#")[0]
                norm = os.path.normpath(os.path.join(here, path)).replace("\\", "/")
                if norm in keymap:
                    k = keymap[norm]
                    if re.search(r"\.md$|/", label) and k in titles:
                        label = titles[k]
                    return f"[{label}](outline-key:{k})"
                if norm.endswith("/") or os.path.isdir(os.path.join(cpath, norm)):
                    cand = norm.rstrip("/") + "/README.md"
                    if cand in keymap:
                        return f"[{label}](outline-key:{keymap[cand]})"
                if norm.startswith("../"):
                    # another client or a repo-level doc: link to GitHub
                    return f"[{label}]({GH}clients/{slug}/{norm})"
                report["warnings"].append(f"{slug}: unresolved link {target} in {here}")
                return label
            return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", rep, text)

        # ---------- links block for the overview (the only place these are listed)
        links, seen = [], set()
        def addlink(label, url):
            if url and url not in seen:
                seen.add(url); links.append(f"- **{label}:** {url}")
        for e, edir, ek in engs:
            tag = f" ({e['name']})" if len(engs) > 1 else ""
            asana = next((s["url"] for s in e.get("sources", []) if s.get("role") == "asana-project"), None)
            if not asana and e.get("asana"):
                asana = f"https://app.asana.com/0/{e['asana']}"
            addlink("Asana" + tag, asana)
            if e.get("drive"):
                addlink("Drive" + tag, f"https://drive.google.com/drive/folders/{e['drive']}")
            for r in e.get("repos", []) or []:
                addlink("Repo" + tag, f"https://github.com/PaperTiger/{r}")
        alltext = ""
        for f in glob.glob(os.path.join(cpath, "**", "*.md"), recursive=True):
            alltext += open(f).read()
        for url in sorted(set(re.findall(r"https://(?:www\.)?figma\.com/[^\s)\]>]+", alltext))):
            addlink("Figma", url)
        for url in sorted(set(re.findall(r"https://[a-z0-9-]+\.slack\.com/archives/[A-Z0-9]+(?=[/\s)\]>]|$)", alltext))):
            addlink("Slack channel", url)

        # ---------- client overview
        readme = open(os.path.join(cpath, "README.md")).read()
        body = inline_reference_links(drop_h1(readme))
        body = relink(body, ".")
        body = body.rstrip() + "\n\n## Links\n\n" + ("\n".join(links) if links else "No tool links found at the source.") + "\n"
        body = body.rstrip() + "\n\n## Meetings\n\nOne doc per client meeting, under [Meetings](outline-key:" + ckey + ":meetings).\n"
        write(base + ".md", fm(name, ckey, f"pt-workspace, clients/{slug}/README.md", f"{GH}clients/{slug}/README.md") + body)

        # ---------- engagements
        meetings_all = []
        for e, edir, ek in engs:
            here = f"engagements/{e['id']}"
            ebase = os.path.join(base, safe(e["name"]))
            info["engagements"].append({"name": e["name"], "status": e.get("status")})
            br = inline_reference_links(drop_h1(open(os.path.join(edir, "README.md")).read()))
            br = drop_section(br, "Links")  # tool links live only in the client overview
            br = relink(br, here)
            br = br.rstrip() + f"\n\nLinks to Asana, Drive and the repo are in the [client overview](outline-key:{ckey}).\n"
            write(ebase + ".md", fm(e["name"], ek, f"pt-workspace, clients/{slug}/{here}/README.md", f"{GH}clients/{slug}/{here}/README.md") + br)
            for fname, title in (("scope.md", "Scope"), ("decisions.md", "Decisions")):
                p = os.path.join(edir, fname)
                if not os.path.exists(p):
                    report["warnings"].append(f"{slug}/{e['id']}: no {fname} at source")
                    continue
                t = relink(inline_reference_links(drop_h1(open(p).read())), here)
                write(os.path.join(ebase, title + ".md"), fm(title, f"{ek}:{fname[:-3]}", f"pt-workspace, clients/{slug}/{here}/{fname}", f"{GH}clients/{slug}/{here}/{fname}") + t)
            for mf in sorted(glob.glob(os.path.join(edir, "meetings", "*.md"))):
                meetings_all.append((e, here, mf))

        # ---------- meetings (one Meetings parent per client)
        mbase = os.path.join(base, "Meetings")
        intro = (f"One doc per real client meeting with {name}, named `YYYY-MM-DD Title`, newest first. "
                 "Summaries only, never raw transcripts. Internal meetings don't get a doc: what they decide goes into the brief and Decisions.\n")
        write(mbase + ".md", fm("Meetings", ckey + ":meetings", "Written during the Outline move") + intro)
        for e, here, mf in meetings_all:
            meta, mbody = strip_frontmatter(open(mf).read())
            date = str(meta.get("date") or os.path.basename(mf)[:10])
            mtitle = re.sub(r"^#\s*", "", (re.search(r"^# .*", mbody, re.M) or [""])[0]) if not meta.get("title") else meta["title"]
            title = f"{date} {mtitle}".strip()
            head = []
            if meta.get("attendees"):
                head.append("**Attendees:** " + ", ".join(map(str, meta["attendees"])))
            if len(engs) > 1:
                head.append(f"**Engagement:** [{e['name']}](outline-key:ws:eng:{slug}:{e['id']})")
            if meta.get("sources"):
                head.append("**Notes from:** " + ", ".join(f"`{s}`" for s in meta["sources"]))
            mb = relink(inline_reference_links(drop_h1(mbody)), here + "/meetings")
            mkey = f"ws:meeting:{slug}:{os.path.basename(mf)[:-3]}"
            write(os.path.join(mbase, safe(title) + ".md"),
                  fm(title, mkey, f"pt-workspace, clients/{slug}/{here}/meetings/{os.path.basename(mf)}", f"{GH}clients/{slug}/{here}/meetings/{os.path.basename(mf)}")
                  + ("\n\n".join(head) + "\n\n" if head else "") + mb)
            info["meetings"] += 1
        report["clients"].append(info)

    write(os.path.join(OUT, "_workspace-report.json"), json.dumps(report, indent=2))
    print(json.dumps({"clients": len(report["clients"]),
                      "meetings": sum(c["meetings"] for c in report["clients"]),
                      "by_collection": {k: [c["name"] for c in report["clients"] if c["collection"] == k] for k in ("Clients", "Archive")},
                      "warnings": report["warnings"]}, indent=1))


main()
