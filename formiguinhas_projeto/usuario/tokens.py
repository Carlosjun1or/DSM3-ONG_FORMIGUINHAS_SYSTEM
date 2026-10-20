from django.contrib.auth.tokens import PasswordResetTokenGenerator


class UsuarioPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f'{user.pk}{user.senha}{timestamp}'


password_reset_token = UsuarioPasswordResetTokenGenerator()
