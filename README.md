# IG_AOE_tags

A standalone AOE-branded gallery prototype for posts associated with `#artofed`, `#artofedcommunity`, `#theartofed`, and `@theartofed`.

## Current status

The gallery reads content from `data/posts.json`. The package now includes a scheduled GitHub Action that can query the three hashtags and update that file using a protected Meta system-user token.

The Meta API only returns recent public hashtag media. The sync keeps the visual sample posts if no target hashtag results are available, and replaces them once live target posts are found.

## Publish with GitHub Pages

1. Upload the contents of this folder to the root of the `IG_AOE_tags` repository.
2. Open **Settings → Pages** in the repository.
3. Under **Build and deployment**, select **Deploy from a branch**.
4. Select the `main` branch and the `/ (root)` folder, then click **Save**.
5. GitHub will provide the published URL, usually:

   `https://jenleban.github.io/IG_AOE_tags/`

## Add the Meta token

1. Open **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**.
3. Use this exact name:

   `META_ACCESS_TOKEN`

4. Paste the Meta system-user token as the value and save it.

Never commit the token to the repository or put it in browser-side JavaScript.

## Run the sync

The workflow is in `.github/workflows/sync-instagram.yml` and is scheduled every six hours. It can also be run manually from **Actions → Sync Instagram gallery → Run workflow**.

The workflow queries:

- `#artofed`
- `#artofedcommunity`
- `#theartofed`

Instagram mentions such as `@theartofed` require a separate webhook flow and are not included in this scheduled hashtag sync.
