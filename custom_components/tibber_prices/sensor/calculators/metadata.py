"""Calculator for home metadata, metering point, and subscription data."""

from __future__ import annotations

from .base import TibberPricesBaseCalculator


class TibberPricesMetadataCalculator(TibberPricesBaseCalculator):
    """
    Calculator for home metadata, metering point, and subscription data.

    Handles sensors that expose static or slowly-changing user data from the
    Tibber API, such as home characteristics, metering point information, and
    subscription details.
    """

    def get_home_metadata_value(self, field: str) -> str | int | None:
        """
        Get home metadata value from user data.

        String values are converted to lowercase for ENUM device_class compatibility.

        Args:
            field: The metadata field name (e.g., "type", "size", "mainFuseSize").

        Returns:
            The field value, or None if not available.

        """
        user_homes = self.coordinator.get_user_homes()
        if not user_homes:
            return None

        # Find the home matching this sensor's home_id
        home_id = self.config_entry.data.get("home_id")
        if not home_id:
            return None

        home_data = next((home for home in user_homes if home.get("id") == home_id), None)
        if not home_data:
            return None

        value = home_data.get(field)

        # Convert string to lowercase for ENUM device_class
        if isinstance(value, str):
            return value.lower()

        return value

    def get_metering_point_value(self, field: str) -> str | int | None:
        """
        Get metering point data value from user data.

        Args:
            field: The metering point field name (e.g., "gridCompany", "priceAreaCode").

        Returns:
            The field value, or None if not available.

        """
        user_homes = self.coordinator.get_user_homes()
        if not user_homes:
            return None

        home_id = self.config_entry.data.get("home_id")
        if not home_id:
            return None

        home_data = next((home for home in user_homes if home.get("id") == home_id), None)
        if not home_data:
            return None

        metering_point = home_data.get("meteringPointData")
        if not metering_point:
            return None

        return metering_point.get(field)

    def get_subscription_value(self, field: str) -> str | None:
        """
        Get subscription value from user data.

        String values are converted to lowercase for ENUM device_class compatibility.

        Args:
            field: The subscription field name (e.g., "status").

        Returns:
            The field value, or None if not available.

        """
        user_homes = self.coordinator.get_user_homes()
        if not user_homes:
            return None

        home_id = self.config_entry.data.get("home_id")
        if not home_id:
            return None

        home_data = next((home for home in user_homes if home.get("id") == home_id), None)
        if not home_data:
            return None

        subscription = home_data.get("currentSubscription")
        if not subscription:
            return None

        value = subscription.get(field)

        # Convert string to lowercase for ENUM device_class
        if isinstance(value, str):
            return value.lower()

        return value

    def get_day_pattern_value(self, day: str) -> str | None:
        """
        Get the detected price pattern for a calendar day.

        Args:
            day: One of "yesterday", "today", or "tomorrow".

        Returns:
            Pattern string (e.g. "valley", "peak", "flat") or None if not available.

        """
        if not self.coordinator.data:
            return None

        day_patterns = self.coordinator.data.get("dayPatterns")
        if not day_patterns:
            return None

        day_data = day_patterns.get(day)
        if not day_data:
            return None

        return day_data.get("pattern")

    def get_current_price_phase_value(self) -> str | None:
        """
        Get the current intra-day price phase (rising / falling / flat).

        Finds the monotone segment in today's day-pattern that covers the
        current time and returns its type string.

        Returns:
            "rising", "falling", or "flat", or None if data is unavailable.

        """
        if not self.coordinator.data:
            return None

        day_patterns = self.coordinator.data.get("dayPatterns")
        if not day_patterns:
            return None

        today_data = day_patterns.get("today")
        if not today_data:
            return None

        segments: list[dict] | None = today_data.get("segments")
        if not segments:
            return None

        from homeassistant.util.dt import parse_datetime  # noqa: PLC0415

        now = self.coordinator.time.now()
        current_segment: dict | None = None
        for segment in segments:
            seg_start_str: str | None = segment.get("start")
            if not seg_start_str:
                continue
            seg_start = parse_datetime(seg_start_str)
            if seg_start is not None and now >= seg_start:
                current_segment = segment

        if current_segment is None:
            return None

        return current_segment.get("type")

    def get_next_price_phase_value(self) -> str | None:
        """
        Get the next intra-day price phase (rising / falling / flat).

        Finds the monotone segment in today's day-pattern that starts after
        the current segment and returns its type string.

        Returns:
            "rising", "falling", or "flat", or None if no next segment exists.

        """
        if not self.coordinator.data:
            return None

        day_patterns = self.coordinator.data.get("dayPatterns")
        if not day_patterns:
            return None

        today_data = day_patterns.get("today")
        if not today_data:
            return None

        segments: list[dict] | None = today_data.get("segments")
        if not segments:
            return None

        from homeassistant.util.dt import parse_datetime  # noqa: PLC0415

        now = self.coordinator.time.now()
        current_index: int | None = None
        for i, segment in enumerate(segments):
            seg_start_str: str | None = segment.get("start")
            if not seg_start_str:
                continue
            seg_start = parse_datetime(seg_start_str)
            if seg_start is not None and now >= seg_start:
                current_index = i

        if current_index is None or current_index + 1 >= len(segments):
            return None

        return segments[current_index + 1].get("type")

    def _find_current_segment(self) -> tuple[int, list[dict]] | tuple[None, None]:
        """
        Find the currently active segment in today's day pattern.

        Returns:
            Tuple of (current_index, segments) or (None, None) if unavailable.

        """
        if not self.coordinator.data:
            return None, None

        day_patterns = self.coordinator.data.get("dayPatterns")
        if not day_patterns:
            return None, None

        today_data = day_patterns.get("today")
        if not today_data:
            return None, None

        segments: list[dict] | None = today_data.get("segments")
        if not segments:
            return None, None

        from homeassistant.util.dt import parse_datetime  # noqa: PLC0415

        now = self.coordinator.time.now()
        current_index: int | None = None
        for i, segment in enumerate(segments):
            seg_start_str: str | None = segment.get("start")
            if not seg_start_str:
                continue
            seg_start = parse_datetime(seg_start_str)
            if seg_start is not None and now >= seg_start:
                current_index = i

        if current_index is None:
            return None, None

        return current_index, segments

    def get_price_phase_timing_value(self, value_type: str) -> object:
        """
        Get timing-related values for the current intra-day price phase segment.

        Args:
            value_type: One of "end_time", "remaining_minutes", "duration", "progress".

        Returns:
            - datetime for "end_time"
            - int/float for duration/remaining/progress (0 when no active segment)
            - None for timestamps when no segment is available

        """
        current_index, segments = self._find_current_segment()
        if current_index is None or segments is None:
            return 0 if value_type in ("remaining_minutes", "duration", "progress") else None

        seg = segments[current_index]
        time = self.coordinator.time

        if value_type == "end_time":
            end_str: str | None = seg.get("end")
            if not end_str:
                return None
            from homeassistant.util.dt import parse_datetime  # noqa: PLC0415

            return parse_datetime(end_str)

        if value_type == "remaining_minutes":
            end_str = seg.get("end")
            if not end_str:
                return 0
            minutes = time.minutes_until_rounded(end_str)
            return max(0, minutes)

        if value_type == "duration":
            start_str: str | None = seg.get("start")
            end_str = seg.get("end")
            if not start_str or not end_str:
                return None
            from homeassistant.util.dt import parse_datetime  # noqa: PLC0415

            start_dt = parse_datetime(start_str)
            end_dt = parse_datetime(end_str)
            if start_dt is None or end_dt is None:
                return None
            return max(0.0, (end_dt - start_dt).total_seconds() / 60)

        if value_type == "progress":
            start_str = seg.get("start")
            end_str = seg.get("end")
            if not start_str or not end_str:
                return 0
            from homeassistant.util.dt import parse_datetime  # noqa: PLC0415

            start_dt = parse_datetime(start_str)
            end_dt = parse_datetime(end_str)
            if start_dt is None or end_dt is None:
                return 0
            now = time.now()
            total = (end_dt - start_dt).total_seconds()
            if total <= 0:
                return 0
            elapsed = (now - start_dt).total_seconds()
            return min(100.0, max(0.0, (elapsed / total) * 100))

        return None

    def get_next_phase_of_type_value(self, phase_type: str, value_type: str) -> object:
        """
        Find the next intra-day phase of a given type and return its timing.

        Searches remaining segments for today (after current) plus all of tomorrow.

        Args:
            phase_type: "rising", "falling", or "flat".
            value_type: "start_time" (returns datetime) or "in_minutes" (returns int).

        Returns:
            - datetime for "start_time"
            - int for "in_minutes"
            - None if no future segment of this type exists

        """
        if not self.coordinator.data:
            return None

        day_patterns = self.coordinator.data.get("dayPatterns")
        if not day_patterns:
            return None

        current_index, today_segments = self._find_current_segment()
        if today_segments is None:
            return None

        # Remaining segments in today (after current index)
        start_idx = (current_index + 1) if current_index is not None else 0
        remaining_today: list[dict] = today_segments[start_idx:]

        # All segments in tomorrow (if available)
        tomorrow_data = day_patterns.get("tomorrow")
        tomorrow_segments: list[dict] = tomorrow_data.get("segments", []) if tomorrow_data else []

        # Search in order: remaining today → all tomorrow
        for segment in (*remaining_today, *tomorrow_segments):
            if segment.get("type") == phase_type:
                start_str: str | None = segment.get("start")
                if not start_str:
                    continue
                if value_type == "start_time":
                    from homeassistant.util.dt import parse_datetime  # noqa: PLC0415

                    return parse_datetime(start_str)
                if value_type == "in_minutes":
                    return self.coordinator.time.minutes_until_rounded(start_str)

        return None
