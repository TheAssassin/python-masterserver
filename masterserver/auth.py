from collections import namedtuple
from typing import Dict

import bn_crypto


AuthRequest = namedtuple("AuthRequest", ["user_name", "challenge", "expected_answer"])

AuthDBEntry = namedtuple("AuthDBEntry", ["pubkey", "flags"])


class AuthStorage:
    # users to auth pubkeys map
    _users: Dict[str, AuthDBEntry] = {}

    @classmethod
    def generate_auth_challenge(cls, user_name: str) -> AuthRequest:
        pubkey = cls._users[user_name].pubkey
        challenge, expected_answer = bn_crypto.generate_auth_challenge(pubkey)
        return AuthRequest(user_name, challenge, expected_answer)

    @staticmethod
    def validate_auth_reply(reply: str, auth_request: AuthRequest):
        reply_num = int(reply, 16)

        # for some reason, the challenge answers are unsigned
        # until the reason has been figured out, we do an unsigned comparison
        expected_answer_num = abs(int(auth_request.expected_answer, 16))

        return reply_num == expected_answer_num

    @classmethod
    def get_user_flags(cls, user_name: str):
        return "".join(cls._users[user_name].flags)
