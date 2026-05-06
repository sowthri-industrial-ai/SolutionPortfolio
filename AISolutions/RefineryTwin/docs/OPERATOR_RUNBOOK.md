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
- **AWS root email:** stored in password manager (entry "AWS Root — RefineryTwin")
- **AWS IAM admin user:** sowthri-admin
- **AWS IAM credentials:** stored in password manager as "AWS IAM — sowthri-admin"
- **NGC account email:** stored in password manager (entry "NGC Account — RefineryTwin")
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
| 2026-05-05 | ap-south-1 (Mumbai) | g6.xlarge | 65.2.153.152 (changes on restart) | 580.105.08 | First instance. NVIDIA L4 GPU 24 GB VRAM. Story 0.2 instance ID `i-084dcf23391e63165`. Stopped after verification. |

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
| 2026-05-05 | Story 0.2 — first instance launch + verify + stop | 0.5 | ~$0.50 (covered by credits) | -$119.50 |

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
git status
git diff --cached | grep -iE "ghp_|sk-|password|api[-_]?key" | head   # secrets scan
git commit -m "phase-0/0.0: bootstrap RefineryTwin project skeleton"
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

### Story 0.1 — Pre-flight on Mac (DONE 2026-05-05)

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
- *Initial confusion:* NGC's UI splits "Personal Keys", "Secret Manager", "NGC Catalog" as menu items. Only "Personal Keys" is the credential type we need.
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
   - `RefineryTwin-EarlyWarning`: $10/month, alerts via email at 100%
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
- *Initial budgets too conservative:* $5 / $10 thresholds would have triggered alerts on day 2 of normal use. Raised to $10 / $100. Realistic budgets matter for AWS reviewer perception too — unrealistic caps look like a red flag.
- *AWS Free Tier program vs Free Tier credit naming confusion:* The "AWS Free Tier" credit name is misleading — it's NOT restricted to "free-tier-eligible" services. It's a $100 general-purpose credit that applies to GPU EC2. Verified by checking the credit's eligible-services list (full directory of AWS services including Amazon Elastic Compute Cloud).

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

#### Block 5 — Pre-flight checks + quota request (DONE 2026-05-05)

**Instance type selection:**
- Originally planned: g5.xlarge ($1.21/hr, A10G GPU) per Lambda-era plan
- After analyzing Mumbai region availability via uploaded CSV of all 37 GPU instance types, switched to: **g6.xlarge** ($0.97/hr, 4 vCPUs, 1× NVIDIA L4 GPU 24 GB VRAM)
- Reason: newer Ada Lovelace architecture (vs g5's Ampere), 20% cheaper, identical practical capability for Omniverse Kit workload
- Excluded: g6e ($2.24/hr — overkill), p4d/p5/p5en (research-grade $26-76/hr — far too expensive)

**Service Quota check:**
- Service Quotas → EC2 → "Running On-Demand G and VT instances"
- Quota code: `L-DB2E81BA`
- Region: ap-south-1
- Default for new accounts: 0

**Quota request #1 — DENIED (2026-05-01 ~3:30pm IST):**
- Submitted via Service Quotas console requesting value 4
- Form had no use-case description field
- Auto-denied within ~30 minutes
- Email cited: "Service quotas are put in place to help you gradually ramp up activity"
- Email invited reopen with detailed use case

**Quota request #2 — APPEAL via AWS Support chat (SUBMITTED 2026-05-01 ~6:30pm IST):**
- Opened AWS Support Center → started live chat
- Agent: **Esteban**
- Provided detailed use case: NVIDIA Omniverse Kit project, GitHub link, cost controls, account context
- Esteban submitted formal exception request to EC2 team
- Esteban's response: "We need to wait for the EC2 team to review this, generally not all features are immediately available on your account since it is brand new... I have asked to see if an exception can be made so you can access these G instances earlier than usual"

**Wait period (2026-05-01 evening through 2026-05-05 morning):**
- Weekend in between (Saturday and Sunday) — AWS Trust & Safety team weekday-staffed
- Status: Pending Amazon action throughout
- 4 business days elapsed from escalation to follow-up

**Polite follow-up via chat (2026-05-05 ~7:25am IST):**
- Reopened the case via AWS Support chat
- Agent: **Richa**
- Briefly checked in on status, asked if anything else needed
- Approval confirmed live in chat at 7:29am IST: "I'm pleased to inform you that your request for All G and VT instances has been approved. Your new quota is 4."
- Richa: "Please try launching an instance and check if it works for you"

**Status as of 2026-05-05:**
- Case ID: 177764536900839 (Resolved)
- Applied account-level quota value: 4 (verified in console)
- Unblocked: Story 0.2 launch

**Plan B status:**
- JarvisLabs (https://jarvislabs.ai) was kept ready as backup throughout the wait
- Not used — AWS path resolved cleanly
- Documentation kept in case of future provider needs

---

### Story 0.2 — AWS instance launched (DONE 2026-05-05)

**What was done:**
- Launched first g6.xlarge instance via EC2 console wizard
- SSH'd from Mac to instance using existing ed25519 key pair
- Verified NVIDIA L4 GPU detected and operational via `nvidia-smi`
- Stopped instance cleanly to halt billing

**Instance details:**
- Instance ID: `i-084dcf23391e63165`
- Region: ap-south-1 (Mumbai)
- Availability Zone: ap-south-1b
- Type: g6.xlarge ($0.97/hr while Running)
- AMI: `ami-001ba428c0f3efe11` — Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.6.0 (Ubuntu 22.04) build 20260103
- Public IP at first boot: `65.2.153.152` (changes on each restart — note that)
- Public DNS at first boot: `ec2-65-2-153-152.ap-south-1.compute.amazonaws.com`
- Security group: `refinery-twin-sg` (SSH from My IP only, source `5.244.109.155/32`)
- Key pair: `sowthri-mac-refinery-twin`
- EBS root volume: 200 GiB gp3, encrypted, delete-on-termination=Yes
- Instance store: 250 GB NVMe SSD ephemeral (free; wiped on stop)
- Total storage shown in summary: 2 volume(s) - 450 GiB (200 EBS + 250 instance store)

**Working SSH command:**
```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@<public-ip>
# First-time fingerprint prompt: type "yes"
# Server fingerprint stored to ~/.ssh/known_hosts
```

**SSH key flow (verified):**
- Local: `~/.ssh/id_ed25519` (mode 600), fingerprint `SHA256:6mV0wTzN0uL7kCbiHuVWcDA+WMGr5Pzl9HBXMcYsS88`
- Remote: AWS pushes the registered Key Pair's public key into `/home/ubuntu/.ssh/authorized_keys` automatically at instance launch
- Auth flow: server sends challenge, Mac signs with private key (key never leaves Mac), server verifies signature against public key

**Verification — `nvidia-smi` output (2026-05-05 19:01:54 UTC):**
```
NVIDIA-SMI 580.105.08    Driver Version: 580.105.08    CUDA Version: 13.0
GPU 0: NVIDIA L4
  - Bus-Id:        00000000:31:00.0
  - Display:       Off
  - Persistence-M: On
  - Fan:           N/A
  - Temp:          29C
  - Performance:   P8 (idle)
  - Power:         12W / 72W
  - Memory:        0 MiB / 23034 MiB (24 GB total)
  - Utilization:   0%
No running processes
```

All values consistent with a healthy idle L4 GPU on Linux:
- Driver 580.x is recent and stable
- CUDA 13.0 available (newer than the AMI banner suggested 12.6)
- 23034 MiB total memory ~ 24 GB nominal (driver overhead accounts for the small delta)

**Workflow that works (memorize):**
1. Launch via EC2 console -> wait for state = Running, status = 2/2 (~3 min)
2. Get public IP from instance row
3. SSH from Mac terminal: `ssh -i ~/.ssh/id_ed25519 ubuntu@<ip>`
4. Do work
5. Exit SSH: `exit`
6. Stop via EC2 console: select instance -> Instance state -> Stop instance
7. Verify state shows "Stopped" before walking away

**Stop discipline (CRITICAL — re-emphasize):**
- Instance MUST be stopped at end of every work session
- "Stopped" = $0 compute charges (only ~$0.02/hr EBS storage)
- "Running" = $0.97/hr — leaving overnight burns ~$8 for nothing
- AWS Budgets configured: $10 early warning will email if forgotten
- Discipline beats budgets; budgets are a backstop, not a permission slip

**Issues encountered & resolution:**
- *Storage UI added an unwanted Volume 2 (8 GiB):* During launch wizard, an extra 8 GiB EBS volume appeared (Not encrypted, Delete-on-termination=No). Removed via the Remove button before clicking Launch. The 250 GB NVMe instance store is separate and free.
- *Source type "My IP" not in dropdown initially:* When configuring the security group rule, "Source type" dropdown didn't show My IP option until the rule was removed and re-added through "Add security group rule" flow. AWS UI inconsistency — workaround was simple, just needed extra clicks.
- *AWS new-account quota of 0 (resolved earlier):* See Story 0.1 Block 5 for full chronicle of quota appeal saga.

---

### What's NOT done yet in Phase 0

- **Story 0.3** — Install system dependencies (Vulkan, Xvfb, x11vnc, novnc, websockify) (~30 min, ~$0.30)
- **Story 0.4** — Verify Vulkan + GPU recognized by `vulkaninfo --summary` (~15 min)
- **Story 0.5** — Clone kit-app-template, build Kit Base Editor (~60 min)
- **Story 0.6** — Boot Kit headlessly under Xvfb, confirm clean startup (~30 min)
- **Story 0.7** — Set up VNC tunnel from Mac to cloud, see Kit window in browser (~30 min)
- **Story 0.8** — Phase 0 snapshot (EBS), document snapshot ID, test boot-from-snapshot (~15 min)

Total Phase 0 remaining: ~3 hours of focused work across 6 stories.

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
| AMI | Amazon Machine Image — pre-baked disk image AWS clones to your instance at boot |
| EBS | Elastic Block Store — AWS's persistent disk service. Billed per GiB-month even when stopped. |
| Instance store | Local NVMe SSD on the host. Free, ephemeral, wiped on stop. |
| g6.xlarge | Our chosen instance type: 4 vCPU, 16 GB RAM, 1x NVIDIA L4, $0.97/hr |

---

## Common failure modes

### Saudi-issued card declined at Lambda Labs (2026-04-30)

**Symptom:** Card rejected at Lambda Labs payment processor at signup.
**Root cause:** Lambda's payment processor is restrictive about Saudi-issued cards. AWS uses a different processor that accepts them.
**Resolution:** Pivoted cloud provider to AWS. Don't waste time fighting card friction at one provider when another might just work.

### NGC menu reorganization — "Setup" became "Personal Keys" (2026-04-30)

**Symptom:** Charter said "Profile -> Setup" but the dropdown showed "Key Permission Services / Secret Manager / NGC Catalog" instead.
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

### AWS quota approvals slow on weekends (observed 2026-05-02 to 2026-05-05)

**Symptom:** Case submitted Friday evening Mumbai time, status still "Pending Amazon action" Saturday morning. Took 4 business days to resolve.
**Root cause:** AWS Support operates 24/7 but quota review (Trust & Safety / EC2 team) is heavier weekday-staffed. New-account exception requests need human judgment, which queues until business hours resume.
**Resolution:** Don't refresh case page repeatedly on weekends. Use the wait time for runbook updates, charter deltas, and reading prep docs. For new accounts, file quota requests early in the week (Monday/Tuesday) to avoid weekend stall. A polite follow-up via chat after 3+ business days can move things along.

### Storage configuration UI auto-attaches unwanted volumes (2026-05-05)

**Symptom:** During EC2 launch wizard, after configuring the root volume to 200 GiB, an additional 8 GiB Volume 2 appeared with Not-encrypted and Delete-on-termination=No defaults.
**Root cause:** AWS launch wizard sometimes auto-attaches secondary volumes based on AMI defaults or session state. Behavior is inconsistent.
**Resolution:** Always inspect the Configure storage section carefully before launching. Click Remove on any unwanted volumes. The Summary panel "X volume(s) - Y GiB" includes both EBS and ephemeral instance store, which can be confusing — instance store is free and ephemeral, EBS is billed and persistent.

### Security group "Source type" dropdown sometimes lacks "My IP" (2026-05-05)

**Symptom:** When configuring inbound SSH rule, "Source type" dropdown didn't show My IP option immediately.
**Root cause:** AWS UI inconsistency — depending on how you arrived at the rule (auto-created vs manually added), the available source-type options differ.
**Resolution:** Remove the auto-created rule and add a fresh one via "Add security group rule" button. The fresh rule's Source type dropdown reliably includes My IP.

---

## Decision log (cross-references PROJECT_CHARTER §11)

| Date | Decision | Why |
|---|---|---|
| 2026-04-29 | Charter locked: personal-demo scope, snapshot-driven, no public URL | Owner reviewed alternatives, chose this scope |
| 2026-04-29 | Monorepo at `SolutionPortfolio/AISolutions/RefineryTwin/`, not separate repos | Personal demo with one consumer (interviewer); monorepo simpler workflow |
| 2026-04-29 | HTTPS + PAT for git auth, NOT SSH for git | Owner preference; PAT cached in macOS keychain |
| 2026-04-29 | Repos public from day one | Owner preference for transparency and recruiter-readability |
| 2026-04-29 | Kit extension namespace: `com.sowthri.cdutwin` | Hyphens illegal in Python package names |
| 2026-04-30 | **PIVOT: Lambda Labs -> AWS** for cloud provider | Lambda's payment processor declined Saudi-issued card; Lambda doesn't accept PayPal; Lambda has no India region. AWS Mumbai is closer to Saudi than Lambda's US-only data centers, accepts the card, and has $120 in promotional credits. |
| 2026-04-30 | AWS region: ap-south-1 (Mumbai) | Closest available region with reliable g6 capacity; 120ms latency from Dammam (acceptable for SSH+VNC); Aramco runs many workloads from Mumbai (interview relevance) |
| 2026-04-30 | Instance type: g6.xlarge (L4 GPU) instead of g5.xlarge (A10G) | Newer Ada architecture, 20% cheaper, equivalent capability for Omniverse Kit. CSV analysis of all 37 GPU types in Mumbai confirmed this is the right size/cost point. |
| 2026-04-30 | AWS Budgets: $10 early warning + $100 monthly cap | Realistic for $0.97/hr x ~125-hour project usage; lower thresholds caused false-positive alerts |
| 2026-05-01 | JarvisLabs (https://jarvislabs.ai) chosen as Plan B if AWS denies | Indian provider, instant access, no quota gates, $0.44/hr L4 instances, accepts Indian payment methods. Hardware identical to AWS g6.xlarge. |
| 2026-05-05 | AWS GPU quota appeal granted via human Support chat (4 vCPUs in ap-south-1) | Brand-new account flagged for fraud prevention. First automated request denied; appeal via chat with detailed use case + GitHub URL succeeded. Esteban submitted appeal Friday; Richa confirmed approval Tuesday morning. Realistic time-to-approval for new-account GPU access: 2-4 business days, not 24 hours. |
| 2026-05-05 | EBS root volume sized at 200 GiB gp3, encrypted, delete-on-termination=Yes | Sized for full project: Kit (~30 GB) + Isaac Sim (~50 GB) + drivers + USD + buffer. Encryption is free at-rest data protection. Delete-on-terminate prevents orphaned billing. Instance store (250 GB NVMe) accepted as free ephemeral scratch. |

---

**Operator runbook end. Append-only.**
