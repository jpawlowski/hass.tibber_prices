# Test recipes

Variants of the shared fixtures and patterns in [`../SKILL.md`](../SKILL.md) that only some integrations need.

## `mock_api` for a third-party library client

The default `mock_api` patches the client's HTTP method, so the client's own payload handling stays under test. When
the client is a third-party library instead, keep the fixture name and patch the library class **where the integration
imports it** — every import site, since setup and the config flow's validator each import it separately:

```python
@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """Replace the library client at each place the integration imports it."""
    with (
        patch("custom_components.<domain>.{ClassPrefix}ApiClient", autospec=True) as client_class,
        patch(
            "custom_components.<domain>.config_flow_handler.validators.credentials.{ClassPrefix}ApiClient",
            new=client_class,
        ),
    ):
        client = client_class.return_value
        client.async_get_data.return_value = load_json_object_fixture("device.json")
        yield client
```

`autospec=True` makes the mock fail when the real signature changes, which is the whole point. With this variant, set
`side_effect` on the method (`mock_api.async_get_data.side_effect`), not on `mock_api` itself.

## Every entity of a platform: `snapshot_platform`

```python
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_api")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
) -> None:
    """Every sensor matches its recorded registry entry and state."""
    with patch("custom_components.<domain>.PLATFORMS", [Platform.SENSOR]):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
```

`snapshot_platform` (from `pytest_homeassistant.common`) accepts exactly one platform and fails on a
disabled entity, so request `entity_registry_enabled_by_default`, which `pytest-homeassistant` provides — never define
it again in `conftest.py`.
