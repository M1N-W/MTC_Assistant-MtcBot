import unittest

from scripts.seed_class_registry import build_seed_operations


class SeedClassRegistryTest(unittest.TestCase):
    def test_builds_idempotent_registry_and_metadata_operations(self):
        operations = build_seed_operations()
        paths = {operation.path for operation in operations}

        self.assertIn("system/class_registry/mtc12/main", paths)
        self.assertIn("system/class_registry/mtc13/main", paths)
        self.assertIn("classes/mtc12/metadata/main", paths)
        self.assertIn("classes/mtc13/metadata/main", paths)
        self.assertIn("classes/mtc12/terms/2569-t1/metadata/main", paths)
        self.assertIn("classes/mtc12/terms/2569-t1/config/timetable", paths)
        self.assertIn("classes/mtc13/terms/2569-t1/config/timetable", paths)
        self.assertTrue(all(operation.merge for operation in operations))

    def test_mtc13_timetable_seed_shape_is_valid(self):
        operations = build_seed_operations()
        timetable = next(
            operation.data
            for operation in operations
            if operation.path == "classes/mtc13/terms/2569-t1/config/timetable"
        )

        self.assertEqual("Asia/Bangkok", timetable["timezone"])
        self.assertIn("0", timetable["days"])
        self.assertEqual("คอมพิวเตอร์ (ครูจินดาพร)", timetable["days"]["0"][0]["subject"])
        self.assertEqual("221", timetable["days"]["0"][0]["room"])
        self.assertEqual(
            "https://img2.pic.in.th/SaveClip.App_702397967_18144615751449592_1572400629043110676_n.jpg",
            timetable["image_url"],
        )
        self.assertTrue(all(isinstance(key, str) for key in timetable["days"]))

    def test_mtc12_timetable_seed_includes_image_url(self):
        operations = build_seed_operations()
        timetable = next(
            operation.data
            for operation in operations
            if operation.path == "classes/mtc12/terms/2569-t1/config/timetable"
        )

        self.assertEqual("https://img2.pic.in.th/186308.jpg", timetable["image_url"])

    def test_mtc11_timetable_seed_includes_reviewed_https_image_url(self):
        operations = build_seed_operations()
        timetable = next(
            operation.data
            for operation in operations
            if operation.path == "classes/mtc11/terms/2569-t1/config/timetable"
        )

        self.assertEqual("https://img2.pic.in.th/290922.jpg", timetable["image_url"])
        self.assertTrue(timetable["image_url"].startswith("https://"))

    def test_mtc11_registry_seed_includes_verified_term_and_timetable_data(self):
        operations = build_seed_operations()
        paths = {operation.path for operation in operations}

        self.assertIn("system/class_registry/mtc11/main", paths)
        self.assertIn("classes/mtc11/metadata/main", paths)
        self.assertIn("classes/mtc11/terms/2569-t1/metadata/main", paths)
        self.assertIn("classes/mtc11/terms/2569-t1/config/timetable", paths)
        self.assertNotIn("classes/mtc11/terms/2569-t1/config/links", paths)

        registry = next(
            operation.data
            for operation in operations
            if operation.path == "system/class_registry/mtc11/main"
        )
        self.assertEqual("MTC11", registry["display_name"])
        self.assertEqual("m6", registry["grade_level"])
        self.assertEqual("2569-t1", registry["active_term_id"])
        self.assertEqual("ม.6/2", registry["room_label"])

        timetable = next(
            operation.data
            for operation in operations
            if operation.path == "classes/mtc11/terms/2569-t1/config/timetable"
        )
        self.assertEqual("Asia/Bangkok", timetable["timezone"])
        self.assertEqual({"0", "1", "2", "3", "4"}, set(timetable["days"]))
        monday_period_2 = timetable["days"]["0"][1]
        friday_period_1 = timetable["days"]["4"][0]
        self.assertEqual("09:25", monday_period_2["start"])
        self.assertEqual("10:20", monday_period_2["end"])
        self.assertEqual("ค33101 · ครูทักษิณ", monday_period_2["subject"])
        self.assertEqual("634", monday_period_2["room"])
        self.assertEqual("ค33101 · ครูทักษิณ", friday_period_1["subject"])
        self.assertTrue(all("." not in period["start"] and "." not in period["end"] for periods in timetable["days"].values() for period in periods))
        self.assertTrue(all(period["subject"] for periods in timetable["days"].values() for period in periods))
        self.assertEqual("พัก", timetable["days"]["0"][4]["subject"])
        self.assertEqual("-", timetable["days"]["0"][4]["room"])

    def test_invites_are_only_seeded_from_explicit_cli_input(self):
        default_operations = build_seed_operations()
        invited_operations = build_seed_operations(["mtc13=TEST_MTC13"])

        self.assertFalse(any(path.path.startswith("class_invites/") for path in default_operations))
        self.assertTrue(any(path.path == "class_invites/TEST_MTC13" for path in invited_operations))

    def test_invalid_invite_args_are_rejected(self):
        with self.assertRaises(ValueError):
            build_seed_operations(["mtc13=bad/secret"])

        with self.assertRaises(ValueError):
            build_seed_operations(["mtc99=TEST_MTC99"])


if __name__ == "__main__":
    unittest.main()
