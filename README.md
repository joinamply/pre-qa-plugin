# pre-qa-plugin — retired

This marketplace no longer lists any plugins. The `amply` plugin (`/amply:pre-qa` and
`/amply:starter-lint`) now installs from the private Amply starter repo:

```bash
claude plugin marketplace remove amply
claude plugin marketplace add amply-int-tools/project-starter-webflow
claude plugin install amply@amply --scope user
```

Desktop app: **Settings → Plugins → Marketplaces**, remove `amply`, then add
`amply-int-tools/project-starter-webflow` and connect GitHub when prompted. Your GitHub account
needs access to the `amply-int-tools` organization.

Both marketplaces are named `amply`, so remove this one before adding the new one.
