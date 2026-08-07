# example/ — bare extracted credential strings

The same synthetic secrets from `../windows-credential-samples/`, stripped down
to **just the credential string** and organized by the same 11 categories.
No file framing, no comments, no surrounding artifact — one file per credential
type, content only. Intended as ground-truth / answer-key for testing extraction
and parsing tooling.

All values are fake (see `../windows-credential-samples/README.md`).

The `*-template` and `*-fixture` documents are additional generated examples
of clearly non-live setup values across every artifact family. They are
labelled `placeholder_or_test` because the surrounding language explicitly
marks them as replacements, samples, tests, or training material; they are
never usable credentials.

Convention inside the files:
- `user:password` or `DOMAIN\user:password` on one line
- NTLM hashes in pwdump form `user:rid:lm:nt:::`
- multi-part secrets (e.g. AWS) = one value per line
