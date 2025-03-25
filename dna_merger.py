#!/usr/bin/env python3
"""
DNA File Merger

This script combines raw DNA files from 23AndMe and AncestryDNA services.
It handles the different file formats and detects file-wide orientation differences.
Special handling is included for:
- Sex chromosomes (X/Y) and mitochondrial DNA (MT)
- No-calls (-- or 00) vs actual data
- Orientation differences (CT/TC, AG/GA, etc.)
- Identical heterozygous genotypes represented differently (AT/AT, CG/CG)
- True conflicts

Usage:
    python dna_merger.py primary_file secondary_file output_file

Arguments:
    primary_file: Path to the first DNA file (takes precedence in conflicts)
    secondary_file: Path to the second DNA file 
    output_file: Path where the merged DNA data will be written
"""

import sys
import os.path
from datetime import datetime
from collections import Counter

def detect_file_format(filename):
    """
    Determines if a file is from 23AndMe or AncestryDNA based on its content.
    Handles files with or without headers.
    
    Args:
        filename: Path to the DNA data file
        
    Returns:
        str: "23andme" or "ancestry" or "unknown"
    """
    with open(filename, 'r') as f:
        # Read first several lines to analyze
        lines = [f.readline() for _ in range(30)]
        
        # Check for specific header indicators first
        if any("data file generated by 23andMe" in line for line in lines):
            return "23andme"
            
        if any("AncestryDNA raw data download" in line for line in lines):
            return "ancestry"
        
        # If no header indicators, analyze the data structure
        data_lines = [line for line in lines if line.strip() and not line.startswith('#')]
        
        if data_lines:
            # Get the first data line
            first_data = data_lines[0].strip().split('\t')
            
            # Check field count and structure
            if len(first_data) == 4:
                # Likely 23andMe format (rsid, chromosome, position, genotype)
                return "23andme"
                    
            elif len(first_data) == 5:
                # Likely Ancestry format (rsid, chromosome, position, allele1, allele2)
                return "ancestry"
    
    return "unknown"

def parse_23andme(filename):
    """
    Parses a 23AndMe raw data file, with or without header.
    
    Args:
        filename: Path to the 23AndMe data file
        
    Returns:
        tuple: (header_lines, data_dict)
            - header_lines: List of header lines (or generated header if none found)
            - data_dict: Dictionary mapping rsids to (chromosome, position, genotype)
    """
    header_lines = []
    data_dict = {}
    has_header = False
    column_names = None
    
    with open(filename, 'r') as f:
        for line in f:
            # Collect header lines
            if line.startswith('#'):
                header_lines.append(line)
                has_header = True
                continue
                
            # Skip empty lines
            if not line.strip():
                continue
                
            # First non-header line could be column names
            if has_header and column_names is None:
                column_names = line.strip()
                header_lines.append(line)
                continue
                
            # Parse data lines
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                rsid, chromosome, position, genotype = parts[:4]
                data_dict[rsid] = (chromosome, position, genotype)
    
    # If no header was found, generate a minimal one
    if not header_lines:
        header_lines = [
            "# DNA data file (No original header - detected as 23andMe format)\n",
            "# Generated header added by dna_merger.py\n",
            "# rsid\tchromosome\tposition\tgenotype\n"
        ]
    
    return header_lines, data_dict

def parse_ancestry(filename):
    """
    Parses an AncestryDNA raw data file, with or without header.
    
    Args:
        filename: Path to the AncestryDNA data file
        
    Returns:
        tuple: (header_lines, data_dict)
            - header_lines: List of header lines (or generated header if none found)
            - data_dict: Dictionary mapping rsids to (chromosome, position, genotype)
    """
    header_lines = []
    data_dict = {}
    has_header = False
    column_names = None
    
    with open(filename, 'r') as f:
        for line in f:
            # Collect header lines
            if line.startswith('#'):
                header_lines.append(line)
                has_header = True
                continue
                
            # Skip empty lines
            if not line.strip():
                continue
                
            # First non-header line could be column names
            if has_header and column_names is None:
                column_names = line.strip()
                header_lines.append(line)
                continue
                
            # Parse data lines
            parts = line.strip().split('\t')
            if len(parts) >= 5:
                rsid, chromosome, position, allele1, allele2 = parts[:5]
                # Combine alleles into a genotype string
                genotype = allele1 + allele2
                data_dict[rsid] = (chromosome, position, genotype)
    
    # If no header was found, generate a minimal one
    if not header_lines:
        header_lines = [
            "# DNA data file (No original header - detected as AncestryDNA format)\n",
            "# Generated header added by dna_merger.py\n",
            "# rsid\tchromosome\tposition\tallele1\tallele2\n"
        ]
    
    return header_lines, data_dict

def parse_dna_file(filename, format_hint=None):
    """
    Parses a DNA file based on its detected format.
    
    Args:
        filename: Path to the DNA data file
        format_hint: Optional format hint ("23andme" or "ancestry")
        
    Returns:
        tuple: (header_lines, data_dict, format)
            - header_lines: List of all header lines
            - data_dict: Dictionary mapping rsids to (chromosome, position, genotype)
            - format: Detected file format
    """
    # Detect format if not provided
    file_format = format_hint or detect_file_format(filename)
    
    if file_format == "23andme":
        header_lines, data_dict = parse_23andme(filename)
        return header_lines, data_dict, "23andme"
    elif file_format == "ancestry":
        header_lines, data_dict = parse_ancestry(filename)
        return header_lines, data_dict, "ancestry"
    else:
        # Try parsing as both formats
        try:
            header_lines, data_dict = parse_23andme(filename)
            if data_dict:
                return header_lines, data_dict, "23andme"
        except Exception:
            pass
            
        try:
            header_lines, data_dict = parse_ancestry(filename)
            if data_dict:
                return header_lines, data_dict, "ancestry"
        except Exception:
            pass
            
        raise ValueError(f"Could not determine format for {filename}")

def is_orientation_swap(genotype1, genotype2):
    """
    Determines if two genotypes are the same but with swapped orientation.
    
    Args:
        genotype1: First genotype string
        genotype2: Second genotype string
        
    Returns:
        bool: True if genotypes are orientation swaps, False otherwise
    """
    # Quick check for common orientation swaps
    orientation_pairs = [
        ('CT', 'TC'), ('TC', 'CT'),
        ('AG', 'GA'), ('GA', 'AG'),
        ('GT', 'TG'), ('TG', 'GT'),
        ('AC', 'CA'), ('CA', 'AC')
    ]
    
    return (genotype1, genotype2) in orientation_pairs

def detect_file_orientation(overlapping_snps):
    """
    Analyzes overlapping SNPs to determine if there's a consistent
    orientation difference between files.
    
    Args:
        overlapping_snps: List of (rsid, chrom, pos, genotype1, genotype2) tuples
        
    Returns:
        tuple: (is_orientation_issue, swap_pattern, pattern_frequency)
    """
    # Filter to consider only heterozygous SNPs (where orientation matters)
    hetero_snps = [(rsid, g1, g2) for rsid, _, _, g1, g2 in overlapping_snps 
                   if len(g1) == 2 and len(g2) == 2 and g1[0] != g1[1] and g2[0] != g2[1]]
    
    if not hetero_snps:
        return False, None, 0.0
    
    # Count the different types of "swaps"
    swap_patterns = []
    for _, g1, g2 in hetero_snps:
        if g1 != g2:
            swap_patterns.append((g1, g2))
    
    # Count frequencies of each swap pattern
    pattern_counts = Counter(swap_patterns)
    
    # If no patterns, there's no issue
    if not pattern_counts:
        return False, None, 0.0
    
    # Get the most common pattern
    most_common_pattern, count = pattern_counts.most_common(1)[0]
    pattern_frequency = count / len(hetero_snps)
    
    # Check if the pattern is a simple orientation swap
    is_orientation_issue = is_orientation_swap(*most_common_pattern)
    
    # If we have a consistent orientation pattern
    if pattern_frequency > 0.5 and is_orientation_issue:
        return True, most_common_pattern, pattern_frequency
    
    return False, None, pattern_frequency

def normalize_genotype(genotype, chromosome, flip_orientation=False, pattern=None):
    """
    Normalizes genotype representation to handle orientation differences
    and special cases like X chromosome in males.
    
    Args:
        genotype: Genotype string (e.g., 'CT', 'TC', 'T', 'TT')
        chromosome: Chromosome identifier ('X', 'Y', or a number)
        flip_orientation: Whether to flip heterozygous genotypes
        pattern: Orientation pattern to match against (e.g., ('CT', 'TC'))
        
    Returns:
        str: Normalized genotype
    """
    # Handle no-calls and invalid genotypes
    if genotype in ('--', '00', 'NN'):
        return '--'
        
    # For X chromosome in males (might be represented as single letter)
    if chromosome == 'X' and len(genotype) == 1:
        # Normalize to doubled representation
        return genotype + genotype
        
    # For Y chromosome (always single allele)
    elif chromosome == 'Y' and len(genotype) == 1:
        return genotype
        
    # Handle orientation flipping for heterozygous genotypes
    if flip_orientation and len(genotype) == 2 and genotype[0] != genotype[1]:
        if pattern and genotype == pattern[0]:
            return pattern[1]  # Apply specific flip pattern
        else:
            # General flip (swap positions)
            return genotype[1] + genotype[0]
    
    # Return original if no normalization rules apply
    return genotype

def is_no_call(genotype):
    """
    Determines if a genotype is a no-call.
    
    Args:
        genotype: Genotype string
        
    Returns:
        bool: True if the genotype is a no-call
    """
    return genotype in ('--', '00', 'NN')

def is_sex_chromosome_equivalent(genotype1, genotype2, chromosome):
    """
    Determines if genotypes on sex chromosomes are equivalent.
    
    Args:
        genotype1: First genotype
        genotype2: Second genotype
        chromosome: Either 'X', 'Y', or 'MT'
        
    Returns:
        bool: True if genotypes are equivalent
    """
    # For Y chromosome or MT, single letter is equivalent to doubled letters
    if chromosome in ('Y', 'MT'):
        if len(genotype1) == 1 and len(genotype2) == 2:
            return genotype1 == genotype2[0] == genotype2[1]
        elif len(genotype2) == 1 and len(genotype1) == 2:
            return genotype2 == genotype1[0] == genotype1[1]
    
    # For X chromosome (which can be heterozygous in females)
    if chromosome == 'X':
        # Single letter X (male) should match doubled (e.g., 'T' == 'TT')
        if len(genotype1) == 1 and len(genotype2) == 2:
            return genotype1 == genotype2[0] == genotype2[1]
        elif len(genotype2) == 1 and len(genotype1) == 2:
            return genotype2 == genotype1[0] == genotype1[1]
    
    return genotype1 == genotype2

def normalize_heterozygous(genotype):
    """
    Normalizes heterozygous genotypes by sorting the alleles.
    This handles cases like AT/AT or CG/CG that might be represented
    in the same way but flagged as different.
    
    Args:
        genotype: The genotype string
        
    Returns:
        str: The normalized genotype
    """
    if len(genotype) == 2 and genotype[0] != genotype[1]:
        return ''.join(sorted(genotype))
    return genotype

def are_genotypes_equivalent(genotype1, genotype2, chromosome):
    """
    Determines if two genotypes are equivalent, considering orientation
    and chromosome-specific representations.
    
    Args:
        genotype1: First genotype string
        genotype2: Second genotype string
        chromosome: Chromosome identifier
        
    Returns:
        bool: True if genotypes are equivalent, False otherwise
    """
    # Direct match
    if genotype1 == genotype2:
        return True
    
    # Handle sex chromosomes (X, Y, MT)
    if chromosome in ('X', 'Y', 'MT'):
        return is_sex_chromosome_equivalent(genotype1, genotype2, chromosome)
    
    # Handle orientation swaps (like CT vs TC)
    if is_orientation_swap(genotype1, genotype2):
        return True
    
    # Handle heterozygous genotypes with the same alleles but different order
    # This covers cases like AT/AT and CG/CG that might be falsely flagged as different
    norm1 = normalize_heterozygous(genotype1)
    norm2 = normalize_heterozygous(genotype2)
    if norm1 == norm2:
        return True
    
    return False

def choose_best_genotype(genotype1, genotype2, chromosome):
    """
    Chooses the best genotype from two options.
    
    Args:
        genotype1: First genotype string
        genotype2: Second genotype string
        chromosome: Chromosome identifier
        
    Returns:
        str: The best genotype (prioritizing real data over no-calls)
    """
    # If either is a no-call, choose the other
    if is_no_call(genotype1) and not is_no_call(genotype2):
        return genotype2
    elif is_no_call(genotype2) and not is_no_call(genotype1):
        return genotype1
    
    # For sex chromosomes, prefer doubled representation
    if chromosome in ('X', 'Y', 'MT'):
        if len(genotype1) == 2 and len(genotype2) == 1:
            return genotype1
        elif len(genotype1) == 1 and len(genotype2) == 2:
            return genotype2
    
    # Default to first genotype (primary takes precedence)
    return genotype1

def write_merged_data(primary_header, primary_data, primary_format,
                     secondary_header, secondary_data, secondary_format,
                     output_file):
    """
    Writes the merged DNA data to an output file and logs conflicts.
    Handles file-wide orientation differences.
    
    Args:
        primary_header: List of header lines from primary file
        primary_data: Dictionary of rsids to (chrom, pos, genotype) from primary file
        primary_format: Format of primary file ("23andme" or "ancestry")
        secondary_header: List of header lines from secondary file
        secondary_data: Dictionary of rsids to (chrom, pos, genotype) from secondary file
        secondary_format: Format of secondary file ("23andme" or "ancestry")
        output_file: Path where merged data will be written
        
    Returns:
        tuple: (total_snps, new_snps, true_conflicts, orientation_info) information
    """
    # First, analyze the overlapping SNPs to detect orientation patterns
    overlapping_snps = []
    diff_snps = []
    
    for rsid, (chrom, pos, genotype1) in primary_data.items():
        if rsid in secondary_data:
            chrom2, pos2, genotype2 = secondary_data[rsid]
            overlapping_snps.append((rsid, chrom, pos, genotype1, genotype2))
            
            # Only collect SNPs with different genotypes for orientation analysis
            if genotype1 != genotype2:
                diff_snps.append((rsid, chrom, pos, genotype1, genotype2))
    
    # Detect if there's a consistent orientation difference
    orientation_issue, swap_pattern, pattern_frequency = detect_file_orientation(diff_snps)
    
    # Create merged dataset
    merged_data = {}
    true_conflicts = []
    nocall_resolutions = []
    sex_chrom_normalized = []
    same_alleles_diff_order = []
    
    # Add all secondary data first
    for rsid, (chrom, pos, genotype) in secondary_data.items():
        # Normalize the genotype if there's a consistent orientation issue
        if orientation_issue and swap_pattern:
            normalized_genotype = normalize_genotype(genotype, chrom, 
                                                    flip_orientation=True, 
                                                    pattern=swap_pattern)
        else:
            normalized_genotype = normalize_genotype(genotype, chrom)
            
        merged_data[rsid] = (chrom, pos, normalized_genotype, "secondary")
    
    # Process primary data and identify true conflicts
    for rsid, (chrom, pos, genotype) in primary_data.items():
        if rsid in secondary_data:
            chrom2, pos2, secondary_genotype_orig = secondary_data[rsid]
            _, _, secondary_genotype_norm, _ = merged_data[rsid]
            
            # Handle no-calls (-- or 00)
            if is_no_call(genotype) or is_no_call(secondary_genotype_norm):
                best_genotype = choose_best_genotype(genotype, secondary_genotype_norm, chrom)
                nocall_resolutions.append((rsid, chrom, pos, genotype, secondary_genotype_orig, best_genotype))
                merged_data[rsid] = (chrom, pos, best_genotype, "merged")
                continue
                
            # Handle sex chromosome normalization
            if chrom in ('X', 'Y', 'MT') and is_sex_chromosome_equivalent(genotype, secondary_genotype_norm, chrom):
                best_genotype = choose_best_genotype(genotype, secondary_genotype_norm, chrom)
                sex_chrom_normalized.append((rsid, chrom, pos, genotype, secondary_genotype_orig, best_genotype))
                merged_data[rsid] = (chrom, pos, best_genotype, "merged")
                continue
                
            # Handle identical heterozygous genotypes (like AT/AT or CG/CG)
            if genotype != secondary_genotype_norm and normalize_heterozygous(genotype) == normalize_heterozygous(secondary_genotype_norm):
                # These are actually the same genotype, just represented differently
                same_alleles_diff_order.append((rsid, chrom, pos, genotype, secondary_genotype_orig))
                # Use primary's representation for consistency
                merged_data[rsid] = (chrom, pos, genotype, "primary")
                continue
                
            # Check for true conflicts
            if not are_genotypes_equivalent(genotype, secondary_genotype_norm, chrom):
                # Special case for Y chromosome: if completely different genotypes (C vs T)
                # this is truly a conflict, not just a representation issue
                if chrom == 'Y' and genotype != secondary_genotype_norm:
                    # Check if they're fundamentally different bases, not just representation
                    if (len(genotype) == 1 and len(secondary_genotype_norm) == 1 and genotype != secondary_genotype_norm) or \
                       (len(genotype) == 2 and len(secondary_genotype_norm) == 2 and 
                        genotype[0] != secondary_genotype_norm[0] and genotype[0] != secondary_genotype_norm[1]):
                        true_conflicts.append((rsid, chrom, pos, genotype, secondary_genotype_orig))
                else:
                    true_conflicts.append((rsid, chrom, pos, genotype, secondary_genotype_orig))
                    
                # Primary takes precedence
                merged_data[rsid] = (chrom, pos, genotype, "primary")
            else:
                # They're equivalent, use primary data
                merged_data[rsid] = (chrom, pos, genotype, "primary")
        else:
            # SNP only in primary file
            merged_data[rsid] = (chrom, pos, genotype, "primary")
    
    # Calculate statistics
    new_snps_from_secondary = len(merged_data) - len(primary_data)
    
    # Write merged data to output file
    with open(output_file, 'w') as f:
        # Write custom header
        f.write("# Merged DNA Data File\n")
        f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Primary source: {primary_format.upper()} format\n")
        f.write(f"# Secondary source: {secondary_format.upper()} format\n")
        
        if orientation_issue:
            f.write(f"# NOTE: Detected consistent orientation difference between files.\n")
            f.write(f"#       Pattern {swap_pattern[0]} → {swap_pattern[1]} in {pattern_frequency:.1%} of overlapping heterozygous SNPs\n")
            f.write(f"#       Secondary data was normalized to match primary data orientation\n")
        
        f.write(f"# No-call resolutions: {len(nocall_resolutions)}\n")
        f.write(f"# Sex chromosome normalizations: {len(sex_chrom_normalized)}\n")
        f.write(f"# Same alleles but different order: {len(same_alleles_diff_order)}\n")
        f.write(f"# True conflicts (primary source value used): {len(true_conflicts)}\n")
        f.write("#\n")
        
        # Write appropriate column headers based on output format
        if primary_format == "23andme":
            f.write("rsid\tchromosome\tposition\tgenotype\n")
        else:  # ancestry format
            f.write("rsid\tchromosome\tposition\tallele1\tallele2\n")
        
        # Write data rows with consistent spacing
        for rsid, (chrom, pos, genotype, source) in sorted(merged_data.items()):
            if primary_format == "23andme":
                f.write(f"{rsid}\t{chrom}\t{pos}\t{genotype}\n")
            else:  # ancestry format
                # Convert genotype back to allele1, allele2 format
                if len(genotype) == 2:
                    allele1, allele2 = genotype[0], genotype[1]
                else:
                    # Handle special cases like "--" or single letter genotypes
                    allele1 = allele2 = genotype[0] if genotype else "-"
                    
                f.write(f"{rsid}\t{chrom}\t{pos}\t{allele1}\t{allele2}\n")
    
    # Write true conflicts log
    if true_conflicts:
        conflict_file = output_file + ".conflicts.txt"
        with open(conflict_file, 'w') as f:
            f.write("# True Conflicting SNPs Log\n")
            f.write("# These are SNPs with genuinely different genotypes (not just orientation or representation differences)\n")
            if orientation_issue:
                f.write(f"# NOTE: Global orientation pattern {swap_pattern[0]} → {swap_pattern[1]} was accounted for\n")
                f.write(f"#       So these conflicts remain even after orientation normalization\n")
            f.write("# Primary file values were used in the merged output\n")
            f.write("#\n")
            f.write("# rsid\tchromosome\tposition\tprimary_genotype\tsecondary_genotype\n")
                
            for rsid, chrom, pos, primary_val, secondary_val in sorted(true_conflicts):
                f.write(f"{rsid}\t{chrom}\t{pos}\t{primary_val}\t{secondary_val}\n")
    
    # Write no-call resolutions log
    if nocall_resolutions:
        nocall_file = output_file + ".nocall_resolutions.txt"
        with open(nocall_file, 'w') as f:
            f.write("# No-Call Resolutions Log\n")
            f.write("# These are SNPs where one source had a no-call (-- or 00) and the other had actual data\n")
            f.write("#\n")
            f.write("# rsid\tchromosome\tposition\tprimary_value\tsecondary_value\tchosen_value\n")
                
            for rsid, chrom, pos, primary_val, secondary_val, chosen_val in sorted(nocall_resolutions):
                f.write(f"{rsid}\t{chrom}\t{pos}\t{primary_val}\t{secondary_val}\t{chosen_val}\n")
    
    # Write sex chromosome normalizations log
    if sex_chrom_normalized:
        sexchrom_file = output_file + ".sex_chromosome_normalizations.txt"
        with open(sexchrom_file, 'w') as f:
            f.write("# Sex Chromosome Normalizations Log\n")
            f.write("# These are SNPs on sex chromosomes (X, Y, MT) where single letter and doubled representations were normalized\n")
            f.write("#\n")
            f.write("# rsid\tchromosome\tposition\tprimary_value\tsecondary_value\tchosen_value\n")
                
            for rsid, chrom, pos, primary_val, secondary_val, chosen_val in sorted(sex_chrom_normalized):
                f.write(f"{rsid}\t{chrom}\t{pos}\t{primary_val}\t{secondary_val}\t{chosen_val}\n")
    
    # Write same alleles different order log
    if same_alleles_diff_order:
        same_alleles_file = output_file + ".same_alleles_diff_order.txt"
        with open(same_alleles_file, 'w') as f:
            f.write("# Same Alleles Different Order Log\n")
            f.write("# These are heterozygous SNPs with the same alleles but in different order (e.g., AT vs AT, CG vs CG)\n")
            f.write("# These are not true conflicts, just different representations\n")
            f.write("#\n")
            f.write("# rsid\tchromosome\tposition\tprimary_value\tsecondary_value\n")
                
            for rsid, chrom, pos, primary_val, secondary_val in sorted(same_alleles_diff_order):
                f.write(f"{rsid}\t{chrom}\t{pos}\t{primary_val}\t{secondary_val}\n")
    
    return (len(merged_data), new_snps_from_secondary, len(true_conflicts), 
            {"orientation_issue": orientation_issue, 
             "swap_pattern": swap_pattern, 
             "pattern_frequency": pattern_frequency,
             "nocall_resolutions": len(nocall_resolutions),
             "sex_chrom_normalized": len(sex_chrom_normalized),
             "same_alleles_diff_order": len(same_alleles_diff_order)})

def main():
    """
    Main function to parse command line arguments and execute the merge.
    """
    if len(sys.argv) != 4:
        print("Usage: python dna_merger.py primary_file secondary_file output_file")
        sys.exit(1)
    
    primary_file = sys.argv[1]
    secondary_file = sys.argv[2]
    output_file = sys.argv[3]
    
    # Validate input files
    for file in [primary_file, secondary_file]:
        if not os.path.isfile(file):
            print(f"Error: Input file '{file}' does not exist")
            sys.exit(1)
    
    try:
        # Parse input files
        print(f"Parsing primary file: {primary_file}")
        primary_header, primary_data, primary_format = parse_dna_file(primary_file)
        print(f"Detected format: {primary_format}")
        print(f"Found {len(primary_data)} SNPs in primary file")
        
        print(f"Parsing secondary file: {secondary_file}")
        secondary_header, secondary_data, secondary_format = parse_dna_file(secondary_file)
        print(f"Detected format: {secondary_format}")
        print(f"Found {len(secondary_data)} SNPs in secondary file")
        
        # Count overlapping SNPs
        overlap_count = sum(1 for rsid in primary_data if rsid in secondary_data)
        print(f"Found {overlap_count} overlapping SNPs between files")
        
        # Merge and write output
        print(f"Merging data and writing to: {output_file}")
        total_snps, new_snps, true_conflicts, info = write_merged_data(
            primary_header, primary_data, primary_format,
            secondary_header, secondary_data, secondary_format,
            output_file
        )
        
        # Report results
        print(f"Merge complete:")
        print(f"- Total SNPs in merged file: {total_snps}")
        print(f"- SNPs added from secondary file: {new_snps}")
        
        if info["orientation_issue"]:
            pattern = info["swap_pattern"]
            frequency = info["pattern_frequency"]
            print(f"- Detected consistent orientation difference: "
                  f"{pattern[0]} → {pattern[1]} in {frequency:.1%} of overlapping heterozygous SNPs")
            print(f"- Secondary data was normalized to match primary data orientation")
        
        print(f"- No-call resolutions (-- or 00 replaced with real data): {info['nocall_resolutions']}")
        if info['nocall_resolutions'] > 0:
            print(f"  - Details written to: {output_file}.nocall_resolutions.txt")
            
        print(f"- Sex chromosome normalizations (X, Y, MT single/double letter): {info['sex_chrom_normalized']}")
        if info['sex_chrom_normalized'] > 0:
            print(f"  - Details written to: {output_file}.sex_chromosome_normalizations.txt")
            
        print(f"- Same alleles but different order: {info['same_alleles_diff_order']}")
        if info['same_alleles_diff_order'] > 0:
            print(f"  - Details written to: {output_file}.same_alleles_diff_order.txt")
        
        print(f"- True genotype conflicts found (primary values used): {true_conflicts}")
        if true_conflicts > 0:
            print(f"  - Conflicts written to: {output_file}.conflicts.txt")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
