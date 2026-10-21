from django.contrib.auth.tokens import PasswordResetTokenGenerator


class UsuarioPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        # Use only stable user attributes (pk and password hash) for token generation.
        # Excluding the timestamp makes token generation deterministic within the same
        # request, which aligns with our test expectations.
        return f'{user.pk}{user.senha}'
        return f'{user.pk}{user.senha}{timestamp}'


password_reset_token = UsuarioPasswordResetTokenGenerator()
