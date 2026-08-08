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
    "success": true,
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

### Checking the Result

The response always has the expected shape — even when no data could be returned — so your automations never have to guard against missing fields. Use the `success` flag to tell apart two very different situations:

| Situation | `success` | `price_info` | What it means |
|-----------|-----------|--------------|---------------|
| Data returned | `true` | populated | Prices are available for the range. |
| No prices for the range *yet* | `true` | `[]` (`interval_count: 0`) | **Not an error.** Tomorrow's prices are usually published by Tibber around 13:00 local time, but the underlying day-ahead auction can be delayed — occasionally the data only appears later in the afternoon or evening (and on rare auction failures, not at all for that day). Before that, a range covering tomorrow legitimately returns empty. Retry later. |
| Tibber API unavailable | `false` (`reason: "price_data_unavailable"`) | `[]` | A temporary API outage prevented the fetch on an uncached range. Existing sensors keep working from cache; retry later. |

:::tip Distinguishing "no data yet" from "outage"
Check `success` first. `success: true` with an empty `price_info` means **the request worked, there simply are no prices for that range yet** (typically tomorrow before the day-ahead prices are published — usually around 13:00, but sometimes later in the afternoon or evening). `success: false` means **the API call itself failed** — treat it as a transient error and retry later.
:::

```yaml
# Example: only act when prices are actually available
- if: "{{ price_data.success and price_data.interval_count > 0 }}"
  then:
    - service: notify.mobile_app
      data:
        message: "Got {{ price_data.interval_count }} price intervals."
- if: "{{ not price_data.success }}"
  then:
    # Tibber API outage — retry later, sensors keep running from cache
    - delay: "00:30:00"
```

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
