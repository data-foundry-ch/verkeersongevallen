# Dutch Road Accident Map — Implementation Roadmap

## A2-first vertical slice

1. [x] Scaffold repo and dependencies
2. [x] DuckDB connection helper with spatial extension
3. [x] Raw data profiler (`make profile`)
4. [x] A2 column/value detection in profiler
5. [x] `column_map.generated.yml` generation
6. [x] `column_map.yml` as mapping layer
7. [x] Raw ingestion into DuckDB (`make ingest`)
8. [x] Normalized road tables (`roads_norm`, `roads_a2_norm`)
9. [x] Normalized accident tables (`accidents_norm`, `accidents_a2_norm`)
10. [x] A2 bin generation (`make bins`)
11. [x] FastAPI A2 endpoints
12. [x] React + MapLibre frontend (default A2)
13. [x] A2 validation report (`make validate`)
14. [x] README and Makefile

## After A2 MVP works

- [ ] Generalize bin generation to all A/N roads
- [ ] Vector tiles / PMTiles serving
- [ ] Direction-specific carriageways
- [ ] Municipality/province filters
- [ ] Time-of-day / day-of-week filters
- [ ] Improved bin geometry via hectometer chainage ordering
- [ ] Full road search UX
