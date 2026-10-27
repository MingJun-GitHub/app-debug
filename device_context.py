"""Best-effort runtime context reader for the installed iOS / Android app.

The debug workspace must not require changes in either mobile project. This
module reads the environment and Sensors ABTest caches that the apps already
write to their private sandboxes.
"""

from __future__ import annotations

import json
import plistlib
import struct
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


IOS_APP_CONTAINER_ID = "com.bloomchic.shopify"
ANDROID_PACKAGE = "com.bloomchic.app"

IOS_PREFERENCES = "Library/Preferences/com.bloomchic.shopify.plist"
IOS_AB_RESULTS = "Library/sensorsanalytics-abtest-SensorsABTestExperimentResultsResponseData.plist"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, tuple, int, float, bool)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _running_app_id(platform: str, udid: str) -> str | None:
    return IOS_APP_CONTAINER_ID if platform == "ios" else ANDROID_PACKAGE


def _decode_ns_keyed_archive(blob: bytes, _depth: int = 0) -> Any:
    """Decode the subset of NSKeyedArchiver used by the Sensors SDK."""
    if _depth > 8:
        return None
    archive = plistlib.loads(blob)
    objects = archive.get("$objects")
    if not isinstance(objects, list):
        return archive

    def class_name(value: dict[str, Any]) -> str:
        class_ref = value.get("$class")
        if not isinstance(class_ref, plistlib.UID):
            return ""
        class_index = class_ref.data
        if not 0 <= class_index < len(objects):
            return ""
        class_object = objects[class_index]
        if not isinstance(class_object, dict):
            return ""
        classes = class_object.get("$classes")
        if isinstance(classes, list) and classes:
            return str(classes[0])
        return str(class_object.get("$classname") or "")

    active: set[int] = set()

    def resolve(value: Any) -> Any:
        if isinstance(value, plistlib.UID):
            index = value.data
            if not 0 <= index < len(objects) or index in active:
                return None
            if index == 0:
                return None
            active.add(index)
            try:
                return resolve(objects[index])
            finally:
                active.discard(index)

        if isinstance(value, dict):
            name = class_name(value)
            if name in ("NSDictionary", "NSMutableDictionary"):
                keys = resolve(value.get("NS.keys", [])) or []
                values = resolve(value.get("NS.objects", [])) or []
                return {
                    str(key): resolve(item)
                    for key, item in zip(keys, values)
                }
            if name in ("NSArray", "NSMutableArray"):
                return resolve(value.get("NS.objects", [])) or []
            if name in ("NSData", "NSMutableData"):
                return resolve(value.get("NS.data"))
            if name in ("NSString", "NSMutableString"):
                return resolve(value.get("NS.string"))
            if name == "NSDate":
                timestamp = value.get("NS.time")
                return timestamp
            if name == "NSUUID":
                return resolve(value.get("NS.uuidbytes"))
            return {
                str(key): resolve(item)
                for key, item in value.items()
                if key != "$class"
            }

        if isinstance(value, list):
            return [resolve(item) for item in value]
        return value

    top = archive.get("$top")
    root = top.get("root") if isinstance(top, dict) else None
    return resolve(root)


def _normalize_group(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return _text(value)


def _experiment_from_dict(
    key: str,
    raw: dict[str, Any],
    *,
    state: str = "in",
    source: str = "sensors_cache",
) -> dict[str, Any]:
    variable = raw.get("variable") if isinstance(raw, dict) else None
    if not isinstance(variable, dict):
        variables = raw.get("variables") if isinstance(raw, dict) else None
        variable = variables[0] if isinstance(variables, list) and variables else {}
    param_name = str(variable.get("paramName") or variable.get("name") or key)
    value = variable.get("value")
    return {
        "key": param_name,
        "group": _normalize_group(value),
        "experimentId": _text(raw.get("experimentId") or raw.get("abtest_experiment_id")),
        "experimentGroupId": _text(raw.get("experimentGroupId") or raw.get("abtest_experiment_group_id")),
        "controlGroup": bool(raw.get("controlGroup") or raw.get("is_control_group")),
        "whiteList": bool(raw.get("whiteList") or raw.get("is_white_list")),
        "state": state,
        "source": source,
    }


def _parse_sensor_payload(
    payload: dict[str, Any],
    *,
    source: str = "sensors_cache",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    experiments: list[dict[str, Any]] = []
    out_experiments: list[dict[str, Any]] = []

    def add_items(raw_items: Any, state: str, target: list[dict[str, Any]]) -> None:
        if isinstance(raw_items, str):
            try:
                raw_items = json.loads(raw_items)
            except json.JSONDecodeError:
                return
        if isinstance(raw_items, dict):
            raw_items = list(raw_items.values())
        if not isinstance(raw_items, list):
            return
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            key = str(
                item.get("abtest_unique_id")
                or item.get("abtest_experiment_id")
                or "unknown"
            )
            row = _experiment_from_dict(key, item, state=state, source=source)
            if row["key"] and row["group"]:
                target.append(row)

    add_items(payload.get("results") or payload.get("experiments"), "in", experiments)
    add_items(
        payload.get("outResults") or payload.get("out_results") or payload.get("outList"),
        "out",
        out_experiments,
    )
    identifier = _text(payload.get("identifier") or payload.get("distinctId"))
    return experiments, out_experiments, identifier


def parse_sensor_ab_json(raw: str, *, source: str = "sensors_cache") -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return {"experiments": [], "outExperiments": [], "distinctId": ""}
    experiments, out_experiments, identifier = _parse_sensor_payload(payload, source=source)
    return {
        "experiments": experiments,
        "outExperiments": out_experiments,
        "distinctId": identifier,
    }


def parse_ios_ab_archive(blob: bytes) -> dict[str, Any]:
    outer = _decode_ns_keyed_archive(blob)
    if not isinstance(outer, bytes):
        return {"experiments": [], "outExperiments": [], "distinctId": ""}

    root = _decode_ns_keyed_archive(outer)
    if not isinstance(root, dict):
        return {"experiments": [], "outExperiments": [], "distinctId": ""}

    experiments: list[dict[str, Any]] = []
    out_experiments: list[dict[str, Any]] = []

    results = root.get("results")
    if isinstance(results, dict):
        for key, raw in results.items():
            if isinstance(raw, dict):
                row = _experiment_from_dict(str(key), raw)
                if row["group"]:
                    experiments.append(row)

    out_results = root.get("outResults")
    if isinstance(out_results, dict):
        for key, raw in out_results.items():
            if isinstance(raw, dict):
                row = _experiment_from_dict(str(key), raw, state="out")
                if row["group"]:
                    out_experiments.append(row)

    response_object = root.get("responseObject")
    if isinstance(response_object, dict):
        fallback_in, fallback_out, _ = _parse_sensor_payload(response_object)
        if not experiments:
            experiments = fallback_in
        if not out_experiments:
            out_experiments = fallback_out

    identity = root.get("userIdenty")
    if not isinstance(identity, dict):
        identity = {}
    distinct_id = _text(identity.get("distinctId"))
    if not distinct_id and isinstance(response_object, dict):
        distinct_id = _text(response_object.get("identifier"))

    return {
        "experiments": experiments,
        "outExperiments": out_experiments,
        "distinctId": distinct_id,
        "anonymousId": _text(identity.get("anonymousId")),
    }


def parse_ios_preferences(blob: bytes) -> dict[str, Any]:
    values = plistlib.loads(blob)
    site = ""
    for key, label in (
        ("isUsSiteEnabled", "Shopify-US"),
        ("isUkSiteEnabled", "Shopify-UK"),
        ("isEuSiteEnabled", "Shopify-EU"),
        ("isAuSiteEnabled", "Shopify-AU"),
    ):
        if values.get(key) is True:
            site = label
            break
    return {
        "environment": "test" if values.get("isDebugUrlEnabled") is True else "production",
        "deviceId": _text(values.get("sensorAnonymousId")),
        "distinctId": _text(values.get("sab_distinctId")),
        "site": site,
        "country": _text(values.get("BCPrivacyRegion")),
    }


def _run(command: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        errors="replace",
    )


def _copy_ios_file(udid: str, source: str, destination: Path) -> str | None:
    try:
        result = _run(
            [
                "xcrun",
                "devicectl",
                "device",
                "copy",
                "from",
                "--device",
                udid,
                "--domain-type",
                "appDataContainer",
                "--domain-identifier",
                IOS_APP_CONTAINER_ID,
                "--source",
                source,
                "--destination",
                str(destination),
            ],
            timeout=35,
        )
        if result.returncode != 0 or not destination.exists():
            message = " ".join((result.stderr or result.stdout).split())
            return f"无法读取 iOS 文件 {source}: {message[-320:]}"
        return None
    except Exception as exc:  # noqa: BLE001
        return f"无法读取 iOS 文件 {source}: {exc}"


def read_ios_app_context(udid: str) -> dict[str, Any]:
    warnings: list[str] = []
    prefs: dict[str, Any] = {}
    ab_data: dict[str, Any] = {}
    timestamps: list[float] = []

    with tempfile.TemporaryDirectory(prefix="app-debug-ios-") as temp_dir:
        temp = Path(temp_dir)
        preferences_path = temp / "preferences.plist"
        ab_path = temp / "ab-results.plist"

        warning = _copy_ios_file(udid, IOS_PREFERENCES, preferences_path)
        if warning:
            warnings.append(warning)
        else:
            try:
                prefs = parse_ios_preferences(preferences_path.read_bytes())
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"iOS UserDefaults 解析失败: {exc}")

        warning = _copy_ios_file(udid, IOS_AB_RESULTS, ab_path)
        if warning:
            warnings.append(warning)
        else:
            try:
                ab_data = parse_ios_ab_archive(ab_path.read_bytes())
                timestamps.append(ab_path.stat().st_mtime)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"iOS AB 缓存解析失败: {exc}")

    experiments = ab_data.get("experiments") or []
    out_experiments = ab_data.get("outExperiments") or []
    available = bool(prefs or experiments or out_experiments)
    return {
        "available": available,
        "appId": IOS_APP_CONTAINER_ID,
        "environment": {
            "name": prefs.get("environment") or "unknown",
            "site": prefs.get("site") or "",
            "country": prefs.get("country") or "",
        },
        "ids": {
            "deviceId": prefs.get("deviceId") or ab_data.get("anonymousId") or "",
            "distinctId": prefs.get("distinctId") or ab_data.get("distinctId") or "",
        },
        "experiments": experiments,
        "outExperiments": out_experiments,
        "snapshotAt": (
            datetime.fromtimestamp(max(timestamps), timezone.utc).astimezone().isoformat(timespec="seconds")
            if timestamps
            else None
        ),
        "warnings": warnings,
    }


def _adb_package_output(serial: str, arguments: list[str], *, timeout: int = 20) -> bytes:
    result = subprocess.run(
        ["adb", "-s", serial, "exec-out", "run-as", ANDROID_PACKAGE, *arguments],
        capture_output=True,
        timeout=timeout,
    )
    return result.stdout if result.returncode == 0 else b""


def parse_android_ab_preferences(blob: bytes) -> dict[str, Any]:
    root = ElementTree.fromstring(blob)
    raw_value = ""
    for node in root:
        if node.tag != "string":
            continue
        if node.attrib.get("name") == "key_experiment_with_distinct_id":
            raw_value = node.text or ""
            break
    if not raw_value:
        return {"experiments": [], "outExperiments": [], "distinctId": ""}
    return parse_sensor_ab_json(raw_value)


def parse_mmkv_value(blob: bytes, key: str) -> Any:
    """Extract a plain scalar/string value from an unencrypted MMKV container."""
    key_bytes = key.encode("utf-8")
    start = 0
    while True:
        position = blob.find(key_bytes, start)
        if position < 0:
            return None
        start = position + 1
        if position < 4:
            continue
        key_length = struct.unpack_from("<I", blob, position - 4)[0]
        if key_length != len(key_bytes):
            continue
        value_header = position + len(key_bytes)
        if value_header + 4 > len(blob):
            continue
        value_length = struct.unpack_from("<I", blob, value_header)[0]
        if value_length > 10 * 1024 * 1024:
            continue
        value_start = value_header + 4
        value_end = value_start + value_length
        if value_end > len(blob):
            continue
        payload = blob[value_start:value_end]
        if not payload:
            return ""
        if len(payload) == 1 and payload[0] in (0, 1):
            return bool(payload[0])
        try:
            return payload.rstrip(b"\x00").decode("utf-8")
        except UnicodeDecodeError:
            return payload


def _mmkv_string(blob: bytes, key: str) -> str:
    value = parse_mmkv_value(blob, key)
    return value if isinstance(value, str) else ""


def read_android_app_context(serial: str) -> dict[str, Any]:
    warnings: list[str] = []
    prefs: dict[str, Any] = {}
    ab_data: dict[str, Any] = {}
    mmkv_values: list[bytes] = []

    shared_prefs = _adb_package_output(serial, ["cat", "shared_prefs/spUtils.xml"])
    if shared_prefs:
        try:
            ab_data = parse_android_ab_preferences(shared_prefs)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Android AB 缓存解析失败: {exc}")
    else:
        warnings.append("无法读取 Android AB 缓存，确认当前安装的是 Debug 包且已启动过 App。")

    listing = _adb_package_output(serial, ["ls", "-1", "files/mmkv"])
    for filename in listing.decode("utf-8", errors="replace").splitlines():
        filename = filename.strip()
        if not filename or filename.endswith(".crc"):
            continue
        try:
            blob = _adb_package_output(serial, ["cat", f"files/mmkv/{filename}"])
            if blob:
                mmkv_values.append(blob)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"无法读取 MMKV {filename}: {exc}")

    if mmkv_values:
        environment_values = [
            parse_mmkv_value(blob, "is_dev_environment")
            for blob in mmkv_values
        ]
        device_ids = [
            _mmkv_string(blob, "original_SENSOR_ANONYMOUS_ID")
            for blob in mmkv_values
        ]
        production_site = next(
            (_mmkv_string(blob, "test_cur_site_config_data") for blob in mmkv_values if _mmkv_string(blob, "test_cur_site_config_data")),
            "",
        )
        test_site = next(
            (_mmkv_string(blob, "cur_site_config_data") for blob in mmkv_values if _mmkv_string(blob, "cur_site_config_data")),
            "",
        )
        environment_flag = next(
            (value for value in environment_values if isinstance(value, bool)),
            None,
        )
        raw_site = test_site if environment_flag is True else production_site
        try:
            site = json.loads(raw_site) if raw_site else {}
        except json.JSONDecodeError:
            site = {}
        prefs = {
            "environment": (
                "test" if environment_flag is True
                else "production" if environment_flag is False
                else "unknown"
            ),
            "deviceId": next((item for item in device_ids if item), ""),
            "site": _text(site.get("show_name") or site.get("site_code")),
            "country": _text(site.get("country_code") or site.get("main_country_code")),
        }
    else:
        warnings.append("无法读取 Android MMKV，环境和 App 设备 ID 可能不可用。")

    experiments = ab_data.get("experiments") or []
    out_experiments = ab_data.get("outExperiments") or []
    available = bool(prefs or experiments or out_experiments)
    return {
        "available": available,
        "appId": ANDROID_PACKAGE,
        "environment": {
            "name": prefs.get("environment") or "unknown",
            "site": prefs.get("site") or "",
            "country": prefs.get("country") or "",
        },
        "ids": {
            "deviceId": prefs.get("deviceId") or "",
            "distinctId": ab_data.get("distinctId") or "",
        },
        "experiments": experiments,
        "outExperiments": out_experiments,
        "snapshotAt": now_iso() if available else None,
        "warnings": warnings,
    }


def read_app_context(platform: str, udid: str) -> dict[str, Any]:
    if not udid:
        return {
            "available": False,
            "appId": _running_app_id(platform, udid) or "",
            "environment": {"name": "unknown", "site": "", "country": ""},
            "ids": {"deviceId": "", "distinctId": ""},
            "experiments": [],
            "outExperiments": [],
            "snapshotAt": None,
            "warnings": ["设备未连接。"],
        }
    try:
        if platform == "ios":
            return read_ios_app_context(udid)
        return read_android_app_context(udid)
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "appId": _running_app_id(platform, udid) or "",
            "environment": {"name": "unknown", "site": "", "country": ""},
            "ids": {"deviceId": "", "distinctId": ""},
            "experiments": [],
            "outExperiments": [],
            "snapshotAt": None,
            "warnings": [f"读取 App 上下文失败: {exc}"],
        }
