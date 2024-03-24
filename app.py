from flask import Flask, render_template, jsonify, request, Response
import time
import board
import neopixel
import adafruit_dht
import sqlite3
import pygame
import os
import RPi.GPIO as GPIO


import picamera2 #camera module for RPi camera
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder, H264Encoder
from picamera2.outputs import FileOutput, FfmpegOutput
import io

import subprocess
from flask_restful import Resource, Api, reqparse, abort
import atexit
from datetime import datetime
from threading import Condition
from flask import redirect, url_for





app = Flask(__name__, static_folder='static')
api = Api(app)

class StreamingOutput(io.BufferedIOBase):
	def __init__(self):
		self.frame = None
		self.condition = Condition()

	def write(self, buf):
		with self.condition:
			self.frame = buf
			self.condition.notify_all()

#defines the function that generates our frames
def genFrames():
	with picamera2.Picamera2() as camera:
		camera.configure(camera.create_video_configuration(main={"size": (640, 480)}))
		encoder = JpegEncoder()
		output1 = FfmpegOutput('test2.mp4', audio=False) 
		output3 = StreamingOutput()
		output2 = FileOutput(output3)
		encoder.output = [output1, output2]
		
		camera.start_encoder(encoder) 
		camera.start() 
		output1.start() 
		time.sleep(5) 
		output1.stop() 
		print('done')
		while True:
			with output3.condition:
				output3.condition.wait()
			frame = output3.frame
			yield (b'--frame\r\n'
				b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            
#defines the route that will access the video feed and call the feed function
class video_feed(Resource):
	def get(self):
		return Response(genFrames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
     

# Initialize Pygame mixer
pygame.mixer.init()

# Define the path to the music folder
music_folder_path = '/home/pi/Downloads/drum sounds/'

# Get a list of all music files in the folder
music_files = [filename for filename in os.listdir(music_folder_path) if filename.endswith('.mp3')]

# Index to keep track of the current playing music
current_music_index = 0


# Sensor data pin is connected to GPIO 4
# sensor = adafruit_dht.DHT22(board.D4)
# Uncomment for DHT11
sensor = adafruit_dht.DHT11(board.D18)


# Initialize NeoPixel strip with GPIO Data Pin
pixels = neopixel.NeoPixel(board.D10, 55, brightness=1)

# Scaling factor for humidity readings
humidity_scaling_factor = 0.5  # Adjust this factor as needed

@app.route('/')
def index():
    return render_template('index.html', music_files=music_files)

api.add_resource(video_feed, '/cam')

@app.route('/live_feed')
def live_feed():
    return render_template('live_feed.html')



# Define a route to handle playing music
@app.route('/play_music/<action>')
def play_music(action):
    global current_music_index
    
    if action == 'play':
        play_current_music()
    elif action == 'next':
        current_music_index = (current_music_index + 1) % len(music_files)
        play_current_music()
    elif action == 'prev':
        current_music_index = (current_music_index - 1) % len(music_files)
        play_current_music()
    elif action == 'stop':
        pygame.mixer.music.stop()
    
    
    # Return the current song name
    return jsonify({'song_name': music_files[current_music_index]})

def play_current_music():
    global current_music_index
    music_file = music_files[current_music_index]
    music_file_path = os.path.join(music_folder_path, music_file)
    pygame.mixer.music.load(music_file_path)
    pygame.mixer.music.play()

@app.route('/control/<color>')
def control(color):
    if color == 'red':
        red_pattern()
    elif color == 'green':
        green_pattern()
    elif color == 'blue':
        blue_pattern()

    elif color == 'off':
        turn_off()
        
    else:
        default_pattern()
    return jsonify({'status': 'success'})

def red_pattern():
    for i in range(len(pixels)):
        pixels[i] = (255, 0, 0)
        time.sleep(0.05)

def green_pattern():
    for i in range(len(pixels)):
        pixels[i] = (0, 255, 0)
        time.sleep(0.05)

def blue_pattern():
    for i in range(len(pixels)):
        pixels[i] = (0, 0, 255)
        time.sleep(0.05)

def default_pattern():
    for i in range(len(pixels)):
        pixels[i] = (255, 255, 255)
        time.sleep(0.05)

def turn_off():
    pixels.fill((0, 0, 0))



@app.route('/sensor_data')
def sensor_data():
    try:

        # Connect to the SQLite database
        conn = sqlite3.connect('sensor_data.db')
        c = conn.cursor()

        # Read sensor data
        temperature_c = sensor.temperature
        temperature_f = temperature_c * (9 / 5) + 32
        humidity = sensor.humidity * humidity_scaling_factor  # Apply scaling factor

        # Store sensor data in the database
        c.execute("INSERT INTO sensor_readings (temperature_c, temperature_f, humidity) VALUES (?, ?, ?)",
                  (temperature_c, temperature_f, humidity))
        conn.commit()

         # Close the connection
        conn.close()

        # Return sensor data as JSON
        return jsonify({
            'temperature_c': temperature_c,
            'temperature_f': temperature_f,
            'humidity': humidity
        })
    except RuntimeError as error:
        # Handle sensor reading errors
        return jsonify({'error': str(error)})
    

if __name__ == "__main__":
    app.run(debug = False, host = '0.0.0.0', port=5000)

     