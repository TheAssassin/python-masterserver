import json
from collections import namedtuple
from typing import Dict

import bn_crypto


AuthRequest = namedtuple("AuthRequest", ["user_name", "challenge", "expected_answer"])

AuthDBEntry = namedtuple("AuthDBEntry", ["pubkey", "flags"])


class AuthStorage:
    @classmethod
    def get_user(cls, user_name: str):
        try:
            with open("auth.json", "r") as f:
                data = json.load(f)

            user_data = data[user_name]

            try:
                user = AuthDBEntry(user_data["pubkey"], user_data["flags"])
            except KeyError:
                raise ValueError("invalid user format")

            return user

        except IOError:
            raise KeyError("auth db not found")

    @classmethod
    def generate_auth_challenge(cls, user_name: str) -> AuthRequest:
        pubkey = cls.get_user(user_name).pubkey
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
        return "".join(cls.get_user(user_name).flags)
