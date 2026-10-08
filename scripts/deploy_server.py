"""Deploy only source files. Credentials are never printed or passed in argv."""
import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True, help="SSH user@host")
    parser.add_argument("--directory", required=True, help="Dedicated absolute server directory")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--copy-local-env", action="store_true", help="Opaque copy into a new deployment only")
    parser.add_argument("--install", action="store_true", help="Install and enable system timers after preflight")
    parser.add_argument("--sudo-credential-file", type=Path, help="Existing SERVER_SUDO_PASSWORD setting")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+@[a-zA-Z0-9_.-]+", args.host):
        parser.error("SSH 대상 형식이 올바르지 않습니다.")
    if (not re.fullmatch(r"/[a-zA-Z0-9_./-]+", args.directory)
            or ".." in args.directory.split("/")
            or args.directory.rstrip("/") in ("/", "/opt", "/home", "/home/ubuntu")):
        parser.error("독립 서버 폴더를 지정하세요.")
    directory = args.directory.rstrip("/")
    quoted = shlex.quote(directory)
    ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", args.host]

    def remote(command):
        subprocess.run(ssh + [command], check=True)

    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT, check=True)
    if args.update:
        remote(f"test -f {quoted}/redmine_notifier.py")
        remote(f"stamp=$(date +%Y%m%d-%H%M%S) && mkdir -p {quoted}/scheduler-backup/code-$stamp && "
               f"cp {quoted}/redmine_notifier.py {quoted}/scheduler-backup/code-$stamp/")
    else:
        remote(f"test ! -e {quoted} && mkdir -m 700 {quoted}")
    if args.copy_local_env:
        remote(f"test ! -e {quoted}/.env && (umask 077; touch {quoted}/.env)")
        subprocess.run(["scp", "--", str(ROOT / ".env"), f"{args.host}:{directory}/.env"], check=True)
        remote(f"chmod 600 {quoted}/.env")
    remote(f"mkdir -p {quoted}/tests {quoted}/scripts {quoted}/deploy/systemd")
    sources = [ROOT / name for name in ("redmine_notifier.py", "redmine.py", "RedmineWeek.py", "redmineOpenNotice.py",
                                       "requirements.txt", ".env.example", "README.md", "SPEC.md")]
    for folder in ("tests", "scripts", "deploy"):
        sources.extend(path for path in (ROOT / folder).rglob("*") if path.is_file()
                       and path.suffix in (".py", ".ps1", ".sh", ".service", ".timer"))
    for source in sources:
        relative = source.relative_to(ROOT)
        destination = directory + "/" + relative.parent.as_posix()
        subprocess.run(["scp", "--", str(source), f"{args.host}:{destination}/"], check=True)
    remote(f"cd {quoted} && python3 -m venv .venv && .venv/bin/python -m pip install -q -r requirements.txt "
           "&& .venv/bin/python -m unittest discover -s tests -v && sh -n scripts/install_server.sh")
    if args.install:
        if not args.sudo_credential_file:
            parser.error("서비스 설치에는 기존 sudo 인증 설정 파일이 필요합니다.")
        password = next((line.partition("=")[2] for line in
                         args.sudo_credential_file.read_text(encoding="utf-8-sig").splitlines()
                         if line.startswith("SERVER_SUDO_PASSWORD=")), "")
        if not password:
            parser.error("기존 서버 인증 설정이 없습니다.")
        command = f"sh {quoted}/scripts/install_server.sh {shlex.quote(args.host.split('@')[0])}"
        subprocess.run(ssh + ["sudo -S -p '' " + command], input=password + "\n", text=True, check=True)
    print("서버 파일·테스트 확인 완료. ON/OFF와 실제 전송은 별도로 검증하세요.")


if __name__ == "__main__":
    main()
