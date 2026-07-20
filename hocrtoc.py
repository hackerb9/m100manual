#!/bin/python

import xml
import xml.etree.ElementTree as ET
import re
import sys

# Usage:
# 1. Create toc.hocr file using 'tesseract page.png toc hocr'
#    (Optionally, correct the hocr file using ScribeOCR).
# 2. Run this program ./hocrtoc.py output.hocr > annot.json
#    (Optionally, set boxwidth=1 in emit_annotation to see links.)
#    (Optionally, edit annot.json if there are any mistakes.)
# 3. Use cpdf -set-annotations annot.json foo.pdf -o bar.pdf

# Tips:
# * Only the hOCR file for the table of contents page(s) is needed. 
#
# * If the table of contents spans multiple pages in the PDF - say
#   pages 7 to 9 - use 'pdfimages -p -f 7 -l 9 -png input.pdf page'.
#
# * To create a single hOCR for multiple pages, tesseract has to read
#   the list of pages from a "file", but you needn't make a real file:
#   'tesseract <(ls page*.png) toc hocr'


# BUGS:

# * cpdf 2.9 removes the outline (AKA "bookmarks", AKA "index") from
#   the sidebar when adding annotations. (Weirdly, I can still jump to
#   the page number in Atril using ^L and typing the section name.)

# Todo:
#
# * Use pikepdf to add annotations (instead of external cpdf command).
#
# * Allow user to specify which page(s) have the TOC (Table of Contents). 
#
# * Allow user to specify page label offset.
#
# * Use pikepdf to convert page label to page number
#   (e.g., TOC says "Chapter One. . . . 5", but the page labeled "5"
#   is actually page number 11 due to cover, colophon, preface, etc.)
#
# * If no hocr file exists, extract the TOC pages as images and run
#   tesseract to generate the hocr file.
#
# * Give a better interface for fixing OCR mistakes in the hocr.
#   Currently, one is expected to input a perfect hocr file, edited
#   manually using something like scribeocr.  
# 
# * What would be a better way for removing or fixing mistaken
#   annotations? Other than editing the annot.json output file before
#   running cpdf, is there any terminal (character cell) interface
#   that makes sense?

def main(root):

    toc_fudge = 7;              # XXX hardcoded PDF page number of TOC
				# This should be passed in by command line

    start_annotations()

    pgnum=-1
    for page in root.iter():
        if page.get('class') != 'ocr_page':
            continue
        pgnum=pgnum+1

        # Parse "<div class='ocr_page' title='bbox 0 0 3500 4529'>"
        hocrbbox=page.get('title')
        hocrbbox=re.search(r'bbox[^;]*', hocrbbox).group(0).split()[1:]
        hocrbbox=list(map(float, hocrbbox))
        hocrmaxy=max(hocrbbox[3], hocrbbox[1])

        for line in page.iter():
            if line.get('class') != 'ocr_line':
                continue

            bbox=line.attrib['title']
            bbox=re.search(r'bbox[^;]*', bbox).group(0).split()[1:]
            bbox=list(map(float, bbox))
            # Flip origin from hocr's top-left to PDF's bottom-left.
            bbox=(bbox[0], hocrmaxy-bbox[1], bbox[2], hocrmaxy-bbox[3])
            # Convert from pixel coordinates to printer's points.
            PixelsPI=600        # XXX hardcoded DPI but should be detected
            PointsPI=72
            bbox=list(x/PixelsPI*PointsPI for x in bbox)

            text=''
            for word in line.findall('{*}span'):
                if word.get('class') != 'ocrx_word':
                    continue
                text=text+' '+word.text
            numstr=''
            for c in word.text[::-1]:
                if c.isdigit():
                    numstr=c+numstr
                else:
                    break
            if numstr:
                # Map from human sense of "page number" to PDF's literal number
                refpg=label_to_page_number(numstr)
                if (refpg >= 0):
                    xyz=(0, hocrmaxy/PixelsPI*PointsPI, 0)
                    emit_annotation(pgnum+toc_fudge, refpg, bbox, text, xyz)
                else:
                    print(f"Error converting '{numstr}' to a page number",
                          text, file=sys.stderr)
            else:
                print("Ignoring line without number at end",
                      text, file=sys.stderr)
    end_annotations()


def label_to_page_number(label):
    r"""XXX This is just a stub.

    Return the PDF page number (0 indexed) given the label that humans
    use to refer to a page numbers. For example, the table of contents
    may indicate page "1", but that might be the 10th page in the file
    due to prefatory material.
    """

    # XXX Hardcoded for each PDF file until we can figure out how to use
    # pikepdf to convert from labels to page numbers.
    return int(label)+8



def print_tree(t, prefix=""):
    r"""Just for debugging XML."""
    for child in t:
        print(prefix, child.tag, child.attrib, child.text)
        print_tree(child, prefix+'\t')
        

def start_annotations():
    print("""[
  [ -1, { "/CPDFJSONannotformatversion": { "I": 1 } } ]
    """)
    
def end_annotations():
    print("]")


# cpdf 2.9 has a feature where object numbers are automatically
# generated when setting annotations. Unfortunately, it also has a
# misfeature where one must still specify a unique object number for
# every annotation. Silly!
cpdf_kludge=32768

def emit_annotation(pagefrom, pageto, rect, comment="",   xyz=None):
    r"""Print the JSON formatted PDF annotation to create a link on
    'pagefrom' with a bounding box of 'rect' and a destination of 'pageto'.
    Note that pagefrom and pageto are literal PDF page numbers, not labels. 
    """

    boxwidth=1                  # Set to 1 to debug with boxes around links

    if not xyz:
        xyz=(0, 11*72, 0)       # location on destinatinon page
        		 	# XXX defaults to top of page for US Letter
    global cpdf_kludge
    cpdf_kludge=cpdf_kludge+1

    print(f',\n'
      f'[ '
        f'{pagefrom}, '          # page annotation appears on
        f'{cpdf_kludge}, '       # object number. cpdf ignores and auto assigns.
        f'{{ '
          # Optional description for accessibility and manual editing
          f'"/Contents": {{ "U": "{comment}" }},'

	  # Required type for simple links is /Annot/Link
          f'"/Type": {{ "N": "/Annot" }},'
          f'"/Subtype": {{ "N": "/Link" }},'
          # Destination page. X, Y in top left, Z is zoom; 0 to disable.
          f'"/Dest": [ {{ "I": {pageto} }}, {{ "N": "/XYZ"}},'
    	            f' {{ "I": {xyz[0]} }}, {{ "I": {xyz[1]} }}, {{ "I": {xyz[2]} }} ],'

          # bounding box rectangle (x1, y1, x2, y2)
          f'"/Rect": [ '
            f'{{ "F": {rect[0]} }},'
            f'{{ "F": {rect[1]} }},'
            f'{{ "F": {rect[2]} }},'
            f'{{ "F": {rect[3]} }}'
          f'],'
          # Annotation border geometry: horiz, vert corner radius, and width.
          # (Width of 0 means no border).
          f'"/Border": [ {{ "I": 0 }}, {{ "I": 0 }}, {{ "I": {boxwidth} }} ],'

          # Color of border (if width>0)
          f'"/C": [ {{ "I": 1 }}, {{ "I": 0 }}, {{ "I": 0 }} ],'

          # Highlighting mode on mouse hover (N)one, (I)nvert, (O)utline, or (P)ush
          f'"/H": {{ "N": "/I" }}'
        f'}}'
    f']', end='')

    # Reminder to self, instead of "/Dest", one could use an Action:
    # "/A": { "/S": { "N": "/GoTo" }, "/D": { "U": "chapter.1" } },


if len(sys.argv) <= 2:
    print(f"Usage: {sys.argv[0]} <infile.hocr> <outfile.json>", file=sys.stderr)
    exit(1)

try:
    root = ET.parse(sys.argv[1]).getroot()
except OSError as e:
    print(f"{sys.argv[1]}: {e.strerror}", file=sys.stderr)
    exit(1)

try:
    sys.stdout = open(sys.argv[2], 'w')
except OSError as e:
    print(f"{sys.argv[2]}: {e.strerror}", file=sys.stderr)
    exit(1)
    
main(root)
