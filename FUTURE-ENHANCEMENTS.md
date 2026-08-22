# Future enhancements

Work we deliberately deferred, with enough context to pick it up cold. This file lives on `main`
only — `publish.sh` ships notebooks + `labHelpers.py`, so students never see it.

An entry belongs here when the lab is **correct and complete as it stands** but a better version
exists that we chose not to build yet — usually because it needs live testing on a spawned notebook,
or because the payoff is a nice-to-have. Bugs do not belong here; fix those.

---

## Lab 08 Part 5 · the real browser page for the WebSocket

**Status:** open. The lab is complete without it (2026-08-22, commit `04f3777`).

**What students do today.** They write `wsClient.html`, see it rendered in the notebook, and prove
server push with `wsLive.py` — one connection, ten seconds, the value rewriting the same line. The
step that used to say `scp thor:~/networkingLab/wsClient.html .` and "open it on your computer" is
gone: their WebSocket server runs inside *their* notebook container, nothing on the device publishes
`WS_PORT`, so no laptop browser can reach it. The notebook now explains that as the lesson.

**The enhancement.** Let the page actually run in the student's browser, reaching the socket through
the Hub: `wss://<hub>/user/<netid>/proxy/<WS_PORT>/`. jupyter-server-proxy does proxy websockets, and
the notebook image already allows the `/proxy/` form (`dgxhub/images/notebook/jupyter_server_config.py`
in JetsonMachineAdmin).

**Why it is not done.** The page must be served from the Hub origin to carry the auth cookie into the
proxy. Jupyter's `/files/` endpoint serves HTML under a `sandbox` CSP, which makes it a unique origin —
credentials are likely not sent, and the WS handshake 401s. That is a prediction, not a measurement.

**How to settle it** (needs a real spawn, ~30 min):

1. Spawn a notebook as a test student, start `runWSServer.sh` in a terminal.
2. Open `wsClient.html` through `/user/<netid>/files/networkingLab/wsClient.html` and, from that page,
   `new WebSocket("wss://" + location.host + location.pathname.replace(/files\/.*/, "proxy/<WS_PORT>/"))`.
3. Watch the browser console and `journalctl -u jupyterhub -f`. A 401/403 on the handshake confirms the
   cookie is not crossing the sandbox.
4. If it fails, the fallbacks worth trying, cheapest first: relax the CSP for `/files/` in the image's
   `jupyter_server_config.py`; or have `wsServer.py` serve the page itself on the same port so page and
   socket share an origin the proxy already forwards.

If it works, add it as a **bonus step** after the `wsLive.py` watch — do not replace that watch, which
is what makes the lab pass without a browser in the loop.

---

## Lab 04 Part 8 · recreate Grafana automatically when its `root_url` is stale

**Status:** open, low priority. Diagnostics landed 2026-08-22, commit `3db982d`.

Grafana's `GF_SERVER_ROOT_URL` bakes in the student's netid, device address and port at container
creation. Anything that changes those — a re-pulled notebook, a reassigned port, a different
default-route gateway after a network change — leaves a **healthy** Grafana that answers only on a
path the notebook no longer asks for, so its Hub link bounces off to `localhost:3000`.

Today `showDashboard()` detects exactly that and prints the `--force-recreate` command, and the Part 8
checkpoint fails with the same hint. The enhancement is to skip the manual step: have the Part 8 cell
compare the running container's `root_url` with the current one and recreate the service itself.

Deferred on purpose — a lab that silently recreates a student's container hides the mechanism this
part is teaching, and the volume-preserving recreate is a one-liner they can read. Revisit only if
students keep getting stuck on it.
