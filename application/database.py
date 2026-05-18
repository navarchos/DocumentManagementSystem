from werkzeug.security import generate_password_hash

from app import db
from application.models import Department, User


def seed_initial_data():
    if User.query.count() == 0:
        departments = [
            ('dept-1', 'Центральный аппарат'),
            ('dept-2', 'Юридический отдел'),
            ('dept-3', 'Организационный отдел'),
            ('dept-4', 'Информационный отдел'),
        ]
        for d_id, d_name in departments:
            if db.session.get(Department, d_id) is None:
                db.session.add(Department(id=d_id, name=d_name))
        db.session.commit()

        users_data = [
            ('u-admin', 'Администратор', 'admin@ldpr.ru', 'admin', 'admin123', 'admin', None),
            ('u-sec', 'Секретарь', 'sec@ldpr.ru', 'secretary', 'sec123', 'secretary', None),
            ('u-head-central', 'Руководитель ЦА', 'headca@ldpr.ru', 'head_central', 'head123', 'head_central', 'dept-1'),
            ('u-head-dept', 'Начальник отдела', 'headdept@ldpr.ru', 'head_department', 'head123', 'head_department', 'dept-2'),
            ('u-ast', 'Помощник', 'ast@ldpr.ru', 'assistant', 'ast123', 'assistant', None),
            ('u-exec', 'Исполнитель', 'exec@ldpr.ru', 'executor', 'exec123', 'executor', 'dept-2'),
        ]
        for uid, full_name, email, username, plain_pwd, role, dept_id in users_data:
            if db.session.get(User, uid) is None:
                hashed = generate_password_hash(plain_pwd)
                db.session.add(User(
                    uid=uid,
                    full_name=full_name,
                    email=email,
                    username=username,
                    password=hashed,
                    role=role,
                    department_id=dept_id,
                ))
        db.session.commit()
