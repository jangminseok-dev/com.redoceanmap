#!/usr/bin/env bash
# 복원 리허설(②-M3 게이트) — 최신 덤프를 임시 DB에 실제로 복원해 "복원 가능한 백업"임을 증명.
#
# 백업의 가치는 복원이 되느냐로만 증명된다 — pg_restore --list(목차 검증)는 통과해도
# 실복원이 깨질 수 있다(확장 누락·권한 등). 이 스크립트는 실DB를 절대 건드리지 않는다:
# 같은 컨테이너에 임시 DB(restore_rehearsal)를 만들어 복원 → 핵심 테이블 행수 확인 → 드랍.
#
# 실행(백엔드 PC, 분기 1회 수동 — 사람이 결과를 봐야 의미가 있어 cron에 걸지 않는다):
#   /home/host/projects/com.redoceanmap/minseok/scripts/restore_rehearsal.sh
#
# 성공 기준: 메인·market 둘 다 "리허설 통과" 출력(핵심 테이블 전부 존재·행수 > 0).
set -euo pipefail

BACKUP_DIR=/mnt/d/redoceanmap-backups
REHEARSAL_DB=restore_rehearsal

rehearse() {
    local container=$1 db_user=$2 label=$3 glob=$4 tables=$5

    local dump
    dump=$(ls -1t "$BACKUP_DIR"/$glob 2>/dev/null | head -1)
    if [ -z "$dump" ]; then
        echo "[오류] $label 덤프가 없다($BACKUP_DIR/$glob)"
        return 1
    fi
    echo "── $label 리허설: $(basename "$dump") ($(du -h "$dump" | cut -f1)) ──"

    # 임시 DB 재생성 — 이전 리허설 잔재가 있어도 깨끗하게
    docker exec "$container" psql -U "$db_user" -d postgres \
        -c "DROP DATABASE IF EXISTS $REHEARSAL_DB;" -c "CREATE DATABASE $REHEARSAL_DB;" > /dev/null
    # pgvector 확장은 DB 단위 — 덤프의 CREATE EXTENSION이 실행되지만 명시 선생성이 안전
    docker exec "$container" psql -U "$db_user" -d "$REHEARSAL_DB" \
        -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null

    # --no-owner: 덤프의 소유자 구문을 무시(리허설 DB 소유자로 귀속). 오류 시 즉시 실패.
    if ! docker exec -i "$container" pg_restore -U "$db_user" -d "$REHEARSAL_DB" \
            --no-owner --exit-on-error < "$dump"; then
        echo "[오류] $label 복원 실패 — 백업이 복원 불가 상태다. 즉시 원인 조사 필요"
        docker exec "$container" psql -U "$db_user" -d postgres \
            -c "DROP DATABASE IF EXISTS $REHEARSAL_DB;" > /dev/null
        return 1
    fi

    # 핵심 테이블 행수 — 존재하지 않으면 쿼리가 실패해 리허설이 실패한다(의도)
    local failed=0
    for table in $tables; do
        local count
        count=$(docker exec "$container" psql -U "$db_user" -d "$REHEARSAL_DB" -tA \
            -c "SELECT count(*) FROM $table;")
        printf "  %-24s %s행\n" "$table" "$count"
        if [ "$count" -eq 0 ]; then
            echo "  [경고] $table 이 비어 있다 — 원본과 대조 필요"
            failed=1
        fi
    done

    docker exec "$container" psql -U "$db_user" -d postgres \
        -c "DROP DATABASE IF EXISTS $REHEARSAL_DB;" > /dev/null
    if [ "$failed" -eq 1 ]; then
        return 1
    fi
    echo "$label 리허설 통과"
}

# 메인 DB — 사용자·수집·대화의 유일 저장소.
# 검증 테이블은 **확실히 채워져 있는 것만** 고른다 — 신생 기능 테이블(bookmarks·user_profiles)을
# 넣으면 아직 0행인 것이 정상인데 리허설 실패로 오탐한다.
rehearse redoceanmap-pgvector-1 redocean "메인(redoceanmap)" "redoceanmap-*.dump" \
    "users news_articles price_bars conversations"

# market 전용 DB — 상권 3NF의 유일본(이관 후 메인 사본은 롤백용 동결)
rehearse market-pgvector market "market" "market-*.dump" \
    "trade_area estimated_sales store market_news_articles"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 복원 리허설 전체 통과 — 백업은 복원 가능하다"
