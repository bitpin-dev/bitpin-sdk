## What and why

<!-- One paragraph. The PR title is a Conventional Commit, e.g. "feat(python): add fetch_x"; it becomes the release note. -->

## Checklist (see REVIEW.md)

- [ ] Spec changed first; generated files regenerated
- [ ] Tests fail without the change and pass with it, on both clients
- [ ] Write operations are still sent at most once
- [ ] No secrets, real customer data or private backend details
- [ ] Docs updated in English **and** Persian (and `llms.txt` if the API surface changed)
