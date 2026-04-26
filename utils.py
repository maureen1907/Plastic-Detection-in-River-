import base64
import numpy as np
import cv2


def base64_to_image(base64_string):
    # Decode the base64 string to bytes
    image_data = base64.b64decode(base64_string)
    
    # Convert bytes to a NumPy array
    nparr = np.frombuffer(image_data, np.uint8)
    
    # Decode the image using OpenCV
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    return img

def image_to_base64(image):
    # Encode the image to JPEG format
    _, buffer = cv2.imencode('.jpg', image)
    
    # Convert the buffer to a base64 string
    base64_string = base64.b64encode(buffer).decode('utf-8')
    
    return base64_string