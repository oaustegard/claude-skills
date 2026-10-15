<!-- Split from aboard-io/tinylittleoffice skill/tinyoffice/SKILL.md (MIT). Build a link from an example with scripts/tlo.py. -->

# trip: a route on a map

A table `Place | Lat:number | Lon:number | Note`, in decimal degrees. `units: km` or `units: miles` in the head (driving hours are estimated otherwise); `route: dots` for places that stand alone, not a route.

A week in Portugal:

```
---
units: km
---
Place | Lat:number | Lon:number | Note
--- | --- | --- | ---
Lisbon | 38.7223 | -9.1393 | Pastéis de nata in Belém, then the 28 tram up to Graça
Sintra | 38.8029 | -9.3817 | Pena Palace first thing, before the tour buses
Óbidos | 39.3606 | -9.1571 | Walk the town walls; ginjinha in a chocolate cup
Coimbra | 40.2033 | -8.4103 | The Joanina Library: book the 10 am slot
Porto | 41.1579 | -8.6291 | Port cellars across the river in Gaia
```

Templates: A weekend in Copenhagen, Iceland’s Ring Road, A Dublin food crawl, Yosemite’s Mist Trail loop, The Loire by bike, A college tour, A week in Portugal, Down the Pacific coast, The Scottish Highlands, Rome, the places to see, Japan by rail, The last 100 km of the Camino, New York in the movies, A wedding on Lake Como. Its own files: `.gpx`, `.geojson`.
