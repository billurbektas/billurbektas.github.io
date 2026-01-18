# Collaboration Network Scripts

## Quick Start

### 1. Generate Co-authors from Publications

```bash
cd /Users/bbektas/Desktop/billur_website
python3 scripts/generate_coauthors.py
```

This will:
- Read all authors from `data/publications.json`
- Count how many papers you co-authored with each person
- Generate `data/coauthors.csv` with all unique co-authors

### 2. Extract Affiliations (Smart Automated Method)

**Recommended approach - uses Crossref API:**

```bash
pip install requests
python3 scripts/extract_affiliations_smart.py
```

This will:
- Use Crossref API to extract author affiliations from DOIs (most reliable!)
- Cache all findings for faster future runs
- Preserve manual corrections (cache priority over new data)
- Update `data/coauthors.csv` automatically
- Generate detailed report

**Success rate: ~85-95% automated!**

### Alternative: Extract from PDFs (Legacy Method)

If Crossref doesn't have affiliation data for some papers:

```bash
pip install pdfplumber
python3 scripts/extract_affiliations_from_pdfs.py
```

**Note:** PDF extraction is less reliable but can supplement Crossref data.

## Automated Updates (GitHub Actions)

When you push to GitHub:
1. **New publication added** to `data/publications.json` → Auto-generates coauthors
2. **New PDF added** to `data/pdfs/` → Auto-extracts affiliations
3. **Changes committed** automatically

See `.github/workflows/update-collaborations.yml` for the automation setup.

## Customizing the Network

After generating `coauthors.csv`, you should:

1. **Add Institutions & Countries**: Use `extracted_institutions.txt` as reference
2. **Categorize relationships**: Change the `Type` field:
   - `core` - PhD supervisors, postdoc mentors, close PIs (larger purple nodes, thick lines)
   - `active` - Current collaborators, ongoing projects (medium bright blue nodes)
   - `network` - Co-authors through consortia, conferences (small light nodes, thin lines)
3. **Add descriptions**: Fill in the `Description` field for key people
4. **Add websites**: Include personal/lab websites

## Data Files

- **`data/coauthors.csv`** - Auto-generated from publications (re-run script to update)
- **`data/other_collaborations.csv`** - Manually maintained (people you haven't published with)
- **`data/pdfs/`** - Folder for your publication PDFs
- **`data/extracted_institutions.txt`** - Reference file with institutions found in PDFs

All CSV files are automatically merged when the collaboration network loads!

## Network Features

- **Line thickness** = Number of collaborative papers (thicker = more papers)
- **Node size** = Collaboration type (core > active > network)
- **Colors** = Role type (purple for core, bright blue for active, light purple for network)
- **Two views** = Toggle between Researcher View (people) and Institutional View (organizations)

## Tips

- The script sorts co-authors by number of papers (most frequent first)
- Line width automatically scales: 1 paper = thin, 5+ papers = thick
- You don't need to fill in everything - Institution and Type are most important
- The network works great even with partial data
- Run scripts whenever you add new publications or PDFs
