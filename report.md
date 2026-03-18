---
generated: 2026-03-18 10:25
query: "Indian Trail, North Carolina"
total_locations: 36885
---

# Satellite Internet Coverage Obstruction Risk Assessment
## Indian Trail, North Carolina

**Prepared for:** Telecommunications Regulatory Filing
**Area of Interest:** 35.0182°N–35.1327°N, 80.7270°W–80.5768°W
**Total Broadband Serviceable Locations Assessed:** 36,885

---

## Executive Summary

Indian Trail, North Carolina, presents a **favorable environment for LEO satellite internet service delivery**, with 88.6% of assessed locations classified as low obstruction risk and an average tree canopy cover of just 24.3%. Only 10 locations (< 0.1%) were flagged as high risk due to dense overhead canopy, while 4,208 locations (11.4%) fall into the medium-risk category where some installation accommodations may be required. Overall, the obstruction risk profile for this service area does not present a material barrier to LEO satellite broadband deployment.

---

## Methodology

### Data Sources

- **NLCD Tree Canopy Cover (TCC):** USGS National Land Cover Database tree canopy cover layer, providing per-pixel estimates of canopy density (0–100%) at 30-meter resolution.
- **FCC Broadband Serviceable Location (BSL) Fabric:** Location coordinates for all broadband serviceable locations within the query boundary.

### Risk Scoring

Each location was assigned a composite obstruction risk score (0.0–1.0) anchored primarily on the tree canopy cover percentage extracted at and around the location point. The score accounts for canopy density as a proxy for potential signal path obstruction to LEO satellites, which require a wide, unobstructed view of the sky (typically ≥100° field of view).

### Risk Classification Thresholds

| Tier | Risk Score | Operational Interpretation |
|------|-----------|---------------------------|
| **LOW** | < 0.40 | Standard installation expected; minimal canopy obstruction to satellite field of view. |
| **MEDIUM** | 0.40–0.60 | Elevated obstruction likelihood; may require optimized dish placement, elevated mounting, or selective vegetation management. |
| **HIGH** | > 0.60 | Significant obstruction expected; professional site survey strongly recommended prior to service commitment. Seasonal and growth-related canopy variation may further degrade performance. |

---

## Risk Distribution

| Risk Tier | Location Count | Percentage |
|-----------|---------------|------------|
| Low | 32,667 | 88.6% |
| Medium | 4,208 | 11.4% |
| High | 10 | < 0.1% |

The distribution is heavily skewed toward low risk. The 11.4% medium-risk population is consistent with Indian Trail's suburban development pattern, where residential lots retain moderate tree cover—particularly in older subdivisions and along riparian corridors—but rarely at densities sufficient to severely obstruct a LEO satellite antenna's field of view. The near-zero high-risk count (10 of 36,885) indicates that dense, closed-canopy conditions are exceptionally rare at serviceable locations in this area.

The maximum observed tree canopy cover at any single location was 94.0%, but such values are extreme outliers. The area-wide average of 24.3% TCC reflects a landscape dominated by cleared residential and commercial parcels interspersed with moderate suburban tree cover.

---

## Key Findings

**Geographic and Land Cover Context.** Indian Trail is a rapidly growing suburban municipality in Union County, situated approximately 25 km southeast of Charlotte. The study area spans roughly 12.8 km east-to-west and 12.7 km north-to-south. Land cover is predominantly low-density to medium-density residential development, commercial corridors (notably along US-74 and NC-84), and transitional parcels in various stages of subdivision build-out.

**Canopy Characteristics.** Tree cover in the area is characteristic of the Carolina Piedmont suburban fringe: deciduous hardwood stands (oak-hickory) and scattered loblolly pine interspersed across residential lots. Older neighborhoods and parcels adjoining stream buffers (e.g., tributaries of Crooked Creek and Richardson Creek) exhibit higher canopy densities, accounting for the medium-risk concentration. Newer subdivisions, which dominate much of Indian Trail's recent growth footprint, generally have immature or sparse canopy with minimal obstruction risk.

**Terrain.** The Piedmont terrain in this area is gently rolling with elevation variations of approximately 30–50 meters across the study extent. Terrain-induced obstruction is negligible for LEO constellations at these gradients and does not meaningfully contribute to risk scores.

**Seasonal Variability.** Given the prevalence of deciduous species, locations in the medium-risk tier will experience reduced canopy obstruction during the leaf-off season (approximately November through March), potentially improving winter-period signal reliability. Conversely, full-canopy summer conditions represent the worst-case obstruction scenario captured in the TCC data.

---

## Notable High-Risk Locations

The following five locations represent the highest obstruction risk scores in the study area and warrant individual attention during service provisioning:

| Rank | Location ID | Latitude | Longitude | Risk Score | TCC (%) | Notes |
|------|------------|----------|-----------|------------|---------|-------|
| 1 | 40134795 | 35.12457 | -80.67461 | 0.754 | 86% | Northern portion of study area; likely situated within or adjacent to a dense hardwood stand. Highest risk score in the dataset. |
| 2 | 40122526 | 35.07332 | -80.69160 | 0.729 | 80% | West-central area near older rural-residential parcels with mature canopy. |
| 3 | 40021757 | 35.12961 | -80.61853 | 0.697 | 59% | Northeastern quadrant; moderate TCC but elevated composite score suggests additional contributing factors (e.g., tall surrounding canopy at parcel perimeter). |
| 4 | 40141657 | 35.12033 | -80.72090 | 0.663 | 66% | Northwestern edge of study area, proximate to wooded parcels along the boundary with Stallings/Matthews. |
| 5 | 40134822 | 35.11820 | -80.67970 | 0.627 | 77% | Northern-central area, approximately 500 m from Location 40134795; likely part of the same contiguous canopy zone. |

Locations 40134795 and 40134822 appear spatially clustered in the northern portion of the study area, suggesting a localized zone of dense canopy that could affect a small number of adjacent serviceable locations.

---

## Recommendations

1. **Targeted Site Surveys for High-Risk Locations.** All 10 high-risk locations should receive a pre-installation site survey using a satellite field-of-view assessment tool (e.g., the Starlink obstruction detection feature or a fish-eye lens survey). Given the extremely small count, this represents a negligible operational burden.

2. **Elevated Mounting for Medium-Risk Locations.** For the 4,208 medium-risk locations, providers should plan for potential roof-peak or pole-mount installations (3–6 m above ground level) to clear surrounding canopy. Installer dispatch protocols should include elevated mounting hardware as standard equipment for these addresses.

3. **Seasonal Performance Expectations.** Subscribers at medium-risk locations with deciduous canopy should be advised that service quality may vary seasonally, with best performance during leaf-off months. Providers should factor this into service-level commitment language for affected locations.

4. **Canopy Growth Monitoring.** Indian Trail's suburban expansion includes significant new landscaping and maturing tree plantings. Locations currently classified as low risk in newer subdivisions may migrate toward medium risk over a 5–10 year