# Local identity synchronization

Identity synchronization is opt-in and is disabled until a superuser enrolls a
node. Enrollment and mapping are managed at
`/admin-overview/identities/`; this page is available only to active
superusers. Issue a dedicated token for each node and copy it once into that
node's private local ia3 configuration. The master stores only the SHA-256
token hash. The identity token is separate from the shared distributed-sync
secret and must not be put in source control, a URL, or logs.

An enrolled node may `POST` JSON to `/knowledge/sync/identities/` using
`Authorization: Bearer <per-node-token>`. The payload contains the exact node
ID and a bounded list of local IDs with username, email, and active-state
metadata. Node IDs are trimmed and normalized to lowercase. Username and email
are advisory metadata: they never create or select an account link, including
when they exactly match an existing account. A superuser must explicitly link a
pending local identity to a Django account selected by primary key; the UI
shows username and email only to help a human distinguish candidates. Multiple
node identities can share an account's stable global UUID only after each
explicit link.

Synchronization does not provide SSO or exchange passwords, password hashes,
sessions, roles, or permissions. It does not copy Django account data to a
node. Local authorization remains local. A mapped identity reports `active`
only while both the node's local account and the linked Django account are
active; otherwise it reports `revoked`. An unlinked identity reports
`pending`.

To recover a lost or exposed token, revoke the node credential in the admin
page, update that node's private local configuration, and issue a replacement
token. A revoked credential cannot sync; reissuing replaces its hash and makes
the previous token invalid. If a node is not explicitly enrolled, requests are
rejected and no identities are synchronized.
