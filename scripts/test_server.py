#!/usr/bin/env python3
"""
Web UI server for testing generators.

Usage:
    uv run python scripts/test_server.py
    # Open http://localhost:8000
"""

import subprocess
import sys
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.common import GENERATORS_PATH  # noqa: E402
from scripts.local_test import TestResult, list_generators, test_generator  # noqa: E402


@dataclass
class DownloadState:
    """State of the current download operation."""

    running: bool = False
    total: int = 0
    completed: int = 0
    current_repo: str = ""
    error: Optional[str] = None
    downloaded: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)


@dataclass
class RunState:
    """State of the current test run."""

    running: bool = False
    generators: list[str] = field(default_factory=list)
    current_index: int = 0
    current_generator: str = ""
    results: list[TestResult] = field(default_factory=list)
    error: Optional[str] = None


# Global state
state = RunState()
state_lock = threading.Lock()

download_state = DownloadState()
download_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    """Serve the main UI page."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/generators")
async def get_generators():
    """List available generators."""
    generators = list_generators()
    return {"generators": generators}


@app.post("/api/run")
async def run_tests(request: dict):
    """Start a test run."""
    global state

    with state_lock:
        if state.running:
            return JSONResponse(
                status_code=400,
                content={"error": "A test run is already in progress"},
            )

        generators = request.get("generators", [])
        num_samples = request.get("num_samples", 3)
        seed = request.get("seed")

        if not generators:
            return JSONResponse(
                status_code=400,
                content={"error": "No generators selected"},
            )

        state = RunState(
            running=True,
            generators=generators,
            current_index=0,
            current_generator=generators[0] if generators else "",
            results=[],
        )

    # Run tests in background thread
    thread = threading.Thread(
        target=_run_tests_thread,
        args=(generators, num_samples, seed),
        daemon=True,
    )
    thread.start()

    return {"status": "started", "total": len(generators)}


def _run_tests_thread(generators: list[str], num_samples: int, seed: Optional[int]):
    """Background thread to run tests."""
    global state

    for i, gen in enumerate(generators):
        with state_lock:
            state.current_index = i
            state.current_generator = gen

        try:
            result = test_generator(
                generator=gen,
                num_samples=num_samples,
                seed=seed,
                keep_output=False,
            )
        except Exception as e:
            result = TestResult(
                generator=gen,
                success=False,
                num_samples_requested=num_samples,
                num_samples_generated=0,
                duration_seconds=0,
                samples_per_second=0,
                peak_memory_mb=0,
                error=str(e),
            )

        with state_lock:
            state.results.append(result)

    with state_lock:
        state.running = False
        state.current_generator = ""


@app.get("/api/status")
async def get_status():
    """Get current run status."""
    with state_lock:
        return {
            "running": state.running,
            "total": len(state.generators),
            "completed": len(state.results),
            "current_index": state.current_index,
            "current_generator": state.current_generator,
            "progress": f"{len(state.results)}/{len(state.generators)}",
        }


@app.get("/api/results")
async def get_results():
    """Get test results."""
    with state_lock:
        results = [r.to_dict() for r in state.results]
        total = len(state.generators)
        passed = sum(1 for r in state.results if r.success)

        return {
            "results": results,
            "summary": {
                "total": total,
                "passed": passed,
                "failed": total - passed if not state.running else len(state.results) - passed,
                "running": state.running,
            },
        }


@app.post("/api/stop")
async def stop_tests():
    """Stop the current test run (note: cannot stop mid-generator)."""
    global state
    with state_lock:
        if state.running:
            state.generators = state.generators[: state.current_index + 1]
        return {"status": "stopping"}


@app.get("/api/remote-repos")
async def list_remote_repos():
    """List available repos from GitHub with local status."""
    try:
        # Check if gh is installed
        result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            return JSONResponse(
                status_code=500,
                content={"error": "GitHub CLI (gh) is not installed"},
            )

        # List repos from vm-dataset org
        result = subprocess.run(
            ["gh", "repo", "list", "vm-dataset", "--limit", "300", "--json", "name", "-q", ".[].name"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to list repos: {result.stderr}"},
            )

        # Get all repos with latest commit SHA from GitHub
        all_repos = result.stdout.strip().split("\n")
        repos = sorted([r for r in all_repos if r.strip()])

        # Get latest commit for each repo from GitHub API (batch query)
        result = subprocess.run(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"""query={{
                {"".join(f'r{i}: repository(owner:"vm-dataset", name:"{repo}") {{ defaultBranchRef {{ target {{ oid }} }} }} ' for i, repo in enumerate(repos))}
            }}""",
            ],
            capture_output=True,
            text=True,
        )

        remote_commits = {}
        if result.returncode == 0:
            import json

            try:
                data = json.loads(result.stdout)
                for i, repo in enumerate(repos):
                    ref = data.get("data", {}).get(f"r{i}", {}).get("defaultBranchRef")
                    if ref:
                        remote_commits[repo] = ref["target"]["oid"]
            except Exception:
                pass

        # Check local repos
        generators_path = Path(GENERATORS_PATH)
        repo_status = []
        for repo in repos:
            repo_path = generators_path / repo
            status = {"name": repo, "downloaded": False, "up_to_date": None}

            if repo_path.exists():
                status["downloaded"] = True
                # Get local HEAD commit
                try:
                    local = subprocess.run(
                        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if local.returncode == 0 and repo in remote_commits:
                        local_sha = local.stdout.strip()
                        remote_sha = remote_commits[repo]
                        status["up_to_date"] = local_sha == remote_sha
                except Exception:
                    pass

            repo_status.append(status)

        return {"repos": repo_status}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.post("/api/download-repos")
async def download_repos(request: dict):
    """Start downloading selected generator repos from GitHub."""
    global download_state

    repos = request.get("repos", [])
    if not repos:
        return JSONResponse(
            status_code=400,
            content={"error": "No repos selected"},
        )

    with download_lock:
        if download_state.running:
            return JSONResponse(
                status_code=400,
                content={"error": "Download already in progress"},
            )

        download_state = DownloadState(running=True, total=len(repos))

    # Run download in background thread
    thread = threading.Thread(target=_download_repos_thread, args=(repos,), daemon=True)
    thread.start()

    return {"status": "started", "total": len(repos)}


def _download_repos_thread(repos: list[str]):
    """Background thread to download repos."""
    global download_state

    try:
        # Create generators directory
        generators_path = Path(GENERATORS_PATH)
        generators_path.mkdir(parents=True, exist_ok=True)

        for i, repo in enumerate(repos):
            with download_lock:
                download_state.current_repo = repo
                download_state.completed = i

            repo_path = generators_path / repo

            if repo_path.exists():
                # Update existing repo
                result = subprocess.run(
                    ["git", "-C", str(repo_path), "pull", "--quiet"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    with download_lock:
                        download_state.updated.append(repo)
            else:
                # Clone new repo
                result = subprocess.run(
                    ["gh", "repo", "clone", f"vm-dataset/{repo}", str(repo_path), "--", "--depth", "1", "--quiet"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    with download_lock:
                        download_state.downloaded.append(repo)

        with download_lock:
            download_state.completed = len(repos)
            download_state.current_repo = ""
            download_state.running = False

    except Exception as e:
        with download_lock:
            download_state.error = str(e)
            download_state.running = False


@app.get("/api/download-status")
async def get_download_status():
    """Get current download status."""
    with download_lock:
        return {
            "running": download_state.running,
            "total": download_state.total,
            "completed": download_state.completed,
            "current_repo": download_state.current_repo,
            "error": download_state.error,
            "downloaded_count": len(download_state.downloaded),
            "updated_count": len(download_state.updated),
        }


if __name__ == "__main__":
    print("Starting Generator Test Server...")
    print("Open http://localhost:8000 in your browser")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
