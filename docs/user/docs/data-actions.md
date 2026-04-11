# Data & Utility Actions

Actions for fetching raw price data and managing integration state.

---

## tibber_prices.get_price

**Purpose:** Fetches raw price interval data for any time range. Uses intelligent caching — only intervals not already cached are fetched from the Tibber API.

**Parameters:**

| Parameter | Description | Required |
|-----------|-------------|----------|
| `entry_id` | Config entry ID | Yes |
| `start_time` | Start of the time range | Yes |
| `end_time` | End of the time range | Yes |

**Example:**

<details>
<summary>Show YAML: Get Price</summary>

```yaml
service: tibber_prices.get_price
data:
    entry_id: YOUR_CONFIG_ENTRY_ID
    start_time: "2025-11-01T00:00:00"
    end_time: "2025-11-02T00:00:00"
response_variable: price_data
```

</details>

**Response Format:**

<details>
<summary>Show JSON: Get Price Response</summary>

```json
{
    "home_id": "abc-123",
    "start_time": "2025-11-01T00:00:00+01:00",
    "end_time": "2025-11-02T00:00:00+01:00",
    "interval_count": 96,
    "price_info": [
        {
            "startsAt": "2025-11-01T00:00:00+01:00",
            "total": 0.2534,
            "energy": 0.1218,
            "tax": 0.1316
        }
    ]
}
```

</details>

**Use cases:**
- Fetching historical price data for analysis
- Comparing prices across arbitrary date ranges
- Building custom charts with historical data

**Note:** Times are automatically converted to your Tibber home's timezone. The interval pool caches previously fetched intervals, so repeated calls for the same range are fast.

---

## tibber_prices.refresh_user_data

**Purpose:** Forces an immediate refresh of user data (homes, subscriptions) from the Tibber API.

**Example:**

<details>
<summary>Show YAML: Refresh User Data</summary>

```yaml
service: tibber_prices.refresh_user_data
data:
    entry_id: YOUR_CONFIG_ENTRY_ID
```

</details>

**Note:** User data is cached for 24 hours. Trigger this action only when you need immediate updates (e.g., after changing Tibber subscriptions).
