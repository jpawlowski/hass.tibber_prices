---
comments: false
---

# API Reference

Documentation of the Tibber GraphQL API used by this integration.

## GraphQL Endpoint

```
https://api.tibber.com/v1-beta/gql
```

**Authentication:** Bearer token in `Authorization` header

## Queries Used

### User Data Query

Fetches home information and metadata:

```graphql
query {
  viewer {
    homes {
      id
      appNickname
      address {
        address1
        postalCode
        city
        country
      }
      timeZone
      currentSubscription {
        priceInfo {
          current {
            currency
          }
        }
      }
      meteringPointData {
        consumptionEan
        gridAreaCode
      }
    }
  }
}
```

**Cached for:** 24 hours

### Price Data Query

Fetches quarter-hourly prices:

```graphql
query($homeId: ID!) {
  viewer {
    home(id: $homeId) {
      currentSubscription {
        priceInfo {
          range(resolution: QUARTER_HOURLY, first: 384) {
            nodes {
              total
              startsAt
              level
            }
          }
        }
      }
    }
  }
}
```

**Parameters:**
- `homeId`: Tibber home identifier
- `resolution`: Always `QUARTER_HOURLY`
- `first`: 384 intervals (4 days of data)

**Cached until:** Midnight local time

## Rate Limits

Tibber API rate limits (as of 2024):
- **5000 requests per hour** per token
- **Burst limit:** 100 requests per minute

Integration stays well below these limits:
- Polls every 15 minutes = 96 requests/day
- User data cached for 24h = 1 request/day
- **Total:** ~100 requests/day per home

## Response Format

### Price Node Structure

```json
{
  "total": 0.2456,
  "startsAt": "2024-12-06T14:00:00.000+01:00",
  "level": "NORMAL"
}
```

**Fields:**
- `total`: Price including VAT and fees (currency's major unit, e.g., EUR)
- `startsAt`: ISO 8601 timestamp with timezone
- `level`: Tibber's own classification (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE)

### Currency Information

```json
{
  "currency": "EUR"
}
```

Supported currencies:
- `EUR` (Euro) - displayed as ct/kWh
- `NOK` (Norwegian Krone) - displayed as øre/kWh
- `SEK` (Swedish Krona) - displayed as öre/kWh

## Error Handling

### Common Error Responses

**Invalid Token:**
```json
{
  "errors": [{
    "message": "Unauthorized",
    "extensions": {
      "code": "UNAUTHENTICATED"
    }
  }]
}
```

**Rate Limit Exceeded:**
```json
{
  "errors": [{
    "message": "Too Many Requests",
    "extensions": {
      "code": "RATE_LIMIT_EXCEEDED"
    }
  }]
}
```

**Home Not Found:**
```json
{
  "errors": [{
    "message": "Home not found",
    "extensions": {
      "code": "NOT_FOUND"
    }
  }]
}
```

Integration handles these with:
- Exponential backoff retry (3 attempts)
- ConfigEntryAuthFailed for auth errors
- ConfigEntryNotReady for temporary failures

## Data Transformation

Raw API data is enriched with:
- **Trailing 24h average** - Calculated from previous intervals
- **Leading 24h average** - Calculated from future intervals
- **Price difference %** - Deviation from average
- **Custom rating** - Based on user thresholds (different from Tibber's `level`)

See `utils/price.py` for enrichment logic.

---

💡 **External Resources:**
- [Tibber API Documentation](https://developer.tibber.com/docs/overview)
- [GraphQL Explorer](https://developer.tibber.com/explorer)
- [Get API Token](https://developer.tibber.com/settings/access-token)
