# EdgeNotebook

Hands-on lab series for **CS 494 — Edge Computing Systems**. Each lab is a Jupyter notebook that
teaches a slice of the edge stack — Docker/Podman, system architecture, telemetry, time-series
databases, on-device AI (YOLO), benchmarking, optimization/security, networking, and fleet
management — by having students *build and run real containers and services on a GPU edge box*.

## How students use it

The labs are launched from the class JupyterHub, **not** cloned by hand. Each **Launch** button on
the course site is an [nbgitpuller](https://nbgitpuller.readthedocs.io/) link that pulls the
**`release`** branch (see *Releasing labs* below) into the student's `~/EdgeNotebook` and opens the
lab. A student's next Launch click fast-forwards their copy to the latest `release` — so fixes reach
everyone automatically, and students only ever have the notebooks that have been released.

Students sign in to the Hub with an instructor-issued account and password (they don't clone, push,
or manage credentials themselves).

## Releasing labs (weekly rollout, instructor)

Two branches:

- **`main`** — where you develop and test (all notebooks + these docs + `publish.sh`). The
  Hermes test agents clone `main`. Students never see it.
- **`release`** — what students pull. It holds only `labHelpers.py` plus the notebooks that have
  been released so far. Orphan history, so the docs never appear even in `git log`.

Release one or more labs with a single command:

```bash
./publish.sh lab01              # accepts lab01, lab01DevTooling, or a full filename
./publish.sh lab01 lab02        # several at once
./publish.sh --list             # show what students currently have
./publish.sh --unpublish lab01  # withdraw a lab you released too early
```

`publish.sh` does both halves of a rollout: it copies the notebook(s) + current `labHelpers.py`
onto `release` **and** flips `published: true` on the matching course-site lab card so the Labs
page starts listing that lab (the site auto-deploys on push). Until a lab is published, students
cannot pull it and its card is not built at all. Develop freely on `main`; ship week by week.

Notes:
- A dedicated worktree, `../EdgeNotebook-release`, is created automatically so your `main`
  checkout is never disturbed.
- The course-site checkout is assumed at `../UIC_Course_Website`; override with `COURSE_SITE_DIR`.
  If the site is absent, the card step is skipped and only the notebook is released.
- To fix a released lab, just re-run `./publish.sh <lab>` — it re-syncs that notebook from `main`.
- To withdraw one, `./publish.sh --unpublish <lab>` removes it from `release` and sets the site
  card back to `published: false`. It resolves the name against `release` rather than `main`, so
  you can only withdraw something students actually have, and it refuses to remove `labHelpers.py`.
  Students keep any copy already pulled — nbgitpuller does not delete their files — so this hides
  the lab from newcomers rather than recalling it from everyone.
- Pushing the site does **not** deploy it. The Labs page changes only after the site is rebuilt
  and rsynced on the box; see `DEPLOY.md` in the course-site repo.

## Term-start rollout

Two independent halves. Confusing them is the usual mistake:

| | Controlled by | Effect |
|---|---|---|
| `release` branch | `publish.sh` / `--unpublish` | what a Launch **actually pulls** |
| site cards | same script, `published:` flag | what the Labs page **lists** |

A Launch pulls the **whole branch**, not one notebook — `urlpath` only picks which
file opens. So every notebook on `release` lands in the student's `~/EdgeNotebook`
no matter which cards are hidden. Hiding a card is cosmetic; removing it from
`release` is what controls access.

### 1. Open everything up for testing

```
./publish.sh lab00 lab01 lab02 lab03 lab04 lab05 lab06 lab07 lab08 lab09 \
             labAA labBB labCC labDD labEE
```

Then deploy (below). The Labs page lists all 15 and the tester can click through
them like a student.

Safe only while no one but the tester has an account. Otherwise use a
`branch=main` launch URL with `targetpath=EdgeNotebook-test`, which tests the
same path without touching what students pull.

### 2. Withdraw down to the term-start set

```
./publish.sh --unpublish lab00 lab01 lab02 lab03 lab04 lab05 lab06 lab07 \
                         lab08 lab09 labEE
./publish.sh --list        # expect: labAA labBB labCC labDD + labHelpers.py
```

Deploy again. Term starts with the four background notebooks visible; release
the numbered labs weekly as the course reaches them.

### 3. Only then create student accounts

The window that matters is a student's **first Launch**, not when their account
is made. Withdrawal never deletes files already pulled, so anyone who launched
while everything was open keeps all 15 permanently. Finish step 2 before anyone
new signs in.

### Deploying

Pushing updates GitHub only. The Labs page changes when the box rebuilds:

```
ssh papka@cs494.evl.uic.edu
cd /opt/cs494-site
git pull
bundle exec jekyll build
rsync -a --delete _site/ /var/www/cs494/
```

Run those at the box prompt rather than as one long `ssh '...'` line, which wraps
and breaks. `rsync` prints nothing on success.


## Lab order and prerequisites

The numbered notebooks **`lab00Docker` … `lab09Fleet`** are the core course sequence and are
meant to be done in order.

Four optional on-ramps come before them: **AA** Linux command basics, **BB** Python and Jupyter,
**CC** synthetic experiment data, **DD** research-quality figures. These are **independent** — do
any subset, in any order, or skip them. None requires another: DD uses the `experiment.csv` that CC
writes to `~/experimentLab` *if it is there*, and otherwise generates a stand-in dataset, so you can
run DD without CC (or without AA/BB). Any real "run X first" dependency a lab has will be stated
here in this README, not assumed inside the notebook.

One optional capstone comes **after** the core sequence: **EE** cross-device performance. It leans
on the method from CC, the figures from DD, and the benchmarking ideas from `lab06`, so it is best
done once those are behind you. Students write one portable `benchmark.py` (run with `uv`, so it
carries to any machine), measure this DGX and a second device, then merge the results and compare
compute, memory bandwidth, memory capacity, and sustained thermal behaviour. It ships a real DGX
Spark baseline so the comparison works even from a single machine.

## The runtime these labs target

The class box is an **NVIDIA DGX Spark (GB10)** running JupyterHub. The key design point: containers
students build run on **their own rootless Podman on the host**, driven from the notebook over a
bound socket — GPU-capable, isolated per student, no privilege. (`docker` in the labs is that
Podman.) The labs are written for this runtime:

- **GPU in containers** via `NVIDIA_VISIBLE_DEVICES` (rootless Podman ignores `--runtime nvidia`).
- **Port seam** — a container's published port lives on the *host*, so labs reach services via
  `deviceAddress()` / `$DEVICE_ADDR` (the host gateway), never the notebook's `localhost`.
- **Per-student uniqueness** — `USER` and each lab's ports derive from the student's **UID** (real
  NetIDs share digits and would collide); device identity is *queried* (`deviceName()` → hostname),
  not hardcoded.

## Portable to other edge hardware

These labs began on a Jetson and were adapted for the GB10. Where a tool differs by platform
(`tegrastats` vs `nvidia-smi dmon`, `/proc/device-tree` vs DMI, `nvpmodel` vs `nvidia-smi`), the
notebook runs the right one for the box **and** includes a **📟 On a Jetson** callout explaining the
equivalent — because knowing that edge fleets mix hardware is part of the course.

## Layout

- `lab00Docker` … `lab09Fleet` — the labs, in course order.
- `labAALinux`, `labBBPython`, `labCCDataCollection`, `labDDPlotting` — optional on-ramps (before
  the core sequence); `labEEPerformance` — optional cross-device capstone (after it).
- `Stories/` — one plain-language explainer per lab (`00.md` … `EE.md`, matching the lab codes):
  what the lab is really about and why it matters, with no code. Prose for reading before or
  instead of the notebook; `publish.sh` never sends `.md` files to `release`, so these stay
  instructor-side unless deliberately linked from the course site.
- `labHelpers.py` — shared toolkit imported by every lab: `setupLab` (per-student identity + ports +
  `labEnv.sh`), `preflight`/`checkpoint` graded checks, `deviceAddress()`, `deviceName()`, and Docker/
  Podman/GPU probes.

The DGX-side build, provisioning (`roster.sh`), and the one-time adaptation scripts live in the
[JetsonMachineAdmin](https://github.com/mpapka/JetsonMachineAdmin) repo (`dgxhub/`,
`DGX-SPARK-JUPYTERHUB-BUILD.md`).
