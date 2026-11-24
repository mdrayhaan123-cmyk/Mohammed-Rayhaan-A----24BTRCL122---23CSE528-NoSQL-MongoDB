import os, platform, shutil, socket, subprocess, time, psutil

try:
    import winreg
except ImportError:
    winreg = None

_CACHE = {"ts": 0.0, "specs": "", "apps": "", "threats": ""}

def _ps(cmd: str, timeout: int = 8) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return (r.stdout or "").strip()
    except Exception as e:
        return f"Unavailable ({e})"

def get_installed_apps() -> str:
    if _CACHE["apps"] and (time.time() - _CACHE["ts"] < 300):
        return _CACHE["apps"]
    apps = set()
    for cli, label in [("code", "Visual Studio Code"), ("docker", "Docker"), ("python", "Python"), ("git", "Git"), ("mongosh", "MongoDB Shell")]:
        if shutil.which(cli):
            apps.add(f"{label} ({cli} in PATH)")
    if winreg is not None:
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for hive, subkey in reg_paths:
            try:
                with winreg.OpenKey(hive, subkey) as root:
                    for i in range(winreg.QueryInfoKey(root)[0]):
                        try:
                            sub = winreg.EnumKey(root, i)
                            with winreg.OpenKey(root, sub) as item:
                                name, _ = winreg.QueryValueEx(item, "DisplayName")
                                if name:
                                    apps.add(str(name).strip())
                        except OSError:
                            continue
            except OSError:
                continue
    sorted_apps = sorted(apps)
    summary = ", ".join(sorted_apps[:80]) if sorted_apps else "None detected"
    _CACHE["apps"] = summary
    return summary

def get_hardware_specs() -> str:
    if _CACHE["specs"] and (time.time() - _CACHE["ts"] < 300):
        return _CACHE["specs"]
    cpu = _ps("(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)")
    gpu = _ps("(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join '; '")
    model = _ps("(Get-CimInstance Win32_ComputerSystem | ForEach-Object { \"$($_.Manufacturer) $($_.Model)\" })")
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    disk = psutil.disk_usage("C:\\")
    disk_info = f"{round(disk.used/(1024**3),1)}GB / {round(disk.total/(1024**3),1)}GB ({disk.percent}% used)"
    os_ver = _ps("(Get-CimInstance Win32_OperatingSystem | ForEach-Object { \"$($_.Caption) (Build $($_.BuildNumber))\" })")
    specs = (
        f"Device: {model} | Hostname: {socket.gethostname()}\n"
        f"OS: {os_ver} ({platform.machine()})\n"
        f"CPU: {cpu} ({psutil.cpu_count(logical=False)} Cores / {psutil.cpu_count(logical=True)} Threads)\n"
        f"GPU: {gpu}\n"
        f"RAM: {ram_gb} GB | C: Drive: {disk_info}"
    )
    _CACHE["specs"] = specs
    return specs

def run_live_threat_scan(force: bool = False) -> str:
    if not force and _CACHE["threats"] and (time.time() - _CACHE["ts"] < 120):
        return _CACHE["threats"]

    listening, external = [], []
    for c in psutil.net_connections(kind="inet"):
        if c.status == "LISTEN" and c.laddr:
            listening.append(f"{c.laddr.ip}:{c.laddr.port}")
        elif c.status == "ESTABLISHED" and c.raddr and not c.raddr.ip.startswith(("127.", "::1")):
            external.append(f"{c.laddr.port}->{c.raddr.ip}:{c.raddr.port}")
    listening = sorted(set(listening))[:20]
    external = sorted(set(external))[:15]

    sec_audit = _ps("""
    $mp = Get-MpComputerStatus -ErrorAction SilentlyContinue
    $fw = (Get-NetFirewallProfile -ErrorAction SilentlyContinue | ForEach-Object { "$($_.Name):$($_.Enabled)" }) -join ', '
    $ep = Get-ExecutionPolicy
    $rdp = (Get-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -ErrorAction SilentlyContinue).fDenyTSConnections
    $smb1 = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters' -Name SMB1 -ErrorAction SilentlyContinue).SMB1
    $threats = (Get-MpThreatDetection -ErrorAction SilentlyContinue | Select-Object -First 3 | ForEach-Object { $_.ThreatID }) -join ', '
    "DefenderRT=$($mp.RealTimeProtectionEnabled) | Tamper=$($mp.IsTamperProtected) | Firewall=[$fw] | ExecPolicy=$ep | RDP_Disabled=$rdp | SMBv1_Reg=$smb1 | RecentDetections=[$threats]"
    """, timeout=5)

    startup = _ps("(Get-CimInstance Win32_StartupCommand | Select-Object -First 10 -ExpandProperty Name) -join '; '", timeout=5)
    secret_hits = []
    scan_root = os.path.expanduser("~")
    for root, dirs, files in os.walk(scan_root):
        dirs[:] = [d for d in dirs if d not in ("AppData", "node_modules", ".git", "__pycache__", "venv", ".venv", "OneDrive")]
        if root.count(os.sep) - scan_root.count(os.sep) > 2:
            continue
        for f in files:
            if f in (".env", "id_rsa", "credentials.json") or f.endswith((".pem", ".key")):
                secret_hits.append(os.path.join(root, f))
                if len(secret_hits) >= 10:
                    break

    report = (
        f"Security Controls: {sec_audit}\n"
        f"Listening Ports ({len(listening)}): {', '.join(listening) or 'None'}\n"
        f"External Connections ({len(external)}): {', '.join(external) or 'None'}\n"
        f"Startup Items: {startup or 'None'}\n"
        f"Sensitive/Key Files Found ({len(secret_hits)}): {', '.join(secret_hits) or 'None'}"
    )
    _CACHE["threats"] = report
    _CACHE["ts"] = time.time()
    return report
