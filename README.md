# KAFD-Malham SFLA Tracker

Interactive map for tracking Safe Forced Landing Area (SFLA) usability along the KAFD to Malham (RYA5) corridor.

## Architecture
- **Frontend:** Leaflet.js dark map on GitHub Pages
- **Backend:** Airtable (Malham Sites + Malham Change Log tables)
- **Data Source:** KML file synced via `sync_kmz.py`

## URLs
- **Live:** https://willslawrence.github.io/sfla-malham-tracker/
- **Repo:** `willslawrence/sfla-malham-tracker`

## Features
- 95 SFLA polygon shapes with status tracking
- 10 GPS waypoints (D1-D7, SFLA RYA5, KAFD-Malham)
- Radial Suitable/Unsuitable buttons
- Age-based color degradation for stale reviews
- GPS tracking, satellite toggle

> 📋 Operational reference (covers both Riyadh UAM and KAFD-Malham trackers): see `memory/sfla.md`
