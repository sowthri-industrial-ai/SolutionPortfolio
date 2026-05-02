# Operator Runbook — Refinery Twin

This runbook is the cumulative record of every working command, every
solved problem, every gotcha discovered during the project. It exists
so the build knowledge doesn't live only on a server we'll someday
terminate.

**Charter principle 8: if it's not in the runbook, it didn't happen.**

The point of this document is that a competent stranger could rebuild
the demo from scratch by following it. That standard is not "thorough
notes for me" — it's "step-by-step instructions that work for someone
who is not me."

---

## How to use this document

- **Append, never delete.** When something changes, add a new entry with the date. Don't erase history.
- **Commands as code blocks.** Not prose. A future-you needs to copy-paste, not interpret.
- **Outcomes after every command.** "What I expected" + "what actually happened" + "what fixed it if different."
- **Document at the time of discovery, not at the end of the day.** Memory degrades fast.

---

## My environment

- **Owner GitHub handle:** sowthri-industrial-ai (org)
- **Local working directory:** ~/Documents/SolutionPortfolio/AISolutions/RefineryTwin
- **Local Mac:** SOWTHRIs-MacBook-Air
- **Local Python:** 3.11.3, project venv at `RefineryTwin/.venv` (created 2026-04-30, empty, awaiting Phase 1)
- **Cloud provider:** AWS (pivoted from Lambda Labs 2026-04-30 — see Decision log)
- **AWS account ID:** 534883914089
- **AWS account alias:** sowthri-industrial-ai
- **AWS region:** ap-south-1 (Mumbai)
- **AWS root email:** [your AWS root email — fill in]
- **AWS IAM admin user:** sowthri-admin
- **AWS IAM credentials:** stored in password manager as "AWS IAM — sowthri-admin"
- **NGC account email:** [your NGC email — fill in]
- **NGC API key:** stored in password manager as "NGC API Key — RefineryTwin"
- **GitHub PAT:** stored in macOS keychain via `osxkeychain` credential helper
- **SSH key path:** `~/.ssh/id_ed25519` (private), `~/.ssh/id_ed25519.pub` (public)
- **SSH key fingerprint:** `SHA256:6mV0wTzN0uL7kCbiHuVWcDA+WMGr5Pzl9HBXMcYsS88`
- **SSH key uploaded to AWS as Key Pair:** `sowthri-mac-refinery-twin` (in ap-south-1)

---

## Cloud instance details

(updated as instance is rebuilt across the project)

| Date provisioned | Region | Instance type | Public IP | Driver version | Notes |
|---|---|---|---|---|---|
| (pending quota approval) | ap-south-1 (Mumbai) | g6.xlarge | TBD | TBD | NVIDIA L4 GPU, 24 GB VRAM, 4 vCPU, 16 GB RAM, $0.97/hr |

---

## Snapshots

(every phase boundary creates one)

| Date | Phase | Snapshot ID | Size (GB) | Boot-from-snapshot tested? | Notes |
|---|---|---|---|---|---|
| | | | | | |

---

## Cost log

(track spend over the project)

| Date | Activity | Hours | Cost (USD) | Cumulative |
|---|---|---|---|---|
| 2026-05-01 | AWS account creation, IAM, MFA, budgets | 0 | $0.00 | $0.00 |
| 2026-05-01 | AWS promotional credits issued | — | -$120.00 (credit balance) | -$120.00 |

---

## Phase 0 — Foundation

### Story 0.0 — Project skeleton in git (DONE 2026-04-30)

**What was done:**
- Used existing SolutionPortfolio working copy at `~/Documents/SolutionPortfolio`
- Created `AISolutions/RefineryTwin/` directory tree with module skeleton
- Copied charter docs into `docs/charter/`
- Initialized OPERATOR_RUNBOOK.md from template
- Wrote `.gitignore` at project root and repo root
- Wrote README.md stub
- First commit, push, tag

**Working commands:**
```bash
cd ~/Documents/SolutionPortfolio/AISolutions
mkdir -p RefineryTwin/{docs/charter,docs/media,asset-library,data-fabric,kit-extension,isaac-scenarios}
cp 2.refinery-twin-prep/charter/*.md RefineryTwin/docs/charter/
cp RefineryTwin/docs/charter/RUNBOOK_TEMPLATE.md RefineryTwin/docs/OPERATOR_RUNBOOK.md
# created README.md and .gitignore via cat heredocs (see git history for content)

cd ~/Documents/SolutionPortfolio
git add .gitignore AISolutions/RefineryTwin/
git status   # confirmed clean: only project files + repo-root .gitignore
git diff --cached | grep -iE "ghp_|sk-|password|api[-_]?key" | head   # secrets scan, all matches in docs only
git commit -m "phase-0/0.0: bootstrap RefineryTwin project skeleton

- Charter docs in docs/charter/ (8 files)
- Operator runbook initialized at docs/OPERATOR_RUNBOOK.md
- Module skeleton: asset-library, data-fabric, kit-extension, isaac-scenarios
- .gitignore at project root and repo root
- Project README stub"
git push origin main
git tag -a phase-0-start -m "Phase 0 begins 2026-04-30 — RefineryTwin project bootstrapped"
git push origin --tags
```

**Result:**
- Commit hash: `44790b8`
- 12 files changed, 2819 insertions
- Tag `phase-0-start` pushed to origin
- Visible at: https://github.com/sowthri-industrial-ai/SolutionPortfolio/tree/main/AISolutions/RefineryTwin

**Issues encountered & resolution:**
- None. Smooth execution.

---

### Story 0.1 — Pre-flight on Mac (IN PROGRESS, started 2026-04-30, paused 2026-05-01 awaiting AWS quota approval)

#### Block 1 — SSH key generation (DONE 2026-04-30)

Generated ed25519 SSH key for cloud access. macOS native `ssh-keygen`.

**Working commands:**
```bash
ssh-keygen -t ed25519 -C "sowthri2020@yahoo.com"
# 3x Enter: default location, no passphrase, confirm no passphrase
```

**Result:**
- Private key: `~/.ssh/id_ed25519` (mode 600)
- Public key: `~/.ssh/id_ed25519.pub` (mode 644)
- Fingerprint: `SHA256:6mV0wTzN0uL7kCbiHuVWcDA+WMGr5Pzl9HBXMcYsS88`

To copy public key to clipboard for paste into cloud console:
```bash
pbcopy < ~/.ssh/id_ed25519.pub
```

**Issues encountered & resolution:**
- None.

#### Block 2 — NGC account + Personal Key (DONE 2026-04-30)

Created NGC account at https://ngc.nvidia.com.
Generated Personal Key under Profile → Personal Keys.

**Services granted to the key:**
- NGC Catalog (required to pull container images)
- Private Registry (required for org-private images)

**Storage:** Saved in password manager as "NGC API Key — RefineryTwin".

**Issues encountered & resolution:**
- *Initial confusion:* NGC's UI splits "Personal Keys", "Secret Manager", "NGC Catalog" as menu items. Only "Personal Keys" is the credential type we need. "Secret Manager" is for storing other credentials inside NGC; "NGC Catalog" is the container browse view, not a credential.
- *Resolution:* Click Personal Keys, generate new, tick NGC Catalog + Private Registry services minimum.

#### Block 3 — Cloud provider account: AWS (DONE 2026-05-01)

**Major pivot from original plan.** Original Lambda Labs plan abandoned. See Decision log below.

**AWS setup performed:**

1. **Account created** at https://aws.amazon.com (fresh signup, new email)
2. **MFA enabled on root account** using Google Authenticator
   - Console → top-right account dropdown → Security credentials
   - Multi-factor authentication → Assign MFA device
   - Authenticator app, named `sowthri-root-phone`, scanned QR, entered 2 consecutive TOTP codes
3. **Verified MFA** by signing out completely, signing back in
   - Confirmed: password AND TOTP code both required
4. **Created IAM user `sowthri-admin`** (admin alternative to root)
   - IAM → Users → Create user
   - Provided console access, custom password, no force-reset
   - Attached AWS managed policy: `AdministratorAccess`
   - Saved IAM sign-in URL + username + password in password manager
5. **Enabled IAM access to billing**
   - Account name (top-right) → Account → IAM User and Role Access to Billing → Edit → Activate IAM Access
6. **Created two AWS Budgets:**
   - `RefineryTwin-EarlyWarning`: $10/month, alerts via email at 100% (i.e., $10 spent triggers alert)
   - `RefineryTwin-MonthlyBudget`: $100/month, alerts at 85% and 100%
   - Note: budgets initially set to $5/$10 (too conservative — single 12-hour overnight mistake costs $12), raised to $10/$100 after recalibration
7. **Signed out of root, signed in as `sowthri-admin`** via IAM user URL
   - Confirmed: top-right shows `sowthri-industrial-ai (534883914089)` and `sowthri-admin`
8. **Confirmed region:** Asia Pacific (Mumbai) `ap-south-1`
9. **Verified $120 in promotional credits**
   - $100 "AWS Free Tier" (general-purpose, applies to EC2)
   - $20 "Explore AWS: Set up a cost budget"
   - Both expire 2027-05-01

**Account details for reference:**
- AWS account ID: `534883914089`
- AWS account alias: `sowthri-industrial-ai`
- IAM user: `sowthri-admin`
- Default region: `ap-south-1`

**Issues encountered & resolution:**
- *Confusion about budget realism:* Initial budgets at $5 / $10 were too low for a $0.97/hr GPU project — would trigger alerts on day 2 of normal use. Raised to $10 / $100 to match project reality. This matters because AWS reviewers reading the appeal will notice unrealistic budget caps as a possible red flag.
- *Confusion: AWS Free Tier program vs Free Tier promotional credit:* The "AWS Free Tier" credit name is misleading — it's NOT restricted to "free-tier-eligible" services. It's a $100 general-purpose credit that applies to GPU EC2. Verified by checking the credit's eligible-services list (full directory of AWS services including Amazon Elastic Compute Cloud).

#### Block 4 — SSH key uploaded to AWS (DONE 2026-05-01)

EC2 → Network & Security → Key Pairs → Import key pair.

**Form fields:**
- Name: `sowthri-mac-refinery-twin`
- Key pair file: pasted from `pbcopy < ~/.ssh/id_ed25519.pub`

**Verification:**
- Key visible in Mumbai region's Key Pairs list
- Type: ed25519
- Fingerprint matches local: `SHA256:6mV0wTzN0uL7kCbiHuVWcDA+WMGr5Pzl9HBXMcYsS88`

**Issues encountered & resolution:**
- None.

#### Block 5 — Pre-flight checks + quota request (IN PROGRESS 2026-05-01, BLOCKED on AWS approval)

**Instance type selection:**
- Originally planned: g5.xlarge ($1.21/hr, A10G GPU) per Lambda-era plan
- After analyzing Mumbai region availability via uploaded CSV of all 37 GPU instance types, switched to: **g6.xlarge** ($0.97/hr, 4 vCPUs, 1× NVIDIA L4 GPU 24 GB VRAM)
- Reason: newer Ada Lovelace architecture (vs g5's Ampere), 20% cheaper, identical practical capability for Omniverse Kit workload
- Excluded from consideration: g6e ($2.24/hr — overkill), p4d/p5/p5en (research-grade $26-76/hr — far too expensive)

**Service Quota check:**
- Service Quotas → EC2 → "Running On-Demand G and VT instances"
- Quota code: `L-DB2E81BA`
- Region: ap-south-1
- **Applied account-level quota value: 0** (default for new accounts)

**Quota request #1 — DENIED (2026-05-01 ~3:30pm IST):**
```
Request submitted via Service Quotas console
Requested quota value: 4 (= one g6.xlarge worth of vCPUs)
Form had no use-case description field
Status flipped to: Pending
```

**Denial received ~30 min later via email:**
> Hello, I am sorry but at this time we are unable to approve your service quota increase request. Service quotas are put in place to help you gradually ramp up activity and decrease the likelihood of large bills due to sudden, unexpected spikes. If you'd like to appeal this decision, please reopen this case and provide as detailed a use case as possible. With this additional information, we would be more than happy to re-assess this request.

**Quota request #2 — APPEAL via AWS Support chat (SUBMITTED 2026-05-01 ~6:30pm IST):**

Opened AWS Support Center → started live chat. Agent: **Esteban**.

**Appeal use case provided** (paraphrased into chat):
- Personal portfolio project for senior engineering interview in digital twin / Physical AI space
- Building NVIDIA Omniverse Kit application + Isaac Sim scenarios for refinery digital twin
- Project documented publicly: https://github.com/sowthri-industrial-ai/SolutionPortfolio/tree/main/AISolutions/RefineryTwin
- Specific resource: single g6.xlarge in ap-south-1 (4 vCPUs, 1× NVIDIA L4 GPU)
- Cost controls: AWS Budgets $10/$100, MFA on root, dedicated IAM admin user, $120 promotional credits
- Estimated 125 instance-hours over 5 weeks, well within credit balance

**Esteban's response:**
> We need to wait for the EC2 team to review this, generally not all features are immediately available on your account since it is brand new, just created today. I have asked to see if an exception can be made so you can access these G instances earlier than usual, once we have a response I will let you know.

**Status as of 2026-05-02 morning (Saturday IST):**
- Case ID: `177764536900839`
- Case status: **Pending Amazon action**
- No new correspondence overnight
- AWS Support technically operates 24/7 but quota approvals slow on weekends — realistic response window: today afternoon to Monday Mumbai time

**Plan B if denied or excessively delayed:**
JarvisLabs (https://jarvislabs.ai), Indian provider, L4 GPU at $0.44/hr, instant access, no quota gates, accepts Indian payment methods. Owner has confirmed payment access. Hardware (L4) is identical to AWS g6.xlarge. Software stack (PyTorch-focused image) would need manual Omniverse Kit + Isaac Sim install — same effort as on AWS, possibly with 2-4 hours additional debugging if their pre-baked image conflicts. Not committed yet — only opened if AWS denies.

---

### What's NOT done yet in Phase 0

After AWS quota approves:

- **Story 0.2** — Launch g6.xlarge, SSH in, run nvidia-smi (~30 min)
- **Story 0.3** — Install system dependencies (Vulkan, Xvfb, x11vnc, novnc, websockify) (~30 min)
- **Story 0.4** — Verify Vulkan + GPU recognized by `vulkaninfo --summary` (~15 min)
- **Story 0.5** — Clone kit-app-template, build Kit Base Editor (~60 min)
- **Story 0.6** — Boot Kit headlessly under Xvfb, confirm clean startup (~30 min)
- **Story 0.7** — Set up VNC tunnel from Mac to cloud, see Kit window in browser (~30 min)
- **Story 0.8** — Phase 0 snapshot (EBS), document snapshot ID, test boot-from-snapshot (~15 min)

Total Phase 0 remaining: ~3.5 hours of focused work after GPU access lands.

---

### Story 0.2 — AWS instance launched

(awaiting quota approval — to be filled in)

---

### Story 0.3 — System dependencies installed

(to be filled in)

---

### Story 0.4 — Vulkan + GPU verified

(to be filled in)

---

### Story 0.5 — Kit App Template built

(to be filled in)

---

### Story 0.6 — Xvfb + Kit headless boot

(to be filled in)

---

### Story 0.7 — VNC accessible from Mac

(to be filled in)

---

### Story 0.8 — Phase 0 snapshot

(to be filled in)

---

## Phase 1 — CDU scene in Kit

(stories filled in after Phase 0 gate review)

---

## Phase 2 — Custom extension

(filled in after Phase 1 gate review)

---

## Phase 3 — Live data binding

(filled in after Phase 2 gate review)

---

## Phase 4 — Isaac Sim scenarios

(filled in after Phase 3 gate review)

---

## Phase 5 — Polish, snapshot, repos

(filled in after Phase 4 gate review)

---

## Glossary

For when you come back to this in 6 months and forget what something means.

| Term | Meaning in this project |
|---|---|
| Kit | NVIDIA Omniverse Kit, the framework. Our app is built on it. |
| NGC | NVIDIA GPU Cloud, the container registry for Omniverse / Isaac Sim images |
| RTX | Ray Tracing eXtensions; here, NVIDIA's path-traced rendering modes in Kit |
| USD | Universal Scene Description, Pixar's 3D scene format. Our refinery scene format. |
| ISA-95 | International standard for enterprise-control system integration. Our naming convention. |
| OPC UA | Open Platform Communications Unified Architecture. Industrial protocol standard. |
| Fabric | Kit's runtime data layer for fast scene-graph updates (vs file-backed USD writes) |
| Flow | NVIDIA's volumetric fluid simulator; we use it for gas dispersion |
| PhysX | NVIDIA's rigid-body and articulation physics; we use it for rover and valves |
| Articulation | A jointed rigid-body chain in PhysX (e.g., a robot arm or a valve actuator) |
| IAM | AWS Identity and Access Management — controls who can do what in an AWS account |
| MFA | Multi-Factor Authentication — second factor beyond password (TOTP code from app) |
| Quota | AWS limit on resource usage (e.g., max vCPUs of GPU instances). New accounts default to 0 for GPU. |
| L4 | NVIDIA L4 GPU (Ada Lovelace architecture, 24 GB VRAM). Our GPU. |

---

## Common failure modes

### Saudi-issued card declined at Lambda Labs (2026-04-30)

**Symptom:** Card rejected at Lambda Labs payment processor at signup.
**Root cause:** Lambda's payment processor is restrictive about Saudi-issued cards. AWS uses a different processor that accepts them.
**Resolution:** Pivoted cloud provider to AWS. Don't waste time fighting card friction at one provider when another might just work.

### NGC menu reorganization — "Setup" became "Personal Keys" (2026-04-30)

**Symptom:** Charter said "Profile → Setup" but the dropdown showed "Key Permission Services / Secret Manager / NGC Catalog" instead.
**Root cause:** NVIDIA redesigned NGC menus in 2024-2025. Credential generation flow moved from "Setup" to "Personal Keys".
**Resolution:** Direct URL works regardless of UI changes: `https://ngc.nvidia.com/setup` or `https://ngc.nvidia.com/setup/personal-keys`. Of the visible menu items, "Personal Keys" is the right one (not Secret Manager, not Catalog).

### AWS new account default GPU quota = 0 (2026-05-01)

**Symptom:** Cannot launch any G-family instance. Service Quotas page shows "Running On-Demand G and VT instances" applied limit of 0.
**Root cause:** AWS gates GPU access on new accounts as fraud prevention. Default quota is 0 for the first weeks of an account's life.
**Resolution:** File quota request for exactly 4 vCPUs (no more — smaller requests approve faster). If the form-based request denies (auto-decline is common for brand-new accounts), use Support chat for the appeal — a live agent can submit a properly-contextualized exception request.

### AWS first quota request denied without explanation (2026-05-01)

**Symptom:** Submitted via Service Quotas form, denied within 30 min by automated system. Form had no use-case description field.
**Root cause:** Brand-new account + GPU request + no use case provided = automatic high-risk flagging.
**Resolution:** Always use AWS Support chat for first-time GPU requests on new accounts. Provide: real project description, GitHub URL for verification, specific minimum instance, cost controls already in place. Don't ask for headroom — request the exact minimum.

### AWS quota approvals slow on weekends (observed 2026-05-02)

**Symptom:** Case submitted Friday evening Mumbai time, status still "Pending Amazon action" Saturday morning.
**Root cause:** AWS Support operates 24/7 but quota review (Trust & Safety team) is heavier weekday-staffed. New-account exception requests need human judgment, which queues until business hours resume.
**Resolution:** Don't refresh case page repeatedly on weekends. Use the wait time for runbook updates, charter deltas, and reading prep docs. Realistic approval window for weekend submissions: Monday Mumbai business hours.

---

## Decision log (cross-references PROJECT_CHARTER §11)

| Date | Decision | Why |
|---|---|---|
| 2026-04-29 | Charter locked: personal-demo scope, snapshot-driven, no public URL | Owner reviewed alternatives, chose this scope |
| 2026-04-29 | Monorepo at `SolutionPortfolio/AISolutions/RefineryTwin/`, not separate repos | Personal demo with one consumer (interviewer); monorepo simpler workflow |
| 2026-04-29 | HTTPS + PAT for git auth, NOT SSH for git | Owner preference; PAT cached in macOS keychain |
| 2026-04-29 | Repos public from day one | Owner preference for transparency and recruiter-readability |
| 2026-04-29 | Kit extension namespace: `com.sowthri.cdutwin` | Hyphens illegal in Python package names |
| 2026-04-30 | **PIVOT: Lambda Labs → AWS** for cloud provider | Lambda's payment processor declined Saudi-issued card; Lambda doesn't accept PayPal; Lambda has no India region. AWS Mumbai is closer to Saudi than Lambda's US-only data centers, accepts the card, and has $120 in promotional credits. |
| 2026-04-30 | AWS region: ap-south-1 (Mumbai) | Closest available region with reliable g6 capacity; 120ms latency from Dammam (acceptable for SSH+VNC); Aramco runs many workloads from Mumbai (interview relevance) |
| 2026-04-30 | Instance type: g6.xlarge (L4 GPU) instead of g5.xlarge (A10G) | Newer Ada architecture, 20% cheaper, equivalent capability for Omniverse Kit. CSV analysis of all 37 GPU types in Mumbai confirmed this is the right size/cost point. |
| 2026-04-30 | AWS Budgets: $10 early warning + $100 monthly cap | Realistic for $0.97/hr × ~125-hour project usage; lower thresholds caused false-positive alerts |
| 2026-05-01 | JarvisLabs (https://jarvislabs.ai) chosen as Plan B if AWS denies | Indian provider, instant access, no quota gates, $0.44/hr L4 instances, accepts Indian payment methods. Hardware identical to AWS g6.xlarge. |

---

**Operator runbook end. Append-only.**
