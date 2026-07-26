# Campaign synchronization and gallery bundles

GMCampaignDesigner deliberately exposes three different distribution formats:

* **Manual asset-library bundles** contain selected entities and attachments.
  Importing them merges the selected material into a campaign. They do not have
  a campaign identity or revision and never participate in update checks.
* **Synchronized campaign snapshots** contain one complete campaign, including
  a transactionally consistent SQLite snapshot. They carry a campaign UUID,
  parent revision, monotonically increasing revision, and content digest. They
  are installed/replaced as a whole rather than merged.
* **Image-library-only bundles** contain reusable image-library records. They
  are manual bundles and must never trigger campaign update prompts.

## Publication protocol

`modules/generic/campaign_sync/publisher.py` is the sole publication path for a
synchronized full campaign. It reads the installed campaign identity/revision,
finds the latest remote revision for that exact UUID, and requires it to match
the revision on which the local copy is based. If it does not match, publication
stops until the remote update has been downloaded and reconciled.

The publisher creates a consistent SQLite backup and complete bundle, assigns
the next integer revision, embeds the campaign content SHA-256 digest, records
the completed archive SHA-256 digest in release and installed metadata, and
checks the remote revision again immediately before release creation. Local
installed metadata and the local baseline advance only after release creation
and post-publication verification succeed. A duplicate revision or a newer
revision observed afterward marks the publication as **conflicted**; the
application never silently chooses a winner.

Enabling synchronization on a legacy campaign creates revision 1 and a UUID in
`.gmcd/sync.json`. The same metadata is embedded in the synchronized bundle
manifest, so installing the snapshot on another computer retains the campaign
UUID. **Unlink this local copy** removes only the local link; it does not delete
remote releases.

## Concurrency limitation

GitHub Releases has no atomic compare-and-swap or transactional revision
allocator. Checking immediately before and after publication makes conflicts
visible but leaves a small multi-writer race. Strict guarantees require a
dedicated backend that allocates revisions transactionally.
