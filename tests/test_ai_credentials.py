import base64
import unittest

from cryptography.exceptions import InvalidTag

from mtc_assistant.ai_credentials import (
    CredentialCipher,
    CredentialScope,
    StoredCredential,
    mask_api_key,
)


class AICredentialCipherTest(unittest.TestCase):
    def setUp(self):
        self.key_v1 = b"1" * 32
        self.key_v2 = b"2" * 32
        self.cipher = CredentialCipher({1: self.key_v1, 2: self.key_v2}, current_version=2)
        self.scope = CredentialScope("class", "mtc13", "openai")

    def test_encrypts_and_decrypts_with_scope_bound_aad(self):
        encrypted = self.cipher.encrypt("sk-test-secret", self.scope)

        self.assertNotIn("sk-test-secret", encrypted.ciphertext)
        self.assertEqual(2, encrypted.key_version)
        self.assertEqual("sk-test-secret", self.cipher.decrypt(encrypted, self.scope))

    def test_tampering_or_scope_change_is_rejected(self):
        encrypted = self.cipher.encrypt("sk-test-secret", self.scope)
        raw = bytearray(base64.b64decode(encrypted.ciphertext))
        raw[0] ^= 1
        tampered = StoredCredential(
            ciphertext=base64.b64encode(bytes(raw)).decode("ascii"),
            nonce=encrypted.nonce,
            key_version=encrypted.key_version,
        )

        with self.assertRaises(InvalidTag):
            self.cipher.decrypt(tampered, self.scope)
        with self.assertRaises(InvalidTag):
            self.cipher.decrypt(encrypted, CredentialScope("class", "mtc12", "openai"))
        with self.assertRaises(InvalidTag):
            self.cipher.decrypt(encrypted, CredentialScope("class", "mtc13", "anthropic"))

    def test_masking_never_returns_the_full_key(self):
        self.assertEqual("••••cret", mask_api_key("sk-test-secret"))
        self.assertEqual("••••", mask_api_key("abc"))


if __name__ == "__main__":
    unittest.main()
