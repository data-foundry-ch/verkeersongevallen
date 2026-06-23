-- Accidents per official A2 km (BRON HECTOMETER / 10 = km along the road).
-- Run in DuckDB, e.g.:
--   duckdb data/processed/accidents.duckdb < sql/queries/accidents_per_km.sql

LOAD spatial;

WITH scored AS (
    SELECT
        a.accident_id,
        a.accident_year,
        a.severity,
        COALESCE(
            a.hm / 10.0,
            (TRY_CAST(hi.BEGKM AS DOUBLE) + TRY_CAST(hi.ENDKM AS DOUBLE)) / 2.0
        ) AS road_km
    FROM accidents_a2_norm a
    INNER JOIN roads_a2_norm r ON a.wegvak_id = r.wegvak_id
    LEFT JOIN raw_nwb_hectointervallen hi
        ON CAST(hi.WVK_ID AS VARCHAR) = r.wegvak_id
    WHERE COALESCE(r.carriageway, '') = 'HR'
      AND a.accident_year BETWEEN 2015 AND 2024
)
SELECT
    FLOOR(road_km)::INTEGER AS road_km,
    COUNT(*) AS accident_count
FROM scored
WHERE road_km IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- Boxtel corridor example (km 115–145):
-- SELECT * FROM (...) WHERE road_km BETWEEN 115 AND 145;
