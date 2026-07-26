# Testing these notebooks (for the Hermes test agents)

How to execute the labs so results reflect real student experience, and how to run
many students at once without confusing infrastructure limits for notebook bugs.

## Golden rule: run like a student

Execute each notebook **top to bottom in one persistent kernel** (nbclient /
papermill / `jupyter nbconvert --execute`), never cell-by-cell in isolation and
never a hand-picked subset.

Why it matters: cells build on each other. Setup cells set the working directory
(`%cd`, `os.chdir`), create folders (`mkdir`, `os.makedirs`), and define variables.
Later cells rely on that state. **Skipping a setup cell produces a false failure** in
a later cell (a `FileNotFoundError` on a path the skipped cell would have created, or
a `NameError` on a variable a skipped cell would have defined). Several "failures" in
past reports were exactly this, not real bugs.

Specifics:
- **Preserve kernel working directory across cells.** A `%cd`/`os.chdir` in one cell
  must still be in effect for the next. If your runner resets cwd per cell, that is a
  harness bug, not a notebook bug.
- **Respect the `raises-exception` cell tag.** A cell tagged `raises-exception`
  raises **on purpose** (e.g. a `NameError` demo the next cells then fix). Expect the
  exception; do not count it as a failure. This is the standard nbclient tag.
- **Give cells generous timeouts.** Some cells pull images, build containers, or
  download models (10-35s is normal; allow at least 120s per cell).
- **Distinguish notebook bug vs missing service.** Many cells need a running service
  the student starts earlier (InfluxDB, Grafana, a docker/podman container) or the
  GPU. If the service is not up, that is an environment/ordering issue, not a broken
  notebook. Report it separately.

## What "pass" means

These labs self-grade with `checkpoint()` / `check()` calls. **The checkpoints are
the source of truth.** A lab is GREEN when its checkpoints pass, not merely when no
cell raised. Report checkpoint results per part, and quote the failing `check` label
(not just the cell number) when one fails.

## Running as multiple students at once

Each student is fully isolated: their own container, their own home (`~`), their own
per-user ports and container names. Student A cannot break student B's files. But a
few things are **shared or rate-limited** — those are what to watch under load:

1. **Warm the hub before the fleet.** The first spawn after a reboot is slow/fragile
   (large image, cold caches, boot-time state). Spawn **one** student and confirm it
   comes up, then launch the rest — the image is hot for everyone after that. Do
   **not** kick off a mass concurrent spawn immediately after a reboot.
2. **Stagger spawns.** The hub caps concurrent spawns (`concurrent_spawn_limit`), so
   extra spawns queue; add a few seconds between launches so 20 students do not all
   read the multi-GB image at the same instant.
3. **Use distinct accounts with distinct UIDs.** Each lab derives its ports and
   identity from the student's **UID** (so real rosters do not collide). Test accounts
   must have different UIDs, or two students will land on the same port. Verify with
   `id <user>`.
4. **The GPU is shared and not memory-capped.** One GB10, all students. GPU-heavy
   labs (lab05 YOLO, lab06 benchmarking) run real inference; many at once can exhaust
   GPU memory. For a first fleet run, cap the number of *simultaneous* GPU labs and
   watch `nvidia-smi` (memory + utilization). CPU RAM is capped per container
   (`mem_limit`), GPU memory is not.
5. **Host disk / image pulls are shared.** Student containers run on each student's
   own rootless Podman, but they pull from the same host image store and write to the
   same disk. Concurrent first-time pulls/builds contend; expect the first fleet run
   to be slower than steady state.

## Reporting under concurrency

- Report **per student** and an **aggregate**. A real notebook bug fails the **same
  cell deterministically for every student**; a concurrency/resource issue fails
  **only under load** or for a subset. Label which is which — do not file a
  load-induced timeout as a notebook bug.
- Include: account, UID, spawn time, per-notebook verdict, failing `check` labels,
  and (for GPU labs) peak `nvidia-smi` memory during the run.
