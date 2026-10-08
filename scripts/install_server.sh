#!/bin/sh
# Run after deployment and dry-run validation. Never displays secret file contents.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
run_user=${1:-${SUDO_USER:-}}
if [ "$(id -u)" -ne 0 ]; then
    echo '관리자 권한으로 설치해야 합니다.' >&2
    exit 1
fi
case "$project_dir" in
    *[!a-zA-Z0-9_./-]*) echo '서버 설치 경로에는 영문·숫자·점·밑줄·하이픈만 사용할 수 있습니다.' >&2; exit 1 ;;
esac
case "$run_user" in
    ''|root|*[!a-zA-Z0-9_-]*) echo 'root 이외의 실행 계정을 지정하세요.' >&2; exit 1 ;;
esac
id "$run_user" >/dev/null
test -x "$project_dir/.venv/bin/python"
test -s "$project_dir/.env"
test -f "$project_dir/redmine_notifier.py"
test -x /usr/bin/flock
run_group=$(id -gn "$run_user")
install -d -o "$run_user" -g "$run_group" -m 700 "$project_dir/runtime" "$project_dir/logs"
chown "$run_user:$run_group" "$project_dir/.env"
chmod 600 "$project_dir/.env"
staging=$(mktemp -d)
trap 'rm -rf -- "$staging"' EXIT HUP INT TERM
for unit in redmine-notifier@.service redmine-notifier-daily.timer redmine-notifier-weekly.timer; do
    sed -e "s|@PROJECT_DIR@|$project_dir|g" -e "s|@RUN_USER@|$run_user|g" \
        "$project_dir/deploy/systemd/$unit" > "$staging/$unit"
done
systemd-analyze verify "$staging/redmine-notifier@.service" "$staging/redmine-notifier-daily.timer" "$staging/redmine-notifier-weekly.timer"
backup="$project_dir/scheduler-backup/systemd-$(date +%Y%m%d-%H%M%S)"
install -d -m 700 "$backup"
for unit in redmine-notifier@.service redmine-notifier-daily.timer redmine-notifier-weekly.timer; do
    if [ -e "/etc/systemd/system/$unit" ]; then
        cp -p -- "/etc/systemd/system/$unit" "$backup/$unit"
    fi
    install -m 644 "$staging/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable --now redmine-notifier-daily.timer redmine-notifier-weekly.timer
systemctl list-timers --all --no-pager redmine-notifier-daily.timer redmine-notifier-weekly.timer
echo '예약 실행 설치 완료. ON/OFF와 실제 전송 결과를 별도로 확인하세요.'
