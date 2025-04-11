import argparse
from builtins import Exception, ValueError, any, open, print
import os
import re
from pathlib import Path

from pytesseract import image_to_string
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_args():
    parser = argparse.ArgumentParser(description='receiptprocessor and categorizer')
    parser.add_argument('--input', default='incoming_receipts', help='input directory with receipt images')
    parser.add_argument('--output', default='out/txt/', help='output directory')
    return parser.parse_args()

def binarize_image(im):
    return im.point(lambda x: 255 if x > 170 else 0)

def extract_warranty_and_products(text):
    warranty_date = re.search(r'warranty.*?(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
    products = re.findall(r'([A-Za-z\s]+)\s+(\d+\.\d{2})', text)
    return warranty_date.group(1) if warranty_date else None, products

def categorize_receipt(text):
    # Simple categorization based on keywords
    categories = {
        'restaurant': ['restaurant', 'cafe', 'diner'],
        'grocery': ['grocery', 'supermarket', 'food','walmart'],
        'electronics': ['electronics', 'technology', 'gadget'],
        'warrenty': ['warrenty', 'WARRENTY', 'valid until', 'expiry']
    }
    for category, keywords in categories.items():
        if any(keyword in text.lower() for keyword in keywords):
            return category
    return 'other'

def generate_output(path, category, warranty_date, products, text):
    try:
        with open(path, "w") as file:
            file.write(f"Category: {category}\n\n")
            file.write(f"Extracted Text:\n{text}\n\n")
            if warranty_date:
                file.write(f"Warranty Date: {warranty_date}\n")
            file.write("Products:\n")
            for name, price in products:
                file.write(f"{name}: {price}\n")
        logging.debug(f'Generated {path}')
    except IOError as e:
        logging.error(f"Error writing to text file: {e}")

def process_receipt(image_path, output_dir):
    try:
        logging.debug(f"Processing receipt: {image_path}")
        im = Image.open(image_path).convert('L')
        im = binarize_image(im)
        text = image_to_string(im, lang='eng')
        logging.debug(f"Extracted text: {text}")
        category = categorize_receipt(text)
        warranty_date, products = extract_warranty_and_products(text)
        logging.debug(f"Categorized as: {category}, Warranty Date: {warranty_date}, Products: {products}")
        
        # Create category subdirectory
        category_dir = os.path.join(output_dir, category)
        os.makedirs(category_dir, exist_ok=True)
        
        # Generate output file
        output_path = os.path.join(category_dir, Path(image_path).stem + '.txt')
        generate_output(output_path, category, warranty_date, products, text)
        
        return category, warranty_date, output_path
    except Exception as e:
        logging.error(f"Error processing image {image_path}: {e}")
        return None, None, None

def check_expiring_warranties(warranties, days_threshold=7):
    today = datetime.now().date()
    expiring_soon = []
    for item, date_str, path in warranties:
        try:
            date = datetime.strptime(date_str, "%m/%d/%Y").date()
            if (date - today).days <= days_threshold:
                expiring_soon.append((item, date, path))
        except ValueError:
            logging.warning(f"Invalid date format for {item}: {date_str}")
    return expiring_soon

def main():
    args = parse_args()
    logging.debug(f"Input directory: {args.input}, Output directory: {args.output}")
    os.makedirs(args.output, exist_ok=True)
    warranties = []

    # Process all receipts in the incoming directory
    for filename in os.listdir(args.input):
        if filename.endswith(('.jpg', '.jpeg', '.png')):
            image_path = os.path.join(args.input, filename)
            category, warranty_date, new_path = process_receipt(image_path, args.output)
            if category:
                logging.info(f"Processed {filename}: Category - {category}, Warranty Date - {warranty_date}")
                if warranty_date:
                    warranties.append((filename, warranty_date, new_path))

    # Check for expiring warranties
    expiring_soon = check_expiring_warranties(warranties)
    for item, date, path in expiring_soon:
        logging.warning(f"ALERT: Warranty for {item} is expiring on {date}. Receipt stored at {path}")

if __name__ == "__main__":
    main()