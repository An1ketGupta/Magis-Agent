#!/usr/bin/env bash
# Check whether a machine can run the experiments (vLLM + SWE-bench Docker images). Read-only: installs
# and changes nothing. Run inside Linux / WSL2 on the GPU machine:
#     bash exp/SWE-bench/check_machine.sh 2>&1 | tee machine_check.txt
section() { echo; echo "=== $1"; }
ok() { echo "  [ok]   $1"; }
warn() { echo "  [warn] $1"; }

section "System"
grep PRETTY_NAME /etc/os-release
uname -r
grep -qi microsoft /proc/version && echo "  WSL2" || echo "  native Linux"
echo "  user: $(whoami), CPUs: $(nproc), RAM: $(free -g | awk '/Mem:/{print $2}') GB total, $(free -g | awk '/Mem:/{print $7}') GB available"

section "GPU"
if command -v nvidia-smi >/dev/null; then
    nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu,driver_version --format=csv
    echo "  processes using the GPU now (other users' jobs show up here):"
    nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader | sed 's/^/    /'
    nvidia-smi | grep -o "CUDA Version: [0-9.]*" | sed 's/^/  /'
else
    warn "nvidia-smi not found: no GPU driver visible here (on WSL2 the Windows NVIDIA driver provides it)"
fi

section "Disk (SWE-bench Lite images need ~150-250 GB, repos ~5 GB, a 7B model ~15 GB)"
df -h "$HOME" | tail -1 | awk '{print "  home: " $4 " free of " $2}'
if grep -qi microsoft /proc/version; then
    # WSL2's disk is a virtual file on a Windows drive: the Windows drive's free space is the real limit
    df -h /mnt/c 2>/dev/null | tail -1 | awk '{print "  Windows C: drive (the real limit on WSL2): " $4 " free of " $2}'
fi
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
    root=$(docker info --format '{{.DockerRootDir}}')
    echo "  docker root: $root"
    df -h "$root" 2>/dev/null | tail -1 | awk '{print "  docker disk: " $4 " free of " $2}'
fi

section "Docker"
if ! command -v docker >/dev/null; then
    warn "docker not installed"
elif docker info >/dev/null 2>&1; then
    ok "docker works without sudo (server $(docker version --format '{{.Server.Version}}'))"
    docker info --format '  storage driver: {{.Driver}}, CPUs: {{.NCPU}}, memory: {{.MemTotal}}'
    docker system df | sed 's/^/  /'
    if docker run --rm --gpus all ubuntu:22.04 nvidia-smi -L >/dev/null 2>&1; then
        ok "containers can use the GPU"
    else
        warn "containers cannot use the GPU (only needed if vLLM runs in Docker)"
    fi
else
    warn "docker installed but not usable by $(whoami): needs the docker group or Docker Desktop's WSL integration"
fi

section "Python / CUDA tooling"
for py in python3 python3.11 python3.12 conda; do
    command -v $py >/dev/null && echo "  $py: $($py --version 2>&1)"
done
command -v nvcc >/dev/null && nvcc --version | tail -1 | sed 's/^/  nvcc: /'
python3 -c "import vllm; print('  vllm', vllm.__version__)" 2>/dev/null || echo "  vllm: not installed in system python"
python3 -c "import torch; print('  torch', torch.__version__, 'cuda', torch.cuda.is_available())" 2>/dev/null || echo "  torch: not installed in system python"
pip3 --version 2>/dev/null | sed 's/^/  /'
python3 -c "import venv" 2>/dev/null && ok "python venv module available" || warn "python3-venv missing"

section "Network"
for url in https://huggingface.co https://registry-1.docker.io/v2/ https://github.com https://pypi.org; do
    code=$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$url")
    [ "$code" != "000" ] && ok "$url reachable ($code)" || warn "$url NOT reachable"
done
command -v tailscale >/dev/null && tailscale ip -4 2>/dev/null | sed 's/^/  tailscale ip: /'

section "Who else is using the machine"
who | sed 's/^/  /'
uptime | sed 's/^/  /'
