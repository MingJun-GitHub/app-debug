import base64
import json
import plistlib
import unittest

from device_context import (
    _decode_ns_keyed_archive,
    parse_android_ab_preferences,
    parse_android_sensor_identity,
    parse_ios_ab_archive,
    parse_ios_preferences,
    parse_ios_sensor_distinct_id,
    parse_mmkv_value,
    parse_sensor_ab_json,
)


def archive(objects, root=1):
    return plistlib.dumps({
        "$archiver": "NSKeyedArchiver",
        "$version": 100000,
        "$top": {"root": plistlib.UID(root)},
        "$objects": objects,
    }, fmt=plistlib.FMT_BINARY)


def archived_data(blob):
    return archive([
        "$null",
        {
            "$class": plistlib.UID(2),
            "NS.data": blob,
        },
        {"$classes": ["NSData", "NSObject"]},
    ])


def varint(value):
    encoded = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            encoded.append(byte | 0x80)
        else:
            encoded.append(byte)
            return bytes(encoded)


class DeviceContextTest(unittest.TestCase):
    def test_decodes_ns_keyed_dictionary(self):
        blob = archive([
            "$null",
            {
                "$class": plistlib.UID(2),
                "NS.keys": plistlib.UID(3),
                "NS.objects": plistlib.UID(4),
            },
            {"$classes": ["NSDictionary", "NSObject"]},
            [plistlib.UID(5)],
            [plistlib.UID(6)],
            "key",
            "value",
        ])
        self.assertEqual(_decode_ns_keyed_archive(blob), {"key": "value"})

    def test_parses_android_ab_preferences(self):
        payload = (
            '{"identifier":"distinct-1","experiments":"[{\\"abtest_experiment_id\\":\\"42\\",'
            '\\"variables\\":[{\\"name\\":\\"home_page\\",\\"value\\":\\"B\\"}]}]"}'
        )
        xml = (
            '<?xml version="1.0" encoding="utf-8" standalone="yes" ?>'
            '<map><string name="key_experiment_with_distinct_id">'
            f'{payload.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")}'
            '</string></map>'
        ).encode()
        parsed = parse_android_ab_preferences(xml)
        self.assertEqual(parsed["distinctId"], "distinct-1")
        self.assertEqual(parsed["experiments"][0]["key"], "home_page")
        self.assertEqual(parsed["experiments"][0]["group"], "B")

    def test_parses_sensor_payload(self):
        parsed = parse_sensor_ab_json(
            '{"identifier":"abc","experiments":[{"abtest_experiment_id":"1",'
            '"variables":[{"name":"look_ab","value":"A"}]}]}'
        )
        self.assertEqual(parsed["distinctId"], "abc")
        self.assertEqual(parsed["experiments"][0]["key"], "look_ab")
        self.assertEqual(parsed["experiments"][0]["group"], "A")

    def test_parses_sensor_out_list(self):
        parsed = parse_sensor_ab_json(
            '{"out_list":[{"abtest_experiment_id":"2",'
            '"variables":[{"name":"old_experiment"}]}]}'
        )
        self.assertEqual(parsed["outExperiments"][0]["key"], "old_experiment")
        self.assertEqual(parsed["outExperiments"][0]["group"], "")

    def test_parses_ios_preferences(self):
        parsed = parse_ios_preferences(plistlib.dumps({
            "isDebugUrlEnabled": True,
            "isUsSiteEnabled": True,
            "sensorAnonymousId": "device-1",
            "BCPrivacyRegion": "US",
        }))
        self.assertEqual(parsed["environment"], "test")
        self.assertEqual(parsed["deviceId"], "device-1")
        self.assertEqual(parsed["site"], "Shopify-US")

    def test_parses_ios_site_from_persistent_site_config(self):
        site_config = json.dumps({
            "show_name": "Shopify-UK",
            "site_code": "SPUK",
            "shopify_access_token": "must-not-be-returned",
        })
        site_archive = archive(["$null", site_config])
        parsed = parse_ios_preferences(plistlib.dumps({
            "bc.persistent.BCSiteConfigTable.CurUserSelectSiteConfig": site_archive,
        }))
        self.assertEqual(parsed["site"], "Shopify-UK")

    def test_parses_ios_sensor_distinct_id_archive(self):
        blob = archive(["$null", "distinct-1"])
        self.assertEqual(parse_ios_sensor_distinct_id(blob), "distinct-1")

    def test_parses_ios_ab_results_and_out_results(self):
        inner = archive([
            "$null",
            {
                "$class": plistlib.UID(2),
                "results": plistlib.UID(3),
                "outResults": plistlib.UID(11),
                "responseObject": plistlib.UID(15),
                "userIdenty": plistlib.UID(16),
            },
            {"$classes": ["SABFetchResultResponse", "NSObject"]},
            {
                "$class": plistlib.UID(4),
                "NS.keys": plistlib.UID(5),
                "NS.objects": plistlib.UID(6),
            },
            {"$classes": ["NSDictionary", "NSObject"]},
            ["home_page"],
            [plistlib.UID(7)],
            {
                "$class": plistlib.UID(8),
                "experimentId": "42",
                "experimentGroupId": "7",
                "variable": plistlib.UID(9),
            },
            {"$classes": ["SABExperimentResult", "NSObject"]},
            {
                "$class": plistlib.UID(10),
                "paramName": "home_page",
                "value": "B",
            },
            {"$classes": ["SABExperimentResultVariable", "NSObject"]},
            {
                "$class": plistlib.UID(4),
                "NS.keys": ["old_experiment"],
                "NS.objects": [plistlib.UID(12)],
            },
            {
                "$class": plistlib.UID(8),
                "experimentId": "41",
                "variable": plistlib.UID(14),
            },
            "$null",
            {
                "$class": plistlib.UID(10),
                "paramName": "old_experiment",
            },
            {
                "$class": plistlib.UID(4),
                "NS.keys": [],
                "NS.objects": [],
            },
            {
                "$class": plistlib.UID(17),
                "distinctId": "distinct-1",
                "anonymousId": "anonymous-1",
            },
            {"$classes": ["SABUserIdenty", "NSObject"]},
        ])
        parsed = parse_ios_ab_archive(archived_data(inner))
        self.assertEqual(parsed["distinctId"], "distinct-1")
        self.assertEqual(parsed["anonymousId"], "anonymous-1")
        self.assertEqual(parsed["experiments"][0]["key"], "home_page")
        self.assertEqual(parsed["experiments"][0]["group"], "B")
        self.assertEqual(parsed["experiments"][0]["experimentId"], "42")
        self.assertEqual(parsed["outExperiments"][0]["key"], "old_experiment")
        self.assertEqual(parsed["outExperiments"][0]["group"], "")

    def test_parses_unencrypted_mmkv_value(self):
        key = b"is_dev_environment"
        entry = varint(len(key)) + key + varint(1) + b"\x01"
        blob = varint(len(entry)) + entry
        self.assertIs(parse_mmkv_value(blob, "is_dev_environment"), True)

    def test_parses_mmkv_string(self):
        key = b"original_SENSOR_ANONYMOUS_ID"
        value = b"anonymous-1"
        payload = varint(len(value)) + value
        entry = varint(len(key)) + key + varint(len(payload)) + payload
        blob = varint(len(entry)) + entry
        self.assertEqual(parse_mmkv_value(blob, key.decode()), "anonymous-1")

    def test_parses_android_sensor_identity(self):
        identity = json.dumps({"$identity_android_id": "device-1"}).encode()
        encoded = base64.b64encode(identity).decode()
        xml = (
            "<map>"
            '<string name="events_distinct_id">SPUK_device-1</string>'
            f'<string name="user_ids">Base64:{encoded}</string>'
            "</map>"
        ).encode()
        parsed = parse_android_sensor_identity(xml)
        self.assertEqual(parsed["deviceId"], "device-1")
        self.assertEqual(parsed["distinctId"], "SPUK_device-1")


if __name__ == "__main__":
    unittest.main()
