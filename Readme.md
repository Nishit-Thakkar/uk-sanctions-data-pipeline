# UK Sanctions List – Data Transformation for KYC Screening

**Author:** Nishit Thakkar  
**Data Source:** [OFSI UK Financial Sanctions List](https://www.gov.uk/government/publications/the-uk-sanctions-list)  
**Last Raw Data Date:** 29 April 2026  
**Python Version:** 3.9.6

---

## Overview

This project extracts, cleanses, and restructures the UK Office of Financial Sanctions Implementation (OFSI) sanctions list into a flat, deduplicated dataset suitable for automated customer screening and fuzzy-logic name matching.

The raw OFSI CSV uses a **cross-product design** each sanctioned entity is spread across many rows, one per name variant. This produces 57,033 rows for only 6,046 unique entities, making it unsuitable for direct use in a screening system. This pipeline collapses those rows into one record per entity.

---

## Repository Structure

```text
├── Data_Transform_script.py   # Main transformation script (Python)
├── UK-Sanctions-List.csv      # Raw OFSI data (input)
├── sanctions_clean.csv        # Cleaned, aggregated output (15 columns, 6,046 rows)
├── analysis.ipynb             # Exploratory data analysis notebook
├── requirements.txt           # Python dependencies
└── README.md                  # Execution instructions and insights
```

---

## How to Run (Tested on Python 3.9.6)

### 1. Install Dependencies
The script relies only on `pandas` and standard Python libraries.
```bash
pip install -r req.txt
```

### 2. Place Input File
Ensure the latest `UK-Sanctions-List.csv` is downloaded and placed in the same root directory as the script.

### 3. Execute the Script
```bash
python Data_Transform_script.py
```
The script will output progress logs to the console, explicitly warning you if any fragile data issues are encountered (e.g., missing primary names), and will generate `sanctions_clean.csv`.

---

## Output Schema (Prepared for Customer Matching)

The cleaned file contains **15 columns**, categorized by how they should be utilized in a bank's matching engine. The data encompasses three entity types: **Individuals**, corporate **Entities**, and **Ships**.

| Column | Source Field(s) | Description | Matching Strategy |
|---|---|---|---|
| `Unique_ID` | `Unique ID` | OFSI's stable identifier for the entity. | Primary Key |
| `Entity_Type` | `Designation Type` | Individual, Entity, or Ship. | Filter / Context |
| `Gender` | `Gender` | Male/Female designation for Individuals. | Hard Match (KYC) |
| `Primary_Name` | `Name 1–6` + `Name type` | The canonical, officially designated name. | Fuzzy Match |
| `Aliases` | `Name 1–6` + `Name type` | Deduplicated list of alternative names/spellings. | Fuzzy Match |
| `DOBs` | `D.O.B` | Cleaned dates of birth. Multiple retained if uncertain. | Soft/Hard Match |
| `Associated_Countries` | `Address Country`, `Nationality`, `Country of birth` | Consolidated geographic footprint. | Soft Match |
| `Passport_Numbers` | `Passport number` | Known passport numbers, deduplicated. | Hard Match |
| `National_IDs` | `National Identifier number` | National identity documents (e.g., SSN equivalents). | Hard Match |
| `IMO_Numbers` | `IMO number` | Maritime vessel numbers (Crucial for Ship entities). | Hard Match |
| `Phone_Numbers` | `Phone number` | Cleansed phone numbers (artefacts removed). | Hard Match |
| `Email_Addresses` | `Email address` | Known email addresses. | Hard Match |
| `Positions_Titles` | `Position` | Known roles or titles (Useful for PEP screening). | Contextual |
| `Sanctions_Regime` | `Regime Name` | Legal sanctions regime (e.g., Russia, Cyber). | Compliance |
| `Sanctions_Imposed` | `Sanctions Imposed` | Sanction type applied (e.g., Asset Freeze). | Compliance |

*Note: Sparsely populated or non-discriminating fields (e.g., `Alias strength`, `Address Line 1-6`, physical ship specifications) were intentionally dropped as they bloat the screening index without improving match accuracy.*

---

## Data Quality Issues Found & How They Were Fixed

### 1. Cross-Product Row Explosion
**Issue:** 6,046 unique entities were spread across 57,033 rows — one row per name variant. Each unique entity can have a primary name, primary name variations, and multiple aliases, all stored as separate rows with the same `Unique ID`.  
**Fix:** Grouped all rows by `Unique ID` using `pandas groupby` and aggregated multi-value fields (names, countries, DOBs, etc.) into deduplicated, comma-separated strings.

---

### 2. Inconsistent Name Type Casing (6 Variants of 3 Values)
**Issue:** The `Name type` field had six spelling variants due to inconsistent casing and a typo:

| Raw Value | Count |
|---|---|
| Alias | 34,303 |
| Primary name | 7,244 |
| Primary Name Variation | 6,153 |
| Primary Name | 6,034 |
| Primary name variation | 3,233 |
| ALias | 2 |

**Fix:** Applied `normalise_name_type()` — a lookup-table mapping all six variants to three canonical values: `Primary Name`, `Primary Name Variation`, `Alias`. This ensured the aggregation logic correctly identified the true primary name for each entity.

---

### 3. Five Different Date of Birth Formats
**Issue:** The `D.O.B` field contained five different formats, with OFSI using placeholder characters (`dd`, `mm`) where parts of the date were unknown:

| Format | Example | Count |
|---|---|---|
| Full date | `30/01/1972` | 16,585 |
| Year only (dd/mm placeholder) | `dd/mm/1958` | 7,510 |
| Month & Year (dd placeholder) | `dd/09/1958` | 526 |
| Year only (bare) | `1971` | 186 |
| Other / partial | `'00/00/1975`, `15/08/19yy` | 2 |

**Fix:** Applied `clean_dob_for_kyc()` — a regex-based parser that extracts maximum precision without inventing false date components (e.g. `dd/mm/1958` → `1958`, `dd/09/1977` → `09/1977`). After aggregation, multiple DOBs for one entity are retained as a comma-separated list rather than discarded.

---

### 4. Leading Apostrophe Artefact in Phone Numbers
**Issue:** Data corruption in the `Phone number` field took two forms:
1. **1,011 rows** contained a leading single quote character (e.g. `'0202-104748`). This is an Excel spreadsheet artefact forcing text formatting. 
2. **Negative integer codes** (e.g. `-101823`, `-222831`) appeared in the raw data. These are clearly internal system reference codes polluting the phone number string. 
**Fix:** Applied a `clean_phone()` validation function to strip the leading `'` character and actively drop any values matching a negative numeric regex pattern.

---

### 5. Exact Duplicate Rows
**Issue:** 650 rows were exact duplicates across all columns.  
**Fix:** Applied `pandas drop_duplicates()` as the first step in the pipeline, before any transformation.

---
## Issue Identified After aggregating the file 

---

### 6. Undetected Pipe-Delimited Duplications
**Issue:** In the `Sanctions Imposed` column, **287 rows** contained duplicated strings separated by a pipe character instead of a comma (e.g. `Shipping sanctions: (see 'Other information')|Shipping sanctions: (see 'Other information')`). Standard comma-splitting deduplication fails on these internal delimiters.
**Fix:** Upgraded the `clean_list()` deduplication function to parse and split strings using both commas and pipes (`re.split(r'[,|]')`), utilizing a case-insensitive set to cleanly deduplicate the arrays.

---

### 7. Inconsistent ALL CAPS Name Formatting
**Issue:** **470 individuals** have their Primary Name formatted entirely in ALL CAPS (e.g. `SAYYED MOHAMMED HAQQANI`), while their aliases are listed in mixed title case. For fuzzy matching algorithms, this casing inconsistency can lower match confidence scores.
**Fix:** Changed all the name to a lower case to keep it consistent for script and also reduce one logic for the final screening script.

---

### 8. Sparse Fields (Expected)
**Issue:** Many KYC fields are sparsely populated by design — OFSI only publishes information it holds. Post-cleaning population rates:

| Field | Populated |
|---|---|
| Unique_ID, Entity_Type, Primary_Name, Sanctions_Regime, Sanctions_Imposed | 100% |
| Associated_Countries | 78.4% |
| DOBs | 54.1% |
| Gender | 48.1% |
| Aliases | 46.3% |
| Positions_Titles | 43.7% |
| Passport_Numbers | 9.4% |
| IMO_Numbers | 10.4% |

**Note:** This sparsity is inherent to the source data, not a cleaning failure. Screening logic must accommodate partial matches.

## Key Design Decisions

**Name splitting (Primary vs Alias):** The script isolates the `Primary Name` row for each entity as the canonical match name. All other name rows — including variations and aliases — are collapsed into `Aliases`. This is important because a fuzzy matcher should weight a hit on the primary name more heavily than a hit on an alias.

**Country consolidation:** Three separate country fields (`Address Country`, `Nationality(/ies)`, `Country of birth`) are merged into a single `Associated_Countries` field. In practice, an individual may appear with only one of these populated — consolidating them maximises the chance of a geographic match against customer records.

**DOB precision retention:** Rather than normalising all DOBs to a single format or discarding partial dates, the script retains whatever precision OFSI provides. A screening system can use year-only DOBs for a weaker signal, and exact DOBs for a stronger one.

**No invented data:** The pipeline never imputes missing values. If a field is unknown, it remains blank. This is essential for a compliance use case where a false positive match is costly and a fabricated data point could cause one.
