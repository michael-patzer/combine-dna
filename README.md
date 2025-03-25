DNA File Merger

This script combines raw DNA files from 23AndMe and AncestryDNA services.
It handles the different file formats and detects file-wide orientation differences.
Special handling is included for:
- Sex chromosomes (X/Y) and mitochondrial DNA (MT)
- No-calls (-- or 00) vs actual data
- Orientation differences (CT/TC, AG/GA, etc.)
- Identical heterozygous genotypes represented differently (AT/AT, CG/CG) (Mostly a file formatting issue)
- True conflicts

Usage:
    python dna_merger.py primary_file secondary_file output_file

Arguments:
    primary_file: Path to the first DNA file (takes precedence in conflicts)
    secondary_file: Path to the second DNA file 
    output_file: Path where the merged DNA data will be written
