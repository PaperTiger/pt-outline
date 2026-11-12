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

`patches/02-theme-colors.patch`: easier-to-read greys, in `shared/styles/theme.ts` only.

| Color | Was | Now |
| --- | --- | --- |
| Light: small grey text (dates, details) | `#66778F`, 4.6:1 | `#4B5563`, 7.6:1 |
| Light: sidebar menu text | `#4E5C6E`, 6.1:1 | `#2B313B`, 11.6:1 |
| Dark: sidebar background | `#08090C` | black |
| Dark: sidebar menu text | `#66778F`, 4.4:1 | `#E4E7EB`, 16.9:1 |
| Dark: small grey text | `#66778F`, 4.1:1 | `#A3ADBA`, 8.2:1 |
| Dark: secondary text | lighter slate | `#C3CAD3`, 11.2:1 |

The ratios are contrast against the background (4.5:1 is the usual minimum for text). To change a color, edit the
patch's values, or re-make it the way "Upgrading Outline" describes.

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
