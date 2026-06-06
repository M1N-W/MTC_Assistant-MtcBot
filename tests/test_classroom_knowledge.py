import unittest

import mtc_assistant.classroom_knowledge as classroom_knowledge
import mtc_assistant.features as features
from mtc_assistant.config import Bio_LINK, Physic_LINK


class ClassroomKnowledgeTest(unittest.TestCase):
    def setUp(self):
        self.primary_client = features.gemini_client_primary
        self.primary_model = features.gemini_model_primary
        self.fallback_client = features.gemini_client_fallback
        self.fallback_model = features.gemini_model_fallback
        features.gemini_client_primary = None
        features.gemini_model_primary = None
        features.gemini_client_fallback = None
        features.gemini_model_fallback = None

    def tearDown(self):
        features.gemini_client_primary = self.primary_client
        features.gemini_model_primary = self.primary_model
        features.gemini_client_fallback = self.fallback_client
        features.gemini_model_fallback = self.fallback_model

    def test_knowledge_base_does_not_embed_legacy_science_urls(self):
        knowledge_text = "\n".join(chunk.text for chunk in classroom_knowledge.KNOWLEDGE_BASE)

        self.assertNotIn(Bio_LINK, knowledge_text)
        self.assertNotIn(Physic_LINK, knowledge_text)

    def test_science_resource_answer_does_not_return_legacy_urls(self):
        answer = classroom_knowledge.answer_classroom_question("ถามเอกสาร ชีวะ ฟิสิกส์")

        self.assertNotIn(Bio_LINK, answer)
        self.assertNotIn(Physic_LINK, answer)
        self.assertIn("learning resources", answer.lower())


if __name__ == "__main__":
    unittest.main()
