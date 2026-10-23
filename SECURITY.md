# Security

Report vulnerabilities privately through **Security > Report a vulnerability**.
Only the default branch is maintained.

Keep database passwords and Telegram credentials in local environment files or
deployment secrets. CI uses dummy Telegram values and blocks outbound sockets in
backend tests; it does not scrape providers, send notifications or deploy services.

Renovate prepares dependency updates. Minor, patch, pin and digest changes can merge
only after the repository's required checks pass on an up-to-date branch. Major
updates and security PRs require manual review.
