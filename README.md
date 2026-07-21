# EdgeNotebook

Hands-on lab series for **CS 494 — Edge Computing Systems**. Each lab is a Jupyter notebook that
teaches a slice of the edge stack — Docker/Podman, system architecture, telemetry, time-series
databases, on-device AI (YOLO), benchmarking, optimization/security, networking, and fleet
management — by having students *build and run real containers and services on a GPU edge box*.

## How students use it

The labs are launched from the class JupyterHub, **not** cloned by hand. Each **Launch** button on
the course site is an [nbgitpuller](https://nbgitpuller.readthedocs.io/) link that pulls this repo
into the student's `~/EdgeNotebook` and opens the lab. A student's next Launch click fast-forwards
their copy to the latest `main` — so fixes here reach everyone automatically.

Students sign in to the Hub with an instructor-issued account and password (they don't clone, push,
or manage credentials themselves).

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
