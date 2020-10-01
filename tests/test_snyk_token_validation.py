"""Snyk Token Validation Tests."""
import unittest
from unittest.mock import patch
import f8a_report.snyk_token_validation_main as token_validation
from f8a_report.helpers.db_gateway import TokenValidationQueries


class TestSnykTokenValidation(unittest.TestCase):
    """Test cases for checking Snyk Token Validation."""

    @patch('f8a_report.snyk_token_validation_main.decrypt_api_token')
    @patch('f8a_report.snyk_token_validation_main.is_snyk_token_valid')
    def test_registered_user(self, is_snyk_token_valid, decrypt_api_token):
        """Test case for checking registered user."""
        decrypt_api_token.return_value = b'gAAAAABfNTgGNBoO7RkDM'
        is_snyk_token_valid.return_value = True
        user_to_tokens = {'5b24a89e-2bf4': b'XM2skHfuCWXPflF3MvIRj3'}
        unregistered_users = token_validation.call_snyk_api(user_to_tokens)

        assert len(unregistered_users) == 0

    @patch('f8a_report.snyk_token_validation_main.decrypt_api_token')
    @patch('f8a_report.snyk_token_validation_main.is_snyk_token_valid')
    def test_unregistered_user(self, is_snyk_token_valid, decrypt_api_token):
        """Test case for checking unregistered user."""
        decrypt_api_token.return_value = b'gAAAAABfNTgGNBoO7RkDM'
        is_snyk_token_valid.return_value = False
        user_to_tokens = {'5b24a89e-2bf4': b'XM2skHfuCWXPflF3MvIRj3'}
        unregistered_users = token_validation.call_snyk_api(user_to_tokens)

        assert len(unregistered_users) == 1

    @patch.object(TokenValidationQueries, 'get_registered_user_tokens')
    @patch.object(TokenValidationQueries, 'update_users_to_unregistered')
    @patch('f8a_report.snyk_token_validation_main.decrypt_api_token')
    @patch('f8a_report.snyk_token_validation_main.is_snyk_token_valid')
    def test_main(self, is_snyk_token_valid, decrypt_api_token,
                  update_users_to_unregistered, get_registered_user_tokens):
        """Test cases for statement flow in main."""
        decrypt_api_token.return_value = b'gAAAAABfNTgGNBoO7RkDM'
        is_snyk_token_valid.return_value = False
        token_validation.main()

        get_registered_user_tokens.assert_called_once()

        update_users_to_unregistered.assert_called_once()
