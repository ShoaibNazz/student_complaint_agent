"""Convenience launcher:  python run.py"""
import os
import socket
import subprocess
import sys
import time
import uvicorn


def _can_bind(host: str, port: int) -> bool:
    """Return True if we can actually bind a TCP socket to (host, port)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def _free_port_if_in_use(host: str, port: int) -> None:
    """If the target port cannot be bound on Windows, stop stale processes (including orphaned multiprocessing forks) holding it."""
    for _ in range(3):
        if _can_bind(host, port):
            return

        if sys.platform == "win32":
            try:
                output = subprocess.check_output(
                    ["netstat", "-ano", "-p", "tcp"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                current_pid = os.getpid()
                listening_pids = set()
                for line in output.splitlines():
                    parts = line.split()
                    if len(parts) >= 5 and parts[3].upper() == "LISTENING":
                        local_addr = parts[1]
                        if local_addr.endswith(f":{port}"):
                            try:
                                pid = int(parts[4])
                                if pid > 0 and pid != current_pid:
                                    listening_pids.add(pid)
                            except ValueError:
                                pass

                if listening_pids:
                    pid_list_str = ",".join(str(p) for p in listening_pids)
                    ps_cmd = (
                        f"$targets = @({pid_list_str}); "
                        f"Get-CimInstance Win32_Process | Where-Object {{ "
                        f"($targets -contains $_.ProcessId) -or "
                        f"($targets -contains $_.ParentProcessId) -or "
                        f"($_.CommandLine -match '--multiprocessing-fork') "
                        f"}} | ForEach-Object {{ "
                        f"Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue "
                        f"}}"
                    )
                    subprocess.run(
                        ["powershell", "-NoProfile", "-Command", ps_cmd],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                    for pid in listening_pids:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                        )
                    time.sleep(0.6)
            except Exception:
                break
        else:
            break


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    _free_port_if_in_use(host, port)
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
