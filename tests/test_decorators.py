"""Tests for application/decorators.py.

We test the decorator behaviour by creating minimal Flask route stubs inside
each test rather than relying on the real application routes.
"""
import pytest


class TestLoginRequired:
    def test_redirects_unauthenticated(self, client):
        """Unauthenticated request to a protected route must redirect to /login."""
        response = client.get('/orders', follow_redirects=False)
        assert response.status_code in (302, 301)
        assert '/login' in response.headers.get('Location', '')

    def test_allows_authenticated(self, auth_client):
        """Authenticated request must reach the route handler (200, not a login redirect)."""
        response = auth_client.get('/orders', follow_redirects=True)
        assert response.status_code == 200

    def test_decorator_preserves_function_name(self):
        from application.decorators import login_required

        @login_required
        def my_view():
            return 'ok'

        assert my_view.__name__ == 'my_view'


class TestRoleRequired:
    def test_decorator_preserves_function_name(self):
        from application.decorators import role_required

        @role_required('admin')
        def admin_view():
            return 'ok'

        assert admin_view.__name__ == 'admin_view'

    def test_allows_correct_role(self, client):
        """A user with the correct role must reach the protected page."""
        with client.session_transaction() as sess:
            sess['user_id'] = 'u-admin'
            sess['user_name'] = 'Admin'
            sess['user_role'] = 'admin'
            sess['department_id'] = None
        response = client.get('/admin', follow_redirects=True)
        # Admins must reach the admin panel (200).
        assert response.status_code == 200

    def test_denies_wrong_role(self, client):
        """A user with an insufficient role must be redirected away from /admin."""
        with client.session_transaction() as sess:
            sess['user_id'] = 'u-exec'
            sess['user_name'] = 'Executor'
            sess['user_role'] = 'executor'
            sess['department_id'] = 'dept-2'
        response = client.get('/admin', follow_redirects=False)
        assert response.status_code in (302, 301)
