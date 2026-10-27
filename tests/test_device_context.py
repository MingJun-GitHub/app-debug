import plistlib
import struct
import unittest

from device_context import (
    _decode_ns_keyed_archive,
    parse_android_ab_preferences,
    parse_ios_preferences,
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

    def test_parses_unencrypted_mmkv_value(self):
        key = b"is_dev_environment"
        entry = struct.pack("<I", len(key)) + key + struct.pack("<I", 1) + b"\x01"
        blob = struct.pack("<I", len(entry)) + entry
        self.assertIs(parse_mmkv_value(blob, "is_dev_environment"), True)

    def test_parses_mmkv_string(self):
        key = b"original_SENSOR_ANONYMOUS_ID"
        value = b"anonymous-1"
        entry = struct.pack("<I", len(key)) + key + struct.pack("<I", len(value)) + value
        blob = struct.pack("<I", len(entry)) + entry
        self.assertEqual(parse_mmkv_value(blob, key.decode()), "anonymous-1")


if __name__ == "__main__":
    unittest.main()
