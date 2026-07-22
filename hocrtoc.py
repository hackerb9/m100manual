#!/bin/python

from getopt import gnu_getopt
import xml
import xml.etree.ElementTree as ET
import re
import sys

# Usage:
# 1. Create toc.hocr file using 'tesseract page.png toc hocr'
#    (Optionally, correct the hocr file using ScribeOCR).
# 2. Run this program ./hocrtoc.py output.hocr annot.json
#    (Optionally, use --debug to see links.)
#    (Optionally, edit annot.json if there are any mistakes.)
# 3. Use cpdf -set-annotations annot.json in.pdf -o out.pdf

# Tips:
# * Only the hOCR file for the table of contents page(s) is needed. 
#
# * If the table of contents spans multiple pages in the PDF - say
#   pages 7 to 9 - use 'pdfimages -p -f 7 -l 9 -png input.pdf page'.
#
# * To create a single hOCR for multiple pages, tesseract has to read
#   the list of pages from a "file", but you needn't make a real file:
#   'tesseract <(ls page*.png) toc hocr'
#
# * For grabbing an index which can have multiple numbers separated by
# * columns, it is best run tesseract like so to grab individual char boxes: 
#
#    tesseract <(ls page*png) output -c hocr_char_boxes=1 hocr



# * You'll likely want to specify which page(s) have the TOC. (-t 7-8)
#   The default is 0. Note that PDF files actually number the first
#   page as 0, but most PDF viewers increase the count by one.
#
# * You may need to specify the page number of "Page 1". (-L 10)
#   The same caveat about PDF page numbers beginning at 0 applies here.
#
# * If the annotations show up on the wrong page, use the -T option to
#   shift them forward or back.

# BUGS:  
#
# * The interface consistently numbers pages starting with 0. That's
#   the way PDF works internally, but it's not what other user facing
#   programs do, including cpdf.
#
# * Probably many more, but none known at the moment.

# Todo:
#
# * Use pikepdf to add annotations (instead of external cpdf command).
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

def main(root, toc_first_page=0, toc_last_page=-1,
         toc_offset=0, index_mode=False):
    f"""
    root is the hocr XML tree to process,
    toc_first and _last are the page number of the TOC in the hocr input.
    toc_offset is the number of pages to shift annotations in PDF output.
    index_mode indicates if numbers should be highlighted individually (instead of entire lines).
    """

    # Get rid of whitespace that tesseract adds before ocrx_cinfo tags 
    root = preprocess_hocr(root)
    start_annotations()

    pgnum=-1
    for page in root.iter():
        if page.get('class') != 'ocr_page':
            continue
        pgnum=pgnum+1

        if pgnum < toc_first_page:
            continue
        if (pgnum > toc_last_page) and (toc_last_page >= 0):
            continue

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
            bbox=list(pixels_to_points(x) for x in bbox)

            text=''
            for word in line.findall('{*}span'):
                if word.get('class') != 'ocrx_word':
                    continue
                if word.text:
                    text=text+' '+word.text
                for char in word.findall('{*}span'):
                    if char.get('class') != 'ocrx_cinfo':
                        continue
                    if char.text:
                        text=text+char.text
            if not text:
                continue
            numstr=''
            for c in text[::-1]:
                if c.isdigit():
                    numstr=c+numstr
                else:
                    break
            if numstr:
                # Map from human sense of "page number" to PDF's literal number
                refpg=label_to_page_number(numstr)
                if (refpg >= 0):
                    if (Verbose_Flag>0):
                        print(f"Adding link to page {refpg} from {pgnum+toc_offset}"
                              f" for text: {text}", file=sys.stderr)
                    xyz=(0, pixels_to_points(hocrmaxy), 0)
                    emit_annotation(pgnum+toc_offset, refpg, bbox, text, xyz)
                else:
                    print(f"Error converting '{numstr}' to a page number",
                          text, file=sys.stderr)
            else:
                if (Verbose_Flag>1):
                    print("Ignoring line without number at end",
                          text, file=sys.stderr)
    end_annotations()

    if pgnum < toc_first_page:
        print(f"Invalid TOC first page={toc_first_page}. Last page num is {pgnum} in hocr file.", file=sys.stderr)
        
def pixels_to_points(x):
    """hOCR specifies bounding boxes using pixel coordinates.
    PDF needs that scaled to printer's points"""
    PointsPerInch=72
    return x * PointsPerInch / PixelsPerInch


def label_to_page_number(label):
    r"""XXX This is just a stub.

    Return the PDF page number (0 indexed) given the label that humans
    use to refer to a page numbers. For example, the table of contents
    may indicate page "1", but that might be the 10th page in the file
    due to prefatory material.
    """

    # XXX Uses a value passed in from the command line for each PDF
    # file until we can figure out how to use pikepdf to convert from
    # labels to page numbers.
    return int(label)+Label_Offset


def preprocess_hocr(root):
    r"""Fix tesseract's mistaken whitespace before each ocrx_cinfo. 

    `tesseract -c hocr_char_boxes=1` generates HTML that looks like this:

<span class='ocrx_word' id='word_1_14' title='bbox 83 105 94 111; x_wconf 96'>
  <span class='ocrx_cinfo' title='x_bboxes 83 105 88 111; x_conf 99.5'>A</span>
  <span class='ocrx_cinfo' title='x_bboxes 89 105 94 111; x_conf 99.5'>C</span>
</span>

    That's a problem since HTML/XML treats white-space as meaningful.
    Python's XML reads the above as "\n  A\n  C\n" instead of "AC".

    We could try to walk the tree to find that errant whitespace, but
    that is annoyingly tricky to get right with XPATH.

    Fortunately, there's an easier solution: regexes!

	    [\n\s]*(<span class="ocrx_cinfo)

    Yes, it is not a general fix, but as far as I know, this is not a
    general problem. This is a patch just for tesseract 5.5.0.
    """
    hocrtext = xml.etree.ElementTree.tostring(root, encoding="unicode")
    
    regex = re.compile(r"""
    	[\n\s]*                 # Chew up whitespace & newlines
        (?=			# Positive lookahead assertion
    	    <(html:)?           #    Tag start and optional "html:" prefix
    	    SPAN[^>]*CLASS=     #    SPAN tag, CLASS property
            "OCRX_CINFO"        #    Character info class
        )			# End group "cinfo"
    """, flags = re.IGNORECASE | re.VERBOSE) # Ignore case, allow comments

    rv = re.sub(regex, '' , hocrtext)
    return ET.fromstring(rv)

def print_tree(t, prefix=""):
    r"""Just for debugging hocr XML."""
    for child in t.findall('*'):
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

    boxwidth = Debug_Flag       # Set to 1 to debug with boxes around links

    if not xyz:
        xyz=(0, 11*72, 0)       # location on destinatinon page
        		 	# defaults to top of page for US Letter

    # Cpdf requires the object number to be unique, but then ignores
    # it and auto assigns a different number.
    global cpdf_kludge
    cpdf_kludge=cpdf_kludge+1

    # cpdf numbers pages starting with 1!
    pagefrom = pagefrom + 1

    print(f',\n'
      f'[ '
        f'{pagefrom}, '          # page annotation appears on
        f'{cpdf_kludge}, '       # object number. cpdf autoassigns.
        f'{{ '
          # Optional description for accessibility and manual editing
          f'"/Contents": {{ "U": "{enquote(comment)}" }},'

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

def enquote(s):
    r"""Given a string with possible double-quotes in it ("), put
    a backslash in front of them."""
    regex = re.compile(r'"')
    return re.sub(regex, '\\"', s)

# Parse args, open files, call main()

import optparse

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.set_usage("%prog [-v] [-t <p1>[-<p2>]] [-T <p> ] <input.hocr> <output.json>\n"
                     "\tWhere <p> is a PDF page number (first page is 0).\n\n"
                     "%prog: Add hyperlinks annotations to a scanned Table of Contents")
    parser.add_option('-t', '--toc-page-number', dest='toc_pgnum', default="-", metavar='P1-P2',
                      help="Which pages in the input hocr file hold the Table of Contents to parse. Use x-y (dash) to separate a range. First page is 0. Defaults to all pages.")
    parser.add_option('-d', '--dpi', dest='DPI', default="600", 
                      help="Dots Per Inch of the scan for converting from hocr bitmap coordinates to PDF typographic points. Defaults to 600.")
    parser.add_option('-T', '--toc-offset', dest='toc_offset', default="0", metavar='N',
                      help="Annotations are drawn shifted this many pages in the output. Useful if hocr is created from a PDF with just the TOC. Defaults to +0.")
    parser.add_option('-L', '--label-offset', dest='label_offset', default="0", metavar='N',
                      help="The PDF page number of the page labeled '1'. Useful when front matter — title page, colophon, frontispiece, etc. — come before page 1.")
    parser.add_option('-v', dest='verbose', action='count', default=0,
                      help="Increase verbosity")
    parser.add_option('-i', '--index-mode', dest='index_mode', action='store_true', default=False,
                      help="Make links for individual numbers. Useful for indices which often have multiple pages listed for an entry.")
    parser.add_option('--debug', dest='debug', action='count', default=0,
                      help="Show red boxes around annotations")
    
    (opts, args) = parser.parse_args()

    if len(args) <= 1:
        print(f"Usage: {sys.argv[0]} <infile.hocr> <outfile.json>", file=sys.stderr)
        exit(1)

    try:
        root = ET.parse(args[0]).getroot()
    except OSError as e:
        print(f"{args[0]}: {e.strerror}", file=sys.stderr)
        exit(1)

    try:
        sys.stdout = open(args[1], 'w')
    except OSError as e:
        print(f"{args[1]}: {e.strerror}", file=sys.stderr)
        exit(1)

    if '-' in opts.toc_pgnum:
        (toc_first_page, toc_last_page) = opts.toc_pgnum.split('-')
        if not toc_first_page: toc_first_page="0"
        if not toc_last_page: toc_last_page="-1"
    else:
        toc_first_page = opts.toc_pgnum
        toc_last_page  = opts.toc_pgnum

    global Label_Offset
    Label_Offset=int(opts.label_offset)
    global PixelsPerInch
    PixelsPerInch = float(opts.DPI)
    global Debug_Flag
    Debug_Flag = opts.debug
    global Verbose_Flag
    Verbose_Flag = opts.verbose

    main(root,
         toc_first_page=int(toc_first_page),
         toc_last_page=int(toc_last_page),
         toc_offset=int(opts.toc_offset),
         index_mode=opts.index_mode)
