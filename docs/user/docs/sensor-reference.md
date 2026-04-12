---
comments: false
---

# Entity Reference (All Languages)

<EntitySearch />

## How to Find Your Entity in Home Assistant

**Entity ID pattern:** `sensor.<home_name>_<suffix>`

- `<home_name>` is generated from your Tibber home display name (lowercase, spaces replaced with underscores)
- `<suffix>` is shown in the **Entity ID suffix** column below

**Three ways to find an entity:**

1. **Search above** — Type the entity name in your language to filter the tables below
2. **Device page** — Go to **Settings → Devices & Services → Tibber Prices** →
   click your home device → all entities are listed
3. **Developer Tools** — Go to **Developer Tools → States** →
   type `tibber` in the filter

:::tip
You can also use your browser's built-in search (**Ctrl+F** / **Cmd+F**) to search the full page text.
:::

**Enabled by default:** The ✅ column shows whether a sensor is enabled by default.
Sensors marked ❌ must be enabled manually via
**Settings → Devices & Services → Entities** → find the entity → toggle **Enabled**.

**Detailed documentation:** See the **[Sensors Overview](sensors-overview.md)** for detailed
explanations of each sensor's purpose, attributes, and automation examples.

---

## Sensors

### Core Price Sensors


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-current_interval_price" class="entity-anchor"></span>`current_interval_price` | Current Electricity Price | Aktueller Strompreis | Nåværende strømpris | Huidige Elektriciteitsprijs | Aktuellt elpris | ✅ |
| <span id="ref-current_interval_price_base" class="entity-anchor"></span>`current_interval_price_base` | Current Electricity Price (Energy Dashboard) | Aktueller Strompreis (Energie-Dashboard) | Nåværende strømpris (Energi-dashboard) | Huidige Elektriciteitsprijs (Energie Dashboard) | Aktuellt elpris (Energidashboard) | ✅ |
| <span id="ref-next_interval_price" class="entity-anchor"></span>`next_interval_price` | Next Electricity Price | Nächster Strompreis | Neste strømpris | Volgende Elektriciteitsprijs | Nästa elpris | ✅ |
| <span id="ref-previous_interval_price" class="entity-anchor"></span>`previous_interval_price` | Previous Electricity Price | Vorheriger Strompreis | Forrige strømpris | Vorige Elektriciteitsprijs | Föregående elpris | ❌ |

### Hourly Average Sensors


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-current_hour_average_price" class="entity-anchor" data-refs="sensors-average#available-average-sensors"></span>`current_hour_average_price` | ⌀ Hourly Price Current | ⌀ Stunden-Preis aktuell | ⌀ Timepris nåværende | ⌀ Uurprijs Huidig | ⌀ Timpris aktuell | ✅ |
| <span id="ref-next_hour_average_price" class="entity-anchor" data-refs="sensors-average#available-average-sensors"></span>`next_hour_average_price` | ⌀ Hourly Price Next | ⌀ Stunden-Preis nächste Stunde | ⌀ Timepris neste | ⌀ Uurprijs Volgend | ⌀ Timpris nästa | ✅ |

### Daily Statistics


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-lowest_price_today" class="entity-anchor" data-refs="sensors-overview#daily-min-max"></span>`lowest_price_today` | Today's Lowest Price | Mindestpreis heute | Dagens laveste pris | Laagste Prijs Vandaag | Dagens lägsta pris | ✅ |
| <span id="ref-highest_price_today" class="entity-anchor" data-refs="sensors-overview#daily-min-max"></span>`highest_price_today` | Today's Highest Price | Höchstpreis heute | Dagens høyeste pris | Hoogste Prijs Vandaag | Dagens högsta pris | ✅ |
| <span id="ref-average_price_today" class="entity-anchor" data-refs="sensors-average#available-average-sensors"></span>`average_price_today` | ⌀ Price Today | ⌀ Preis heute | ⌀ Pris i dag | ⌀ Prijs Vandaag | ⌀ Pris idag | ✅ |
| <span id="ref-lowest_price_tomorrow" class="entity-anchor" data-refs="sensors-overview#daily-min-max"></span>`lowest_price_tomorrow` | Tomorrow's Lowest Price | Mindestpreis morgen | Morgendagens laveste pris | Laagste Prijs Morgen | Morgondagens lägsta pris | ✅ |
| <span id="ref-highest_price_tomorrow" class="entity-anchor" data-refs="sensors-overview#daily-min-max"></span>`highest_price_tomorrow` | Tomorrow's Highest Price | Höchstpreis morgen | Morgendagens høyeste pris | Hoogste Prijs Morgen | Morgondagens högsta pris | ✅ |
| <span id="ref-average_price_tomorrow" class="entity-anchor" data-refs="sensors-average#available-average-sensors"></span>`average_price_tomorrow` | ⌀ Price Tomorrow | ⌀ Preis morgen | ⌀ Pris i morgen | ⌀ Prijs Morgen | ⌀ Pris imorgon | ✅ |

### 24h Window Sensors


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-trailing_price_average" class="entity-anchor" data-refs="sensors-average#available-average-sensors"></span>`trailing_price_average` | ⌀ Price Trailing 24h | ⌀ Preis nachlaufend 24h | ⌀ Pris glidende 24t | ⌀ Prijs Afgelopen 24u | ⌀ Pris glidande 24h | ❌ |
| <span id="ref-leading_price_average" class="entity-anchor" data-refs="sensors-average#available-average-sensors"></span>`leading_price_average` | ⌀ Price Leading 24h | ⌀ Preis vorlaufend 24h | ⌀ Pris fremtidig 24t | ⌀ Prijs Komende 24u | ⌀ Pris framåt 24h | ❌ |
| <span id="ref-trailing_price_min" class="entity-anchor" data-refs="sensors-overview#24-hour-rolling-min-max"></span>`trailing_price_min` | Trailing 24h Minimum Price | 24h-Mindestpreis nachlaufend | Glidende 24t minimumspris | Afgelopen 24u Minimumprijs | Glidande 24h minimipris | ❌ |
| <span id="ref-trailing_price_max" class="entity-anchor" data-refs="sensors-overview#24-hour-rolling-min-max"></span>`trailing_price_max` | Trailing 24h Maximum Price | 24h-Höchstpreis nachlaufend | Glidende 24t maksimumspris | Afgelopen 24u Maximumprijs | Glidande 24h maximipris | ❌ |
| <span id="ref-leading_price_min" class="entity-anchor" data-refs="sensors-overview#24-hour-rolling-min-max"></span>`leading_price_min` | Leading 24h Minimum Price | 24h-Mindestpreis vorlaufend | Fremtidig 24t minimumspris | Komende 24u Minimumprijs | Framåt 24h minimipris | ❌ |
| <span id="ref-leading_price_max" class="entity-anchor" data-refs="sensors-overview#24-hour-rolling-min-max"></span>`leading_price_max` | Leading 24h Maximum Price | 24h-Höchstpreis vorlaufend | Fremtidig 24t maksimumspris | Komende 24u Maximumprijs | Framåt 24h maximipris | ❌ |

### Future Price Averages


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-next_avg_1h" class="entity-anchor"></span>`next_avg_1h` | ⌀ Price Next 1h | ⌀ Preis nächste 1h | ⌀ Pris neste 1t | ⌀ Prijs Komende 1u | ⌀ Pris nästa 1h | ✅ |
| <span id="ref-next_avg_2h" class="entity-anchor"></span>`next_avg_2h` | ⌀ Price Next 2h | ⌀ Preis nächste 2h | ⌀ Pris neste 2t | ⌀ Prijs Komende 2u | ⌀ Pris nästa 2h | ✅ |
| <span id="ref-next_avg_3h" class="entity-anchor"></span>`next_avg_3h` | ⌀ Price Next 3h | ⌀ Preis nächste 3h | ⌀ Pris neste 3t | ⌀ Prijs Komende 3u | ⌀ Pris nästa 3h | ✅ |
| <span id="ref-next_avg_4h" class="entity-anchor"></span>`next_avg_4h` | ⌀ Price Next 4h | ⌀ Preis nächste 4h | ⌀ Pris neste 4t | ⌀ Prijs Komende 4u | ⌀ Pris nästa 4h | ✅ |
| <span id="ref-next_avg_5h" class="entity-anchor"></span>`next_avg_5h` | ⌀ Price Next 5h | ⌀ Preis nächste 5h | ⌀ Pris neste 5t | ⌀ Prijs Komende 5u | ⌀ Pris nästa 5h | ✅ |
| <span id="ref-next_avg_6h" class="entity-anchor"></span>`next_avg_6h` | ⌀ Price Next 6h | ⌀ Preis nächste 6h | ⌀ Pris neste 6t | ⌀ Prijs Komende 6u | ⌀ Pris nästa 6h | ❌ |
| <span id="ref-next_avg_8h" class="entity-anchor"></span>`next_avg_8h` | ⌀ Price Next 8h | ⌀ Preis nächste 8h | ⌀ Pris neste 8t | ⌀ Prijs Komende 8u | ⌀ Pris nästa 8h | ❌ |
| <span id="ref-next_avg_12h" class="entity-anchor"></span>`next_avg_12h` | ⌀ Price Next 12h | ⌀ Preis nächste 12h | ⌀ Pris neste 12t | ⌀ Prijs Komende 12u | ⌀ Pris nästa 12h | ❌ |

### Price Level Sensors


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-current_interval_price_level" class="entity-anchor" data-refs="sensors-ratings-levels#available-level-sensors"></span>`current_interval_price_level` | Current Price Level | Aktuelles Preisniveau | Nåværende prisnivå | Huidig Prijsniveau | Aktuell prisnivå | ✅ |
| <span id="ref-next_interval_price_level" class="entity-anchor" data-refs="sensors-ratings-levels#available-level-sensors"></span>`next_interval_price_level` | Next Price Level | Nächstes Preisniveau | Neste prisnivå | Volgend Prijsniveau | Nästa prisnivå | ✅ |
| <span id="ref-previous_interval_price_level" class="entity-anchor" data-refs="sensors-ratings-levels#available-level-sensors"></span>`previous_interval_price_level` | Previous Price Level | Vorheriges Preisniveau | Forrige prisnivå | Vorig Prijsniveau | Föregående prisnivå | ❌ |
| <span id="ref-current_hour_price_level" class="entity-anchor" data-refs="sensors-ratings-levels#available-level-sensors"></span>`current_hour_price_level` | Current Hour Price Level | Aktuelles Stunden-Preisniveau | Nåværende timepris nivå | Huidig Uur Prijsniveau | Aktuell timprisnivå | ✅ |
| <span id="ref-next_hour_price_level" class="entity-anchor" data-refs="sensors-ratings-levels#available-level-sensors"></span>`next_hour_price_level` | Next Hour Price Level | Nächstes Stunden-Preisniveau | Neste timepris nivå | Volgend Uur Prijsniveau | Nästa timprisnivå | ✅ |
| <span id="ref-yesterday_price_level" class="entity-anchor" data-refs="sensors-ratings-levels#available-level-sensors"></span>`yesterday_price_level` | Yesterday's Price Level | Preisniveau gestern | Prisnivå i går | Gisteren Prijsniveau | Gårdagens prisnivå | ❌ |
| <span id="ref-today_price_level" class="entity-anchor" data-refs="sensors-ratings-levels#available-level-sensors"></span>`today_price_level` | Today's Price Level | Preisniveau heute | Prisnivå i dag | Vandaag Prijsniveau | Dagens prisnivå | ✅ |
| <span id="ref-tomorrow_price_level" class="entity-anchor" data-refs="sensors-ratings-levels#available-level-sensors"></span>`tomorrow_price_level` | Tomorrow's Price Level | Preisniveau morgen | Prisnivå i morgen | Morgen Prijsniveau | Morgondagens prisnivå | ✅ |

### Price Rating Sensors


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-current_interval_price_rating" class="entity-anchor" data-refs="sensors-ratings-levels#available-rating-sensors"></span>`current_interval_price_rating` | Current Price Rating | Aktuelle Preisbewertung | Nåværende prisvurdering | Huidige Prijsbeoordeling | Aktuellt prisbetyg | ❌ |
| <span id="ref-next_interval_price_rating" class="entity-anchor" data-refs="sensors-ratings-levels#available-rating-sensors"></span>`next_interval_price_rating` | Next Price Rating | Nächste Preisbewertung | Neste prisvurdering | Volgende Prijsbeoordeling | Nästa prisbetyg | ❌ |
| <span id="ref-previous_interval_price_rating" class="entity-anchor" data-refs="sensors-ratings-levels#available-rating-sensors"></span>`previous_interval_price_rating` | Previous Price Rating | Vorherige Preisbewertung | Forrige prisvurdering | Vorige Prijsbeoordeling | Föregående prisbetyg | ❌ |
| <span id="ref-current_hour_price_rating" class="entity-anchor" data-refs="sensors-ratings-levels#available-rating-sensors"></span>`current_hour_price_rating` | Current Hour Price Rating | Aktuelle Stunden-Preisbewertung | Nåværende timeprisvurdering | Huidig Uur Prijsbeoordeling | Aktuellt timprisbetyg | ❌ |
| <span id="ref-next_hour_price_rating" class="entity-anchor" data-refs="sensors-ratings-levels#available-rating-sensors"></span>`next_hour_price_rating` | Next Hour Price Rating | Nächste Stunden-Preisbewertung | Neste timeprisvurdering | Volgend Uur Prijsbeoordeling | Nästa timprisbetyg | ❌ |
| <span id="ref-yesterday_price_rating" class="entity-anchor" data-refs="sensors-ratings-levels#available-rating-sensors"></span>`yesterday_price_rating` | Yesterday's Price Rating | Preisbewertung gestern | Prisvurdering i går | Gisteren Prijsbeoordeling | Gårdagens prisbetyg | ❌ |
| <span id="ref-today_price_rating" class="entity-anchor" data-refs="sensors-ratings-levels#available-rating-sensors"></span>`today_price_rating` | Today's Price Rating | Preisbewertung heute | Prisvurdering i dag | Vandaag Prijsbeoordeling | Dagens prisbetyg | ❌ |
| <span id="ref-tomorrow_price_rating" class="entity-anchor" data-refs="sensors-ratings-levels#available-rating-sensors"></span>`tomorrow_price_rating` | Tomorrow's Price Rating | Preisbewertung morgen | Prisvurdering i morgen | Morgen Prijsbeoordeling | Morgondagens prisbetyg | ❌ |
| <span id="ref-daily_rating" class="entity-anchor"></span>`daily_rating` | Daily Price Rating | Tägliche Preisbewertung | Daglig prisvurdering | Dagelijkse Prijsbeoordeling | Dagligt prisbetyg | ✅ |
| <span id="ref-monthly_rating" class="entity-anchor"></span>`monthly_rating` | Monthly Price Rating | Monatliche Preisbewertung | Månedlig prisvurdering | Maandelijkse Prijsbeoordeling | Månatligt prisbetyg | ✅ |

### Price Outlook & Trend


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-current_price_trend" class="entity-anchor" data-refs="automation-examples#sensor-combination-quick-reference"></span>`current_price_trend` | Current Price Trend | Aktueller Preistrend | Nåværende pristrend | Huidige Prijstrend | Aktuell pristrend | ✅ |
| <span id="ref-next_price_trend_change" class="entity-anchor" data-refs="automation-examples#sensor-combination-quick-reference"></span>`next_price_trend_change` | Next Price Trend Change | Nächste Trendänderung | Neste trendendring | Volgende Prijstrend Wijziging | Nästa pristrendändring | ✅ |
| <span id="ref-next_price_trend_change_in" class="entity-anchor"></span>`next_price_trend_change_in` | Next Price Trend Change In | Nächste Trendänderung in | Neste trendendring om | Volgende Prijstrend Wijziging over | Nästa pristrendändring om | ✅ |
| <span id="ref-price_outlook_1h" class="entity-anchor"></span>`price_outlook_1h` | Price Outlook (1h) | Preisausblick (1h) | Prisutblikk (1t) | Prijsvooruitzicht (1u) | Prisöversikt (1h) | ✅ |
| <span id="ref-price_outlook_2h" class="entity-anchor"></span>`price_outlook_2h` | Price Outlook (2h) | Preisausblick (2h) | Prisutblikk (2t) | Prijsvooruitzicht (2u) | Prisöversikt (2h) | ✅ |
| <span id="ref-price_outlook_3h" class="entity-anchor"></span>`price_outlook_3h` | Price Outlook (3h) | Preisausblick (3h) | Prisutblikk (3t) | Prijsvooruitzicht (3u) | Prisöversikt (3h) | ✅ |
| <span id="ref-price_outlook_4h" class="entity-anchor"></span>`price_outlook_4h` | Price Outlook (4h) | Preisausblick (4h) | Prisutblikk (4t) | Prijsvooruitzicht (4u) | Prisöversikt (4h) | ✅ |
| <span id="ref-price_outlook_5h" class="entity-anchor"></span>`price_outlook_5h` | Price Outlook (5h) | Preisausblick (5h) | Prisutblikk (5t) | Prijsvooruitzicht (5u) | Prisöversikt (5h) | ✅ |
| <span id="ref-price_outlook_6h" class="entity-anchor"></span>`price_outlook_6h` | Price Outlook (6h) | Preisausblick (6h) | Prisutblikk (6t) | Prijsvooruitzicht (6u) | Prisöversikt (6h) | ❌ |
| <span id="ref-price_outlook_8h" class="entity-anchor"></span>`price_outlook_8h` | Price Outlook (8h) | Preisausblick (8h) | Prisutblikk (8t) | Prijsvooruitzicht (8u) | Prisöversikt (8h) | ❌ |
| <span id="ref-price_outlook_12h" class="entity-anchor"></span>`price_outlook_12h` | Price Outlook (12h) | Preisausblick (12h) | Prisutblikk (12t) | Prijsvooruitzicht (12u) | Prisöversikt (12h) | ❌ |
| <span id="ref-price_trajectory_2h" class="entity-anchor"></span>`price_trajectory_2h` | Price Trajectory (2h) | Preisverlauf (2h) | Prisforløp (2t) | Prijstrajectorie (2u) | Prisutveckling (2h) | ✅ |
| <span id="ref-price_trajectory_3h" class="entity-anchor"></span>`price_trajectory_3h` | Price Trajectory (3h) | Preisverlauf (3h) | Prisforløp (3t) | Prijstrajectorie (3u) | Prisutveckling (3h) | ✅ |
| <span id="ref-price_trajectory_4h" class="entity-anchor"></span>`price_trajectory_4h` | Price Trajectory (4h) | Preisverlauf (4h) | Prisforløp (4t) | Prijstrajectorie (4u) | Prisutveckling (4h) | ✅ |
| <span id="ref-price_trajectory_5h" class="entity-anchor"></span>`price_trajectory_5h` | Price Trajectory (5h) | Preisverlauf (5h) | Prisforløp (5t) | Prijstrajectorie (5u) | Prisutveckling (5h) | ✅ |
| <span id="ref-price_trajectory_6h" class="entity-anchor"></span>`price_trajectory_6h` | Price Trajectory (6h) | Preisverlauf (6h) | Prisforløp (6t) | Prijstrajectorie (6u) | Prisutveckling (6h) | ❌ |
| <span id="ref-price_trajectory_8h" class="entity-anchor"></span>`price_trajectory_8h` | Price Trajectory (8h) | Preisverlauf (8h) | Prisforløp (8t) | Prijstrajectorie (8u) | Prisutveckling (8h) | ❌ |
| <span id="ref-price_trajectory_12h" class="entity-anchor"></span>`price_trajectory_12h` | Price Trajectory (12h) | Preisverlauf (12h) | Prisforløp (12t) | Prijstrajectorie (12u) | Prisutveckling (12h) | ❌ |

### Volatility Sensors


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-today_volatility" class="entity-anchor" data-refs="automation-examples#sensor-combination-quick-reference,sensors-volatility#available-volatility-sensors"></span>`today_volatility` | Today's Price Volatility | Volatilität heute | Volatilitet i dag | Vandaag Prijsvolatiliteit | Dagens prisvolatilitet | ✅ |
| <span id="ref-tomorrow_volatility" class="entity-anchor" data-refs="sensors-volatility#available-volatility-sensors"></span>`tomorrow_volatility` | Tomorrow's Price Volatility | Volatilität morgen | Volatilitet i morgen | Morgen Prijsvolatiliteit | Morgondagens prisvolatilitet | ❌ |
| <span id="ref-next_24h_volatility" class="entity-anchor"></span>`next_24h_volatility` | Next 24h Price Volatility | Volatilität der nächsten 24h | Volatilitet neste 24t | Komende 24u Prijsvolatiliteit | Nästa 24h prisvolatilitet | ❌ |
| <span id="ref-today_tomorrow_volatility" class="entity-anchor" data-refs="sensors-volatility#available-volatility-sensors"></span>`today_tomorrow_volatility` | Today+Tomorrow Price Volatility | Volatilität heute+morgen | Volatilitet i dag+i morgen | Vandaag+Morgen Prijsvolatiliteit | Idag+Imorgon prisvolatilitet | ❌ |

### Best Price Timing


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-best_price_end_time" class="entity-anchor" data-refs="sensors-timing#available-timing-sensors"></span>`best_price_end_time` | Best Price End | Bestpreis endet | Beste pris slutter | Beste Prijs Einde | Bästa pris slutar | ✅ |
| <span id="ref-best_price_period_duration" class="entity-anchor" data-refs="sensors-timing#available-timing-sensors"></span>`best_price_period_duration` | Best Price Duration | Bestpreis Dauer | Beste pris varighet | Beste Prijs Duur | Bästa pris varaktighet | ❌ |
| <span id="ref-best_price_remaining_minutes" class="entity-anchor" data-refs="sensors-timing#available-timing-sensors"></span>`best_price_remaining_minutes` | Best Price Remaining Time | Bestpreis verbleibend | Beste pris gjenværende tid | Beste Prijs Resterende Tijd | Bästa pris återstående tid | ✅ |
| <span id="ref-best_price_progress" class="entity-anchor" data-refs="sensors-timing#available-timing-sensors"></span>`best_price_progress` | Best Price Progress | Bestpreis Fortschritt | Beste pris fremgang | Beste Prijs Voortgang | Bästa pris framsteg | ✅ |
| <span id="ref-best_price_next_start_time" class="entity-anchor" data-refs="sensors-timing#available-timing-sensors"></span>`best_price_next_start_time` | Best Price Start | Bestpreis startet | Beste pris starter | Beste Prijs Start | Bästa pris startar | ✅ |
| <span id="ref-best_price_next_in_minutes" class="entity-anchor" data-refs="sensors-timing#available-timing-sensors"></span>`best_price_next_in_minutes` | Best Price Starts In | Bestpreis startet in | Beste pris starter om | Beste Prijs Start Over | Bästa pris startar om | ✅ |

### Peak Price Timing


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-peak_price_end_time" class="entity-anchor" data-refs="sensors-timing#available-timing-sensors"></span>`peak_price_end_time` | Peak Price End | Spitzenpreis endet | Topppris slutter | Piekprijs Einde | Topppris slutar | ✅ |
| <span id="ref-peak_price_period_duration" class="entity-anchor" data-refs="sensors-timing#available-timing-sensors"></span>`peak_price_period_duration` | Peak Price Duration | Spitzenpreis Dauer | Topppris varighet | Piekprijs Duur | Topppris varaktighet | ❌ |
| <span id="ref-peak_price_remaining_minutes" class="entity-anchor" data-refs="sensors-timing#available-timing-sensors"></span>`peak_price_remaining_minutes` | Peak Price Remaining Time | Spitzenpreis verbleibend | Topppris gjenværende tid | Piekprijs Resterende Tijd | Topppris återstående tid | ✅ |
| <span id="ref-peak_price_progress" class="entity-anchor" data-refs="sensors-timing#available-timing-sensors"></span>`peak_price_progress` | Peak Price Progress | Spitzenpreis Fortschritt | Topppris fremgang | Piekprijs Voortgang | Topppris framsteg | ✅ |
| <span id="ref-peak_price_next_start_time" class="entity-anchor" data-refs="sensors-timing#available-timing-sensors"></span>`peak_price_next_start_time` | Peak Price Start | Spitzenpreis startet | Topppris starter | Piekprijs Start | Topppris startar | ✅ |
| <span id="ref-peak_price_next_in_minutes" class="entity-anchor" data-refs="sensors-timing#available-timing-sensors"></span>`peak_price_next_in_minutes` | Peak Price Starts In | Spitzenpreis startet in | Topppris starter om | Piekprijs Start Over | Topppris startar om | ✅ |

### Home & Metering Metadata


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-home_type" class="entity-anchor"></span>`home_type` | Home Type | Wohnungstyp | Boligtype | Huistype | Hemtyp | ❌ |
| <span id="ref-home_size" class="entity-anchor"></span>`home_size` | Home Size | Wohnfläche | Boligareal | Huisgrootte | Hemstorlek | ❌ |
| <span id="ref-main_fuse_size" class="entity-anchor"></span>`main_fuse_size` | Main Fuse Size | Hauptsicherung | Hovedsikring | Hoofdzekering Grootte | Huvudsäkringsstorlek | ❌ |
| <span id="ref-number_of_residents" class="entity-anchor"></span>`number_of_residents` | Number of Residents | Anzahl Bewohner | Antall beboere | Aantal Bewoners | Antal boende | ❌ |
| <span id="ref-primary_heating_source" class="entity-anchor"></span>`primary_heating_source` | Primary Heating Source | Primäre Heizquelle | Primær varmekilde | Primaire Verwarmingsbron | Primär värmekälla | ❌ |
| <span id="ref-grid_company" class="entity-anchor"></span>`grid_company` | Grid Company | Netzbetreiber | Nettselskap | Netbedrijf | Nätbolag | ✅ |
| <span id="ref-grid_area_code" class="entity-anchor"></span>`grid_area_code` | Grid Area Code | Netzgebietscode | Nettområdekode | Netgebiedcode | Nätområdeskod | ❌ |
| <span id="ref-price_area_code" class="entity-anchor"></span>`price_area_code` | Price Area Code | Preiszonencode | Prisområdekode | Prijsgebiedcode | Prisområdeskod | ❌ |
| <span id="ref-consumption_ean" class="entity-anchor"></span>`consumption_ean` | Consumption EAN | Verbrauchs-EAN | Forbruks-EAN | Verbruik EAN | Förbruknings-EAN | ❌ |
| <span id="ref-production_ean" class="entity-anchor"></span>`production_ean` | Production EAN | Erzeugungs-EAN | Produksjons-EAN | Productie EAN | Produktions-EAN | ❌ |
| <span id="ref-energy_tax_type" class="entity-anchor"></span>`energy_tax_type` | Energy Tax Type | Energiesteuertyp | Energiavgiftstype | Energiebelasting Type | Energiskattetyp | ❌ |
| <span id="ref-vat_type" class="entity-anchor"></span>`vat_type` | VAT Type | Mehrwertsteuertyp | MVA-type | BTW Type | Momstyp | ❌ |
| <span id="ref-estimated_annual_consumption" class="entity-anchor"></span>`estimated_annual_consumption` | Estimated Annual Consumption | Geschätzter Jahresverbrauch | Estimert årlig forbruk | Geschat Jaarverbruik | Beräknad årlig förbrukning | ✅ |
| <span id="ref-subscription_status" class="entity-anchor"></span>`subscription_status` | Subscription Status | Abonnementstatus | Abonnementsstatus | Abonnement Status | Abonnemangsstatus | ❌ |

### Data & Diagnostics


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-data_lifecycle_status" class="entity-anchor"></span>`data_lifecycle_status` | Data Lifecycle Status | Datenlebenszyklus-Status | Datalivssyklus-status | Data Levenscyclus Status | Datalivscykelstatus | ✅ |
| <span id="ref-chart_data_export" class="entity-anchor"></span>`chart_data_export` | Chart Data Export | Diagramm-Datenexport | Diagramdataeksport | Grafiekdata Export | Diagramdataexport | ❌ |
| <span id="ref-chart_metadata" class="entity-anchor"></span>`chart_metadata` | Chart Metadata | Diagramm-Metadaten | Diagrammetadata | Grafiek Metadata | Diagrammetadata | ✅ |

### Other


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-current_hour_price_rank_today" class="entity-anchor" data-refs="sensors-volatility#available-sensors"></span>`current_hour_price_rank_today` | ⌀ Hourly Price Current Rank (Today) | ⌀ Stündlicher Preisrang Aktuell (heute) | ⌀ Timesprisrang nå (i dag) | ⌀ Uurlijkse prijsrang huidig (vandaag) | ⌀ Timprisrang aktuell (idag) | ❌ |
| <span id="ref-current_hour_price_rank_today_tomorrow" class="entity-anchor" data-refs="sensors-volatility#available-sensors"></span>`current_hour_price_rank_today_tomorrow` | ⌀ Hourly Price Current Rank (Today+Tomorrow) | ⌀ Stündlicher Preisrang Aktuell (heute+morgen) | ⌀ Timesprisrang nå (i dag+i morgen) | ⌀ Uurlijkse prijsrang huidig (vandaag+morgen) | ⌀ Timprisrang aktuell (idag+imorgon) | ❌ |
| <span id="ref-current_interval_price_rank_today" class="entity-anchor" data-refs="sensors-volatility#available-sensors"></span>`current_interval_price_rank_today` | Current Price Rank (Today) | Aktueller Preisrang (heute) | Aktuell prisrang (i dag) | Huidige prijsrang (vandaag) | Aktuellt prisrang (idag) | ✅ |
| <span id="ref-current_interval_price_rank_today_tomorrow" class="entity-anchor" data-refs="sensors-volatility#available-sensors"></span>`current_interval_price_rank_today_tomorrow` | Current Price Rank (Today+Tomorrow) | Aktueller Preisrang (heute+morgen) | Aktuell prisrang (i dag+i morgen) | Huidige prijsrang (vandaag+morgen) | Aktuellt prisrang (idag+imorgon) | ❌ |
| <span id="ref-current_interval_price_rank_tomorrow" class="entity-anchor" data-refs="sensors-volatility#available-sensors"></span>`current_interval_price_rank_tomorrow` | Current Price Rank (Tomorrow) | Aktueller Preisrang (morgen) | Aktuell prisrang (i morgen) | Huidige prijsrang (morgen) | Aktuellt prisrang (imorgon) | ❌ |
| <span id="ref-day_pattern_today" class="entity-anchor"></span>`day_pattern_today` | Today's Price Pattern | Preismuster Heute | Prismønster i dag | Prijspatroon Vandaag | Prismönster Idag | ✅ |
| <span id="ref-day_pattern_tomorrow" class="entity-anchor"></span>`day_pattern_tomorrow` | Tomorrow's Price Pattern | Preismuster Morgen | Prismønster i morgen | Prijspatroon Morgen | Prismönster Imorgon | ❌ |
| <span id="ref-day_pattern_yesterday" class="entity-anchor"></span>`day_pattern_yesterday` | Yesterday's Price Pattern | Preismuster Gestern | Prismønster i går | Prijspatroon Gisteren | Prismönster Igår | ❌ |
| <span id="ref-next_hour_price_rank_today" class="entity-anchor" data-refs="sensors-volatility#available-sensors"></span>`next_hour_price_rank_today` | ⌀ Hourly Price Next Rank (Today) | ⌀ Stündlicher Preisrang Nächste (heute) | ⌀ Timesprisrang neste (i dag) | ⌀ Uurlijkse prijsrang volgende (vandaag) | ⌀ Timprisrang nästa (idag) | ❌ |
| <span id="ref-next_hour_price_rank_today_tomorrow" class="entity-anchor" data-refs="sensors-volatility#available-sensors"></span>`next_hour_price_rank_today_tomorrow` | ⌀ Hourly Price Next Rank (Today+Tomorrow) | ⌀ Stündlicher Preisrang Nächste (heute+morgen) | ⌀ Timesprisrang neste (i dag+i morgen) | ⌀ Uurlijkse prijsrang volgende (vandaag+morgen) | ⌀ Timprisrang nästa (idag+imorgon) | ❌ |
| <span id="ref-next_interval_price_rank_today" class="entity-anchor" data-refs="sensors-volatility#available-sensors"></span>`next_interval_price_rank_today` | Next Price Rank (Today) | Nächster Preisrang (heute) | Neste prisrang (i dag) | Volgende prijsrang (vandaag) | Nästa prisrang (idag) | ❌ |
| <span id="ref-next_interval_price_rank_today_tomorrow" class="entity-anchor" data-refs="sensors-volatility#available-sensors"></span>`next_interval_price_rank_today_tomorrow` | Next Price Rank (Today+Tomorrow) | Nächster Preisrang (heute+morgen) | Neste prisrang (i dag+i morgen) | Volgende prijsrang (vandaag+morgen) | Nästa prisrang (idag+imorgon) | ❌ |
| <span id="ref-previous_interval_price_rank_today" class="entity-anchor" data-refs="sensors-volatility#available-sensors"></span>`previous_interval_price_rank_today` | Last Price Rank (Today) | Letzter Preisrang (heute) | Forrige prisrang (i dag) | Vorige prijsrang (vandaag) | Förra prisrang (idag) | ❌ |
| <span id="ref-previous_interval_price_rank_today_tomorrow" class="entity-anchor" data-refs="sensors-volatility#available-sensors"></span>`previous_interval_price_rank_today_tomorrow` | Last Price Rank (Today+Tomorrow) | Letzter Preisrang (heute+morgen) | Forrige prisrang (i dag+i morgen) | Vorige prijsrang (vandaag+morgen) | Förra prisrang (idag+imorgon) | ❌ |
## Binary Sensors

### Binary Sensors


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-best_price_period" class="entity-anchor" data-refs="period-calculation#what-are-price-periods,sensors-overview#best-price-period-peak-price-period"></span>`best_price_period` | Best Price Period | Bestpreis-Zeitraum | Lavpris-periode | Beste Prijs Periode | Bästa Prisperiod | ✅ |
| <span id="ref-peak_price_period" class="entity-anchor" data-refs="period-calculation#what-are-price-periods,sensors-overview#best-price-period-peak-price-period"></span>`peak_price_period` | Peak Price Period | Spitzenpreis-Zeitraum | Toppris-periode | Piekprijs Periode | Topprisperiod | ✅ |
| <span id="ref-connection" class="entity-anchor"></span>`connection` | Tibber API Connection | Tibber-API-Verbindung | Tibber API-tilkobling | Tibber API Verbinding | Tibber API-anslutning | ✅ |
| <span id="ref-tomorrow_data_available" class="entity-anchor"></span>`tomorrow_data_available` | Tomorrow's Data Available | Morgige Daten verfügbar | Morgendagens data tilgjengelig | Morgen Gegevens Beschikbaar | Morgondagens data tillgänglig | ✅ |
| <span id="ref-has_ventilation_system" class="entity-anchor"></span>`has_ventilation_system` | Has Ventilation System | Hat Lüftungsanlage | Har ventilasjonsanlegg | Heeft Ventilatiesysteem | Har ventilationssystem | ❌ |
| <span id="ref-realtime_consumption_enabled" class="entity-anchor"></span>`realtime_consumption_enabled` | Realtime Consumption Enabled | Echtzeitverbrauch aktiviert | Sanntidsforbruk aktivert | Realtime Verbruik Ingeschakeld | Realtidsförbrukning aktiverad | ❌ |
## Number Entities (Configuration Overrides)

> These entities allow runtime adjustment of period calculation parameters without changing the integration configuration. All are **disabled by default**.

### Best Price Configuration


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-best_price_flex_override" class="entity-anchor" data-refs="configuration#best-price-period-settings"></span>`best_price_flex_override` | Best Price: Flexibility | Bestpreis: Flexibilität | Beste pris: Fleksibilitet | Beste prijs: Flexibiliteit | Bästa pris: Flexibilitet | ❌ |
| <span id="ref-best_price_min_distance_override" class="entity-anchor" data-refs="configuration#best-price-period-settings"></span>`best_price_min_distance_override` | Best Price: Minimum Distance | Bestpreis: Mindestabstand | Beste pris: Minimumsavstand | Beste prijs: Minimale afstand | Bästa pris: Minimiavstånd | ❌ |
| <span id="ref-best_price_min_period_length_override" class="entity-anchor" data-refs="configuration#best-price-period-settings"></span>`best_price_min_period_length_override` | Best Price: Minimum Period Length | Bestpreis: Mindestperiodenlänge | Beste pris: Minimum periodelengde | Beste prijs: Minimale periodelengte | Bästa pris: Minsta periodlängd | ❌ |
| <span id="ref-best_price_min_periods_override" class="entity-anchor" data-refs="configuration#best-price-period-settings"></span>`best_price_min_periods_override` | Best Price: Minimum Periods | Bestpreis: Mindestperioden | Beste pris: Minimum perioder | Beste prijs: Minimum periodes | Bästa pris: Minsta antal perioder | ❌ |
| <span id="ref-best_price_relaxation_attempts_override" class="entity-anchor" data-refs="configuration#best-price-period-settings"></span>`best_price_relaxation_attempts_override` | Best Price: Relaxation Attempts | Bestpreis: Lockerungsversuche | Beste pris: Lemping forsøk | Beste prijs: Versoepeling pogingen | Bästa pris: Lättnadsförsök | ❌ |
| <span id="ref-best_price_gap_count_override" class="entity-anchor"></span>`best_price_gap_count_override` | Best Price: Gap Tolerance | Bestpreis: Lückentoleranz | Beste pris: Gaptoleranse | Beste prijs: Gap tolerantie | Bästa pris: Glaptolerans | ❌ |

### Peak Price Configuration


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-peak_price_flex_override" class="entity-anchor" data-refs="configuration#peak-price-period-settings"></span>`peak_price_flex_override` | Peak Price: Flexibility | Spitzenpreis: Flexibilität | Topppris: Fleksibilitet | Piekprijs: Flexibiliteit | Topppris: Flexibilitet | ❌ |
| <span id="ref-peak_price_min_distance_override" class="entity-anchor" data-refs="configuration#peak-price-period-settings"></span>`peak_price_min_distance_override` | Peak Price: Minimum Distance | Spitzenpreis: Mindestabstand | Topppris: Minimumsavstand | Piekprijs: Minimale afstand | Topppris: Minimiavstånd | ❌ |
| <span id="ref-peak_price_min_period_length_override" class="entity-anchor" data-refs="configuration#peak-price-period-settings"></span>`peak_price_min_period_length_override` | Peak Price: Minimum Period Length | Spitzenpreis: Mindestperiodenlänge | Topppris: Minimum periodelengde | Piekprijs: Minimale periodelengte | Topppris: Minsta periodlängd | ❌ |
| <span id="ref-peak_price_min_periods_override" class="entity-anchor" data-refs="configuration#peak-price-period-settings"></span>`peak_price_min_periods_override` | Peak Price: Minimum Periods | Spitzenpreis: Mindestperioden | Topppris: Minimum perioder | Piekprijs: Minimum periodes | Topppris: Minsta antal perioder | ❌ |
| <span id="ref-peak_price_relaxation_attempts_override" class="entity-anchor" data-refs="configuration#peak-price-period-settings"></span>`peak_price_relaxation_attempts_override` | Peak Price: Relaxation Attempts | Spitzenpreis: Lockerungsversuche | Topppris: Lemping forsøk | Piekprijs: Versoepeling pogingen | Topppris: Lättnadsförsök | ❌ |
| <span id="ref-peak_price_gap_count_override" class="entity-anchor"></span>`peak_price_gap_count_override` | Peak Price: Gap Tolerance | Spitzenpreis: Lückentoleranz | Topppris: Gaptoleranse | Piekprijs: Gap tolerantie | Topppris: Glaptolerans | ❌ |
## Switch Entities (Configuration Overrides)

> These switches control whether the relaxation algorithm is active for period detection. All are **disabled by default**.

### Switches


| Entity ID suffix | 🇬🇧 English | 🇩🇪 Deutsch | 🇳🇴 Norsk | 🇳🇱 Nederlands | 🇸🇪 Svenska | Default |
|---|---|---|---|---|---|---|
| <span id="ref-best_price_enable_relaxation_override" class="entity-anchor"></span>`best_price_enable_relaxation_override` | Best Price: Achieve Minimum Count | Bestpreis: Mindestanzahl erreichen | Beste pris: Oppnå minimumsantall | Beste prijs: Minimum aantal bereiken | Bästa pris: Uppnå minimiantal | ❌ |
| <span id="ref-peak_price_enable_relaxation_override" class="entity-anchor"></span>`peak_price_enable_relaxation_override` | Peak Price: Achieve Minimum Count | Spitzenpreis: Mindestanzahl erreichen | Topppris: Oppnå minimumsantall | Piekprijs: Minimum aantal bereiken | Topppris: Uppnå minimiantal | ❌ |
