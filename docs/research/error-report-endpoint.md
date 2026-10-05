# Spike: `/error_report.json` for structured alarms (issue #13)

Date: 2026-10-05. Method: HTTP GET only, against two real devices (homevolt1 = leader with 2 EMS units,
homevolt2 = single unit), plus `/ems.json` and `/error_history.json` for comparison, and the OpenAPI spec in
tibber/homevolt-local-api-doc (`API_DOCUMENTATION.yaml`, `main`). No POST requests were made.

## Conclusion

The endpoint cannot provide a severity or a numeric alarm code, so it is not usable for the "structured
alarms with severity + error code" goal. **No integration code changes.** What it does offer is a
per-subsystem health list with a coarse four-state status (`ok` / `warning` / `error` / `unknown`), which is
a different feature (subsystem health diagnostics), not alarms. The existing `alarm_str` / `warning_str` /
`info_str` data from `/ems.json` already carries the EMS alarm content.

## Observed payload

Top level is a bare JSON array (36 entries on both devices), not an object. Every entry has exactly these
seven keys on both devices:

| key | type | notes |
| --- | --- | --- |
| `sub_system_id` | int | 0 ECU, 1 EMS, 2 CONNECTIVITY, 3 OTA, 4 PULSE SOLAR, 5 PULSE GRID, 6 EFR_HUB |
| `sub_system_name` | string | |
| `error_id` | int | index within the subsystem, NOT an alarm code (EMS ids go 1,2,4,6,7,8,9,10; gaps) |
| `error_name` | string | check name, mixed style (`power_24v`, `Firmware for esp32`, `distribute status`) |
| `activated` | string | observed `ok`, `error`, `warning`, `unknown` |
| `message` | string | free text, often with live values (`AC voltage: 163.46 V`) |
| `details` | list of strings | empty except EMS `ems_info` here |

Trimmed sample (36 entries cut to 9; entries 7 and 8 are from homevolt2, the rest from homevolt1; the
endpoint contains no serial numbers, hostnames or other identifiers):

```json
[
 {"sub_system_id":0,"sub_system_name":"ECU","error_id":3,"error_name":"local_mode_disabled","activated":"ok","message":"","details":[]},
 {"sub_system_id":1,"sub_system_name":"EMS","error_id":4,"error_name":"ems_alarm","activated":"ok","message":"No EMS alarms","details":[]},
 {"sub_system_id":1,"sub_system_name":"EMS","error_id":8,"error_name":"ems_info","activated":"ok","message":"3 EMS infos","details":["EMS_INFO_FAN_STATE_ON","EMS_INFO_CONNECTED_TO_BACKEND","EMS_INFO_RTC_SYNCRONIZED"]},
 {"sub_system_id":1,"sub_system_name":"EMS","error_id":9,"error_name":"ems_warning","activated":"ok","message":"No EMS warnings","details":[]},
 {"sub_system_id":2,"sub_system_name":"CONNECTIVITY","error_id":2,"error_name":"lte","activated":"error","message":"LTE error: 5","details":[]},
 {"sub_system_id":4,"sub_system_name":"PULSE SOLAR","error_id":7,"error_name":"calibration status","activated":"warning","message":"Line diff invalid","details":[]},
 {"sub_system_id":4,"sub_system_name":"PULSE SOLAR","error_id":4,"error_name":"available","activated":"error","message":"Solar clamp is unassigned","details":[]},
 {"sub_system_id":4,"sub_system_name":"PULSE SOLAR","error_id":1,"error_name":"distribute status","activated":"unknown","message":"","details":[]},
 {"sub_system_id":6,"sub_system_name":"EFR_HUB","error_id":1,"error_name":"ac_voltage","activated":"error","message":"AC voltage: 163.46 V","details":[]}
]
```

## Confirming / refuting the prior observations

- Flat list of 7-key entries: confirmed.
- No severity field: confirmed. The nearest thing is `activated`, which has four values, not two (`warning`
  and `unknown` also occur). It is a per-check status, not an alarm severity. For example `EFR_HUB ac_voltage`
  is `error` at 163-173 V on both devices while they report normal operation (`state_str: Running`).
- No numeric alarm code: confirmed. `error_id` is a position within a subsystem.
- `ems_alarm` / `ems_warning` / `ems_info` carry `details` string lists duplicating `/ems.json`
  `ems_data.alarm_str` / `warning_str` / `info_str`: confirmed for info (identical three strings on both
  devices). Alarm and warning are empty in both places, so duplication for those is only inferred.
  `/ems.json` also exposes numeric bitfields `alarm` / `warning` / `info` (e.g. `info: 13`); these are the
  only numeric codes available, and they live in `/ems.json`, not in this endpoint.
- Alarms currently empty on both devices; LTE reports `error` on both: confirmed. Other non-OK entries:
  EFR_HUB `ac_voltage` (`error`, both), PULSE SOLAR `calibration status` (`warning`, homevolt1), unassigned
  clamp entries (`error` plus `unknown` siblings with empty messages, homevolt2).
- Other fields: none beyond the seven. No timestamp and no activation time per entry.

## Comparison with the OpenAPI spec

The spec (`/error_report.json`, `getErrorReport`) documents an object:

```yaml
{ timestamp: int64, errors: [ { subsystem: string, error_code: int, description: string,
                                severity: enum[INFO, WARNING, ERROR, CRITICAL] } ] }
```

The real devices return none of that: a bare array instead of an object, no `timestamp`, no `errors` wrapper,
and the per-entry fields differ (`sub_system_name` vs `subsystem`, `message` vs `description`, `activated` vs
`severity`); `error_code` has no counterpart and `severity` has no equivalent enum. The spec does not describe
this endpoint, and a client written against it would find nothing. `/error_history.json` (in the spec, with a
`severity` filter) returned HTTP 200 with `[]` on homevolt1, so its real shape is unknown.

## Could not be verified

- A payload with an active EMS alarm or warning: none available. The content of `details` for `ems_alarm` /
  `ems_warning`, and whether `activated` changes for them, is unobserved. Active alarms might add information,
  but nothing observed suggests a code or severity would appear.
- Other firmware versions, or extra entries (BMS-level, follower units); both devices appear to run the same
  firmware, and versions were not compared.
- The meaning of `LTE error: 5` and of the `unknown` state; semantics of `activated` are inferred.
- `/error_history.json` content (empty).
- Behaviour with authentication enabled (the devices used did not require it).

## If revisited

A possible future feature is per-subsystem health diagnostics, not alarms: map `activated` to binary sensors or
an enum sensor per subsystem, with `message` as an attribute. Caveats: `error_name` strings are inconsistent
(spaces, mixed case), some `error` entries are benign (`ac_voltage`, unassigned clamps), and there is no
severity to filter on. Revisit alarms only after capturing a payload with an active alarm.
