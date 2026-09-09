import unittest

from backend.database import DEVELOPMENT_LANGUAGES, FIRMWARE_TARGETS
from backend.tutorial_curriculum import (
    COMMON_LANGUAGE_MODULES,
    EMBEDDED_CORE_MODULES,
    FIRMWARE_TARGET_SPECIALISATIONS,
    LANGUAGE_SPECIALISATIONS,
    VISUALIZATION_POLICY,
    firmware_curriculum,
    language_curriculum,
    missing_firmware_curricula,
    missing_language_curricula,
)


class TutorialCurriculumTestCase(unittest.TestCase):
    def test_every_development_language_has_a_complete_curriculum(self):
        self.assertEqual(missing_language_curricula(set(DEVELOPMENT_LANGUAGES)), set())
        common_ids = {module["id"] for module in COMMON_LANGUAGE_MODULES}
        for code in DEVELOPMENT_LANGUAGES:
            curriculum = language_curriculum(code)
            module_ids = {module["id"] for module in curriculum["modules"]}
            self.assertTrue(common_ids <= module_ids)
            self.assertGreaterEqual(len(curriculum["modules"]), len(COMMON_LANGUAGE_MODULES) + 3)
            self.assertTrue(all(module["subtopics"] for module in curriculum["modules"]))
            self._assert_valid_visualizations(curriculum)

    def test_every_firmware_target_has_embedded_core_and_target_specific_coverage(self):
        self.assertEqual(missing_firmware_curricula(set(FIRMWARE_TARGETS)), set())
        embedded_ids = {module["id"] for module in EMBEDDED_CORE_MODULES}
        for target_id in FIRMWARE_TARGETS:
            curriculum = firmware_curriculum(target_id)
            module_ids = {module["id"] for module in curriculum["modules"]}
            self.assertTrue(embedded_ids <= module_ids)
            self.assertGreaterEqual(len(curriculum["modules"]), len(EMBEDDED_CORE_MODULES) + 2)
            self.assertTrue(all(module["subtopics"] for module in curriculum["modules"]))
            self._assert_valid_visualizations(curriculum)

    def test_all_planned_curricula_have_useful_visualization_candidates(self):
        for code in LANGUAGE_SPECIALISATIONS:
            self._assert_valid_visualizations(language_curriculum(code))
        for target_id in FIRMWARE_TARGET_SPECIALISATIONS:
            self._assert_valid_visualizations(firmware_curriculum(target_id))

    def test_visualization_policy_requires_an_accessible_nonanimated_explanation(self):
        requirements = VISUALIZATION_POLICY["requirements"]
        self.assertTrue(any("textovú a tabuľkovú alternatívu" in item for item in requirements))
        self.assertTrue(any("nesmie spúšťať sama" in item for item in requirements))
        self.assertGreaterEqual(len(VISUALIZATION_POLICY["notUsefulFor"]), 3)

    def _assert_valid_visualizations(self, curriculum):
        module_ids = {module["id"] for module in curriculum["modules"]}
        visualizations = curriculum["visualizations"]
        self.assertTrue(visualizations)
        self.assertEqual(len(visualizations), len({item["id"] for item in visualizations}))
        for visualization in visualizations:
            self.assertTrue(module_ids >= {visualization["moduleId"]})
            self.assertTrue(all(visualization[key] for key in ("kind", "title", "purpose")))
