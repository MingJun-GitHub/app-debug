import unittest

import server


class PageLinkTests(unittest.TestCase):
    def test_h5_link_builds_universal_and_deep_link(self):
        result = server.resolve_page_links(
            "https://www.bloomchic.com/products/sample-product?color=red#reviews"
        )

        self.assertEqual(result["siteHost"], "bloomchic.com")
        self.assertEqual(result["deepLinkHost"], "app")
        values = {item["kind"]: item["value"] for item in result["targets"]}
        self.assertEqual(
            values["universal"],
            "https://www.bloomchic.com/products/sample-product?color=red#reviews",
        )
        self.assertEqual(
            values["deeplink"],
            "bloomchic://app/products/sample-product?color=red#reviews",
        )

    def test_uk_h5_maps_to_uk_app_host(self):
        result = server.resolve_page_links("https://www.bloomchic.co.uk/pages/landing")

        self.assertEqual(result["deepLinkHost"], "app.uk")
        values = {item["kind"]: item["value"] for item in result["targets"]}
        self.assertEqual(
            values["deeplink"],
            "bloomchic://app.uk/pages/landing",
        )

    def test_deep_link_can_be_reversed_to_h5(self):
        result = server.resolve_page_links("bloomchic://app.au/collections/sale")

        values = {item["kind"]: item["value"] for item in result["targets"]}
        self.assertEqual(
            values["universal"],
            "https://au.bloomchic.com/collections/sale",
        )

    def test_us_and_uk_deep_links_use_canonical_domains(self):
        us = server.resolve_page_links("bloomchic://app/orders")
        uk = server.resolve_page_links("bloomchic://app.uk/orders")

        us_values = {item["kind"]: item["value"] for item in us["targets"]}
        uk_values = {item["kind"]: item["value"] for item in uk["targets"]}
        self.assertEqual(us_values["universal"], "https://bloomchic.com/orders")
        self.assertEqual(uk_values["universal"], "https://bloomchic.co.uk/orders")

    def test_aggregator_only_produces_universal_link(self):
        result = server.resolve_page_links("https://bloomchic.page.link/example")

        kinds = {item["kind"] for item in result["targets"]}
        self.assertIn("universal", kinds)
        self.assertNotIn("deeplink", kinds)

    def test_rejects_unsafe_scheme(self):
        with self.assertRaises(ValueError):
            server.resolve_page_links("javascript:alert(1)")


if __name__ == "__main__":
    unittest.main()
