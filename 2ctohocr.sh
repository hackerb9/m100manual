#!/bin/bash -xe

# The M100 manual's index is in 2 columns, which confuses tesseract.

# This script extracts just the index pages, splits the columns (manually), 
# runs tesseract on each, and then merges the pages back again.

# STEPS THIS SCRIPT DOES:
#
# 1. Extract the scanned image files for the Index pages. 
#
# 2. Run splittocolumns: For each image given, create two new images:
#    one with everything but the second column and the other with only
#    the second column. 
#
# 3. Run tesseract on columns individually, emitting a hocr file. 
#
# 4. Munge the hocr file so that both columns are on a single page.
#
# 5. Run hocrtoc: Search for page numbers and turn them into hyperlinks.
######################################################################


# Extract the scanned index pages from input.pdf to index-{000..3}.png
mkdir -p twocol
pdfimages -f 229 -l 232 -png ${1:-input.pdf} twocol/index

# Use the hand-tweaked values to split each image in to two columns.
cd twocol
../splittocolumns.sh

tesseract <(ls index-{000..3}-{frisket,mask}.png) dblpage --dpi 600 \
	  -c hocr_char_boxes=1 -c preserve_interword_spaces=1 hocr

# line numbers of ocr_page <div> tags.  ( 12 377  728 1084 1500 1853 2274 2337)
linenums=$(awk  '/div class=.ocr_page/ {print NR}'  dblpage.hocr)
# find every other page tag		(    377      1084      1853      2337)
linenums=$(awk  'NR%2==0' <<<"$linenums")
# plus the </div> on the previous line 	(376 377 1083 1084 1852 1853 2336 2337)
linenums=$(awk  '{print $1-1 "d;"; print $1 "d;"}' <<<"$linenums")
# delete those lines
sed -e "$linenums"  dblpage.hocr >../index.hocr 
cd ..
rm -r twocol

# Remove physical page numbers from hocr, if they exist
sed -i -E 's/ppageno [^;]+;//' index.hocr

# Run hocrtoc to create hyperlinks from page numbers.
./hocrtoc.py --debug -i -d 600 -P 228 -L 8 index.hocr index.json

# Apply the hyperlinks to the PDF file.
cpdf -set-annotations index.json input.pdf -o output.pdf
