# SmartThings Find HA

A custom Home Assistant integration that exposes Samsung SmartTag locations from **SmartThings Find** as `device_tracker` entities.

> [!IMPORTANT]
> This integration uses Samsung's private SmartThings Find web endpoints. It is not an official Samsung API, and Samsung may change the endpoints or authentication flow without notice.

## Project ownership and credit

This repository is maintained by **[@yaronkof](https://github.com/yaronkof)**.

The project is based on the original **SmartThings Find NextGen** integration by **[@saarglobin](https://github.com/saarglobin)**:

- Original project: https://github.com/saarglobin/smarttags_nextgen_ha
- Current maintained repository: https://github.com/yaronkof/smartthings-find-ha

The original project was itself created as a spiritual successor to Vedeneb's HA-SmartThings-Find project. Original authors and contributors retain credit for their work. See [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE).

## Contributors

- **[@yaronkof](https://github.com/yaronkof)** — current maintainer and project owner.
- **ChatGPT by OpenAI** — development assistance, code review, documentation, architecture, and maintenance support.
- Original authors and contributors remain credited through the repository history, [NOTICE.md](NOTICE.md), and [LICENSE](LICENSE).

## Features

- Creates a Home Assistant `device_tracker` entity for each Samsung SmartTag found in the account.
- Supports multiple SmartTags.
- Automatically adds newly discovered SmartTags without requiring a Home Assistant restart.
- Polls SmartThings Find approximately every **5 minutes**.
- Supports Samsung regions:
  - Europe: `prd-eu`
  - General / US: `prd-us`
  - Asia / Pacific: `prd-ap`
  - Asia / Pacific 2: `prd-ap2`
  - Custom region values when required.
- Keeps the last known coordinates if Samsung temporarily returns no new location.
- Exposes additional attributes:
  - `location_type`
  - `last_seen`
  - `battery_state`
- Detects expired Samsung sessions and starts Home Assistant's reauthentication flow.
- Creates Device Registry entries for SmartTags.
- Creates a diagnostic battery-state sensor for each SmartTag that reports
  Samsung's raw battery value (for example `FULL`, `HIGH`, `MEDIUM`, or `LOW`) and changes its icon accordingly.
- Provides `smarttags_nextgen.locate` for an on-demand per-tag location request and
  `smarttags_nextgen.refresh` to refresh all loaded tags.
- Provides Home Assistant diagnostics with strict redaction: credentials, device
  identifiers, names, coordinates, and Samsung response bodies are not exported.

## Limitations

- Location is cloud-polled, not real-time.
- This integration currently **does not control SmartTags** (ring, search, etc.).
- Samsung provides battery state such as `HIGH`, `MEDIUM`, or `LOW`, not a precise battery percentage. The tracker currently retains the legacy approximate percentage field for backwards compatibility; Home Assistant has deprecated battery values on device trackers, so this may move to a separate entity in a future release.
- The `JSESSIONID` cookie expires periodically and must then be replaced.
- Because this is based on undocumented Samsung web endpoints, a Samsung website/backend change can break the integration.

## Installation

### HACS — recommended

This repository is currently installed as a **custom HACS repository**.

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add:

   `https://github.com/yaronkof/smartthings-find-ha`

4. Select **Integration** as the category.
5. Find **SmartThings Find HA** and install it.
6. Restart Home Assistant if HACS asks you to.
7. Go to **Settings → Devices & services → Add integration** and search for **SmartThings Find HA**.

### Manual installation

1. Download or clone this repository.
2. Copy the integration directory:

   `custom_components/smarttags_nextgen`

   into your Home Assistant configuration directory so the final path is:

   `config/custom_components/smarttags_nextgen`

3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and search for **SmartThings Find HA**.

## Getting the Samsung JSESSIONID

The integration authenticates using the browser session created by the SmartThings Find website. Authentication is intentionally manual: the user copies the `JSESSIONID` cookie from Chrome or another browser on their own computer and enters it in Home Assistant.

1. Open https://smartthingsfind.samsung.com/ in a desktop browser.
2. Sign in to your Samsung account.
3. Open the browser Developer Tools (`F12` in most browsers).
4. Open the **Application** or **Storage** section.
5. Open the cookies for `https://smartthingsfind.samsung.com`.
6. Find the cookie named **`JSESSIONID`**.
7. Copy its **value** and paste it into the integration setup form.
8. Choose the appropriate Samsung region. If none of the predefined regions works for your account, use **Other / Custom** and enter the required `prd-*` value.

### Security warning

Treat the `JSESSIONID` like a password/session token.

**Do not:**

- post it in a GitHub issue,
- paste it into screenshots,
- include it in Home Assistant logs,
- share it with another person.

If a JSESSIONID has accidentally been exposed, sign out of Samsung/SmartThings Find and create a new browser session before using the integration again.

## Session expiration / reauthentication

Samsung browser sessions expire periodically. When this happens, Home Assistant should mark the integration as requiring attention and offer a **Re-authenticate** flow.

Sign in to SmartThings Find again, copy the new `JSESSIONID`, and submit it in Home Assistant.

You can also manually update the JSESSIONID or region from the integration's configuration/options page.

## Entity data

Each SmartTag is represented as a GPS-style `device_tracker`.

Typical data includes:

| Data | Description |
| --- | --- |
| Latitude / longitude | Last known SmartTag position returned by Samsung |
| `location_type` | Samsung location mode, including `offline` when appropriate |
| `last_seen` | Samsung-provided GPS timestamp when available |
| `battery_state` | Raw Samsung battery state such as `HIGH`, `MEDIUM`, or `LOW` |

The battery state is also available as a diagnostic sensor. It intentionally
reports Samsung's raw value (such as `FULL`, `HIGH`, `MEDIUM`, or `LOW`) instead of an invented percentage, because
Samsung does not provide a precise battery level for these tags.

A missing fresh location does **not** necessarily mean the tag is currently at the last known coordinates. Check `last_seen` when location freshness matters.

## Troubleshooting

### Invalid authentication / reauthentication required

The JSESSIONID has probably expired. Sign in to SmartThings Find again and copy a fresh cookie.

### Cannot connect

Possible causes include:

- temporary Samsung service problems,
- networking/DNS issues from Home Assistant,
- Samsung rate limiting,
- a change to Samsung's private endpoints.

Check the Home Assistant logs and retry later before opening an issue.

### No SmartTags appear

Confirm that:

- the tags are visible at https://smartthingsfind.samsung.com/ using the same Samsung account,
- the selected region is correct,
- the JSESSIONID came from `smartthingsfind.samsung.com`, not another Samsung domain.

### Manual services and diagnostics

Use **Developer Tools → Actions** with `smarttags_nextgen.locate` and target a
SmartTag tracker or its **Locate now** button. The optional `device_id` field can
be used for automation when an entity target is not convenient. Use
`smarttags_nextgen.refresh` to refresh all entries. The integration's Diagnostics
download is intentionally limited to counts, region, lifecycle status, and
exception types; it never includes the JSESSIONID, device IDs, coordinates,
names, or raw Samsung responses.

### Reporting bugs

Open issues here:

https://github.com/yaronkof/smartthings-find-ha/issues

Before submitting a bug report, remove all JSESSIONID/cookie values and other private account information from logs and screenshots.

## Contributing

Pull requests and useful bug reports are welcome. Please keep changes focused on the maintained repository (`yaronkof/smartthings-find-ha`).

## Release notes — 0.6.1

- Fixed the setup description link after removing the headed Chrome flow.

## Release notes — 0.6.0

- Removed the headed Chrome/Selenium bootstrap, which is not useful in typical Home Assistant VM/OS installations.
- Kept authentication simple and manual through the browser `JSESSIONID` cookie.

## Release notes — 0.5.3

- Added the missing Options-flow error message for headed Chrome failures.

## Release notes — 0.5.2

- Added the observed Samsung `FULL` battery state to the battery icon mapping.

## Release notes — 0.5.1

- Added a diagnostic battery-state sensor for each SmartTag.
- Reports Samsung's raw `HIGH`, `MEDIUM`, or `LOW` state with a matching icon.

## Release notes — 0.4.0

- Added integration-level `locate` and `refresh` services.
- Added strict, privacy-preserving diagnostics.
- Added optional standard Selenium/Chrome headed persistent-profile bootstrap
  with manual login and manual fallback.
- Stored the coordinator as config-entry runtime data and shut it down on unload.
- Added an optional Selenium headed-Chrome bootstrap helper with a persistent profile for manual Samsung login.
- Kept Samsung browser-session authentication unchanged; no anti-bot bypasses were added.

## Release notes — 0.2.0

- Project maintenance transferred to `yaronkof` with explicit credit to the original developer.
- Updated repository/documentation/issue links.
- Added explicit project attribution notice.
- Added proper authentication and connection exceptions.
- Added Home Assistant reauthentication flow for expired JSESSIONIDs.
- Hardened Samsung response parsing so malformed coordinates do not break all tags.
- Added `last_seen` location metadata.
- Prefer SmartTag nickname over generic model name.
- Added Device Registry information.
- Added dynamic discovery of newly added SmartTags.
- Removed the outdated string-based device tracker `source_type` override.
- Removed dormant credential-header diagnostic logging code.
- Corrected manual installation directory instructions.
- Updated integration manifest metadata for the maintained repository.

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This project is a third-party community integration and is **not affiliated with, maintained by, or endorsed by Samsung or SmartThings**.
