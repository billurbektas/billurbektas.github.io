// bibtex2json.js
const fs = require('fs').promises;
const path = require('path');

class BibTeXParser {
    constructor() {
        this.entries = [];
    }

    async parseFiles(files, bibtexDir) {
        let allEntries = [];
        for (const file of files) {
            console.log(`\nProcessing file: ${file}`);
            const filePath = path.join(bibtexDir, file);
            
            try {
                const content = await fs.readFile(filePath, 'utf8');
                console.log(`File content length: ${content.length} characters`);
                
                const entries = this.parseText(content, file);
                console.log(`Found ${entries.length} entries in ${file}`);
                allEntries = allEntries.concat(entries);
            } catch (error) {
                console.error(`Error processing ${file}:`, error);
            }
        }
        return allEntries;
    }

    parseText(text, filename) {
        // Prepare the text
        text = text.replace(/%.*$/gm, ''); // Remove comments

        // Modified regex to better handle DOI citation keys and complex entries
        const entryRegex = /@(\w+)\s*{([^,]*),\s*([\s\S]*?)(?=\s*@|\s*$)/g;
        const entries = [];

        let match;
        while ((match = entryRegex.exec(text)) !== null) {
            try {
                const [_, type, citationKey, fieldsText] = match;
                const fields = this.parseFields(fieldsText);

                // Create citation key from DOI if present
                const cleanCitationKey = citationKey.replace('https://doi.org/', '').replace(/[/.]/g, '_');
                
                // Process keywords
                let keywords = [];
                if (fields.keywords) {
                    keywords = fields.keywords
                        .split(/,\s*/)
                        .map(k => k.trim().toLowerCase()
                            .replace(/\s+/g, '-')
                            .replace(/[^\w-]/g, ''))
                        .filter(k => k.length > 0);
                }

                // Determine year - if no year or volume is "n/a", mark as "in press"
                let year;
                if (fields.volume === 'n/a' || fields.volume === 'in press') {
                    year = 'in press';
                } else if (fields.year) {
                    year = fields.year;
                } else {
                    year = new Date().getFullYear().toString();
                }

                // Process DOI and URL - prefer URL if DOI doesn't have a full link
                let articleUrl = this.cleanField(fields.doi || '');
                if (articleUrl && !articleUrl.startsWith('http')) {
                    articleUrl = `https://doi.org/${articleUrl}`;
                }
                // Use URL field as fallback if DOI is not available
                if (!articleUrl && fields.url) {
                    articleUrl = this.cleanField(fields.url);
                }

                // Create the entry object
                const entry = {
                    entryType: type.toLowerCase(),
                    citationKey: cleanCitationKey,
                    sourceFile: filename,
                    year: year,
                    title: this.cleanField(fields.title || ''),
                    authors: this.parseAuthors(fields.author || ''),
                    venue: this.cleanField(fields.journal || fields.booktitle || ''),
                    volume: fields.volume || '',
                    number: fields.number || '',
                    pages: fields.pages || '',
                    doi: articleUrl,
                    abstract: this.cleanField(fields.abstract || ''),
                    keywords: keywords,
                    pdfPath: `/pdfs/${cleanCitationKey}.pdf`,
                    blogPost: null,
                    bibtex: match[0].trim()
                };

                entries.push(entry);
            } catch (error) {
                console.error('Error parsing entry:', error);
            }
        }

        return entries;
    }

    parseFields(fieldsText) {
        const fields = {};
        // Updated regex to handle multi-line fields and nested braces
        const fieldRegex = /(\w+)\s*=\s*[{"]?((?:[^{}"]|{[^{}]*})*)["}]?,?\s*/g;

        let match;
        while ((match = fieldRegex.exec(fieldsText)) !== null) {
            const [_, key, value] = match;
            fields[key.toLowerCase()] = value.trim();
        }

        return fields;
    }

    parseAuthors(authorString) {
        return authorString
            .split(/ and /)
            .map(author => {
                author = author.trim().replace(/[{}]/g, '');
                const parts = author.split(',');
                if (parts.length > 1) {
                    // Last Name, First Name format
                    return `${parts[1].trim()} ${parts[0].trim()}`;
                }
                // First Name Last Name format
                return author;
            });
    }

    cleanField(field) {
        return field
            .replace(/[{}]/g, '')  // Remove BibTeX braces
            .replace(/\\[a-z]*/g, '') // Remove BibTeX commands
            .trim();
    }
}

async function convertBibTeXToJSON() {
    try {
        // Create data directory if it doesn't exist
        await fs.mkdir('data').catch(() => {});
        
        // Read all .bib files from the bibtex directory
        const bibtexDir = 'bibtex';
        console.log(`Reading from directory: ${path.resolve(bibtexDir)}`);
        
        const files = await fs.readdir(bibtexDir);
        console.log('All files in directory:', files);
        
        const bibFiles = files.filter(file => file.endsWith('.bib'));
        console.log('BibTeX files found:', bibFiles);

        if (bibFiles.length === 0) {
            console.log('No .bib files found. Please check your files have .bib extension');
            return;
        }

        // Parse all files
        const parser = new BibTeXParser();
        const allEntries = await parser.parseFiles(bibFiles, bibtexDir);

        // Sort entries by year (newest first, with "in press" at top)
        allEntries.sort((a, b) => {
            // "in press" should come first
            if (a.year === 'in press') return -1;
            if (b.year === 'in press') return 1;
            // Then sort numeric years in descending order
            return parseInt(b.year) - parseInt(a.year);
        });

        // Write to JSON file
        await fs.writeFile(
            'data/publications.json',
            JSON.stringify(allEntries, null, 2)
        );

        console.log('\nConversion successful! Check data/publications.json');
        
        // Print statistics
        console.log('\nStatistics:');
        console.log(`Total entries: ${allEntries.length}`);
        
        if (allEntries.length > 0) {
            // Count entries by type
            const typeCount = allEntries.reduce((acc, entry) => {
                acc[entry.entryType] = (acc[entry.entryType] || 0) + 1;
                return acc;
            }, {});
            console.log('\nEntries by type:');
            Object.entries(typeCount).forEach(([type, count]) => {
                console.log(`${type}: ${count}`);
            });

            // Print all keywords found
            const keywords = new Set();
            allEntries.forEach(entry => entry.keywords.forEach(k => keywords.add(k)));
            console.log('\nUnique keywords:', Array.from(keywords).join(', '));

            // Print sample of processed data
            console.log('\nFirst entry preview:');
            const preview = { ...allEntries[0] };
            delete preview.bibtex; // Remove long bibtex field for preview
            delete preview.abstract; // Remove long abstract for preview
            console.log(JSON.stringify(preview, null, 2));
        }

    } catch (error) {
        console.error('Conversion failed:', error);
        console.error('Error details:', error.stack);
    }
}

// Run the converter
convertBibTeXToJSON();