import pandas as pd
import re

#---------- Name building ---------------
def build_full_name(row: pd.Series) -> str:
    """
    Combines Name 1 through Name 6

    Name structure (from OFSI documentation):
      Name 1 = First name (populated for individuals; blank for many entities)
      Name 2 = The second name (NOT surname) of the individual
      Name 3–5 = Additional parts
      Name 6 = Last Name/ Surname
    """
    name_cols = ['Name 1', 'Name 2', 'Name 3', 'Name 4', 'Name 5', 'Name 6']
    # Filter out nulls and join with a space
    names = [str(row[col]).strip().lower() for col in name_cols if pd.notnull(row[col]) and str(row[col]).strip() != '']
    return ' '.join(names)

#---------- Combining Country  ---------------

def combine_countries(row):
    """Combines all geographic references"""
    cols = ['Address Country', 'Nationality(/ies)', 'Country of birth']
    countries = [str(row[col]).strip() for col in cols if pd.notnull(row[col]) and str(row[col]).strip() != '']
    return countries

def clean_list(item_list):
    """Helper function to remove nulls, split by ',' or '|', deduplicate, and join into a string"""
    clean_items = []
    
    for i in item_list:
        if pd.notnull(i) and str(i).strip() != '':
            split_parts = re.split(r'[,|]', str(i))
            for part in split_parts:
                cleaned_part = part.strip()
                if cleaned_part != '':
                    clean_items.append(cleaned_part)
    return ', '.join(sorted(list(set(clean_items))))



def clean_phone(phone_str):
    """Removes apostrophes and drops invalid negative reference codes."""
    if pd.isna(phone_str):
        return None
    p = str(phone_str).replace("'", "").strip()
    # drop internal negative ref codes
    if re.match(r'^-\d+$', p):
        return None
    return p
#---------- Solving name type issue  ---------------

def normalise_name_type(name_type: str) -> str:
    """Standardise case variations in Name type field."""
    if pd.isna(name_type):
        return "Unknown"
    nt = str(name_type).strip()
    mapping = {
        "Primary Name"          : "Primary Name",
        "Primary name"          : "Primary Name",        # inconsistent casing fix
        "Primary Name Variation": "Primary Name Variation",  
        "Primary name variation": "Primary Name Variation",  # inconsistent casing fix
        "Alias"                 : "Alias",
        "ALias"                 : "Alias",               # typo fix
    }
    return mapping.get(nt, nt)



#---------- Standardising DOB  ---------------

def clean_dob_for_kyc(dob_str):
    """
    Cleans messy DOB formats from the UK Sanctions list.
    Retains maximum precision without inventing false dates.
    """
    if pd.isna(dob_str):
        return None
        
    s = str(dob_str).strip()
    
    # Full date
    if re.match(r'^\d{2}/\d{2}/\d{4}$', s):
        return s
        
    # year only placeholder
    match_year_ph = re.match(r'^dd/mm/(\d{4})$', s, re.IGNORECASE)
    if match_year_ph:
        return match_year_ph.group(1)
        
    # Month & Year with placeholders
    match_mo_year = re.match(r'^dd/(\d{2})/(\d{4})$', s, re.IGNORECASE)
    if match_mo_year:
        return f"{match_mo_year.group(1)}/{match_mo_year.group(2)}"
        
    # Bare year
    if re.match(r'^\d{4}$', s):
        return s
    s = s.replace("'", "") # Remove rogue single quotes like "'00/00/1975"
    
    # "00/00/1975" -> Extract "1975"
    match_zeros = re.search(r'00/00/(\d{4})', s)
    if match_zeros:
        return match_zeros.group(1)
        
    # "15/08/19yy" -> Standardize unknown years with "XX"
    s = s.replace("yy", "XX").replace("YY", "XX")
    return s


def aggregate_entity(group):
    # Entity Type
    entity_types = group['Designation Type'].dropna().unique()
    entity_type = entity_types[0] if len(entity_types) > 0 else "Unknown"
    if 'Gender' in group.columns:
        genders = group['Gender'].dropna().unique()
        gender = genders[0] if len(genders) > 0 else ""
    else:
        gender = ""
    # Names (Separating Primary from Aliases)
    primary_names = [name for name in group[group['Clean_Name_Type'] == 'Primary Name']['Full_Name'].tolist() if name.strip() != '']
    primary_name = primary_names[0] if primary_names else group['Full_Name'].iloc[0]
    
    all_names = group['Full_Name'].unique().tolist()
    aliases = [n for n in all_names if n != primary_name]
    
    # Aggregating multi-value fields into lists
    dobs = group['Clean_DOB'].tolist()
    countries = []
    for c_list in group['All_Countries_List']:
        countries.extend(c_list)
        
    passports = group['Passport number'].tolist()
    nat_ids = group['National Identifier number'].tolist()
    
    sanctions = group['Sanctions Imposed'].tolist() if 'Sanctions Imposed' in group.columns else []
    phones = [clean_phone(p) for p in group['Phone number'] if pd.notnull(p)] if 'Phone number' in group.columns else []
    emails = group['Email address'].tolist() if 'Email address' in group.columns else []
    imos = group['IMO number'].tolist() if 'IMO number' in group.columns else []
    positions = group['Position'].tolist() if 'Position' in group.columns else []
    
    regimes = group['Regime Name'].dropna().unique()
    regime = regimes[0] if len(regimes) > 0 else ""
    
    return pd.Series({
        'Unique_ID': group['Unique ID'].iloc[0],
        'Entity_Type': entity_type,
        'Primary_Name': primary_name,
        'Aliases': clean_list(aliases),
        'DOBs': clean_list(dobs),
        'Gender': gender,
        'Associated_Countries': clean_list(countries),
        'Passport_Numbers': clean_list(passports),
        'National_IDs': clean_list(nat_ids),
        'IMO_Numbers': clean_list(imos),
        'Phone_Numbers': clean_list(phones),
        'Email_Addresses': clean_list(emails),
        'Positions_Titles': clean_list(positions),
        'Sanctions_Regime': regime,
        'Sanctions_Imposed': clean_list(sanctions)
    })

def main():
    input_file  = "UK-Sanctions-List.csv"
    output_file  = "sanctions_clean.csv"
    print("Loading raw data...")
    df = pd.read_csv(input_file,header=1,low_memory=False)

    print("Removing exact row duplicates...")
    df.drop_duplicates(inplace=True)

    print("Applying row-level formatting...")
    df['Full_Name'] = df.apply(build_full_name, axis=1)
    df['Clean_Name_Type'] = df['Name type'].apply(normalise_name_type)
    df['Clean_DOB'] = df['D.O.B'].apply(clean_dob_for_kyc)
    df['All_Countries_List'] = df.apply(combine_countries, axis=1)

    print("Aggregating entities by Unique ID...")
    clean_df = df.groupby('Unique ID').apply(aggregate_entity).reset_index(drop=True)
    
    print(f"Exporting structured dataset to {output_file}...")
    clean_df.to_csv(output_file, index=False)
    print("Done!")

if __name__ == "__main__":
    main()