#!/usr/bin/env python3
"""RunPod Pod 控制 CLI

用法:
    python scripts/runpod_ctl.py start
    python scripts/runpod_ctl.py stop
    python scripts/runpod_ctl.py status

環境變數:
    RUNPOD_API_KEY  - RunPod API Key
    RUNPOD_POD_ID   - 目標 Pod ID
"""

import os
import sys
import json
import urllib.request
import urllib.error

API_BASE = "https://rest.runpod.io/v1"


def _get_env() -> tuple[str, str]:
    key = os.environ.get("RUNPOD_API_KEY", "")
    pod_id = os.environ.get("RUNPOD_POD_ID", "")
    if not key:
        print("❌ 請設定 RUNPOD_API_KEY")
        sys.exit(1)
    if not pod_id:
        print("❌ 請設定 RUNPOD_POD_ID")
        sys.exit(1)
    return key, pod_id


def _request(method: str, path: str, api_key: str) -> dict:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    if method in ("POST", "PUT"):
        req.data = b"{}"
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ HTTP {e.code}: {body}")
        sys.exit(1)


def cmd_status(api_key: str, pod_id: str) -> None:
    data = _request("GET", f"/pods/{pod_id}", api_key)
    pod = data.get("data", data)
    name = pod.get("name", pod_id)
    status = pod.get("desiredStatus", pod.get("status", "unknown"))
    runtime = pod.get("runtime", {})
    ports = runtime.get("ports", []) if runtime else []
    print(f"Pod:    {name} ({pod_id})")
    print(f"Status: {status}")
    if ports:
        for p in ports:
            print(f"URL:    https://{pod_id}-{p['privatePort']}.proxy.runpod.net")


def cmd_start(api_key: str, pod_id: str) -> None:
    print(f"▶ Starting pod {pod_id} ...")
    _request("POST", f"/pods/{pod_id}/start", api_key)
    print("✅ Start 指令已送出，Pod 啟動中（約 30-60 秒）")


def cmd_stop(api_key: str, pod_id: str) -> None:
    print(f"⏹ Stopping pod {pod_id} ...")
    _request("POST", f"/pods/{pod_id}/stop", api_key)
    print("✅ Stop 指令已送出")


COMMANDS = {"start": cmd_start, "stop": cmd_stop, "status": cmd_status}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"用法: {sys.argv[0]} [start|stop|status]")
        sys.exit(1)
    key, pod_id = _get_env()
    COMMANDS[sys.argv[1]](key, pod_id)
