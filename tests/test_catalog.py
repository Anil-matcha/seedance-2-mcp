import unittest

from server_core import TOOLS, build_request


class Seedance2CatalogTests(unittest.TestCase):
    def test_catalog_is_focused(self):
        names = {tool["name"] for tool in TOOLS}
        self.assertEqual(
            names,
            {
                "seedance_2_text_to_video",
                "seedance_2_image_to_video",
                "seedance_2_first_last_frame",
                "seedance_2_omni_reference",
                "muapi_predict_result",
                "muapi_account_balance",
            },
        )

    def test_fast_quality_selects_allowlisted_endpoint(self):
        endpoint, payload = build_request(
            "seedance_2_text_to_video",
            {"prompt": "A paper boat on a stream", "quality": "fast"},
        )
        self.assertEqual(endpoint, "seedance-2-text-to-video-fast")
        self.assertNotIn("quality", payload)

    def test_image_generation_requires_a_reference(self):
        with self.assertRaises(ValueError):
            build_request("seedance_2_image_to_video", {"prompt": "Animate it"})


if __name__ == "__main__":
    unittest.main()
