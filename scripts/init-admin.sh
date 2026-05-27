#!/usr/bin/env bash
# 交互式创建一个管理员账号。
# 用法：./scripts/init-admin.sh
set -euo pipefail

cd "$(dirname "$0")/.."

read -r -p "管理员用户名: " USERNAME
read -r -s -p "管理员密码: " PASSWORD
echo
read -r -p "显示名（回车跳过则用用户名）: " DISPLAY
DISPLAY=${DISPLAY:-$USERNAME}

# 在 api 容器里执行
docker compose exec -T api python -c "
from app.db.base import SessionLocal
from app.db.models import User, UserRole
from app.core.security import hash_password
from sqlalchemy import select

with SessionLocal() as db:
    if db.scalar(select(User).where(User.username == '$USERNAME')):
        print('用户已存在')
        raise SystemExit(1)
    u = User(
        username='$USERNAME',
        password_hash=hash_password('$PASSWORD'),
        display_name='$DISPLAY',
        role=UserRole.admin,
    )
    db.add(u)
    db.commit()
    print(f'已创建管理员: {u.username} (id={u.id})')
"
