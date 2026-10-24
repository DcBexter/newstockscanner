# Security

Report vulnerabilities privately through **Security > Report a vulnerability**.
Only the default branch is maintained.

Keep database passwords and Telegram credentials in local environment files or
deployment secrets. CI uses dummy Telegram values and blocks outbound sockets in
backend tests; it does not scrape providers, send notifications or deploy services.

Renovate prepares dependency updates. All update types, including major and security
updates, can merge after the repository's required checks pass on an up-to-date
branch (maintainer decision, 24 October 2026).
