# conus-live

Starting point for a live CONUS flight dashboard. Nothing is wired together yet.

    collector/testing.py   OpenSky auth + one bounded /states/all fetch, with the
                           plan written out in the module docstring
    dashboard/             Flask app serving the D3 map, currently on a mock fleet
                           (see dashboard/README.md to run it)

Intended shape: the collector polls OpenSky and writes snapshots to a store; the
dashboard's mock Fleet is swapped for an adapter that reads from that store. The
HTTP API and browser code stay as they are.

This directory is meant to be moved to other hardware. Do not add machine-specific
paths, and keep credentials out of the tree.
