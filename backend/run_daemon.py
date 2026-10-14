import os
import sys
import time
import subprocess
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
python_exe = backend_dir / ".venv" / "Scripts" / "python.exe"
if not python_exe.exists():
    python_exe = Path(sys.executable)

print(f"Starting SYNAPTRA resilient backend watchdog on 127.0.0.1:8000...")
while True:
    try:
        proc = subprocess.Popen([
            str(python_exe),
            "-m", "uvicorn",
            "main:app",
            "--app-dir", str(backend_dir),
            "--reload-dir", str(backend_dir),
            "--host", "127.0.0.1",
            "--port", "8000",
            "--reload",
        ])
        proc.wait()
        print(f"Uvicorn process {proc.pid} stopped with return code {proc.returncode}. Restarting in 1 second...")
        time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping watchdog.")
        break
    except Exception as exc:
        print(f"Watchdog exception: {exc}. Retrying in 2 seconds...")
        time.sleep(2)
