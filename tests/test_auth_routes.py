"""Tests for the authentication routes (login / logout)."""
import pytest


def _contains_login_page_content(data: bytes) -> bool:
    """Return True if the response data looks like the login page."""
    lower = data.lower()
    return b'login' in lower or 'вход'.encode('utf-8').lower() in lower


class TestLoginPage:
    def test_get_renders_form(self, client):
        response = client.get('/login')
        assert response.status_code == 200
        assert _contains_login_page_content(response.data)

    def test_authenticated_user_redirected_from_login(self, auth_client):
        """An already-logged-in user should be redirected away from /login."""
        response = auth_client.get('/login', follow_redirects=False)
        assert response.status_code in (301, 302)
        location = response.headers.get('Location', '')
        assert location in ('/', '/dashboard') or 'dashboard' in location


class TestLoginPost:
    def test_valid_credentials_redirect_to_dashboard(self, client):
        response = client.post(
            '/login',
            data={'username': 'admin', 'password': 'admin123'},
            follow_redirects=False,
        )
        assert response.status_code in (301, 302)
        location = response.headers.get('Location', '')
        assert location in ('/', '/dashboard') or 'dashboard' in location

    def test_valid_credentials_set_session(self, client):
        with client:
            client.post(
                '/login',
                data={'username': 'admin', 'password': 'admin123'},
                follow_redirects=True,
            )
            with client.session_transaction() as sess:
                assert sess.get('user_id') == 'u-admin'
                assert sess.get('user_role') == 'admin'

    def test_invalid_password(self, client):
        response = client.post(
            '/login',
            data={'username': 'admin', 'password': 'wrongpassword'},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert _contains_login_page_content(response.data)

    def test_nonexistent_user(self, client):
        response = client.post(
            '/login',
            data={'username': 'nobody', 'password': 'whatever'},
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_empty_credentials(self, client):
        response = client.post(
            '/login',
            data={'username': '', 'password': ''},
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_all_seed_users_can_login(self, client):
        """Every seeded user must be able to authenticate with their seed password."""
        credentials = [
            ('admin', 'admin123'),
            ('secretary', 'sec123'),
            ('head_central', 'head123'),
            ('head_department', 'head123'),
            ('assistant', 'ast123'),
            ('executor', 'exec123'),
        ]
        for username, password in credentials:
            r = client.post(
                '/login',
                data={'username': username, 'password': password},
                follow_redirects=False,
            )
            assert r.status_code in (301, 302), f'Login failed for {username}'
            location = r.headers.get('Location', '')
            assert location in ('/', '/dashboard') or 'dashboard' in location, (
                f'Did not redirect to dashboard for {username}'
            )
            client.get('/logout')  # clean up session


class TestLogout:
    def test_logout_clears_session(self, auth_client):
        with auth_client:
            auth_client.get('/logout', follow_redirects=False)
            with auth_client.session_transaction() as sess:
                assert 'user_id' not in sess

    def test_logout_redirects_to_login(self, auth_client):
        response = auth_client.get('/logout', follow_redirects=False)
        assert response.status_code in (301, 302)
        assert '/login' in response.headers.get('Location', '')
