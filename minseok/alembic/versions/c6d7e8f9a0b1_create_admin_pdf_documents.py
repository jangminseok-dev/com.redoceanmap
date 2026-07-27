"""어드민 PDF 요약 문서 테이블 + documents:read/write 권한 시드.

어드민이 업로드한 PDF의 추출 원문·요약을 1행으로 보관한다(원본 바이너리는 미보관).
권한 시드는 c1d2e3f4a5b6(analytics:read) 패턴 그대로 멱등 INSERT + admin 역할 매핑.

Revision ID: c6d7e8f9a0b1
Revises: e1a2b3c4d5f6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c6d7e8f9a0b1'
down_revision: Union[str, Sequence[str], None] = 'e1a2b3c4d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSIONS = [
    ('documents:read', '어드민 PDF 요약 문서 조회'),
    ('documents:write', '어드민 PDF 업로드·요약 실행'),
]


def upgrade() -> None:
    op.create_table(
        'admin_pdf_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('char_count', sa.Integer(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    for code, description in _PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (code, description) "
                "SELECT :code, :description "
                "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)"
            ).bindparams(code=code, description=description)
        )
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles r, permissions p "
                "WHERE r.code = 'admin' AND p.code = :code "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
                "WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
            ).bindparams(code=code)
        )


def downgrade() -> None:
    for code, _ in _PERMISSIONS:
        op.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id = "
                "(SELECT id FROM permissions WHERE code = :code)"
            ).bindparams(code=code)
        )
        op.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))
    op.drop_table('admin_pdf_documents')
