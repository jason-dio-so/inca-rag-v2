# OPS-4: Branch Protection Rules for `main`

This document defines the required branch protection settings for the `main` branch.
These settings ensure that no unconstitutional or failing code can be merged.

---

## Prerequisites

Before applying these rules, ensure the following are in place:

- [x] OPS-1: `.github/PR_REVIEW_RULES.md` exists
- [x] OPS-2: `.github/PULL_REQUEST_TEMPLATE.md` exists
- [x] OPS-3: `.github/workflows/pr-guardian.yml` exists and runs

---

## GitHub UI Path

```
Repository → Settings → Branches → Branch protection rules → Add rule
```

**Branch name pattern:** `main`

---

## Required Settings Checklist

### 1. Pull Request Requirement

| Setting | Value | Purpose |
|---------|-------|---------|
| **Require a pull request before merging** | ✅ Enabled | No direct push to main |
| Require approvals | ❌ Optional | Not mandatory for this repo |
| Dismiss stale pull request approvals | ❌ Optional | - |
| Require review from Code Owners | ❌ Optional | - |

---

### 2. Status Checks (CRITICAL)

| Setting | Value | Purpose |
|---------|-------|---------|
| **Require status checks to pass before merging** | ✅ Enabled | CI must pass |
| **Require branches to be up to date before merging** | ✅ Enabled | Prevent stale merges |

**Required status checks:**

Add the following checks (must match job names in `pr-guardian.yml`):

```
Constitutional Compliance Check
```

> ⚠️ The check name must exactly match the `name:` field in the workflow job.
> In `pr-guardian.yml`, this is: `Constitutional Compliance Check`

---

### 3. Conversation Resolution

| Setting | Value | Purpose |
|---------|-------|---------|
| **Require conversation resolution before merging** | ✅ Enabled | PR Guardian comments must be addressed |

---

### 4. Merge Method Restrictions

| Setting | Value | Purpose |
|---------|-------|---------|
| **Allow squash merging** | ✅ Enabled | 1 PR = 1 commit |
| Allow merge commits | ❌ Disabled | Clean history |
| Allow rebase merging | ❌ Disabled | Clean history |

---

### 5. Administrator Bypass (IMPORTANT)

| Setting | Value | Purpose |
|---------|-------|---------|
| **Do not allow bypassing the above settings** | ✅ Enabled | No exceptions, even for admins |

> ⚠️ This is critical. Without this, admins can force-merge unconstitutional PRs.

---

### 6. Additional Protections

| Setting | Value | Purpose |
|---------|-------|---------|
| Restrict who can push to matching branches | ❌ Optional | - |
| Allow force pushes | ❌ Disabled | Prevent history rewrite |
| Allow deletions | ❌ Disabled | Protect main branch |

---

## Verification Scenarios

After applying the settings, verify the following:

### Scenario 1: Direct Push Attempt

```bash
git checkout main
echo "test" >> README.md
git commit -am "direct push test"
git push origin main
```

**Expected:** ❌ Push rejected

---

### Scenario 2: PR with CI Failure

1. Create a PR with a file containing `carrier` (forbidden term)
2. PR Guardian detects violation
3. Workflow fails

**Expected:** ❌ Merge button disabled, comment posted

---

### Scenario 3: PR with Test Failure

1. Create a PR that breaks a test
2. pytest fails

**Expected:** ❌ Merge button disabled, comment posted

---

### Scenario 4: Clean PR

1. Create a PR with no violations
2. PR Guardian passes
3. pytest passes
4. All template checkboxes completed

**Expected:** ✅ Merge button enabled

---

## Quick Setup Summary

```
☐ Require a pull request before merging
☐ Require status checks to pass before merging
  ☐ Add check: "Constitutional Compliance Check"
☐ Require branches to be up to date before merging
☐ Require conversation resolution before merging
☐ Do not allow bypassing the above settings
☐ Allow squash merging only
☐ Disallow force pushes
☐ Disallow deletions
```

---

## References

- [CLAUDE.md](../../CLAUDE.md) — Execution Constitution
- [PR_REVIEW_RULES.md](../../.github/PR_REVIEW_RULES.md) — PR Guardian Rules
- [pr-guardian.yml](../../.github/workflows/pr-guardian.yml) — CI Workflow
- [ADR-000 ~ ADR-003](../decisions/) — Constitutional ADRs
