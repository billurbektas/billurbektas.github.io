#!/usr/bin/env python3
"""
Extract author affiliations from PDF papers and update coauthors.csv

This script:
1. Reads all PDFs from data/pdfs/ folder
2. Extracts author names and institutional affiliations
3. Updates coauthors.csv with institution information
"""

import os
import csv
import re
from pathlib import Path
from collections import defaultdict

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber not installed")
    print("Install it with: pip install pdfplumber")
    exit(1)


def simplify_institution(inst_text):
    """
    Simplify institution name by removing addresses, departments, etc.
    Keep only the main university/institution name
    """
    # Remove leading numbers (affiliation markers)
    inst_text = re.sub(r'^\d+\s*', '', inst_text)

    # Common patterns to clean
    cleanups = [
        r',\s*\d+.*',  # Remove everything after comma followed by number (address)
        r',\s*[A-Z]{2}\s*\d+.*',  # US state codes
        r'\d{4,}.*',  # Zip codes and everything after
        r'Department of.*?,',  # Remove department names
        r'School of.*?,',
        r'Faculty of.*?,',
        r'Institute for.*?,',
        r'Center for.*?,',
        r'Centre for.*?,',
    ]

    result = inst_text
    for pattern in cleanups:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)

    # Clean up extra whitespace and split camelCase
    result = re.sub(r'([a-z])([A-Z])', r'\1 \2', result)  # Split camelCase
    result = re.sub(r'\s+', ' ', result).strip()

    # Remove trailing commas
    result = result.rstrip(',').strip()

    # Common abbreviations to expand
    expansions = {
        'Univ.': 'University',
        'Univ ': 'University ',
        'U. ': 'University ',
    }

    for abbrev, full in expansions.items():
        result = result.replace(abbrev, full)

    return result


def extract_affiliations_from_text(text):
    """
    Extract numbered affiliations from PDF text
    Returns dict mapping affiliation numbers to (institution, country) tuples
    """
    affiliations = {}

    # Split text into lines
    lines = text.split('\n')

    # Look for affiliation patterns (usually at start of papers)
    # Common formats:
    # 1University of X, Country
    # 1 University of X, Country
    # 1. University of X, Country

    affiliation_pattern = re.compile(
        r'^(\d+)\s*\.?\s*([^,\n]+(?:University|Institute|CNRS|College|School)[^,\n]*),?\s*(.{0,100})$',
        re.MULTILINE
    )

    for match in affiliation_pattern.finditer(text):
        number = match.group(1)
        institution = match.group(2).strip()
        rest = match.group(3).strip()

        # Simplify institution name
        institution = simplify_institution(institution)

        # Try to extract country from the rest
        countries = [
            'Switzerland', 'France', 'Germany', 'USA', 'United States', 'UK',
            'United Kingdom', 'Spain', 'Italy', 'Netherlands', 'Sweden',
            'Norway', 'Denmark', 'Austria', 'Belgium', 'Canada', 'Australia',
            'China', 'Japan', 'India', 'Brazil', 'South Africa', 'New Zealand',
            'Finland', 'Poland', 'Czech Republic', 'Ireland', 'Portugal', 'Greece'
        ]

        country = ''
        for c in countries:
            if c in rest:
                country = c
                if c == 'United States':
                    country = 'USA'
                break

        affiliations[number] = {
            'institution': institution,
            'country': country
        }

    return affiliations


def extract_author_affiliations(text):
    """
    Try to match authors to their affiliations using superscript numbers
    Returns dict mapping author names to affiliation info
    """
    author_affiliations = {}

    # Extract the affiliations first
    affiliations = extract_affiliations_from_text(text)

    if not affiliations:
        return {}

    # Try to find author line (usually near top)
    # Look for patterns like: "John Doe1,2, Jane Smith3"

    lines = text.split('\n')[:30]  # Check first 30 lines

    for line in lines:
        # Look for author names with superscript numbers
        # Pattern: Name followed by numbers
        author_pattern = re.compile(r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(\d+(?:\s*,\s*\d+)*)')

        matches = author_pattern.findall(line)

        for name, numbers in matches:
            # Get first affiliation number
            first_num = numbers.split(',')[0].strip()

            if first_num in affiliations:
                author_affiliations[name] = affiliations[first_num]

    return author_affiliations


def extract_text_from_first_pages(pdf_path, num_pages=3):
    """Extract text from first few pages of PDF where affiliations are usually located"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for i in range(min(num_pages, len(pdf.pages))):
                page_text = pdf.pages[i].extract_text() or ""
                text += page_text + "\n"
            return text
    except Exception as e:
        print(f"  ⚠️  Error reading {pdf_path.name}: {e}")
        return ""


def update_coauthors_csv(coauthors_file, all_affiliations):
    """Update coauthors.csv with extracted affiliation information"""

    # Read existing data
    rows = []
    with open(coauthors_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    updated_count = 0

    # Update rows with affiliation data
    for row in rows:
        author_name = row['Name']

        # Check if we have affiliation data for this author
        if author_name in all_affiliations:
            aff = all_affiliations[author_name]

            # Only update if currently empty
            if not row['Institution'] and aff['institution']:
                row['Institution'] = aff['institution']
                updated_count += 1

            if not row['Country'] and aff['country']:
                row['Country'] = aff['country']

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
    pdfs_dir = base_dir / 'data' / 'pdfs'
    coauthors_file = base_dir / 'data' / 'coauthors.csv'

    print("="*60)
    print("PDF Affiliation Extractor")
    print("="*60)

    # Check if PDFs directory exists
    if not pdfs_dir.exists():
        print(f"\n⚠️  PDF directory not found: {pdfs_dir}")
        print("Creating directory...")
        pdfs_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {pdfs_dir}")
        print("\nPlease add your PDF papers to this folder and run the script again.")
        return

    # Find all PDFs
    pdf_files = list(pdfs_dir.glob('*.pdf'))

    if not pdf_files:
        print(f"\n⚠️  No PDF files found in {pdfs_dir}")
        print("Please add your papers as PDF files to this folder.")
        return

    print(f"\nFound {len(pdf_files)} PDF file(s)")

    # Extract affiliations from all PDFs
    all_author_affiliations = {}
    all_numbered_affiliations = {}

    for pdf_file in pdf_files:
        print(f"\n📄 Processing: {pdf_file.name}")

        # Extract text
        text = extract_text_from_first_pages(pdf_file)

        if not text:
            continue

        # Extract numbered affiliations
        affiliations = extract_affiliations_from_text(text)

        if affiliations:
            print(f"  ✓ Found {len(affiliations)} affiliation(s)")
            for num, aff in list(affiliations.items())[:5]:  # Show first 5
                print(f"    {num}. {aff['institution']}")
                if aff['country']:
                    print(f"       {aff['country']}")

            # Store all affiliations
            for num, aff in affiliations.items():
                key = f"{aff['institution']}, {aff['country']}"
                all_numbered_affiliations[key] = aff

        # Try to match authors to affiliations
        author_affs = extract_author_affiliations(text)
        if author_affs:
            print(f"  ✓ Matched {len(author_affs)} author(s) to affiliations")
            all_author_affiliations.update(author_affs)

    print("\n" + "="*60)
    print("EXTRACTION SUMMARY")
    print("="*60)
    print(f"PDFs processed: {len(pdf_files)}")
    print(f"Unique affiliations found: {len(all_numbered_affiliations)}")
    print(f"Authors matched: {len(all_author_affiliations)}")

    # Save extracted affiliations
    institutions_file = base_dir / 'data' / 'extracted_institutions.txt'
    with open(institutions_file, 'w', encoding='utf-8') as f:
        f.write("Institutions extracted from PDFs:\n")
        f.write("="*60 + "\n\n")

        for key, aff in sorted(all_numbered_affiliations.items()):
            f.write(f"{aff['institution']}\n")
            if aff['country']:
                f.write(f"  Country: {aff['country']}\n")
            f.write("\n")

        if all_author_affiliations:
            f.write("\n" + "="*60 + "\n")
            f.write("Authors matched to affiliations:\n")
            f.write("="*60 + "\n\n")

            for author, aff in sorted(all_author_affiliations.items()):
                f.write(f"{author}\n")
                f.write(f"  {aff['institution']}")
                if aff['country']:
                    f.write(f", {aff['country']}")
                f.write("\n\n")

    print(f"\n✓ Saved to: {institutions_file}")

    # Update coauthors.csv
    if all_author_affiliations:
        updated = update_coauthors_csv(coauthors_file, all_author_affiliations)
        if updated > 0:
            print(f"✓ Updated {updated} author(s) in coauthors.csv")

    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("1. Review extracted_institutions.txt")
    print("2. Manually fill in any missing Institution/Country fields in")
    print("   coauthors.csv using the extracted institutions as reference")
    print("3. Refresh your collaborations page to see the updated network!")
    print("="*60)


if __name__ == '__main__':
    main()
