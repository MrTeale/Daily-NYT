import base64
from datetime import datetime, timedelta
from io import BytesIO

import pytz
import requests
from pdf2image import convert_from_bytes
from PIL import Image


def send_file(path):
    with open(path, 'rb') as image_processed:
        image_processed_data = image_processed.read()
    image_64_encode = base64.b64encode(image_processed_data)

    image_string = image_64_encode.decode('utf-8')

    return {
        "statusCode": "200",
        "body": image_string,
        "headers": {
            "Content-Type": "image/gif",
        },
        "isBase64Encoded": "true"
    }


def get_pdf_scan(date_value):
    url = f"https://static01.nyt.com/images/{date_value.strftime('%Y')}/{date_value.strftime('%m')}/{date_value.strftime('%d')}/nytfrontpage/scan.pdf"
    response = requests.get(url)
    if response.status_code == 404:
        raise requests.HTTPError("404")
    return response.content


def main(event, context):
    # Get current time in NYC
    current_time = datetime.now(pytz.timezone('EST'))

    # Download the raw image
    try:
        pdf_scan = get_pdf_scan(current_time)
    except requests.HTTPError as e:
        pdf_scan = get_pdf_scan(current_time - timedelta(days=1))
    
    jpegopt_value = {
        "quality": 100,
        "optimize": False,
        "progressive": False
    }
    nyt_scan_raw = convert_from_bytes(BytesIO(pdf_scan).read(), use_cropbox=True, dpi=300, grayscale=True, fmt='jpeg', size=(1440, 2560))[0]  
    nyt_scan_raw.save('/tmp/NYT_Raw.jpeg')

    return send_file('/tmp/NYT_Raw.jpeg')

if __name__ == "__main__":
    main("", "")
