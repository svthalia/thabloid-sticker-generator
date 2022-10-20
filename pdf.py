import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

# ===============
#  PDF CONSTANTS
# ===============
# The number of columns and rows of data on each page
columns = 2
rows = 7
items_per_page = columns * rows
# The number of pixels per millimeter of page
ppm = 72 / 25.4
# Label positioning values (in mm)
page_width = 210
page_height = 297
margin_top = 15.15
margin_left = 7.75
label_width = 99.1
label_height = 38.1
# Text in label positioning values (in mm)
margin_text_top = 9.5
margin_text_left = 6.5
margin_text_inner = 4.75


def generate_pdf(input_data, out_file):
    """
    Generates a pdf in the sticker print format
    :param input_data: list of entries containing names and addresses, to be stored in a pdf
    :param out_file: the output pdf file
    """
    # Initialise PDF settings
    print(f"Exporting {len(input_data)} addresses to {out_file}...")
    pdf = canvas.Canvas(out_file, pagesize=(ppm * page_width, ppm * page_height))
    pdf.setTitle("Thabloid Stickers")
    pdfmetrics.registerFont(TTFont("cmunss", "resources/cmunss.ttf"))
    pdf.setFont("cmunss", 11)

    # Loop through all input entries
    for i, entry in input_data.iterrows():
        row = i % items_per_page // 2
        column = (i % items_per_page) % columns

        # Calculate text positions (note that we invert y because it starts at the bottom for some reason)
        text_x = margin_left + column * label_width + margin_text_left
        text_y = page_height - (margin_top + row * label_height + margin_text_top)

        # Draw the name and address
        pdf.drawString(ppm * text_x, ppm * text_y, entry["first_name"] + " " + entry["last_name"])
        pdf.drawString(ppm * text_x, ppm * (text_y - margin_text_inner), entry["address"])
        # Draw second address line, postcode and town. Depends on whether a second address line is set
        postal_code_and_city = entry["postal_code"] + "  " + entry["city"]
        if len(entry["address_2"]) != 0:
            pdf.drawString(ppm * text_x, ppm * (text_y - 2 * margin_text_inner), entry["address_2"])
            pdf.drawString(ppm * text_x, ppm * (text_y - 3 * margin_text_inner), postal_code_and_city)
            if len(entry["country"]) != 0 and entry["country"].lower() != "netherlands":
                pdf.drawString(ppm * text_x, ppm * (text_y - 4 * margin_text_inner), entry["country"].upper())
        else:
            pdf.drawString(ppm * text_x, ppm * (text_y - 2 * margin_text_inner), postal_code_and_city)
            if len(entry["country"]) != 0 and entry["country"].lower() != "netherlands":
                pdf.drawString(ppm * text_x, ppm * (text_y - 3 * margin_text_inner), entry["country"].upper())

        # If we reached a new page, print the current page and re-set the font
        if (i + 1) % items_per_page == 0:
            pdf.showPage()
            pdf.setFont("cmunss", 11)

    # Save the pdf
    pdf.save()
