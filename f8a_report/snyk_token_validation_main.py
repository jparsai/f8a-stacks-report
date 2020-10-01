"""Snyk Token Validation."""

from f8a_report.helpers.db_gateway import TokenValidationQueries
from f8a_utils.user_token_utils import decrypt_api_token, is_snyk_token_valid
import logging

logger = logging.getLogger(__file__)


def main():
    """Snyk Token Validation."""
    user_to_tokens = TokenValidationQueries().get_registered_user_tokens()
    unregistered_users = call_snyk_api(user_to_tokens)
    TokenValidationQueries().update_users_to_unregistered(unregistered_users)


def call_snyk_api(user_to_tokens: dict) -> list:
    """Snyk API invocation to figure out unregistered users."""
    unregistered_users = list()
    for user_id, token in user_to_tokens.items():
        decrypted_token = decrypt_api_token(token)
        if not is_snyk_token_valid(decrypted_token.decode()):
            logger.info("User id %s has an invalid token", user_id)
            unregistered_users.append(user_id)

    return unregistered_users


if __name__ == '__main__':
    main()
