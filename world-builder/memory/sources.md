# Data sources

Every source used by the pipeline, with licence and the attribution string it requires.
Attribution strings are also written into each region's `manifest.json`.

| Source | Used for | Access | Licence | Attribution |
|---|---|---|---|---|
| OpenStreetMap | Roads, footpaths, building footprints, names | `api.openstreetmap.org/api/0.6/map` | ODbL 1.0 | Map data (c) OpenStreetMap contributors |
| Environment Agency LIDAR Composite DSM 1 m (last return) | Building heights, roof shapes, OSM alignment | WCS `environment.data.gov.uk/spatialdata/lidar-composite-digital-surface-model-last-return-dsm-1m/wcs` | OGL v3.0 | Contains Environment Agency information (c) Environment Agency and database right |
| Environment Agency LIDAR Composite DTM 1 m | Terrain heights | WCS `environment.data.gov.uk/spatialdata/lidar-composite-digital-terrain-model-dtm-1m/wcs` | OGL v3.0 | Contains Environment Agency information (c) Environment Agency and database right |

## Candidates (not yet used)
- OS Open Zoomstack / OS OpenMap Local: building footprints cross-check (OGL).
- Copernicus GLO-30: fallback terrain outside EA coverage (reachable via public S3).
