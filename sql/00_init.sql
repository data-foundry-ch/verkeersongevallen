-- DuckDB initialization: spatial extension and helper macros
INSTALL spatial;
LOAD spatial;

-- Ensure consistent SRIDs for transforms
-- RD New (Dutch): EPSG:28992, WGS84: EPSG:4326
