"""
File containing functionality to generate PDFs, given a list of entries
"""
import os
import sys

import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

# ===============
#  PDF CONSTANTS
# ===============
# The number of columns and rows of data on each page
COLUMNS = 2
ROWS = 7
ITEMS_PER_PAGE = COLUMNS * ROWS
# The number of pixels per millimeter of page
PPM = 72 / 25.4
# Label positioning values (in mm)
PAGE_WIDTH = 210
PAGE_HEIGHT = 297
MARGIN_TOP = 15.15
MARGIN_LEFT = 7.75
LABEL_WIDTH = 99.1
LABEL_HEIGHT = 38.1
# Text in label positioning values (in mm)
MARGIN_TEXT_TOP = 9.5
MARGIN_TEXT_LEFT = 6.5
MARGIN_TEXT_INNER = 4.75


def generate_pdf(input_data: pd.DataFrame, out_file: str):
    """
    Generates a pdf in the sticker print format, given an input data dataframe

    Parameters
    ----------
    input_data: pd.DataFrame
        List of entries containing names and addresses, to be stored in a pdf
    out_file: str
        The output pdf file

    Returns
    -------
    pd.DataFrame:
        A DataFrame containing all correct CSV file entries
    """
    # Loading PDF font
    if getattr(sys, 'frozen', False):
        font = os.path.join(sys._MEIPASS, 'resources/cmunss.ttf')
    else:
        font = "resources/cmunss.ttf"
    # Initialise PDF settings
    print(f"Exporting {len(input_data)} addresses to {out_file}...")
    pdf = canvas.Canvas(out_file, pagesize=(PPM * PAGE_WIDTH, PPM * PAGE_HEIGHT))
    pdf.setTitle("Thabloid Stickers")
    pdfmetrics.registerFont(TTFont("cmunss", font))
    pdf.setFont("cmunss", 11)

    # Loop through all input entries
    for i, entry in input_data.iterrows():
        row = i % ITEMS_PER_PAGE // 2
        column = (i % ITEMS_PER_PAGE) % COLUMNS

        # Calculate text positions (note that we invert y
        # because it starts at the bottom for some reason)
        text_x = MARGIN_LEFT + column * LABEL_WIDTH + MARGIN_TEXT_LEFT
        text_y = PAGE_HEIGHT - (MARGIN_TOP + row * LABEL_HEIGHT + MARGIN_TEXT_TOP)

        # Draw the name and address
        pdf.drawString(PPM * text_x, PPM * text_y, entry["first_name"] + " " + entry["last_name"])
        pdf.drawString(PPM * text_x, PPM * (text_y - MARGIN_TEXT_INNER), entry["address"])
        # Draw second address line, postcode and town. Depends on if a second address line is set
        postal_code_and_city = entry["postal_code"] + "  " + entry["city"]
        if len(entry["address_2"]) != 0:
            pdf.drawString(PPM * text_x, PPM * (text_y - 2 * MARGIN_TEXT_INNER), entry["address_2"])
            pdf.drawString(PPM * text_x, PPM * (text_y - 3 * MARGIN_TEXT_INNER), postal_code_and_city)
            if len(entry["country"]) != 0 and entry["country"].lower() != "netherlands":
                pdf.drawString(PPM * text_x, PPM * (text_y - 4 * MARGIN_TEXT_INNER), entry["country"].upper())
        else:
            pdf.drawString(PPM * text_x, PPM * (text_y - 2 * MARGIN_TEXT_INNER), postal_code_and_city)
            if len(entry["country"]) != 0 and entry["country"].lower() != "netherlands":
                pdf.drawString(PPM * text_x, PPM * (text_y - 3 * MARGIN_TEXT_INNER), entry["country"].upper())

        # If we reached a new page, print the current page and re-set the font
        if (i + 1) % ITEMS_PER_PAGE == 0:
            pdf.showPage()
            pdf.setFont("cmunss", 11)

    # Save the pdf
    pdf.save()
