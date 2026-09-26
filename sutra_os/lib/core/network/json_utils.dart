/// Defensive JSON accessors.
///
/// API payloads are decoded dynamically, so a `as Map<String, dynamic>` cast on
/// a shape change throws a `TypeError` and red-screens the app. These helpers
/// coerce instead of throwing, so a single unexpected field degrades to a
/// default value rather than a crash.
library;

Map<String, dynamic> asMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return value.map((k, v) => MapEntry(k.toString(), v));
  return const {};
}

List<dynamic> asList(dynamic value) => value is List ? value : const [];

/// Ids are UUIDs on the wire and strings in the domain, so always normalise.
String asId(dynamic value) => value?.toString() ?? '';

String asString(dynamic value, {String fallback = ''}) {
  if (value == null) return fallback;
  return value is String ? value : value.toString();
}

String? asStringOrNull(dynamic value) {
  if (value == null) return null;
  final s = value is String ? value : value.toString();
  return s.isEmpty ? null : s;
}

int asInt(dynamic value, {int fallback = 0}) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value) ?? fallback;
  return fallback;
}

int? asIntOrNull(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value);
  return null;
}

double asDouble(dynamic value, {double fallback = 0}) {
  if (value is double) return value;
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value) ?? fallback;
  return fallback;
}

/// Like [asDouble] but preserves "the server did not report this", which is
/// distinct from a genuine zero for resource gauges.
double? asDoubleOrNull(dynamic value) {
  if (value is double) return value;
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value);
  return null;
}

bool asBool(dynamic value, {bool fallback = false}) {
  if (value is bool) return value;
  if (value is String) {
    if (value.toLowerCase() == 'true') return true;
    if (value.toLowerCase() == 'false') return false;
  }
  return fallback;
}

/// Reads the first present key from [keys], tolerating both snake_case and
/// camelCase conventions.
T pick<T>(
  Map<String, dynamic> json,
  List<String> keys,
  T Function(dynamic value) parse,
  T fallback,
) {
  for (final key in keys) {
    if (json.containsKey(key) && json[key] != null) {
      return parse(json[key]);
    }
  }
  return fallback;
}

/// ISO-8601 timestamp to a compact display string. Falls back to the raw value
/// so an unexpected format is visible rather than hidden.
String asDisplayDate(dynamic value, {String fallback = '—'}) {
  if (value == null) return fallback;
  final raw = value is String ? value : value.toString();
  if (raw.isEmpty) return fallback;
  final parsed = DateTime.tryParse(raw);
  if (parsed == null) return raw;
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  return '${months[parsed.month - 1]} ${parsed.day}, ${parsed.year}';
}
