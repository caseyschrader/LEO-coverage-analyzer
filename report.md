---
generated: 2026-03-18 11:15
query: "Charlotte, North Carolina"
total_locations: 382609
---

# Satellite Internet Obstruction Risk Assessment
## Charlotte, North Carolina

**Prepared for:** North Carolina Office of Broadband Infrastructure
**Analysis Area:** 35.0105°N–35.4003°N, 81.0117°W–80.6349°W
**Locations Assessed:** 382,609

---

## Executive Summary

The Charlotte analysis area presents a generally favorable environment for LEO satellite internet deployment, with **80.2% of committed locations classified as low risk** for canopy-related signal obstruction. However, nearly one in five locations (19.7%) falls into the medium-risk category, reflecting the city's substantial urban and suburban tree canopy — a well-documented characteristic of the Charlotte metro. A small but non-trivial set of 435 locations (0.1%) are classified as high risk, with tree canopy cover exceeding 80%, and will likely require targeted intervention to ensure reliable service delivery.

---

## Methodology

### Data Sources

- **NLCD Tree Canopy Cover (TCC):** USGS National Land Cover Database, providing per-pixel estimates of tree canopy density at 30-meter resolution. This serves as the primary obstruction proxy.
- **Location Fabric:** Broadband serviceable location records within the defined bounding box, each geocoded to a rooftop or parcel centroid.

### Risk Scoring

Each location receives a composite risk score (0.0–1.0) derived primarily from the tree canopy cover percentage at and immediately surrounding the location point. The score reflects the likelihood that overhead vegetation will degrade or block the line-of-sight path between a ground-mounted satellite dish and LEO satellites at typical operating elevations (25°–90° above the horizon).

### Risk Tier Definitions

| Tier | Risk Score | Interpretation |
|------|-----------|----------------|
| **LOW** | < 0.4 | Minimal canopy obstruction expected. Standard dish installation on a rooftop or ground mount should maintain reliable connectivity. |
| **MEDIUM** | 0.4 – 0.7 | Moderate canopy presence. Service may experience intermittent signal degradation, particularly at lower satellite elevation angles. Elevated mounting or selective tree trimming may be warranted. |
| **HIGH** | > 0.7 | Dense canopy overhead. High probability of persistent signal blockage without mitigation. Professional site survey strongly recommended prior to installation. |

---

## Risk Distribution

| Risk Tier | Locations | Percentage |
|-----------|----------|------------|
| Low | 306,699 | 80.2% |
| Medium | 75,475 | 19.7% |
| High | 435 | 0.1% |

The distribution is heavily weighted toward low risk, which is consistent with Charlotte's mix of commercial corridors, newer suburban developments, and open-lot residential neighborhoods where canopy cover is limited or recently established. The **average tree canopy cover across all locations is 31.5%** — moderate, but generally within the operational tolerance of LEO terminals.

The 19.7% medium-risk population (75,475 locations) is the most operationally significant cohort. These locations are concentrated in Charlotte's mature residential neighborhoods — areas such as Myers Park, Dilworth, Plaza Midwood, and portions of east and south Mecklenburg County — where established hardwood canopy (primarily oaks, maples, and tulip poplars) commonly reaches 40–65% overhead coverage. These locations are serviceable but may experience seasonal performance variation.

The 435 high-risk locations, while a small fraction of the total, represent locations where tree canopy cover reaches **81–98%**, effectively enclosing the site in dense overhead vegetation.

---

## Key Findings

1. **Charlotte's "City of Trees" reputation is reflected in the data.** A 31.5% average canopy cover is notably higher than many comparably sized Sun Belt metros, and it drives the relatively large medium-risk population. Charlotte's aggressive urban tree canopy goals and mature Piedmont hardwood forests contribute directly to obstruction risk.

2. **Terrain is not a significant obstruction factor.** Charlotte sits on the gently rolling Piedmont plateau with elevations ranging from approximately 550 to 830 feet ASL across the study area. There are no ridgelines, deep valleys, or steep grades that would meaningfully compound canopy-based obstruction. The risk profile here is almost entirely vegetation-driven.

3. **Deciduous canopy introduces seasonal variability.** The Charlotte region's dominant tree species are deciduous. Locations in the medium-risk tier (and some high-risk locations) will likely experience measurably better satellite signal quality from November through March when leaf-off conditions reduce effective canopy density by an estimated 30–50%. This means summer months represent the worst-case performance window.

4. **Maximum observed canopy cover reaches 98%.** At least some committed locations are situated beneath near-complete forest canopy — likely in riparian buffers, greenway-adjacent parcels, or heavily wooded estate lots in south Charlotte and the area approaching the Catawba River corridor to the west.

5. **The medium-risk cohort warrants the most attention at scale.** While the 435 high-risk locations can be addressed individually, the 75,475 medium-risk locations represent a systemic challenge. Blanket deployment assumptions may underperform at roughly one-fifth of committed locations without differentiated installation practices.

---

## Notable High-Risk Locations

The following five locations represent the highest obstruction risk scores in the analysis area:

| Rank | Location ID | Latitude | Longitude | Risk Score | Canopy Cover |
|------|------------|----------|-----------|------------|-------------|
| 1 | 40686174 | 35.14098 | -80.79728 | 0.807 | 81% |
| 2 | 40717368 | 35.18353 | -80.69259 | 0.805 | 81% |
| 3 | 178457710 | 35.21704 | -80.81287 | 0.803 | 85% |
| 4 | 40267004 | 35.05476 | -80.87367 | 0.801 | 82% |
| 5 | 40536508 | 35.18827 | -80.79678 | 0.800 | 81% |

**Location 178457710** carries the highest canopy density in the top tier at 85% and is situated in north-central Charlotte near the University City / Mallard Creek area, an area with significant remaining mature tree cover interspersed with suburban development. **Location 40267004**, located in the southwestern portion of the study area near the Steele Creek / Lake Wylie corridor, aligns with known heavily wooded parcels along the Catawba River watershed. The remaining top-five locations are distributed across central and eastern Charlotte in areas consistent with mature residential canopy.

All five locations exceed the 80% canopy threshold and should be considered functionally unserviceable without mitigation.

---

## Recommendations

### For High-Risk Locations (435 locations)

1. **Require professional site surveys** before committing to installation. Remote sensing identifies the risk; on-the-ground assessment determines whether mitigation is viable.
2. **Evaluate non-standard mounting options**, including extended mast poles (20–40 ft), chimney mounts, or placement on detached structures (garages, outbuildings) with better sky visibility.
3. **Assess selective vegetation management** in coordination with property owners and local tree ordinances. Charlotte's tree protection ordinances (City Code Chapter 21) may restrict removal of significant trees; trimming within the dish's field-of-view cone may be a more practical path.
4. **Consider alternative technology** for locations where canopy mitigation is impractical. These locations may be better served by fixed wireless, fiber extension, or hybrid solutions. BEAD challenge processes should account for this possibility.

### For Medium-Risk Locations (75,475 locations)

5. **Establish elevated mounting as the default installation standard** for locations with canopy cover above 40%. An