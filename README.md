# IG_AOE_tags

A standalone AOE-branded gallery prototype for posts associated with `#artofed` and `@theartofed`.

## Current status

This version is a static prototype. The sample content lives in `data/posts.json`. The production version can replace that file through a secure scheduled process after Meta API access is approved.

## Publish with GitHub Pages

1. Upload the contents of this folder to the root of the `IG_AOE_tags` repository.
2. Open **Settings → Pages** in the repository.
3. Under **Build and deployment**, select **Deploy from a branch**.
4. Select the `main` branch and the `/ (root)` folder, then click **Save**.
5. GitHub will provide the published URL, usually:

   `https://jenleban.github.io/IG_AOE_tags/`

The included `.github/workflows/deploy-pages.yml` file is optional for the prototype. It can be used later if we want GitHub Actions to deploy the site or update `data/posts.json` automatically.

## Important security note

Do not place Meta access tokens, app secrets, or other credentials in this repository or in browser-side JavaScript. Those values should remain in GitHub Actions secrets or a server-side integration.
