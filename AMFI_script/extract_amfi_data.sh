#!/bin/bash

URL="https://www.amfiindia.com/spages/NAVAll.txt"
OUTPUT="nav_data.tsv"

curl -s "$URL" | awk -F';' '
BEGIN {
    OFS="\t";
    print "Scheme Name","Asset Value";
}
NF == 6 && $4 != "" && $5 != "" {
    gsub(/^[ \t]+|[ \t]+$/, "", $4);  # Trim spaces in scheme name
    gsub(/^[ \t]+|[ \t]+$/, "", $5);  # Trim spaces in asset value
    print $4, $5;
}' > "$OUTPUT"

echo "Cleaned TSV saved to $OUTPUT"
