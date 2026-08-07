# Decoys — Credential-Shaped Strings That Are NOT Secrets

> This tree is the **negative set** for the corpus in
> [`../`](../). Everything here *looks* like a credential to a naïve
> regex — 32/40/64 hex chars, base64 blobs, `BEGIN ... KEY`, GUIDs, long
> high-entropy tokens — but **none of it is a secret**. Use it to measure and
> tune the **false-positive rate** of a detection/collection tool: a good rule
> flags the files in `../<category>/` and stays silent on these.

All values are synthetic. The point isn't the specific bytes — it's the
*shape*, and the reason each shape is safe.

| Folder | Looks like… | Actually is… | Why it's safe |
|---|---|---|---|
| `checksums-and-file-hashes` | NTLM/MD5/SHA password hashes | content digests of files/packages | one-way digest of *public* data; no account attached |
| `identifiers-and-guids` | secret tokens / session keys | COM CLSIDs, MachineGuid, correlation/request IDs | public, non-secret identifiers; grant no access |
| `public-keys-and-certificates` | private keys (`BEGIN ... KEY`) | **public** keys & X.509 certs | designed to be shared; the private half is the secret |
| `random-strings-and-nonces` | API keys / passwords | CSRF tokens, salts, IVs, nonces, slugs | single-use / public-by-design / not authenticators |
| `encoded-and-binary-blobs` | base64/hex secret material | encoded images, icons, serialized data | decode → ordinary non-secret bytes |
| `version-and-build-fingerprints` | secret hashes/keys | git SHAs, `sha256:` image digests, ETags | build/version metadata; published in every release |
| `placeholders-and-redactions` | keys in config | `<YOUR_KEY>`, `changeme`, `****`, all-zeros | template stubs / already-redacted; not live values |

## Context-oriented benign samples

The additional generated documents use every artifact-family directory shared
with the other labels. They are intentionally ordinary, publishable metadata
rather than credentials: public configuration references, backup inventories,
browser policies, deployment catalogs, build provenance, operator
documentation, certificate metadata, symbol indexes, UI settings, registry
documentation, and remote-client policy. Some include digest-, UUID-, or
encoded-looking values so that a classifier learns that morphology alone is
not a sensitive-content decision.

## The tells (what distinguishes decoy from real)

- **Length lies.** A 32-hex string is *equally* an MD5 file checksum and an
  NTLM hash. Context (surrounding filename, key name, adjacent `user:`) decides,
  not entropy.
- **`BEGIN PUBLIC KEY` / `BEGIN CERTIFICATE` ≠ `BEGIN PRIVATE KEY`.** The word
  `PRIVATE` (or `OPENSSH PRIVATE`) is the actual signal. Same for `id_rsa` vs
  `id_rsa.pub`.
- **Publishable by design.** Stripe `pk_live_…`, Google browser Maps keys, JWKS
  `n`/`e`, OAuth `state`/`nonce`, CSRF tokens — all meant to travel in the clear.
- **Digests are one-way and of public data.** A checksum grants no access even
  if you have it.
- **Identifiers correlate, they don't authenticate.** A tenant/subscription/
  correlation GUID names a thing; it doesn't unlock it.
