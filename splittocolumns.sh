#!/bin/bash
# splittocolumns
# A working example of splitting the two-column Index pages.
#
# Tesseract 5.5 is not very good at detecting two-column layouts. 
# As a workaround, one can split each page into two images by
# masking a rectangle and its inverse.
#
# The masking must be done manually and set in the variable mask, below.
#
# For each filename f, mask[f] holds four numbers: x1, y1, x2, y2.
# (x1,y1) is the top left and (x2,y2) the bottom right point of the
# rectangle which covers the second column of text.
#
# The pixel values can be determined by using the `display` command and
# clicking with the middle mouse button. (Pixel 0,0 is in the top left
# of the page; the same coordinate system as hOCR).

# After this script is run, 1. use tesseract in hocr-mode. 2. Edit the
# resulting .hocr so that each pair of columns are merged into a
# single page by deleting the intervening </div><div class='ocr_page"...>. 
# 3. Optionally adjust the ppageno and id to match the physical and
# logical page numbers.

######################################################################

# hOCR bounding box for entire page.
pgbbox="0 0 5100 6600"
read bbx1 bby1 bbx2 bby2 <<< $pgbbox

declare -A mask
mask["page-229.png"]="2540 1045 4201 6025"
mask["page-230.png"]="2658 1047 4221 6046"
mask["page-231.png"]="2602 1049 4177 6050"
mask["page-232.png"]="2637 1049 4212 2166"


######################################################################

# For laughs, let's die if a variable is used without being set first.
set -o nounset

mkdir -p twocol
for pg in ${!mask[@]}; do
    output="twocol/${pg%.*}"
    echo  "Writing to $output..." >&2
    read x1 y1 x2 y2 <<< ${mask[$pg]}

    # Mask out just the rectangle of the 2nd column
    convert $pg -fill white \
     	    -draw "rectangle $x1,$y1 $x2,$y2" \
	    ${output}-mask.png

    # Mask out everything but the 2nd column. Frisket (inverse mask)
    # done by a CCW rectangle inside a CW rectangle in a single path.
    convert $pg -fill white -stroke none \
	    -draw "path 'M $bbx1,$bby1 $bbx2,$bby1 $bbx2,$bby2 $bbx1,$bby2 Z
	                 M  $x2,$y2  $x2,$y1  $x1,$y1  $x1,$y2  Z'" \
	    ${output}-frisket.png
done

