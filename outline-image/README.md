# Patched Outline image

papertiger.agency runs Outline with a small patch on top, built by `.github/workflows/outline-image.yml`
into `ghcr.io/papertiger/outline:<version>-pt`. Nothing here touches the database, so the stock image can
always replace ours.

## What the patches change

`patches/01-collection-tabs.patch`: on every collection page, the tabs are **Overview, Documents, Recently
updated, Archived**.

- Popular, Recently published, Least recently updated and A–Z are hidden. Their URLs still work.
- **Archived** lists what was archived from that collection, top level only: a client, not its
  engagements and meetings. Newest archived first. It reuses the list Outline already shows for an archived
  collection. A doc archived on its own under a doc that's still active doesn't show here, but it's on
  Outline's own Archive page.

## Upgrading Outline

1. Set `VERSION` to the new release (for example `1.13.0`) on a branch and push. The workflow runs a check
   build without publishing.
2. If "Apply patches" fails, the patch no longer fits that release. Update it: clone Outline at the new tag,
   apply the patch by hand, fix what moved, and save `git diff` over the patch file. Never deploy until the
   check build passes.
3. Merge, run the workflow on `main` with **Publish** on, then on the server set the image in
   `docker-compose.yml` to `ghcr.io/papertiger/outline:<version>-pt` and run `docker compose up -d outline`.
   That restarts Outline (about 30 seconds).

Each published build also gets a `<version>-pt-<commit>` tag, so you can pin an exact build.

## Rolling back

Set the image in `docker-compose.yml` back to `docker.getoutline.com/outlinewiki/outline:<version>` and run
`docker compose up -d outline`. The tabs go back to Outline's defaults. No data changes either way.
