# Discovery matchers

The `manifest.json` half of discovery. Each protocol has one or two rules that are invisible until the matcher
silently never fires, or fires for every device on the network.

**Universal:** the integration is discovered when **all** keys of **any one** matcher match. Duplicate suppression is
the config flow's job, not the matcher's — always `async_set_unique_id()` and `_abort_if_unique_id_configured()`.

## Zeroconf

```json
"zeroconf": [{ "type": "_example._tcp.local.", "properties": { "manufacturer": "acme*" } }]
```

- **Every value under `properties` must be lowercase.** An uppercase character means the matcher never fires, with no
  error anywhere.
- `fnmatch` wildcards are allowed in property values.
- A generic service type (`_http._tcp.local.`, `_printer._tcp.local.`) needs a `name` or `properties` filter, or the
  integration is offered for every unrelated device that speaks it.

## Bluetooth

```json
"bluetooth": [{ "local_name": "ACME*", "connectable": false }]
```

- A `local_name` pattern **may not have a wildcard in the first three characters**.
- `service_uuid` takes the 128-bit form. Convert a 16-bit UUID by substituting it into bytes 3–4 of the Bluetooth base
  UUID: `0xfd3d` → `0000fd3d-0000-1000-8000-00805f9b34fb`.
- `manufacturer_data_start` is a list of integers 0–255, not a hex string.
- `connectable: false` for a device that only advertises. Set it and the discovery also reaches you through
  advertisement-only scanners; reject non-connectable discoveries in the flow if you need a connection.

## DHCP

```json
"dhcp": [{ "hostname": "acme-*", "macaddress": "AABBCC*" }]
```

- **`hostname` arrives lowercase, and `macaddress` arrives lowercase without separators** — `AA:BB:CC:12:34:56`
  becomes `aabbcc123456`. Feed it through `format_mac()` before it becomes a unique ID, or it will never match the
  same device discovered over zeroconf.
- `registered_devices: true` re-checks devices already in the registry — the way to catch a changed IP when
  `hostname` or `oui` would be too broad.
- Prefer zeroconf or SSDP where the device supports them; DHCP only sees the device when its lease renews.

## USB

```json
"usb": [{ "vid": "10C4", "pid": "EA60", "description": "*acme*" }]
```

- VID/PID pairs are frequently shared: `10C4`/`EA60` is every Silicon Labs CP2102 adapter ever made. Match on
  `description` or `serial_number` as well, or users get your integration offered for unrelated hardware.

## SSDP, HomeKit, MQTT

- **SSDP** matches on `st`, `manufacturer`, `modelName` and friends from the device description.
- **HomeKit** matches the model name by prefix. Discovery is no longer routed to integrations that merely listen for
  the HomeKit zeroconf type.
- **MQTT** needs `mqtt` in `dependencies`, and `await mqtt.async_wait_for_mqtt_client(hass)` before subscribing.

## LoRaWAN

```json
"dependencies": ["lorawan"],
"lorawan": [["chirpstack", 744], ["tts", "sensecap"]]
```

- Each matcher is a pair of network-server stack and the vendor's brand ID there. A match starts
  `async_step_integration_discovery` with an empty `LoRaWANDiscoveryInfo`; the library decides which models it
  supports.
- hassfest on an older version rejects the key — add it only once `hacs.json` → `homeassistant` has reached it.

## Helper APIs

Using these from code requires the matching integration in `dependencies` (`zeroconf`, `ssdp`, `dhcp`, `usb`,
`bluetooth`, `network`). Every registration returns an unsubscribe callable — wrap it in `entry.async_on_unload(...)`.

| Helper                                          | Returns                                             |
| ----------------------------------------------- | --------------------------------------------------- |
| `ssdp.async_register_callback(...)`             | Callback on matching SSDP announcements             |
| `usb.async_register_scan_request_callback(...)` | Callback when a USB scan is requested               |
| `network.async_get_adapters(hass)`              | The host's network adapters, for binding or subnets |
