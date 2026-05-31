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
