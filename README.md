# pre-qa-plugin — retired

This marketplace no longer lists any plugins. The pre-QA gate is now its own plugin,
`dev-webflow-pre-qa` (`/dev-webflow-pre-qa:pre-qa`), in Amply's private tools marketplace:

```bash
claude plugin uninstall amply@amply
claude plugin marketplace remove amply
claude plugin marketplace add amply-int-tools/project-tools-webflow
claude plugin install dev-webflow-pre-qa@amply --scope user
```

Desktop app: **Settings → Plugins → Marketplaces**, remove `amply`, then add
`amply-int-tools/project-tools-webflow` and connect GitHub when prompted. Your GitHub account
needs access to the `amply-int-tools` organization.

Both marketplaces are named `amply`, so remove this one before adding the new one. The same
marketplace also carries the `amply` plugin (`/amply:starter-lint`).
