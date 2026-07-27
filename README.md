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

## Lab order and prerequisites

The numbered notebooks **`lab00Docker` … `lab09Fleet`** are the core course sequence and are
meant to be done in order.

Four optional on-ramps come before them: **AA** Linux command basics, **BB** Python and Jupyter,
**CC** synthetic experiment data, **DD** research-quality figures. These are **independent** — do
any subset, in any order, or skip them. None requires another: DD uses the `experiment.csv` that CC
writes to `~/experimentLab` *if it is there*, and otherwise generates a stand-in dataset, so you can
run DD without CC (or without AA/BB). Any real "run X first" dependency a lab has will be stated
here in this README, not assumed inside the notebook.

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
- `labHelpers.py` — shared toolkit imported by every lab: `setupLab` (per-student identity + ports +
  `labEnv.sh`), `preflight`/`checkpoint` graded checks, `deviceAddress()`, `deviceName()`, and Docker/
  Podman/GPU probes.

The DGX-side build, provisioning (`roster.sh`), and the one-time adaptation scripts live in the
[JetsonMachineAdmin](https://github.com/mpapka/JetsonMachineAdmin) repo (`dgxhub/`,
`DGX-SPARK-JUPYTERHUB-BUILD.md`).
