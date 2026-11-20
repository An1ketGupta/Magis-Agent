# Setup: reaching the college GPU over Tailscale

Goal: Claude (running on the laptop) can `ssh capstone-gpu` into the GPU machine. All heavy work (models,
repos, Docker images, experiments) then happens on the GPU machine; nothing large is stored on the laptop.

```
laptop (Windows, Claude Code) --ssh over Tailscale--> GPU machine (Windows → WSL2 Ubuntu): vLLM + Docker + experiments
```
**The GPU machine runs Windows**: follow the Windows section at the end; parts B and C below are for Linux.

Both machines must be in the **same tailnet** (same Tailscale account, or the GPU shared with your
account by its owner from the admin console: Machines → … → Share).

## A. Laptop (once)
1. Install Tailscale: https://tailscale.com/download/windows, or PowerShell `winget install tailscale.tailscale`.
2. Taskbar Tailscale icon → **Log in** with the same account as the GPU.
3. The SSH key is already there: `~/.ssh/capstone_gpu` (private, never share) and `~/.ssh/capstone_gpu.pub`.

## B. GPU machine (at the college; Linux commands)
1. What machine is it, and can you use sudo?
   ```bash
   cat /etc/os-release; whoami; sudo -v && echo "sudo ok"
   ```
   No sudo → steps 2–5 need the lab admin. Do not install anything on a shared machine without permission.
2. Tailscale logged in, and starting by itself after a reboot:
   ```bash
   tailscale status                     # logged out / not found?
   sudo tailscale up                    # prints a login link; open it, log in with the SAME account
   # only if not installed (with permission):  curl -fsSL https://tailscale.com/install.sh | sh
   sudo systemctl enable --now tailscaled
   ```
3. Stop it logging out again: Tailscale admin console (https://login.tailscale.com/admin/machines) →
   the GPU machine → … → **Disable key expiry**. Never run `tailscale logout` on it.
4. SSH server running and enabled:
   ```bash
   sudo systemctl enable --now ssh      # if missing: sudo apt install -y openssh-server
   systemctl is-active ssh              # → active
   ```
5. If a firewall is on (`sudo ufw status` says active), allow SSH over Tailscale only:
   `sudo ufw allow in on tailscale0 to any port 22`
6. If it is a desktop PC: stop it sleeping (experiments run for hours or days). Ask first if it is shared.
   ```bash
   sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
   ```
7. Authorize the laptop's key (one line):
   ```bash
   mkdir -p ~/.ssh && chmod 700 ~/.ssh
   echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBLi/jOQUW6nUDSbic0RoG4V6hxLbJO/vzo0AgPzd7p3 capstone-gpu (aniket laptop)' >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```
8. Note down: `tailscale status | head -1` (machine name), `tailscale ip -4` (100.x.y.z), `whoami`.
   Optional, to save a step: `nvidia-smi; df -h ~ /var/lib/docker; free -h; docker info | head -5`.

## C. Test from the laptop (PowerShell)
```
tailscale status                 # the GPU machine is listed and not "offline"
tailscale ping <gpu-name>
ssh -i $HOME\.ssh\capstone_gpu <username>@<gpu-name-or-100.x.y.z>     # no password prompt → done; `exit`
```

## D. Then Claude does
1. Adds to `~/.ssh/config`: `Host capstone-gpu` (HostName, User, IdentityFile `~/.ssh/capstone_gpu`).
2. Checks GPU/VRAM, disk (SWE-bench images need ~150–250 GB), RAM, Docker without sudo, CUDA driver.
3. On the GPU machine only: Python env, vLLM serving Qwen, this repo, SWE-bench repos and images; then the
   harness check and the smoke test (`STATUS.md`). Long jobs run in `tmux` so they survive disconnects.

## Troubleshooting
| Symptom | Likely cause / fix |
|---|---|
| GPU not in `tailscale status` on the laptop | different account/tailnet, or not shared with you |
| listed but "offline" | machine off/asleep, or Tailscale logged out (key expired, step 3) |
| `ssh`: Connection refused / timed out | SSH server not running (B4), or firewall (B5) |
| `ssh`: Permission denied (publickey) | key not in `~/.ssh/authorized_keys` of *that* user, or permissions (B7); wrong username |
| asks for a password | the key was not used: check the `-i` path, or B7 |

## The GPU machine runs Windows (confirmed 2026-11-20): use this instead of part B
At the college, do W1–W6 in **PowerShell run as administrator** (Start → type PowerShell → right-click →
Run as administrator). Claude then does W8 (WSL2, Docker, GPU, project) remotely over SSH.

**W1. Check**
```powershell
whoami
net localgroup administrators          # is your user in the list?
Get-ComputerInfo -Property OsName, OsVersion
nvidia-smi
Get-PSDrive C, D -ErrorAction SilentlyContinue     # free space (Free column)
```
Not an administrator → W2–W6 need the lab admin.

**W2. Tailscale**
```powershell
winget install --id Tailscale.Tailscale -e --source winget
```
Taskbar Tailscale icon → Log in with the laptop's account (`guptaaniket600.ag@…`). Then in the icon's menu:
**Preferences → Run unattended** (stays connected when nobody is logged in to Windows). In the admin console
(https://login.tailscale.com/admin/machines): the GPU machine → … → **Disable key expiry**.
Check: `& "C:\Program Files\Tailscale\tailscale.exe" status` lists both machines.

**W3. SSH server, started with Windows, PowerShell as the login shell**
```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -PropertyType String -Force `
    -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
Get-NetFirewallRule -Name *OpenSSH* | Select-Object Name, Enabled    # Enabled: True
```

**W4. Authorize the laptop's key**: the file depends on whether your user is an administrator (W1).
```powershell
$key = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBLi/jOQUW6nUDSbic0RoG4V6hxLbJO/vzo0AgPzd7p3 capstone-gpu (aniket laptop)'
# administrator user:
Add-Content -Path C:\ProgramData\ssh\administrators_authorized_keys -Value $key -Encoding ascii
icacls C:\ProgramData\ssh\administrators_authorized_keys /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"
# NOT an administrator, instead:
# New-Item -ItemType Directory -Force $HOME\.ssh; Add-Content -Path $HOME\.ssh\authorized_keys -Value $key -Encoding ascii
```

**W5. Never sleep or hibernate on power** (ask first if the PC is shared)
```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

**W6. Note down and send to Claude**: `& "C:\Program Files\Tailscale\tailscale.exe" ip -4`, `whoami`, and the
outputs of W1. Leave the PC on and Tailscale logged in (signing out of Windows is fine with "Run unattended").

**W7. Test from the laptop**: `ssh -i $HOME\.ssh\capstone_gpu <user>@<100.x.y.z>` gives a PowerShell
prompt on the GPU machine without a password. (A user from `whoami` like `pc\name` logs in as `name`.)

**W8. Claude, remotely**: WSL2 + Ubuntu (`wsl --install -d Ubuntu`, needs one reboot, which is safe because sshd
and Tailscale start by themselves), GPU check inside WSL, Docker Engine in WSL, `.wslconfig` (memory), moving
the WSL disk to a drive with ≥300 GB free if C: is short, then the project setup. Long jobs run in `tmux` in WSL.
