import argparse
import ast
import csv
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger: logging.Logger = logging.getLogger("csv_recursive_field_extractor")

# MODIFY THIS BLOCK: extend FIELDS_RAW with the new fields
FIELDS_RAW: List[str] = [
    "org_id",
    "announcement_language",
    "name",
    "preferred_language",
    "time_zone",
    "address1",
    "city",
    "state",
    "postal_code",
    "country",
    "location_id",
    "premise_route_type",
    "premise_route_id",
    "phone_numbers_1",
    "phone_numbers_2",
    "phone_numbers_3",
    "number_type",
    "number_usage_type",
    "state",
    "phone_number",
    "enable_unknown_extension_route_policy",
    "id",
    "action",
    "call_type",
    "transfer_enabled",
    "email",
    "emails",
    "licenses_id",
    "person_id",
    "use_custom_enabled",
    "use_custom_permissions",
    "display_name",
    "workspace_location_id",
    "webex_calling",
    "extension",
    "primary",
    "direct_number",
    "enabled",
    "destination",
    "rg_id",
    "route_identity",
    "route_type",
    "calling_data",
    "entity_id",
    "group_id",
    "workspace_id",
    "floor_id",
    "first_name",           # NEW
    "last_name",            # NEW
    "licenses",             # NEW
    "legacy_phone_number",  # NEW
    "license_ids",      # NEW
]



def dedupe_preserve_order(items: Sequence[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


FIELDS: List[str] = dedupe_preserve_order(FIELDS_RAW)


def snake_to_camel(snake_key: str) -> str:
    parts: List[str] = [p for p in snake_key.split("_") if p]
    if not parts:
        return snake_key
    first: str = parts[0]
    rest: str = "".join(p[:1].upper() + p[1:] for p in parts[1:])
    return f"{first}{rest}"


def snake_to_pascal(snake_key: str) -> str:
    parts: List[str] = [p for p in snake_key.split("_") if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


# MODIFY THIS FUNCTION: add explicit candidate aliases for the new fields
def build_candidate_keys(field_name: str) -> Tuple[str, ...]:
    candidates: List[str] = []

    candidates.append(field_name)
    candidates.append(field_name.lower())
    candidates.append(field_name.upper())

    camel: str = snake_to_camel(field_name)
    pascal: str = snake_to_pascal(field_name)

    candidates.append(camel)
    candidates.append(pascal)
    candidates.append(camel.lower())
    candidates.append(pascal.lower())

    no_underscore: str = field_name.replace("_", "")
    candidates.append(no_underscore)
    candidates.append(no_underscore.lower())

    if field_name.startswith("phone_numbers_"):
        try:
            idx: int = int(field_name.rsplit("_", 1)[1])
            candidates.append(f"phoneNumbers-{idx}")
            candidates.append(f"phone_numbers-{idx}")
            candidates.append(f"phoneNumbers_{idx}")
            candidates.append(f"phoneNumbers{idx}")
        except Exception:
            pass

    if field_name in {"licenses_id", "person_id", "workspace_id", "group_id", "floor_id"}:
        base: str = field_name.rsplit("_", 1)[0]
        candidates.append(f"{snake_to_camel(base)}Id")
        candidates.append(f"{snake_to_pascal(base)}Id")
        candidates.append(f"{base}Id")
        candidates.append(f"{base}ID")

    if field_name == "org_id":
        candidates.extend(["orgId", "OrgId", "ORG_ID", "orgID", "OrgID"])

    if field_name == "location_id":
        candidates.extend(["locationId", "LocationId", "locationID", "LocationID"])

    if field_name == "workspace_location_id":
        candidates.extend(["workspaceLocationId", "WorkspaceLocationId"])

    if field_name == "rg_id":
        candidates.extend(["rgId", "RGId", "RG_ID", "routeGroupId", "route_group_id"])

    if field_name == "route_identity":
        candidates.extend(["routeIdentity", "RouteIdentity"])

    if field_name == "route_type":
        candidates.extend(["routeType", "RouteType"])

    if field_name == "premise_route_type":
        candidates.extend(["premiseRouteType", "PremiseRouteType"])

    if field_name == "premise_route_id":
        candidates.extend(["premiseRouteId", "PremiseRouteId", "premiseRouteID", "PremiseRouteID"])

    if field_name == "announcement_language":
        candidates.extend(["announcementLanguage", "AnnouncementLanguage"])

    if field_name == "preferred_language":
        candidates.extend(["preferredLanguage", "PreferredLanguage"])

    if field_name == "time_zone":
        candidates.extend(["timeZone", "TimeZone", "timezone", "TZ"])

    if field_name == "postal_code":
        candidates.extend(["postalCode", "PostalCode", "zip", "zipCode", "zipcode"])

    if field_name == "phone_number":
        candidates.extend(["phoneNumber", "PhoneNumber"])

    if field_name == "enable_unknown_extension_route_policy":
        candidates.extend(["enableUnknownExtensionRoutePolicy", "EnableUnknownExtensionRoutePolicy"])

    if field_name == "use_custom_permissions":
        candidates.extend(["useCustomPermissions", "use_customPermissions", "UseCustomPermissions"])

    if field_name == "use_custom_enabled":
        candidates.extend(["useCustomEnabled", "UseCustomEnabled"])

    if field_name == "display_name":
        candidates.extend(["displayName", "DisplayName"])

    if field_name == "direct_number":
        candidates.extend(["directNumber", "DirectNumber"])

    if field_name == "first_name":  # NEW
        candidates.extend(["firstName", "FirstName", "givenName", "given_name", "GivenName"])

    if field_name == "last_name":  # NEW
        candidates.extend(["lastName", "LastName", "familyName", "family_name", "FamilyName", "surname"])

    if field_name == "licenses":  # NEW
        candidates.extend(["Licenses", "license", "License", "licenseList", "license_list"])

    if field_name == "legacy_phone_number":  # NEW
        candidates.extend(["legacyPhoneNumber", "LegacyPhoneNumber", "legacyNumber", "legacy_number"])

    if field_name == "license_ids":  # NEW
        candidates.extend(["addLicenseIds", "AddLicenseIds", "addLicenseIDs", "add_licenseIDs", "licenseIdsToAdd"])

    uniq: List[str] = dedupe_preserve_order([c for c in candidates if c])
    return tuple(uniq)


def try_parse_structured(text_value: str) -> Optional[Any]:
    text: str = text_value.strip()
    if text == "":
        return None

    if text[:1] in {"{", "["} and text[-1:] in {"}", "]"}:
        try:
            return json.loads(text)
        except Exception:
            pass

    try:
        return ast.literal_eval(text)
    except Exception:
        return None


def is_non_empty_value(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, float) and value != value:
        return False

    if isinstance(value, str):
        v: str = value.strip()
        if v == "":
            return False
        lowered: str = v.lower()
        if lowered in {"none", "null", "nan", "n/a", "na"}:
            return False
        parsed: Optional[Any] = try_parse_structured(v)
        if parsed is None:
            return True
        return is_non_empty_value(parsed)

    if isinstance(value, (list, tuple, set)):
        if len(value) == 0:
            return False
        return any(is_non_empty_value(x) for x in value)

    if isinstance(value, dict):
        if len(value) == 0:
            return False
        return any(is_non_empty_value(v) for v in value.values())

    return True


def normalize_for_csv(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        try:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return str(value)
    return str(value)


def iter_nested_key_values(obj: Any) -> Iterable[Tuple[str, Any]]:
    stack: List[Any] = [obj]
    while stack:
        current: Any = stack.pop()
        if isinstance(current, dict):
            for k, v in current.items():
                if isinstance(k, str):
                    yield k, v
                stack.append(v)
        elif isinstance(current, (list, tuple, set)):
            for item in current:
                stack.append(item)


def extract_from_row_direct(row: Dict[str, Any], candidate_keys: Tuple[str, ...]) -> Optional[Any]:
    row_keys: Set[str] = set(row.keys())
    for key in candidate_keys:
        if key in row_keys:
            return row.get(key)
    for key in candidate_keys:
        key_lower: str = key.lower()
        for rk in row_keys:
            if isinstance(rk, str) and rk.lower() == key_lower:
                return row.get(rk)
    return None


def extract_from_row_recursive(row: Dict[str, Any], candidate_keys: Tuple[str, ...]) -> Optional[Any]:
    normalized_candidates: Set[str] = {c.lower() for c in candidate_keys}

    for _, cell in row.items():
        if not is_non_empty_value(cell):
            continue

        parsed: Any = cell
        if isinstance(cell, str):
            maybe: Optional[Any] = try_parse_structured(cell)
            parsed = maybe if maybe is not None else cell

        if isinstance(parsed, str):
            continue

        for nested_key, nested_value in iter_nested_key_values(parsed):
            if nested_key.lower() in normalized_candidates and is_non_empty_value(nested_value):
                return nested_value

    return None


def scan_csv_files(directory: Path, fields: Sequence[str]) -> Dict[str, str]:
    start_ts: float = time.perf_counter()

    remaining: Set[str] = set(fields)
    found: Dict[str, str] = {f: "" for f in fields}
    candidate_map: Dict[str, Tuple[str, ...]] = {f: build_candidate_keys(f) for f in fields}

    csv_paths: List[Path] = sorted([p for p in directory.rglob("*.csv") if p.is_file()], key=lambda p: str(p).lower())
    logger.info("csv_discovered directory=%s csv_files=%s target_fields=%s", str(directory), len(csv_paths), len(fields))

    for csv_path in csv_paths:
        if not remaining:
            break

        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                reader: csv.DictReader = csv.DictReader(f)
                for row in reader:
                    if not remaining:
                        break

                    row_dict: Dict[str, Any] = dict(row)

                    for field_name in list(remaining):
                        candidate_keys: Tuple[str, ...] = candidate_map[field_name]

                        direct_value: Optional[Any] = extract_from_row_direct(row_dict, candidate_keys)
                        if is_non_empty_value(direct_value):
                            found[field_name] = normalize_for_csv(direct_value)
                            remaining.remove(field_name)
                            logger.debug(
                                "field_found mode=direct field=%s file=%s value=%s remaining=%s",
                                field_name,
                                str(csv_path),
                                found[field_name][:200],
                                len(remaining),
                            )
                            continue

                        recursive_value: Optional[Any] = extract_from_row_recursive(row_dict, candidate_keys)
                        if is_non_empty_value(recursive_value):
                            found[field_name] = normalize_for_csv(recursive_value)
                            remaining.remove(field_name)
                            logger.debug(
                                "field_found mode=recursive field=%s file=%s value=%s remaining=%s",
                                field_name,
                                str(csv_path),
                                found[field_name][:200],
                                len(remaining),
                            )

        except Exception as exc:
            logger.error("file_error path=%s exc_type=%s exc=%s", str(csv_path), type(exc).__name__, str(exc)[:800])

    elapsed: float = time.perf_counter() - start_ts
    logger.info("scan_complete remaining_fields=%s elapsed_sec=%.6f", len(remaining), elapsed)

    return found


def write_output_csv(output_path: Path, fields: Sequence[str], values: Dict[str, str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    row: Dict[str, str] = {f: values.get(f, "") for f in fields}

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer: csv.DictWriter = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerow(row)

    logger.info("output_written path=%s", str(output_path))


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", type=str, required=True)
    parser.add_argument("--output_csv", type=str, required=False, default="")
    parser.add_argument("--log_level", type=str, required=False, default="INFO")
    return parser.parse_args(argv)


def main() -> int:
    args: argparse.Namespace = parse_args()

    log_level: str = args.log_level.strip().upper()
    logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

    input_dir: Path = Path(args.input_dir).expanduser().resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error("invalid_input_dir path=%s", str(input_dir))
        return 2

    output_csv: Path = (
        Path(args.output_csv).expanduser().resolve()
        if str(args.output_csv).strip()
        else (input_dir / "resultado_campos.csv")
    )

    if len(FIELDS_RAW) != len(FIELDS):
        logger.warning("duplicate_fields_detected raw=%s deduped=%s", len(FIELDS_RAW), len(FIELDS))

    values: Dict[str, str] = scan_csv_files(input_dir, FIELDS)
    write_output_csv(output_csv, FIELDS, values)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

