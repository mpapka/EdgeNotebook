"""labHelpers.py - shared toolkit for the Edge Computing hands-on notebooks.

Every lab notebook imports this once near the top:

    from labHelpers import *

It provides four things:

1. Pretty output   - showFile / showScriptCard / showEnvCard / showNote and
                     rich tables for docker (dockerVersions, dockerPs, dockerLogs).
2. Lab setup       - setupLab() derives your unique PORT(s) from the digits in
                     your username, exports them to the notebook environment,
                     and writes labEnv.sh so Jupyter-terminal scripts agree
                     with the notebook.
3. Preflight       - preflight() renders a pass/fail table of environment
                     checks before you start (docker daemon, compose, NVIDIA
                     runtime, commands, python packages...).
4. Checkpoints     - checkpoint() verifies your work after each part of a lab
                     and gives targeted feedback: what passed, what failed,
                     how to fix it, and where to read more. labSummary()
                     shows everything you have passed so far.

The module is self-healing: it installs its own display dependencies (rich,
pygments) on first import if they are missing.
"""

# --------------------------------------------------------------------------
# Dependencies
# --------------------------------------------------------------------------

def ensureDependencies(packageNames):
    """Import each package, pip-installing it quietly first if missing."""
    import importlib, subprocess, sys
    for packageName in packageNames:
        moduleName = packageName.split("==")[0]
        try:
            importlib.import_module(moduleName)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", packageName],
                           check=True)


ensureDependencies(["rich", "pygments"])

import os
import re
import html as htmlLib
import json
import pathlib
import shutil
import socket
import subprocess
import urllib.request
from pathlib import Path

from IPython.display import HTML, display
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

richConsole = Console(force_jupyter=True)   # emit HTML inside Jupyter, always

fontStack = ("'Fira Code','JetBrains Mono',SFMono-Regular,Menlo,"
             "Consolas,'Liberation Mono',monospace")


# --------------------------------------------------------------------------
# Pretty output - cards and code display
# --------------------------------------------------------------------------

def styleBackground(styleName):
    """Background color a Pygments style is designed to sit on."""
    return HtmlFormatter(style=styleName).style.background_color or "#272822"


def contrastForeground(backgroundColor):
    """A text color that stays readable on backgroundColor, so plain
    untokenized text never inherits the host editor's default and vanishes."""
    hexPart = backgroundColor.lstrip("#")
    red, green, blue = int(hexPart[0:2], 16), int(hexPart[2:4], 16), int(hexPart[4:6], 16)
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    return "#1a1a1a" if luminance > 140 else "#f5f5f5"


def highlightScript(scriptText, language="bash", style="monokai"):
    """Return highlighted <span>s only (nowrap) so our container controls layout."""
    formatter = HtmlFormatter(style=style, noclasses=True, nowrap=True)
    try:
        lexer = get_lexer_by_name(language)
    except Exception:
        lexer = get_lexer_by_name("text")
    return highlight(scriptText, lexer, formatter).rstrip("\n")


def showScriptCard(scriptText, title, language="bash", envVars=None, style="monokai"):
    """Render any script/snippet as a colored, monospaced card with env chips."""
    envVars = envVars or {}
    backgroundColor = styleBackground(style)
    foregroundColor = contrastForeground(backgroundColor)
    highlightedBody = highlightScript(scriptText, language=language, style=style)

    def buildChip(chipKey, chipValue):
        return (
            f'<span style="background:#2d333b;color:#adbac7;padding:2px 9px;'
            f'border-radius:6px;font-size:12px;white-space:nowrap;">'
            f'{htmlLib.escape(str(chipKey))} '
            f'<b style="color:#6cb6ff;">{htmlLib.escape(str(chipValue))}</b></span>'
        )

    chipsHTML = "".join(buildChip(key, value) for key, value in envVars.items())
    codeHTML = (
        f'<pre style="margin:0;background:{backgroundColor};color:{foregroundColor};'
        f'font-family:{fontStack};font-size:13px;line-height:1.55;'
        f'white-space:pre;overflow-x:auto;">{highlightedBody}</pre>'
    )
    cardHTML = f"""
    <div style="max-width:820px;border-radius:10px;overflow:hidden;
                font-family:{fontStack};box-shadow:0 1px 8px rgba(0,0,0,.28);">
      <div style="background:#1f2430;color:#e6e6e6;padding:10px 14px;
                  display:flex;align-items:center;gap:10px;">
        <span style="font-weight:700;letter-spacing:.3px;">{htmlLib.escape(title)}</span>
        <span style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap;">{chipsHTML}</span>
      </div>
      <div style="background:{backgroundColor};padding:10px 14px;overflow-x:auto;">{codeHTML}</div>
    </div>
    """
    display(HTML(cardHTML))


def showEnvCard(scriptText, title="labEnv.sh", envVars=None):
    """Common case: a shell env file rendered as a bash card."""
    showScriptCard(scriptText, title=title, language="bash", envVars=envVars)


extensionLanguage = {
    ".py": "python", ".sh": "bash", ".yaml": "yaml", ".yml": "yaml",
    ".txt": "text", ".json": "json", ".md": "markdown", ".conf": "text",
    ".csv": "text", ".jsonl": "json", ".html": "html", ".flux": "text",
    "dockerfile": "docker",
}


def showFile(filePath, language=None, title=None, style="monokai", maxLines=None):
    """Read a file from disk and show it as a syntax-highlighted card.

    language is inferred from the extension (or a 'Dockerfile' name) when omitted.
    maxLines truncates long files (a footer notes the truncation).
    """
    path = Path(filePath).expanduser()
    if not path.exists():
        showNote(f"File not found: {path}", kind="warn",
                 title="showFile")
        return
    fileText = path.read_text()
    if maxLines is not None:
        lines = fileText.splitlines()
        if len(lines) > maxLines:
            fileText = "\n".join(lines[:maxLines] + [f"... ({len(lines) - maxLines} more lines)"])
    if language is None:
        key = "dockerfile" if path.name.lower() == "dockerfile" else path.suffix.lower()
        language = extensionLanguage.get(key, "text")
    showScriptCard(fileText, title=title or path.name, language=language, style=style)


noteColors = {
    "info":    ("#0b3d91", "#e8f0fe", "#1a56db"),
    "ok":      ("#14532d", "#ecfdf5", "#059669"),
    "warn":    ("#7c2d12", "#fff7ed", "#d97706"),
    "error":   ("#7f1d1d", "#fef2f2", "#dc2626"),
    "tip":     ("#3b0764", "#faf5ff", "#7c3aed"),
}


def showNote(message, kind="info", title=None, link=None, linkText=None):
    """A colored callout box for feedback: info, ok, warn, error, or tip.

    message may contain simple HTML (e.g. <code>, <b>). link adds a
    'Read more' anchor the student can click.
    """
    textColor, backgroundColor, borderColor = noteColors.get(kind, noteColors["info"])
    icon = {"info": "&#9432;", "ok": "&#10003;", "warn": "&#9888;",
            "error": "&#10007;", "tip": "&#128161;"}.get(kind, "&#9432;")
    titleHTML = (f'<div style="font-weight:700;margin-bottom:4px;">{htmlLib.escape(title)}</div>'
                 if title else "")
    linkHTML = ""
    if link:
        linkHTML = (f'<div style="margin-top:6px;"><a href="{htmlLib.escape(link)}" '
                    f'target="_blank" style="color:{borderColor};font-weight:600;">'
                    f'{htmlLib.escape(linkText or "Read more")} &#8599;</a></div>')
    display(HTML(f"""
    <div style="max-width:820px;border-left:4px solid {borderColor};
                background:{backgroundColor};color:{textColor};
                padding:10px 14px;border-radius:6px;margin:4px 0;
                font-family:system-ui,-apple-system,sans-serif;font-size:14px;
                line-height:1.5;">
      <span style="font-weight:700;">{icon}</span> {titleHTML}{message}{linkHTML}
    </div>
    """))


# --------------------------------------------------------------------------
# Shell helpers
# --------------------------------------------------------------------------

def runShell(command, timeoutSeconds=60):
    """Run a command (list or shell string), capturing stdout+stderr and the
    return code. Never raises."""
    useShell = isinstance(command, str)
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                shell=useShell, timeout=timeoutSeconds)
        return result.stdout + result.stderr, result.returncode
    except FileNotFoundError:
        name = command if useShell else command[0]
        return f"{name}: not found on this machine", 127
    except subprocess.TimeoutExpired:
        return f"timed out after {timeoutSeconds}s", 124


# --------------------------------------------------------------------------
# Docker display helpers
# --------------------------------------------------------------------------

def dockerVersions(runHelloWorld=True):
    """Show docker + compose versions as a panel, optionally verify hello-world."""
    dockerOut, _ = runShell(["docker", "--version"])
    composeOut, _ = runShell(["docker", "compose", "version"])
    versionLines = dockerOut.strip().splitlines() + composeOut.strip().splitlines()
    richConsole.print(Panel("\n".join(versionLines) or "docker not available",
                            title="docker versions", box=box.ROUNDED))
    if not runHelloWorld:
        return
    helloOut, _ = runShell(["docker", "run", "--rm", "hello-world"], timeoutSeconds=120)
    ranOk = "Hello from Docker" in helloOut
    richConsole.print(Panel(
        "[green]hello-world ran successfully[/]" if ranOk
        else "[yellow]hello-world did not confirm - output below[/]\n" + helloOut[:400],
        title="[green]ok[/]" if ranOk else "[yellow]check[/]", box=box.ROUNDED))


def dockerPs(namePattern=None, showAll=False):
    """Render `docker ps` (running containers) as a rich table."""
    fields = "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
    commandList = ["docker", "ps", "--format", fields] + (["-a"] if showAll else [])
    out, code = runShell(commandList)
    rows = [line.split("\t") for line in out.strip().splitlines() if line.strip()]
    if namePattern:
        rows = [row for row in rows if namePattern in row[0]]
    if not rows:
        richConsole.print(Panel("no running containers" if code == 0 else out.strip(),
                                title="docker ps", box=box.ROUNDED))
        return
    table = Table(title="containers" if showAll else "running containers",
                  box=box.SIMPLE_HEAVY, row_styles=["", "on grey11"])
    table.add_column("name", style="cyan", overflow="fold")
    table.add_column("image", overflow="fold")
    table.add_column("status")
    table.add_column("ports", overflow="fold")
    for row in rows:
        row = (row + ["", "", "", ""])[:4]
        statusColor = "green" if row[2].lower().startswith("up") else "yellow"
        table.add_row(row[0], row[1], f"[{statusColor}]{row[2]}[/]", row[3])
    richConsole.print(table)


def dockerLogs(container, tail=20):
    """Show the tail of a container's logs in a panel."""
    out, _ = runShell(["docker", "logs", "--tail", str(tail), container])
    richConsole.print(Panel(out.strip() or "(no output yet)",
                            title=f"logs - {container}", box=box.ROUNDED))


# --------------------------------------------------------------------------
# Lab setup - identity, ports, labEnv.sh
# --------------------------------------------------------------------------

def studentNumber(userName=None):
    """First run of digits in the username, or 1 if there is none."""
    userName = userName or os.environ.get("USER", "student01")
    match = re.search(r"\d+", userName)
    return int(match.group()) if match else 1


def setupLab(labName, ports=None, portOverrides=None, extraEnv=None):
    """Set up this lab's identity, unique ports, and shared labEnv.sh.

    labName        folder name under ~ (e.g. "telemetryLab"); labEnv.sh
                   is written there so terminal scripts can `source` it.
    ports          dict of ENV_NAME -> basePort. Each becomes basePort + the
                   digits in your username, e.g. {"PORT": 5000} gives
                   student07 -> 5007. Multiple entries give multiple unique
                   ports (e.g. {"INFLUX_PORT": 8000, "GRAFANA_PORT": 3000}).
    portOverrides  dict of ENV_NAME -> int to force specific ports.
    extraEnv       dict of additional static env values (e.g. NVIDIA_IMAGE).

    Everything is exported to os.environ (so `!` cells see it) and written to
    ~/<labName>/labEnv.sh (so Jupyter-terminal scripts see it too).
    Returns the dict of resolved values.
    """
    ports = ports or {"PORT": 5000}
    portOverrides = portOverrides or {}
    extraEnv = extraEnv or {}

    if not os.environ.get("USER"):
        os.environ["USER"] = "student01"
    userName = os.environ["USER"]
    number = studentNumber(userName)

    resolved = {"USER": userName}
    envLines = [
        f"# {labName} shared environment - sourced by every helper script.",
        "# Ports are derived from the digits in your username "
        f"(e.g. student07 -> base+7).",
        'studentNum=$(echo "$USER" | grep -oE \'[0-9]+\' | head -n1)',
    ]
    for envName, basePort in ports.items():
        value = int(portOverrides.get(envName, basePort + number))
        os.environ[envName] = str(value)
        resolved[envName] = value
        if envName in portOverrides:
            envLines.append(f"export {envName}={value}")
        else:
            envLines.append(f"export {envName}=$(({basePort} + 10#${{studentNum:-1}}))")
    for envName, envValue in extraEnv.items():
        os.environ[envName] = str(envValue)
        resolved[envName] = envValue
        envLines.append(f"export {envName}={envValue}")

    labDir = pathlib.Path.home() / labName
    labDir.mkdir(parents=True, exist_ok=True)
    envPath = labDir / "labEnv.sh"
    envPath.write_text("\n".join(envLines) + "\n")
    resolved["labDir"] = str(labDir)
    resolved["labEnv"] = str(envPath)

    chipValues = {name: value for name, value in resolved.items()
                  if name not in ("labDir", "labEnv")}
    showEnvCard(envPath.read_text(), title=f"{labName}/labEnv.sh", envVars=chipValues)
    return resolved


# --------------------------------------------------------------------------
# Check predicates - each factory returns fn() -> (ok: bool, detail: str)
# --------------------------------------------------------------------------

def fileExists(filePath):
    def probe():
        path = Path(filePath).expanduser()
        return path.is_file(), str(path) if path.is_file() else f"missing: {path}"
    return probe


def dirExists(dirPath):
    def probe():
        path = Path(dirPath).expanduser()
        return path.is_dir(), str(path) if path.is_dir() else f"missing: {path}"
    return probe


def fileContains(filePath, text):
    def probe():
        path = Path(filePath).expanduser()
        if not path.is_file():
            return False, f"missing: {path}"
        found = text in path.read_text(errors="replace")
        return found, f"'{text}' {'found' if found else 'not found'} in {path.name}"
    return probe


def fileNonEmpty(filePath, minLines=1):
    def probe():
        path = Path(filePath).expanduser()
        if not path.is_file():
            return False, f"missing: {path}"
        lineCount = sum(1 for _ in path.open(errors="replace"))
        return lineCount >= minLines, f"{path.name}: {lineCount} line(s)"
    return probe


def commandSucceeds(command, timeoutSeconds=30):
    def probe():
        out, code = runShell(command, timeoutSeconds=timeoutSeconds)
        display = command if isinstance(command, str) else " ".join(command)
        return code == 0, (out.strip().splitlines() or [display])[0][:120]
    return probe


def outputContains(command, text, timeoutSeconds=30):
    def probe():
        out, _ = runShell(command, timeoutSeconds=timeoutSeconds)
        found = text in out
        return found, f"'{text}' {'found' if found else 'not found'} in output"
    return probe


def commandOnPath(commandName):
    def probe():
        location = shutil.which(commandName)
        return bool(location), location or f"{commandName} not on PATH"
    return probe


def pythonImportable(moduleName):
    def probe():
        import importlib
        try:
            importlib.import_module(moduleName)
            return True, f"import {moduleName} ok"
        except ImportError as importError:
            return False, str(importError)[:120]
    return probe


def envVarSet(envName):
    def probe():
        value = os.environ.get(envName, "")
        return bool(value), f"{envName}={value}" if value else f"{envName} is not set"
    return probe


def dockerDaemonUp():
    def probe():
        out, code = runShell(["docker", "info", "--format", "{{.ServerVersion}}"])
        ok = code == 0 and out.strip() and "not found" not in out and "Cannot connect" not in out
        return bool(ok), (f"server {out.strip()}" if ok else "daemon not reachable")
    return probe


def composeAvailable():
    def probe():
        out, code = runShell(["docker", "compose", "version", "--short"])
        ok = code == 0 and out.strip() and "not found" not in out
        return bool(ok), out.strip()[:60] if ok else "docker compose not found"
    return probe


def nvidiaRuntimeAvailable():
    def probe():
        out, _ = runShell(["docker", "info", "--format", "{{.Runtimes}}"])
        ok = "nvidia" in out
        return ok, "nvidia runtime available" if ok else "nvidia runtime not found"
    return probe


def containerRunning(name):
    def probe():
        out, _ = runShell(["docker", "ps", "--format", "{{.Names}}"])
        names = out.strip().splitlines()
        ok = name in names
        return ok, f"{name} is {'running' if ok else 'NOT running'}"
    return probe


def imageExists(name):
    def probe():
        out, _ = runShell(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"])
        ok = any(line.startswith(name) for line in out.strip().splitlines())
        return ok, f"image {name} {'present' if ok else 'not found'}"
    return probe


def volumeExists(name):
    def probe():
        out, _ = runShell(["docker", "volume", "ls", "--format", "{{.Name}}"])
        ok = name in out.strip().splitlines()
        return ok, f"volume {name} {'present' if ok else 'not found'}"
    return probe


def portListening(port, host="127.0.0.1"):
    def probe():
        probeSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probeSocket.settimeout(2)
        try:
            openOk = probeSocket.connect_ex((host, int(port))) == 0
        finally:
            probeSocket.close()
        return openOk, f"port {port} {'accepting connections' if openOk else 'not reachable'}"
    return probe


def httpOk(url, expectText=None, timeoutSeconds=5):
    def probe():
        try:
            with urllib.request.urlopen(url, timeout=timeoutSeconds) as response:
                body = response.read(65536).decode(errors="replace")
                if expectText is not None and expectText not in body:
                    return False, f"{url} answered but '{expectText}' not in body"
                return True, f"{url} -> HTTP {response.status}"
        except Exception as fetchError:
            return False, f"{url} -> {str(fetchError)[:100]}"
    return probe


def gitRepoAt(dirPath, minCommits=1):
    def probe():
        path = Path(dirPath).expanduser()
        if not (path / ".git").exists():
            return False, f"no git repository at {path}"
        out, code = runShell(["git", "-C", str(path), "rev-list", "--count", "HEAD"])
        if code != 0:
            return False, "repository exists but has no commits yet"
        commitCount = int(out.strip() or 0)
        return commitCount >= minCommits, f"{commitCount} commit(s)"
    return probe


def jsonLinesValid(filePath, requiredKeys=None, minRecords=1):
    def probe():
        path = Path(filePath).expanduser()
        if not path.is_file():
            return False, f"missing: {path}"
        records, badLines = 0, 0
        for line in path.open(errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if requiredKeys and not all(key in record for key in requiredKeys):
                    badLines += 1
                else:
                    records += 1
            except json.JSONDecodeError:
                badLines += 1
        ok = records >= minRecords and badLines == 0
        detail = f"{records} valid record(s)" + (f", {badLines} bad line(s)" if badLines else "")
        return ok, detail
    return probe


# --------------------------------------------------------------------------
# Preflight and checkpoint frameworks
# --------------------------------------------------------------------------

def check(label, probe, hint=None, link=None, linkText=None):
    """Bundle one verification: a label, a probe fn from the factories above
    (or any fn returning bool or (bool, detail)), a fix-it hint shown on
    failure, and an optional documentation link."""
    return {"label": label, "probe": probe, "hint": hint,
            "link": link, "linkText": linkText}


def runProbe(probe):
    """Run a probe safely; normalize the result to (ok, detail)."""
    try:
        result = probe()
    except Exception as probeError:
        return False, f"check crashed: {str(probeError)[:100]}"
    if isinstance(result, tuple):
        return bool(result[0]), str(result[1])
    return bool(result), ""


checkpointResults = {}   # title -> {"passed": int, "total": int}


def renderCheckTable(title, checks, infoRows=None):
    """Shared renderer for preflight and checkpoint tables. Returns failures."""
    table = Table(title=title, box=box.SIMPLE_HEAVY)
    table.add_column("check", style="cyan", overflow="fold")
    table.add_column("result")
    table.add_column("detail", overflow="fold")
    failures = []
    for item in checks:
        ok, detail = runProbe(item["probe"])
        mark = "[green]✓ ok[/]" if ok else "[red]✗ failed[/]"
        table.add_row(item["label"], mark, detail)
        if not ok:
            failures.append(item)
    for infoLabel, infoValue in (infoRows or []):
        table.add_row(infoLabel, "[cyan]info[/]", str(infoValue))
    richConsole.print(table)
    return failures


def preflight(checks, infoRows=None, title="preflight - environment"):
    """Run environment checks before starting a lab. checks is a list built
    with check(...). infoRows is a list of (label, value) informational rows
    (e.g. your USER and PORT)."""
    failures = renderCheckTable(title, checks, infoRows=infoRows)
    if failures:
        for failed in failures:
            showNote(failed.get("hint") or "This must be fixed before continuing.",
                     kind="error", title=f"Fix first: {failed['label']}",
                     link=failed.get("link"), linkText=failed.get("linkText"))
    else:
        showNote("Environment looks good - continue with the lab.", kind="ok")
    return len(failures) == 0


def checkpoint(title, checks, successNote=None, docLink=None, docLinkText=None):
    """Verify a completed lab part and give targeted feedback.

    title        e.g. "Part 4 - sensor container built"
    checks       list built with check(label, probe, hint=..., link=...)
    successNote  extra message shown when everything passes
    docLink      'read more' link shown with the success note
    """
    failures = renderCheckTable(f"checkpoint - {title}", checks)
    passedCount = len(checks) - len(failures)
    checkpointResults[title] = {"passed": passedCount, "total": len(checks)}
    if failures:
        for failed in failures:
            showNote(failed.get("hint") or "Re-run the cells above for this part.",
                     kind="warn", title=f"How to fix: {failed['label']}",
                     link=failed.get("link"), linkText=failed.get("linkText"))
        showNote(f"{passedCount}/{len(checks)} checks passed. Fix the items above, "
                 "then re-run this checkpoint cell - it is safe to run any number of times.",
                 kind="info")
    else:
        showNote(successNote or "All checks passed - move on to the next part.",
                 kind="ok", title=f"{title}: complete",
                 link=docLink, linkText=docLinkText)
    return len(failures) == 0


def labSummary(labTitle="Lab progress"):
    """Scorecard of every checkpoint run so far in this kernel session."""
    if not checkpointResults:
        showNote("No checkpoints have been run yet in this session.", kind="info")
        return
    table = Table(title=labTitle, box=box.SIMPLE_HEAVY)
    table.add_column("checkpoint", style="cyan", overflow="fold")
    table.add_column("score")
    table.add_column("status")
    allPassed = True
    for title, result in checkpointResults.items():
        passed, total = result["passed"], result["total"]
        ok = passed == total
        allPassed = allPassed and ok
        table.add_row(title, f"{passed}/{total}",
                      "[green]✓ complete[/]" if ok else "[yellow]⚠ incomplete[/]")
    richConsole.print(table)
    if allPassed:
        showNote("Every checkpoint passed. Nice work - you are done with this lab.",
                 kind="ok")
    else:
        showNote("Some checkpoints are incomplete. Scroll up, fix the failing parts, "
                 "and re-run their checkpoint cells.", kind="warn")


print("labHelpers ready - setupLab, preflight, checkpoint, labSummary, "
      "showFile, showScriptCard, showEnvCard, showNote, "
      "dockerVersions, dockerPs, dockerLogs + check predicates")
