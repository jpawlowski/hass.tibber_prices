# Caching

What this integration keeps between fetches, where it lives, and what throws it away. The timers that drive the
fetches are in [`ARCHITECTURE.md`](ARCHITECTURE.md); time-travel views and their own caches are in
[`TIME_TRAVEL.md`](TIME_TRAVEL.md).

## Persistent storage

Each config entry writes two files through Home Assistant's `Store`, and the split is strict:

| Store key                                | Written by                             | Holds                                                                                  |
| ---------------------------------------- | -------------------------------------- | -------------------------------------------------------------------------------------- |
| `tibber_prices.interval_pool.{entry_id}` | `coordinator/interval_pool/storage.py` | the price intervals, deduplicated, with when each was fetched and the protected range  |
| `tibber_prices.{entry_id}`               | `coordinator/cache.py`                 | user data (homes, subscription, timezone, currency) and the timestamps that go with it |

**Prices live only in the interval pool.** The coordinator store holds no price data, so nothing has to be cleared at
midnight: `get_intervals_for_day_offsets()` (`coordinator/helpers.py`) filters the pool's flat interval list by date,
and a new day simply selects different intervals. The pool's garbage collector keeps the range from the day before
yesterday to tomorrow (`PROTECTED_DAYS_BEFORE`, `PROTECTED_DAYS_AFTER` in `coordinator/interval_pool/cache.py`).

User data is refreshed once a day (`_user_update_interval` in `coordinator/core.py`), and hourly while the
subscription is still pending (`PENDING_USER_UPDATE_INTERVAL` in `coordinator/price_data_manager.py`).

Both files survive a restart. The coordinator's `clear_cache()` (`coordinator/core.py`) resets them only on
reconfiguration and when the entry is disabled.

## In-memory caches

| Cache               | Where                                                                                | Dropped when                                                                     |
| ------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| Translations        | `_TRANSLATIONS_CACHE`, `_STANDARD_TRANSLATIONS_CACHE` in `const.py`                  | never — loaded at setup by `async_load_translations()` and its standard sibling  |
| Config dictionaries | `_config_cache` in `coordinator/data_transformation.py` and `coordinator/periods.py` | the options change (`invalidate_config_cache()`)                                 |
| Enriched price data | `_cached_transformed_data` in `coordinator/data_transformation.py`                   | options change, new source data, a new local date (`_should_retransform_data()`) |
| Calculated periods  | `_cached_periods` in `coordinator/periods.py`                                        | the hash from `_compute_periods_hash()` changes, or the options change           |

- **Translations** are cached because entity attributes are built synchronously on every state write, and reading a
  file there would block the event loop. `get_translation()` reads the cache; it never loads.
- **The enrichment cache holds prices only.** Periods are not part of it; the coordinator puts the two together, so
  neither cache can serve a stale copy of the other's result.
- **The period hash** covers the full signature of today's and tomorrow's intervals (start, totals, levels, ratings,
  differences), the best and peak configuration, and the level filter overrides. Changing a price inside the same day
  therefore invalidates it, not only a new day.

## What invalidates what

- **Options saved** → `_handle_options_update()` in `coordinator/core.py` calls `invalidate_config_cache()` on the
  data transformer and the period calculator, then re-transforms the data already held. No fetch.
- **Midnight** → `_perform_midnight_data_rotation()` re-transforms the existing data for the new day; the period cache
  follows through its hash. The midnight check is atomic (`TibberPricesMidnightHandler` in
  `coordinator/midnight_handler.py`), so whichever timer gets there first does it once.
- **Tomorrow's prices arrive** → the pool fetches, the source timestamp changes, enrichment re-runs, the period hash
  changes.

No cache invalidates another; each detects its own staleness. Everything runs on the event loop, so none of them
needs a lock.

## When data looks stale

The debug log of `custom_components.tibber_prices.coordinator` names which path ran:

| Log line                                               | Means                               |
| ------------------------------------------------------ | ----------------------------------- |
| `Options update triggered, re-transforming data`       | the options listener fired          |
| `Source data changed, retransforming data`             | new prices reached the transformer  |
| `Midnight turnover detected, retransforming data`      | the date changed since the last run |
| `Using cached period calculation results (hash match)` | periods came from the cache         |
| `Calculating periods (cache miss or hash mismatch)`    | periods were recalculated           |

- Periods do not change after a price change → check that `_compute_periods_hash()` includes the input that changed.
- Yesterday's prices shown as today → check the midnight handler's last check time and the `referenceTime` the data
  carries (`TIME_TRAVEL.md`).
- Descriptions or attribute names missing → `async_load_translations()` did not run at setup, or the key is missing
  from `custom_translations/`, which has no English fallback.
