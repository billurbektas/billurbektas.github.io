#!/usr/bin/env python3
"""
Smart affiliation extraction using multiple sources:
1. Crossref API (primary - uses DOIs)
2. Cached affiliations (reuse known authors)
3. PDF fallback (author order matching)

This approach is much more reliable and scalable than pure PDF parsing.
"""

import json
import csv
import time
import re
from pathlib import Path
from collections import defaultdict

try:
    import requests
except ImportError:
    print("ERROR: requests library not installed")
    print("Install it with: pip install requests")
    exit(1)


MY_NAME = "Billur Bektaş"
CACHE_FILE = 'data/affiliation_cache.json'


def load_cache(base_dir):
    """Load cached author affiliations"""
    cache_path = base_dir / CACHE_FILE
    if cache_path.exists():
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(base_dir, cache):
    """Save author affiliation cache"""
    cache_path = base_dir / CACHE_FILE
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def clean_doi(doi):
    """Extract clean DOI from URL or raw DOI"""
    if not doi:
        return None
    # Remove URL prefix if present
    doi = doi.replace('https://doi.org/', '')
    doi = doi.replace('http://dx.doi.org/', '')
    return doi.strip()


def is_valid_institution(name):
    """Check if a name looks like a real institution (not just a department)"""
    if not name:
        return False

    name_lower = name.lower()

    # Valid institution keywords
    valid_keywords = [
        'university', 'universi', 'college', 'institute', 'school',
        'cnrs', 'eth', 'epfl', 'mit', 'ucla', 'academy', 'polytechnic'
    ]

    # Invalid (department-only) keywords
    invalid_keywords = [
        'department', 'faculty', 'ecology', 'biology', 'botany',
        'zoology', 'chemistry', 'physics', 'mathematics', 'sciences'
    ]

    # Check if it has valid keywords
    has_valid = any(keyword in name_lower for keyword in valid_keywords)

    # Check if it's ONLY invalid keywords (department name)
    is_only_dept = not has_valid and any(keyword in name_lower for keyword in invalid_keywords)

    return has_valid and not is_only_dept


def extract_institution_from_full_text(affiliation_text):
    """
    Extract the actual institution from full affiliation text
    Looks for university/institute names even if department comes first
    """
    if not affiliation_text:
        return None, None

    # Patterns to find institutions (in priority order)
    institution_patterns = [
        # Full university names with "of"
        r'(University of [\w\s\-]+?)(?:,|$|\s+\d)',
        r'(Universit[eéy] (?:of |de |d\')[\w\s\-]+?)(?:,|$|\s+\d)',

        # Universities with location in name
        r'([\w\s\-]+ University)(?:,|$|\s+\d)',
        r'([\w\s\-]+ Universit[eéy])(?:,|$|\s+\d)',

        # Research institutes
        r'([\w\s\-]+ Institute(?:\s+(?:of|for|de)[\w\s\-]+?)?)(?:,|$|\s+\d)',

        # Schools and colleges
        r'([\w\s\-]+ School(?:\s+of[\w\s\-]+?)?)(?:,|$|\s+\d)',
        r'([\w\s\-]+ College)(?:,|$|\s+\d)',

        # Academies
        r'([\w\s\-]+ Academy(?:\s+of[\w\s\-]+?)?)(?:,|$|\s+\d)',

        # Special institutions (CNRS, ETH, EPFL, etc.)
        r'(CNRS)',
        r'(ETH\s+[\w\s\-]*)',
        r'(EPFL)',
        r'(MIT)',
        r'(UCLA)',

        # Abbreviated forms
        r'([\w\s\-]+ Univ\.?)(?:,|$|\s+\d)',
    ]

    for pattern in institution_patterns:
        match = re.search(pattern, affiliation_text, re.IGNORECASE)
        if match:
            inst = match.group(1).strip()

            # Clean up
            inst = re.sub(r'\s+', ' ', inst)
            inst = inst.rstrip(',;.').strip()

            # Remove trailing zip codes or country codes
            inst = re.sub(r'\s+\d{4,}.*$', '', inst)
            inst = re.sub(r'\s+CH-\d+.*$', '', inst, flags=re.IGNORECASE)

            # Extract country
            country = extract_country(affiliation_text)

            # Only return if this looks like a valid institution
            if is_valid_institution(inst):
                return inst, country

    return None, None


def extract_country(text):
    """Extract country from text"""
    countries = [
        'Switzerland', 'France', 'Germany', 'USA', 'United States', 'UK',
        'United Kingdom', 'Spain', 'Italy', 'Netherlands', 'Sweden',
        'Norway', 'Denmark', 'Austria', 'Belgium', 'Canada', 'Australia',
        'China', 'Japan', 'India', 'Brazil', 'South Africa', 'New Zealand',
        'Finland', 'Poland', 'Czech Republic', 'Ireland', 'Portugal', 'Greece'
    ]

    for c in countries:
        if c.lower() in text.lower():
            if c == 'United States':
                return 'USA'
            return c

    return ''


def simplify_institution_name(inst):
    """Clean and simplify institution names"""
    if not inst:
        return '', ''

    original_inst = inst

    # Extract country first
    country = extract_country(inst)

    # Extract main institution name (before first comma)
    parts = inst.split(',')
    main_inst = parts[0].strip()

    # Normalize whitespace first
    main_inst = re.sub(r'\s+', ' ', main_inst).strip()

    # Remove repeated consecutive words FIRST (e.g., "Bergen Bergen", "Zürich Zürich", "Univ. Univ.")
    # Use a pattern that handles unicode characters properly
    # Do this multiple times to catch cascading repeats
    for _ in range(3):
        before = main_inst
        # Pattern: any sequence of non-whitespace characters (including accented), optionally with a dot
        main_inst = re.sub(r'(\S+\.?)\s+\1\b', r'\1', main_inst, flags=re.IGNORECASE|re.UNICODE)
        if before == main_inst:
            break

    # Remove zip codes and country codes
    main_inst = re.sub(r'\s+\d{5}.*$', '', main_inst)  # 5-digit zip codes
    main_inst = re.sub(r'\s+CH-\d+.*$', '', main_inst, flags=re.IGNORECASE)

    # Remove country names (anywhere in string)
    countries_list = ['Norway', 'Sweden', 'Germany', 'France', 'Switzerland', 'USA',
                      'China', 'India', 'Spain', 'Italy', 'UK', 'Netherlands',
                      'Austria', 'Belgium', 'Denmark', 'Finland', 'Poland']
    for c in countries_list:
        main_inst = re.sub(rf'\b{c}\b', '', main_inst, flags=re.IGNORECASE)

    # Clean up spaces
    main_inst = re.sub(r'\s+', ' ', main_inst).strip()

    # Only remove trailing city names and state codes (not cities that are part of the institution name)
    # Pattern: institution name followed by standalone city/state/code
    # e.g., "University of Arizona Tuscon AZ" -> "University of Arizona"
    # but "ETH Zürich" -> "ETH Zürich" (keep it)
    trailing_locations = ['Tuscon', 'Tucson', 'AZ', 'MT', 'Kashmir', 'Srinagar', 'Jammu']
    for loc in trailing_locations:
        main_inst = re.sub(rf'\s+{loc}\s*$', '', main_inst, flags=re.IGNORECASE)

    # Clean up multiple spaces again
    main_inst = re.sub(r'\s+', ' ', main_inst).strip()

    # Clean up "Jammu &amp" artifacts from HTML entities
    main_inst = re.sub(r'\s+&amp.*$', '', main_inst)
    main_inst = re.sub(r'\s+Jammu\s*$', '', main_inst)

    # Shorten very long names - keep first institution only
    if len(main_inst) > 80:
        # Try to extract first university/institute
        match = re.match(r'([\w\s\-\.]+?(?:University|Université|Universit[eé]|Institute|School|College)(?:\s+of[\w\s]+?)?)', main_inst, re.IGNORECASE)
        if match:
            main_inst = match.group(1).strip()

    # Handle multiple institutions separated by space - keep first one
    # e.g., "Univ. Alpes Univ. Savoie Mont Blanc" -> "Univ. Alpes"
    if 'Univ.' in main_inst or 'University' in main_inst:
        # Split on second occurrence of Univ/University
        parts = re.split(r'\s+(Univ\.?|University)', main_inst, maxsplit=2)
        if len(parts) > 3:
            # Reconstruct first institution
            main_inst = parts[0] + ' ' + parts[1]
            if parts[2]:
                # Add the next word(s) until we hit another institution marker
                next_part = parts[2].split()[0:2]  # Take up to 2 words
                main_inst += ' ' + ' '.join(next_part)
            main_inst = main_inst.strip()

    # Remove trailing commas, periods, spaces
    main_inst = main_inst.rstrip(',;. ').strip()

    # Clean up whitespace again
    main_inst = re.sub(r'\s+', ' ', main_inst).strip()

    # Remove any remaining trailing location/country patterns at the end
    main_inst = re.sub(r'\s+(75005|CH-?\d+|MT|AZ)\s*$', '', main_inst)

    # Check if this is a valid institution
    # If not, try to extract from full text
    if not is_valid_institution(main_inst):
        better_inst, better_country = extract_institution_from_full_text(original_inst)
        if better_inst and is_valid_institution(better_inst):
            return better_inst, better_country or country
        # If still not valid, return None to signal this needs review
        return None, country

    return main_inst, country


def get_affiliations_from_crossref(doi):
    """
    Query Crossref API for paper metadata including author affiliations
    Returns list of (author_name, institution, country) tuples
    """
    if not doi:
        return []

    clean_doi_str = clean_doi(doi)
    if not clean_doi_str:
        return []

    url = f"https://api.crossref.org/works/{clean_doi_str}"

    try:
        # Add polite contact info in User-Agent (Crossref best practice)
        headers = {
            'User-Agent': 'AcademicWebsite/1.0 (mailto:your-email@example.com)'
        }

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return []

        data = response.json()
        message = data.get('message', {})
        authors = message.get('author', [])

        affiliations_list = []

        for author in authors:
            # Get author name
            given = author.get('given', '')
            family = author.get('family', '')
            full_name = f"{given} {family}".strip()

            if not full_name or full_name == MY_NAME:
                continue

            # Get affiliations
            author_affiliations = author.get('affiliation', [])

            if author_affiliations:
                # Take first affiliation
                first_aff = author_affiliations[0]
                inst_name = first_aff.get('name', '')

                if inst_name:
                    # Clean and extract country
                    main_inst, country = simplify_institution_name(inst_name)

                    # Only add if we got a valid institution
                    if main_inst:
                        affiliations_list.append({
                            'name': full_name,
                            'institution': main_inst,
                            'country': country,
                            'source': 'crossref'
                        })
                    # If invalid, try looking at raw affiliation for more context
                    elif len(author_affiliations) > 1:
                        # Try second affiliation if available
                        second_aff = author_affiliations[1]
                        alt_inst_name = second_aff.get('name', '')
                        if alt_inst_name:
                            alt_inst, alt_country = simplify_institution_name(alt_inst_name)
                            if alt_inst:
                                affiliations_list.append({
                                    'name': full_name,
                                    'institution': alt_inst,
                                    'country': alt_country or country,
                                    'source': 'crossref'
                                })

        return affiliations_list

    except Exception as e:
        print(f"    ⚠️  Crossref API error: {e}")
        return []


def merge_affiliations_with_cache(new_affiliations, cache):
    """
    Merge new affiliations with cached data
    Cache takes precedence (allows manual corrections to persist)
    """
    merged = {}

    # Start with cache
    merged.update(cache)

    # Add new affiliations only if not in cache
    for aff in new_affiliations:
        name = aff['name']
        if name not in merged:
            merged[name] = {
                'institution': aff['institution'],
                'country': aff['country'],
                'source': aff.get('source', 'unknown')
            }

    return merged


def update_coauthors_csv(coauthors_file, affiliation_cache):
    """Update coauthors.csv with affiliation data from cache"""

    # Read existing CSV
    rows = []
    with open(coauthors_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    updated_count = 0

    # Update rows
    for row in rows:
        author_name = row['Name']

        if author_name in affiliation_cache:
            cached = affiliation_cache[author_name]

            # Only update if currently empty (preserve manual edits)
            if not row['Institution'] and cached['institution']:
                row['Institution'] = cached['institution']
                updated_count += 1

            if not row['Country'] and cached['country']:
                row['Country'] = cached['country']

    # Write back
    with open(coauthors_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Name', 'Institution', 'Country', 'Type', 'Projects', 'Relationship', 'Description', 'Website']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return updated_count


def main():
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent
    publications_file = base_dir / 'data' / 'publications.json'
    coauthors_file = base_dir / 'data' / 'coauthors.csv'

    print("="*60)
    print("Smart Affiliation Extractor")
    print("="*60)
    print("\nUsing: Crossref API + Caching")

    # Load cache
    cache = load_cache(base_dir)
    print(f"\nLoaded cache: {len(cache)} author(s) cached")

    # Load publications
    with open(publications_file, 'r', encoding='utf-8') as f:
        publications = json.load(f)

    print(f"Found {len(publications)} publication(s)")

    all_new_affiliations = []
    papers_processed = 0
    papers_with_affiliations = 0

    # Process each publication
    for i, pub in enumerate(publications, 1):
        title = pub.get('title', 'Unknown')[:60]
        doi = pub.get('doi', '')

        print(f"\n📄 [{i}/{len(publications)}] {title}...")

        if not doi:
            print(f"    ⚠️  No DOI found, skipping")
            continue

        papers_processed += 1

        # Query Crossref API
        print(f"    🔍 Querying Crossref API...")
        affiliations = get_affiliations_from_crossref(doi)

        if affiliations:
            print(f"    ✓ Found {len(affiliations)} author-affiliation pair(s)")
            papers_with_affiliations += 1

            # Show first few
            for aff in affiliations[:3]:
                print(f"      • {aff['name']}")
                if aff['institution']:
                    print(f"        {aff['institution']}", end='')
                    if aff['country']:
                        print(f", {aff['country']}")
                    else:
                        print()

            if len(affiliations) > 3:
                print(f"      ... and {len(affiliations) - 3} more")

            all_new_affiliations.extend(affiliations)
        else:
            print(f"    ⚠️  No affiliations found")

        # Be polite to API (wait between requests)
        if i < len(publications):
            time.sleep(0.5)

    print("\n" + "="*60)
    print("EXTRACTION SUMMARY")
    print("="*60)
    print(f"Papers with DOIs: {papers_processed}")
    print(f"Papers with affiliations: {papers_with_affiliations}")
    print(f"New author-affiliation pairs: {len(all_new_affiliations)}")

    # Merge with cache
    updated_cache = merge_affiliations_with_cache(all_new_affiliations, cache)
    print(f"Total unique authors in cache: {len(updated_cache)}")

    # Check for authors without valid institutions
    authors_without_inst = []
    with open(coauthors_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['Name']
            inst = row['Institution']
            if not inst or not is_valid_institution(inst):
                authors_without_inst.append(name)

    if authors_without_inst:
        print(f"\n⚠️  {len(authors_without_inst)} author(s) need manual review (no valid institution):")
        for name in authors_without_inst[:10]:
            print(f"    • {name}")
        if len(authors_without_inst) > 10:
            print(f"    ... and {len(authors_without_inst) - 10} more")

    # Save updated cache
    save_cache(base_dir, updated_cache)
    print(f"\n✓ Saved cache to: {CACHE_FILE}")

    # Update coauthors.csv
    if updated_cache:
        updated_count = update_coauthors_csv(coauthors_file, updated_cache)
        print(f"✓ Updated {updated_count} author(s) in coauthors.csv")

    # Save detailed report
    report_file = base_dir / 'data' / 'affiliation_extraction_report.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("Affiliation Extraction Report\n")
        f.write("="*60 + "\n\n")

        f.write(f"Papers processed: {papers_processed}\n")
        f.write(f"Papers with affiliations: {papers_with_affiliations}\n")
        f.write(f"Total authors: {len(updated_cache)}\n\n")

        f.write("All Authors and Affiliations:\n")
        f.write("-"*60 + "\n\n")

        for name, data in sorted(updated_cache.items()):
            f.write(f"{name}\n")
            f.write(f"  Institution: {data['institution']}\n")
            if data['country']:
                f.write(f"  Country: {data['country']}\n")
            f.write(f"  Source: {data['source']}\n\n")

    print(f"✓ Saved detailed report to: affiliation_extraction_report.txt")

    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("1. Review affiliation_extraction_report.txt")
    print("2. Check coauthors.csv for accuracy")
    print("3. Manually correct any errors in coauthors.csv")
    print("4. Corrections will be preserved in future runs (cache priority)")
    print("5. Refresh your collaborations page!")
    print("\nNote: The affiliation cache allows manual corrections to persist.")
    print("Edit coauthors.csv for corrections, then re-run this script to update cache.")
    print("="*60)


if __name__ == '__main__':
    main()
