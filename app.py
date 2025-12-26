#!/usr/bin/env python3

import os
import re
import uuid
import shutil
import zipfile
from pathlib import Path
from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
from pypdf import PdfReader, PdfWriter
import pdfplumber

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/pdf-processor/uploads'
app.config['PROCESSING_FOLDER'] = '/tmp/pdf-processor/processing'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSING_FOLDER'], exist_ok=True)

def extract_info(pdf_path):
    """
    Extract the Family Envelope Number and Name from the first page of a PDF letter.
    Returns a tuple (envelope_number, name).
    """
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        text = first_page.extract_text()

        # Split text into lines
        lines = text.split('\n')

        envelope_num = None
        name = None

        # Find the line before the address (which should contain the envelope number)
        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check for envelope number line
            match = re.match(r'^(\d+)\s+Date Printed:', stripped)
            if match:
                envelope_num = int(match.group(1))

                # The name should be on the next line
                if i + 1 < len(lines):
                    name = lines[i+1].strip()
                break

    return envelope_num, name

def sanitize_filename(name):
    """Sanitize a string to be safe for filenames."""
    # Remove invalid characters
    s = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces with underscores
    s = s.replace(' ', '_')
    return s

def split_pdf_into_letters(input_pdf_path, output_folder):
    """
    Split a master PDF into individual letter PDFs.
    Uses "Page x of y" footer to determine letter boundaries.
    Returns a dictionary mapping Family Envelope Number to filename.
    """
    # Create output folder if it doesn't exist
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    # Read the input PDF
    reader = PdfReader(input_pdf_path)

    # Dictionary to store the mapping
    family_mapping = {}

    # Track pages for current letter
    current_letter_pages = []
    current_page_count = 0
    total_pages_in_letter = 0

    def save_letter(pages):
        """Helper to save a list of pages as a PDF."""
        # Create a temporary writer to extract info
        temp_writer = PdfWriter()
        temp_writer.add_page(pages[0])

        # We need to save to a temp file to use pdfplumber for extraction
        temp_filename = output_path / "temp_extract.pdf"
        with open(temp_filename, 'wb') as f:
            temp_writer.write(f)

        envelope_num, name = extract_info(temp_filename)

        # Clean up temp file
        if temp_filename.exists():
            os.remove(temp_filename)

        if name:
            safe_name = sanitize_filename(name)
            # Include envelope number to help ensure uniqueness
            if envelope_num:
                filename = f"{envelope_num}_{safe_name}.pdf"
            else:
                filename = f"{safe_name}.pdf"
        else:
            # Fallback if name not found
            filename = f"letter_unknown_{len(family_mapping)}.pdf"

        filepath = output_path / filename

        # Ensure filename is unique - add counter if file exists
        counter = 1
        while filepath.exists():
            if name:
                safe_name = sanitize_filename(name)
                if envelope_num:
                    filename = f"{envelope_num}_{safe_name}_{counter}.pdf"
                else:
                    filename = f"{safe_name}_{counter}.pdf"
            else:
                filename = f"letter_unknown_{len(family_mapping)}_{counter}.pdf"
            filepath = output_path / filename
            counter += 1

        # Write the full letter
        writer = PdfWriter()
        for p in pages:
            writer.add_page(p)

        with open(filepath, 'wb') as f:
            writer.write(f)

        return filename, envelope_num, name, len(pages)

    # Process each page
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text() or ""

        # Look for "Page X of Y" pattern
        page_match = re.search(r'Page\s+(\d+)\s+of\s+(\d+)', text)

        if page_match:
            current_page_num = int(page_match.group(1))
            total_pages = int(page_match.group(2))

            if current_page_num == 1:
                # Start of a new letter
                if current_letter_pages:
                    current_letter_pages = []

                current_letter_pages.append(page)
                total_pages_in_letter = total_pages

                # If it's a 1-page letter, save immediately
                if total_pages == 1:
                    filename, envelope_num, name, page_count = save_letter(current_letter_pages)
                    if envelope_num:
                        family_mapping[envelope_num] = {
                            'filename': filename,
                            'salutation': name,
                            'page_count': page_count
                        }
                    current_letter_pages = []
                    total_pages_in_letter = 0
            else:
                # Continuation of current letter
                current_letter_pages.append(page)

                # Check if we've reached the last page
                if current_page_num == total_pages:
                    filename, envelope_num, name, page_count = save_letter(current_letter_pages)
                    if envelope_num:
                        family_mapping[envelope_num] = {
                            'filename': filename,
                            'salutation': name,
                            'page_count': page_count
                        }
                    current_letter_pages = []
                    total_pages_in_letter = 0
        else:
            # Fallback: if we can't find the page number, but we have pages accumulating
            if current_letter_pages:
                current_letter_pages.append(page)

    # Handle any remaining pages (if last letter didn't end properly)
    if current_letter_pages:
        filename, envelope_num, name, page_count = save_letter(current_letter_pages)
        if envelope_num:
            family_mapping[envelope_num] = {
                'filename': filename,
                'salutation': name,
                'page_count': page_count
            }

    return family_mapping

def create_even_page_pdf(input_pdf_path, output_pdf_path, family_mapping):
    """
    Create a new PDF with blank pages inserted after odd-page letters
    to ensure each letter has an even number of pages.
    """
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()

    # We need to track which letters have odd pages
    # and insert blank pages after them

    # First, parse the original PDF to identify letter boundaries
    current_letter_pages = []
    letters_info = []

    for page_num, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        page_match = re.search(r'Page\s+(\d+)\s+of\s+(\d+)', text)

        if page_match:
            current_page_num = int(page_match.group(1))
            total_pages = int(page_match.group(2))

            if current_page_num == 1:
                # Save previous letter if exists
                if current_letter_pages:
                    letters_info.append(current_letter_pages)
                current_letter_pages = [page]

                if total_pages == 1:
                    letters_info.append(current_letter_pages)
                    current_letter_pages = []
            else:
                current_letter_pages.append(page)

                if current_page_num == total_pages:
                    letters_info.append(current_letter_pages)
                    current_letter_pages = []
        else:
            if current_letter_pages:
                current_letter_pages.append(page)

    # Handle remaining pages
    if current_letter_pages:
        letters_info.append(current_letter_pages)

    # Now create the new PDF with blank pages inserted as needed
    for letter_pages in letters_info:
        # Add all pages of the letter
        for page in letter_pages:
            writer.add_page(page)

        # If the letter has an odd number of pages, add a blank page
        if len(letter_pages) % 2 == 1:
            # Create a blank page with the same dimensions as the last page
            blank_page = writer.add_blank_page(
                width=letter_pages[-1].mediabox.width,
                height=letter_pages[-1].mediabox.height
            )

    # Write the output PDF
    with open(output_pdf_path, 'wb') as f:
        writer.write(f)

def create_zip_file(processing_dir, zip_filename):
    """Create a zip file containing all generated PDFs."""
    zip_path = Path(processing_dir) / zip_filename

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add individual letters
        letters_dir = Path(processing_dir) / 'individual-letters'
        if letters_dir.exists():
            for pdf_file in letters_dir.glob('*.pdf'):
                zipf.write(pdf_file, f'individual-letters/{pdf_file.name}')

        # Add even-page PDF
        even_page_pdf = Path(processing_dir) / 'even_page_letters.pdf'
        if even_page_pdf.exists():
            zipf.write(even_page_pdf, 'even_page_letters.pdf')

    return zip_path

@app.route('/')
def index():
    """Display the upload form."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and processing."""
    if 'pdf' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['pdf']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'File must be a PDF'}), 400

    try:
        # Create unique processing directory
        process_id = str(uuid.uuid4())
        processing_dir = Path(app.config['PROCESSING_FOLDER']) / process_id
        processing_dir.mkdir(parents=True, exist_ok=True)

        # Save uploaded file
        filename = secure_filename(file.filename)
        upload_path = processing_dir / filename
        file.save(upload_path)

        # Create output directories
        individual_letters_dir = processing_dir / 'individual-letters'
        individual_letters_dir.mkdir(exist_ok=True)

        # Step 1: Split into individual letters
        family_mapping = split_pdf_into_letters(
            str(upload_path),
            str(individual_letters_dir)
        )

        # Step 2: Create even-page PDF
        even_page_pdf = processing_dir / 'even_page_letters.pdf'
        create_even_page_pdf(
            str(upload_path),
            str(even_page_pdf),
            family_mapping
        )

        # Step 3: Create zip file
        zip_filename = 'processed_letters.zip'
        zip_path = create_zip_file(processing_dir, zip_filename)

        # Return the process_id so the client can download the zip
        return jsonify({
            'success': True,
            'process_id': process_id,
            'letters_count': len(family_mapping)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<process_id>')
def download_file(process_id):
    """Download the processed zip file."""
    try:
        processing_dir = Path(app.config['PROCESSING_FOLDER']) / process_id
        zip_path = processing_dir / 'processed_letters.zip'

        if not zip_path.exists():
            return jsonify({'error': 'File not found'}), 404

        # Send file and schedule cleanup
        response = send_file(
            zip_path,
            as_attachment=True,
            download_name='processed_letters.zip',
            mimetype='application/zip'
        )

        # Clean up the processing directory after sending the file
        @response.call_on_close
        def cleanup():
            try:
                if processing_dir.exists():
                    shutil.rmtree(processing_dir)
            except Exception as e:
                app.logger.error(f"Error cleaning up {processing_dir}: {e}")

        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
