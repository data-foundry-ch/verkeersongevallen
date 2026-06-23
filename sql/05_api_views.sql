-- API helper views for FastAPI queries

CREATE OR REPLACE VIEW api_a2_meta AS
SELECT
    (SELECT COUNT(*) FROM accidents_a2_norm) AS a2_accident_count,
    (SELECT COUNT(*) FROM accidents_a2_norm WHERE location_quality = 'unresolved') AS a2_unresolved_count,
    (SELECT COUNT(*) FROM roads_a2_norm) AS a2_segment_count,
    (SELECT MIN(accident_year) FROM accidents_a2_norm) AS year_min,
    (SELECT MAX(accident_year) FROM accidents_a2_norm) AS year_max,
    (SELECT COUNT(*) FROM raw_bron_accidents) AS total_accident_count;

CREATE OR REPLACE VIEW api_a2_severities AS
SELECT DISTINCT severity
FROM accidents_a2_norm
WHERE severity IS NOT NULL
ORDER BY severity;

CREATE OR REPLACE VIEW api_a2_yearly_stats AS
SELECT accident_year, COUNT(*) AS accident_count
FROM accidents_a2_norm
GROUP BY accident_year
ORDER BY accident_year;

CREATE OR REPLACE VIEW api_a2_severity_stats AS
SELECT severity, COUNT(*) AS accident_count
FROM accidents_a2_norm
GROUP BY severity
ORDER BY accident_count DESC;

CREATE OR REPLACE VIEW api_a2_location_quality AS
SELECT location_quality, COUNT(*) AS accident_count
FROM accidents_a2_norm
GROUP BY location_quality
ORDER BY accident_count DESC;

CREATE OR REPLACE VIEW api_a2_top_bins AS
SELECT
    b.bin_id,
    b.bin_size_km,
    b.bin_start_m,
    b.bin_end_m,
    SUM(c.accident_count) AS accident_count
FROM road_bins_a2 b
LEFT JOIN accident_bin_counts_a2 c ON b.bin_id = c.bin_id AND b.bin_size_km = c.bin_size_km
WHERE b.bin_size_km = 1
GROUP BY b.bin_id, b.bin_size_km, b.bin_start_m, b.bin_end_m
ORDER BY accident_count DESC
LIMIT 10;

CREATE OR REPLACE VIEW api_roads_summary AS
SELECT
    'A2' AS road_number,
    (SELECT COUNT(*) FROM roads_a2_norm) AS segment_count,
    (SELECT COUNT(*) FROM accidents_a2_norm) AS accident_count,
    (SELECT ST_Extent(ST_Envelope(geom_wgs84)) FROM roads_a2_norm WHERE geom_wgs84 IS NOT NULL) AS bbox_wkt,
    'implemented' AS status;
