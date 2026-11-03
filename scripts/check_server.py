"""Start a disposable demo server and run the HTTP smoke check against it."""

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as directory:
        environment = {
            **os.environ,
            "SUPPORTFORGE_MODE": "demo",
            "SUPPORTFORGE_DATABASE": str(Path(directory) / "test.sqlite3"),
            "SUPPORTFORGE_API_TOKEN": "",
        }
        with (Path(directory) / "server.log").open("w+") as log:
            process = subprocess.Popen(  # noqa: S603
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "supportforge.app:create_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--no-access-log",
                ],
                cwd=root,
                env=environment,
                stdout=log,
                stderr=log,
            )
            try:
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("Demo server exited before readiness")
                    try:
                        with urllib.request.urlopen(origin + "/healthz", timeout=1):  # noqa: S310
                            break
                    except (urllib.error.URLError, TimeoutError):
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Demo server did not become ready within 45 seconds")
                subprocess.run(  # noqa: S603
                    [sys.executable, "scripts/smoke.py", origin],
                    cwd=root,
                    env=environment,
                    check=True,
                    timeout=60,
                )
            except Exception:
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
