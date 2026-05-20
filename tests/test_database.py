"""Tests for application/database.py (seed_initial_data)."""
import pytest


class TestSeedInitialData:
    def test_departments_seeded(self, app):
        from application.models import Department
        with app.app_context():
            depts = Department.query.all()
            names = {d.name for d in depts}
        assert 'Центральный аппарат' in names
        assert 'Юридический отдел' in names
        assert 'Организационный отдел' in names
        assert 'Информационный отдел' in names

    def test_users_seeded(self, app):
        from application.models import User
        with app.app_context():
            users = {u.username: u for u in User.query.all()}
        assert 'admin' in users
        assert 'secretary' in users
        assert 'head_central' in users
        assert 'head_department' in users
        assert 'assistant' in users
        assert 'executor' in users

    def test_admin_role(self, app):
        from application.models import User
        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
        assert admin.role == 'admin'

    def test_executor_has_department(self, app):
        from application.models import User
        with app.app_context():
            executor = User.query.filter_by(username='executor').first()
        assert executor.department_id == 'dept-2'

    def test_passwords_are_hashed(self, app):
        from werkzeug.security import check_password_hash
        from application.models import User
        with app.app_context():
            users_and_passwords = [
                ('admin', 'admin123'),
                ('secretary', 'sec123'),
                ('executor', 'exec123'),
            ]
            for username, plain_pwd in users_and_passwords:
                user = User.query.filter_by(username=username).first()
                assert check_password_hash(user.password, plain_pwd), (
                    f'Password hash mismatch for {username}'
                )

    def test_idempotent_seed(self, app, db):
        """Calling seed_initial_data() a second time must not raise or duplicate data."""
        from application.models import User
        from application.database import seed_initial_data
        with app.app_context():
            count_before = User.query.count()
            seed_initial_data()
            count_after = User.query.count()
        assert count_after == count_before
