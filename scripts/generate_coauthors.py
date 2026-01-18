#!/usr/bin/env python3
"""
Generate coauthors.csv from publications.json

This script extracts all unique co-authors from your publications
and creates a CSV file for the collaboration network visualization.
"""

import json
import csv
from collections import Counter
from pathlib import Path

def generate_coauthors_csv():
    # Paths
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / 'data'
    publications_file = data_dir / 'publications.json'
    output_file = data_dir / 'coauthors.csv'

    # Your name (to exclude from co-authors)
    MY_NAME = "Billur Bektaş"

    # Load publications
    print(f"Reading publications from {publications_file}...")
    with open(publications_file, 'r', encoding='utf-8') as f:
        publications = json.load(f)

    # Extract all co-authors and count collaborations
    coauthor_counts = Counter()

    for pub in publications:
        if 'authors' in pub and isinstance(pub['authors'], list):
            for author in pub['authors']:
                # Skip yourself
                if author != MY_NAME:
                    coauthor_counts[author] += 1

    print(f"\nFound {len(coauthor_counts)} unique co-authors")
    print(f"Total publications analyzed: {len(publications)}")

    # Prepare CSV data
    csv_data = []

    for author, count in coauthor_counts.most_common():
        csv_data.append({
            'Name': author,
            'Institution': '',  # To be filled manually
            'Country': '',  # To be filled manually
            'Type': 'network',  # Default type - change to 'core' or 'active' as needed
            'Projects': str(count),  # Number of co-authored papers
            'Relationship': 'Co-author',
            'Description': '',  # To be filled manually
            'Website': ''  # To be filled manually
        })

    # Write to CSV
    print(f"\nWriting to {output_file}...")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Name', 'Institution', 'Country', 'Type', 'Projects', 'Relationship', 'Description', 'Website']
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(csv_data)

    print(f"✓ Successfully created {output_file}")
    print(f"✓ Total co-authors: {len(csv_data)}")

    # Show top collaborators
    print("\nTop 10 collaborators by number of papers:")
    for author, count in coauthor_counts.most_common(10):
        print(f"  {count:2d} papers - {author}")

    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("="*60)
    print("1. Open data/coauthors.csv")
    print("2. Fill in Institution and Country for important collaborators")
    print("3. Change 'Type' from 'network' to:")
    print("   - 'core' for supervisors/close mentors")
    print("   - 'active' for current project collaborators")
    print("4. Add descriptions for key collaborators")
    print("5. Refresh your collaborations page to see the network!")
    print("="*60)

if __name__ == '__main__':
    generate_coauthors_csv()
