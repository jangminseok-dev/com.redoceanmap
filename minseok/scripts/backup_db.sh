#!/usr/bin/env bash
# 실운영 DB(pgvector, redoceanmap) 백업 — pg_dump 커스텀 포맷(-Fc, 압축) 7세대 보관.
#
# 대상: 백엔드 PC D드라이브(/mnt/d/redoceanmap-backups) — 로드맵 ②-M3의 로컬 1차 계층.
#   막아주는 것: DB 손상·실수 삭제·볼륨 소실·C:(WSL) 단일 디스크 고장.
#   못 막는 것: PC 통째 사고·랜섬웨어 — 그건 오프사이트 계층(backup_offsite.sh,
#   rclone→Google Drive 주 1회 미러)이 맡는다. 복원 가능성 증명은 restore_rehearsal.sh(분기 1회).
#
# 덤프 직후 pg_restore --list로 무결성을 자가 검증한다(깨진 백업의 조용한 축적 방지).
# 검증 실패 시 해당 덤프를 지우고 비정상 종료 — 기존 세대는 건드리지 않는다.
# 복원 예시:
#   docker exec -i redoceanmap-pgvector-1 pg_restore -U redocean -d <대상DB> --clean --if-exists < <덤프파일>
#
# 백엔드 PC cron (매일 04:00):
#   0 4 * * * /home/host/projects/com.redoceanmap/minseok/scripts/backup_db.sh >> ~/backup_db.log 2>&1
set -euo pipefail

CONTAINER=redoceanmap-pgvector-1
DB_USER=redocean
DB_NAME=redoceanmap
BACKUP_DIR=/mnt/d/redoceanmap-backups
KEEP=7

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
DUMP="$BACKUP_DIR/redoceanmap-$STAMP.dump"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 백업 시작 → $DUMP"
docker exec "$CONTAINER" pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$DUMP"

# 무결성 자가 검증 — 목차가 안 읽히면 덤프가 깨진 것
if ! docker exec -i "$CONTAINER" pg_restore --list < "$DUMP" > /dev/null; then
    echo "[오류] 덤프 무결성 검증 실패 — $DUMP 삭제, 기존 세대 유지"
    rm -f "$DUMP"
    exit 1
fi

SIZE=$(du -h "$DUMP" | cut -f1)
echo "백업 완료: $DUMP ($SIZE), 검증 통과"

# 7세대 초과분 삭제 (최신순 정렬 후 8번째부터)
ls -1t "$BACKUP_DIR"/redoceanmap-*.dump 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
    echo "세대 초과 삭제: $old"
    rm -f "$old"
done

echo "보관 중: $(ls -1 "$BACKUP_DIR"/redoceanmap-*.dump | wc -l)개"

# ── market 전용 DB(market-pgvector, :5434) — 이관 후 상권 데이터의 유일본 ──
# 파일명은 market-* — redoceanmap-* 글롭과 겹치면 메인 로테이션에 섞여 조기 삭제된다.
MARKET_CONTAINER=market-pgvector
MARKET_DUMP="$BACKUP_DIR/market-$STAMP.dump"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] market 백업 시작 → $MARKET_DUMP"
docker exec "$MARKET_CONTAINER" pg_dump -U market -Fc market > "$MARKET_DUMP"
if ! docker exec -i "$MARKET_CONTAINER" pg_restore --list < "$MARKET_DUMP" > /dev/null; then
    echo "[오류] market 덤프 무결성 검증 실패 — $MARKET_DUMP 삭제, 기존 세대 유지"
    rm -f "$MARKET_DUMP"
    exit 1
fi
echo "market 백업 완료: $MARKET_DUMP ($(du -h "$MARKET_DUMP" | cut -f1)), 검증 통과"

ls -1t "$BACKUP_DIR"/market-*.dump 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
    echo "세대 초과 삭제: $old"
    rm -f "$old"
done
echo "market 보관 중: $(ls -1 "$BACKUP_DIR"/market-*.dump | wc -l)개"
