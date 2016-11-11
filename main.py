from flask import Flask, render_template, request, url_for, redirect, make_response, session
from flask_cors import CORS, cross_origin
from ml import *
import os
from config import *
from clarifai.client import ClarifaiApi
import json
from instagram.client import InstagramAPI
import requests
import datetime

app = Flask(__name__)
app.config['CORS_HEADERS'] = 'Content-Type'
app.secret_key = os.urandom(24).encode('hex')
CORS(app)

# Set Clarifai API credentials
os.environ['CLARIFAI_APP_ID'] = CLARIFAI_APP_ID
os.environ['CLARIFAI_APP_SECRET'] = CLARIFAI_APP_SECRET

clarifai_api = ClarifaiApi()

model = None

tag_indices = {}
current_index = 0

# Convert image to vector
def image_vector(img_file):
    img_data = clarifai_api.tag_images(img_file)
    tags = img_data['results'][0]['result']['tag']['classes']

    vector = [0] * current_index

    for tag in tags:
        if tag in tag_indices:
            vector[tag_indices[tag]] = 1

    return vector

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload')
def upload():
    return render_template('upload.html')

@app.route('/register-account', methods=['GET', 'POST'])
def register_account():
    access_token = request.json['token']
    user_id = request.json['user_id']

    if not access_token:
        return 'Missing access token'

    session['access_token'] = access_token
    session['user_id'] = user_id

    api = InstagramAPI(access_token=access_token, client_secret=IG_CLIENT_SECRET)

    recent_media, next_ = api.user_recent_media(user_id=user_id, count=20)

    tags = []
    num_likes = []
    dates = []

    # Convert all images to vectors
    for media in recent_media:
        img_data = clarifai_api.tag_image_urls(media.images['standard_resolution'].url)
        tags.append(img_data['results'][0]['result']['tag']['classes'])
        date = int(media.created_time.strftime("%s")) * 1000
        dates.append(date)
        num_likes.append(media.like_count)

    # Dictionary to store indices of tags
    global tag_indices
    # Iterator for indices
    global current_index

    for vector in tags:
        for tag in vector:
            if tag not in tag_indices:
                tag_indices[tag] = current_index
                current_index += 1

    data = []

    # Generate vectors for each image by marking tags as present
    for i in range(len(tags)):
        vector = [0] * current_index

        for tag in tags[i]:
            vector[tag_indices[tag]] = 1

        # Append date number of likes to end of vector
        vector.append(dates[i])
        vector.append(num_likes[i])

        data.append(vector)

    global model
    model = LikePredictor(data)

    return 'Done'


@app.route('/process-image', methods=['POST'])
def process_image():
    vector = image_vector(request.files['image'])

    global model
    global current_index
    global tag_indices

    data = {'prediction': model.predict(vector)}
    response = make_response(json.dumps(data), 200)
    response.headers['Content-Type'] = 'application/json'
    return response


if __name__ == '__main__':
    app.run(debug=True)

