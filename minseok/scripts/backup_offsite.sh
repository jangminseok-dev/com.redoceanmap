#!/usr/bin/env bash
# 백업 오프사이트 계층(②-M3 잔여) — 로컬 덤프 디렉토리를 rclone으로 Google Drive에 미러.
#
# 로컬 계층(backup_db.sh, 매일 04:00)이 못 막는 것을 막는다: PC 통째 사고·랜섬웨어·화재.
# `rclone sync`라 로컬의 7세대 로테이션이 원격에 그대로 반영된다 — 원격 세대 관리 불요.
# 전송 후 `rclone check`(체크섬 대조 — gdrive는 md5 지원, 재다운로드 없음)로 미러 무결성을
# 검증한다. 로컬 검증(backup_db.sh의 pg_restore --list)과 합치면: 덤프 자체 무결 + 미러 무결.
#
# ⚠ 최초 1회 사람 설정(백엔드 PC):
#   1. rclone 설치: sudo apt install rclone  (또는 https://rclone.org/install.sh)
#   2. rclone config → n(새 remote) → 이름 `gdrive` → 타입 drive → 브라우저 OAuth 승인
#      (WSL이라 브라우저가 안 뜨면 안내되는 `rclone authorize` 명령을 윈도우 쪽에서 실행)
#   3. 확인: rclone lsd gdrive:   (드라이브 최상위 폴더 목록이 나오면 성공)
#   4. 첫 실행을 수동으로: ./backup_offsite.sh  (전량 업로드 — 이후는 증분)
#
# 백엔드 PC cron (매주 일 05:00 — 일간 백업 04:00 뒤, 원안 '주 1회' 정책):
#   0 5 * * 0 /home/host/projects/com.redoceanmap/minseok/scripts/backup_offsite.sh >> ~/backup_offsite.log 2>&1
#
# 복구(PC를 잃었을 때): 새 기기에서 rclone 구성 후
#   rclone copy gdrive:redoceanmap-backups /원하는/경로  → restore_rehearsal.sh 절차로 복원
set -euo pipefail

BACKUP_DIR=/mnt/d/redoceanmap-backups
REMOTE=gdrive:redoceanmap-backups

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 오프사이트 미러 시작 → $REMOTE"

if ! command -v rclone > /dev/null; then
    echo "[오류] rclone 미설치 — 헤더의 최초 설정 절차를 먼저 수행할 것"
    exit 1
fi
if ! rclone listremotes | grep -q '^gdrive:$'; then
    echo "[오류] rclone remote 'gdrive' 미구성 — rclone config로 Google Drive 연결 필요"
    exit 1
fi
if ! ls "$BACKUP_DIR"/redoceanmap-*.dump > /dev/null 2>&1; then
    echo "[오류] 로컬 덤프가 없다($BACKUP_DIR) — backup_db.sh가 돌고 있는지 먼저 확인"
    exit 1
fi

# 덤프만 미러(*.dump) — 디렉토리에 다른 파일이 생겨도 원격을 오염시키지 않는다
rclone sync "$BACKUP_DIR" "$REMOTE" --include "*.dump" --transfers 2 --stats-one-line -v

# 미러 무결성 — 체크섬 대조(불일치·누락이 있으면 비정상 종료 → cron 로그에서 드러난다)
rclone check "$BACKUP_DIR" "$REMOTE" --include "*.dump"

LOCAL_COUNT=$(ls -1 "$BACKUP_DIR"/*.dump | wc -l)
REMOTE_COUNT=$(rclone lsf "$REMOTE" --include "*.dump" | wc -l)
echo "미러 완료: 로컬 ${LOCAL_COUNT}개 = 원격 ${REMOTE_COUNT}개, 체크섬 검증 통과"
